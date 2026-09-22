# This Python file uses the following encoding: utf-8
"""
桌面版（PC 客户端）游戏窗口的后台操作。

阴阳师桌面版是普通 Win32 窗口（Unity 渲染），无法通过 ADB 控制，因此单独实现：

- 截图：PrintWindow(PW_RENDERFULLCONTENT)，可抓取被遮挡或非激活的窗口
- 输入：PostMessage 发送鼠标消息，不移动真实鼠标、不抢焦点

注意 DPI：OAS 主进程默认非 DPI 感知，而游戏窗口通常是。直接混用会让坐标偏移一倍
（200% 缩放下 GetWindowRect 只返回逻辑尺寸）。因此窗口操作一律包在 dpi_aware() 内。
"""
import ctypes
import subprocess
import time
from contextlib import contextmanager
from ctypes import wintypes
from random import randint, random, uniform

import cv2
import numpy as np
import win32api
import win32con
import win32gui
import win32process
import win32ui
from cached_property import cached_property

from module.base.cBezier import BezierTrajectory
from module.base.utils import ensure_time
from module.device.window_account import get_account_id, parse_account_id
from module.logger import logger

# 所有 task 的资源都按 1280x720 制作，桌面端截图统一缩放到这个尺寸
SCREEN_SIZE = (1280, 720)

# 窗口标题分隔符，支持 "阴阳师-网易游戏|阴阳师-MuMu模拟器专版" 这种多候选写法
TITLE_SEPARATOR = '|'

# 查找窗口的重试次数与间隔：客户端重启时窗口会短暂消失，不能一找不到就判定游戏没开
FIND_RETRIES = 4
FIND_RETRY_INTERVAL = 0.5

# 客户区尺寸与目标尺寸的允许偏差（像素）。MoveWindow 受边框/DPI 舍入影响，
# 不可能每次都精确命中，差几个像素对截图缩放没有影响
SIZE_TOLERANCE = 4

_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
_user32 = ctypes.windll.user32
try:
    _user32.SetThreadDpiAwarenessContext.argtypes = [wintypes.HANDLE]
    _user32.SetThreadDpiAwarenessContext.restype = wintypes.HANDLE
except Exception:
    pass


class DesktopWindowError(Exception):
    """桌面端窗口不可用（未找到 / 已关闭 / 尺寸异常）。"""


class DesktopWindowAmbiguous(DesktopWindowError):
    """候选窗口不唯一，且无法确定该用哪一个。

    这类错误**重试也不会好**，所以 is_alive() 不会吞掉它 —— 必须让用户看到并去修配置，
    否则会退化成"随便挑一个窗口"，可能操作到别人的账号。
    """


@contextmanager
def dpi_aware():
    """临时把当前线程切为 DPI 感知，保证拿到物理像素坐标。

    线程级设置，不影响 GUI（Qt）与服务器进程，退出时自动还原。
    """
    old = None
    try:
        old = _user32.SetThreadDpiAwarenessContext(_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
    except Exception as e:
        logger.info(f'SetThreadDpiAwarenessContext unavailable: {e}')
    try:
        yield
    finally:
        if old:
            try:
                _user32.SetThreadDpiAwarenessContext(old)
            except Exception:
                pass


# 游戏客户端把账号 ID 放在启动参数里，形如 /viewer_id=690806847
# 账号 ID 的抓取与解析统一在 module/device/window_account.py，这里只做引用
__all__ = [
    'SCREEN_SIZE', 'DesktopWindow', 'DesktopWindowError', 'DesktopWindowAmbiguous',
    'dpi_aware', 'get_account_id', 'parse_account_id',
]


class DesktopWindow:
    """一个桌面版游戏窗口的句柄、几何信息与后台操作方法。"""

    def __init__(self, title: str = '', class_name: str = '', pid: int = 0,
                 restore_window: bool = True, exe_path: str = '', account_id: str = '',
                 window_size: tuple = None):
        self.title = str(title or '')
        self.class_name = str(class_name or '')
        self.pid = int(pid or 0)
        self.restore_window = bool(restore_window)
        self.exe_path = str(exe_path or '')
        # account_id 存**规范化后的纯数字 ID**：配置页给的是带位置的可读标签
        self.account_id = parse_account_id(account_id)
        # 开启「自动调整窗口大小」时，把客户区拉到这个尺寸；None 表示不动窗口
        self.window_size = tuple(int(v) for v in window_size) if window_size else None
        self._hwnd = 0
        self._warned_unbound = False
        self._resize_attempts = 0
        self._resize_warned = False

    # ------------------------------------------------------------------ 查找
    @staticmethod
    def _window_pid(hwnd: int) -> int:
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return pid
        except Exception:
            return 0

    @classmethod
    def list_windows(cls) -> list:
        """列出所有可见窗口。

        Returns:
            list[tuple[int, str, str, int]]: [(hwnd, title, class_name, pid), ...]
        """
        windows = []

        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    windows.append((hwnd, title, win32gui.GetClassName(hwnd), cls._window_pid(hwnd)))
            return True

        win32gui.EnumWindows(callback, None)
        return windows

    @staticmethod
    def _match_window(win_title: str, win_class: str, title: str, class_name: str) -> bool:
        """标题/类名是否符合条件。title 支持 `|` 分隔的多候选写法。"""
        if class_name and win_class != class_name:
            return False
        if title:
            candidates = [t.strip() for t in title.split(TITLE_SEPARATOR) if t.strip()]
            if candidates and not any(c in win_title for c in candidates):
                return False
        return True

    @classmethod
    def list_game_windows(cls, title: str = '', class_name: str = '') -> list:
        """列出当前所有符合标题/类名条件的游戏窗口。

        供配置页的「选择账号」下拉框使用，用户不用手抄账号 ID。

        Returns:
            list[dict]: 每项含 hwnd / pid / title / class_name / account_id / rect
        """
        result = []
        for hwnd, win_title, win_class, pid in cls.list_windows():
            if not cls._match_window(win_title, win_class, title, class_name):
                continue
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            result.append({
                'hwnd': hwnd,
                'pid': pid,
                'title': win_title,
                'class_name': win_class,
                'account_id': get_account_id(pid),
                'rect': (left, top, right - left, bottom - top),
            })
        return result

    @cached_property
    def title_candidates(self) -> list:
        return [t.strip() for t in self.title.split(TITLE_SEPARATOR) if t.strip()]

    def _resolve_target(self) -> int:
        """在候选中确定要操作哪一个窗口，返回 hwnd；0 表示"暂时没找到"。

        这是多开的核心，规则只有三条，且**每条都宁可失败也不猜**：

        1. 配了 account_id（推荐）：按账号 ID 精确匹配。
           - 命中 1 个 → 用它
           - 命中多个 → 同一账号开了多个窗口，无法确定，抛歧义错误
           - 命中 0 个 → 返回 0，交给 find() 重试（可能是游戏正在启动）
        2. 没配 account_id 且只有 1 个候选 → 用它，但提醒去配置页绑定账号
        3. 没配 account_id 且有多个候选 → 抛歧义错误

        **为什么不退化成"随便挑一个"**：猜错的后果是操作到别人的账号，
        可能给别人用掉体力、强化掉御魂。宁可让脚本停下来报错。
        """
        candidates = []
        for hwnd, win_title, win_class, pid in self.list_windows():
            if self.pid and pid != self.pid:
                continue
            if not self._match_window(win_title, win_class, self.title, self.class_name):
                continue
            candidates.append({'hwnd': hwnd, 'pid': pid})

        if self.account_id:
            matched = [c for c in candidates if get_account_id(c['pid']) == self.account_id]
            if len(matched) == 1:
                return matched[0]['hwnd']
            if len(matched) > 1:
                raise DesktopWindowAmbiguous(
                    f'账号 {self.account_id} 同时开了 {len(matched)} 个窗口，'
                    f'无法确定该操作哪一个，请关掉多余的窗口后重试。'
                )
            return 0

        if not candidates:
            return 0
        if len(candidates) == 1:
            if not self._warned_unbound:
                self._warned_unbound = True
                logger.warning(
                    'Desktop window matched by title only, no account bound. '
                    '建议在「桌面版」设置里选择一个账号 —— 多开时只按标题匹配可能绑错窗口。'
                )
            return candidates[0]['hwnd']
        raise DesktopWindowAmbiguous(
            f'找到 {len(candidates)} 个游戏窗口，但配置里没有绑定账号，无法确定该用哪一个。'
            f'请在「桌面版」设置里选择要操作的账号。'
        )

    def find(self, retries: int = FIND_RETRIES, interval: float = FIND_RETRY_INTERVAL) -> int:
        """找到目标窗口句柄，重试若干次再放弃。

        客户端重启、切换画质、多开器切换实例时窗口会短暂消失几百毫秒；
        直接判定"游戏没开"会误触发 Restart，进而因未配置程序路径而中断脚本。

        Raises:
            DesktopWindowAmbiguous: 配置有歧义，重试无用，直接抛给上层。
            DesktopWindowError: 重试用尽仍未找到。
        """
        for attempt in range(max(1, retries)):
            hwnd = self._resolve_target()
            if hwnd:
                logger.info(f'Desktop window found: hwnd={hwnd} '
                            f'title={win32gui.GetWindowText(hwnd)!r} '
                            f'class={win32gui.GetClassName(hwnd)!r}')
                return hwnd
            if attempt < retries - 1:
                time.sleep(interval)

        # 找不到时给一句"该往哪儿查"的提示，比单纯说 not found 有用得多
        hints = ['请确认桌面版游戏已启动、窗口没有隐藏到托盘',
                 '也可以在「桌面版」设置里核对窗口标题与类名']
        if self.account_id:
            hints.append(f'已绑定账号 {self.account_id}，但当前没有它的窗口在运行')
        if self.pid:
            hints.append(f'当前指定了 PID {self.pid}，游戏重启后 PID 会变，建议改用账号绑定')
        raise DesktopWindowError(
            f'Desktop window not found '
            f'(title={self.title!r}, class={self.class_name!r}, pid={self.pid}, '
            f'account_id={self.account_id!r}). ' + '；'.join(hints) + '。'
        )

    def invalidate(self) -> None:
        """丢弃缓存的句柄，下次访问时重新查找。"""
        self._hwnd = 0

    @property
    def hwnd(self) -> int:
        if self._hwnd and win32gui.IsWindow(self._hwnd):
            return self._hwnd
        self._hwnd = self.find()
        return self._hwnd

    def is_alive(self, retries: int = FIND_RETRIES) -> bool:
        """窗口是否存在。

        Args:
            retries: 探测次数。默认带重试，用来挺过客户端重启时窗口短暂消失的间隙；
                     需要快速判断时（如轮询等待启动）传 1。

        Raises:
            DesktopWindowAmbiguous: 配置有歧义（多开但没绑账号等）。这类问题重试也不会好，
                所以**故意不吞掉** —— 让它抛给上层，用户才能看到并去改配置。
                若在这里吞掉并返回 False，上层会判定"游戏没开"从而反复跑 Restart，
                形成死循环，真正的配置问题反而被掩盖。
        """
        if self._hwnd and win32gui.IsWindow(self._hwnd):
            return True
        try:
            self._hwnd = self.find(retries=retries)
            return True
        except DesktopWindowAmbiguous:
            logger.critical('Desktop window binding is ambiguous, please fix the config')
            raise
        except DesktopWindowError:
            return False

    # ------------------------------------------------------------------ 几何
    # 注意：窗口尺寸/位置与线程的 DPI 感知上下文强相关 —— 同一个窗口，
    # 在 dpi_aware() 里读到 1278x720，在默认上下文里可能读到 639x360（差 2 倍）。
    # 所以这三个方法自己套 dpi_aware()，保证不管谁调用都返回同一套（物理像素）数值。
    def window_rect(self) -> tuple:
        """窗口在屏幕上的矩形 (left, top, right, bottom)，物理像素。"""
        with dpi_aware():
            return win32gui.GetWindowRect(self.hwnd)

    def client_size(self) -> tuple:
        """客户区（游戏画面）尺寸 (width, height)，物理像素。"""
        with dpi_aware():
            left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
            return right - left, bottom - top

    def _client_size_or_raise(self) -> tuple:
        """客户区尺寸；不可用时抛错（窗口最小化或尚未完成渲染）。"""
        client_w, client_h = self.client_size()
        if client_w <= 1 or client_h <= 1:
            raise DesktopWindowError(f'Desktop window client size invalid: {client_w}x{client_h}')
        return client_w, client_h

    @staticmethod
    def _size_matched(actual: tuple, target: tuple, tolerance: int = SIZE_TOLERANCE) -> bool:
        """两个尺寸是否在容差内相符。"""
        return (abs(actual[0] - target[0]) <= tolerance
                and abs(actual[1] - target[1]) <= tolerance)

    def resize(self, width: int, height: int, tolerance: int = SIZE_TOLERANCE,
               attempts: int = 3) -> tuple:
        """把客户区调整到尽量接近 width x height，返回最终客户区尺寸。

        **为什么不能一步到位**：游戏客户端有自己的 DPI 缩放 —— 实测窗口
        `GetDpiForWindow()=192` 而系统 DPI 是 96，请求尺寸和实际尺寸之间差约 2 倍
        （请求客户区 1280x720，实际变成 2682x1511）。所以这里迭代几次，
        按「目标/实测」的比例反向修正请求值。

        这个做法**与 DPI 数值无关**：它只关心"目标 ÷ 实测"这个比率，所以换到
        100% 缩放或别的分辨率下同样成立。若窗口 DPI 与系统一致（无换算），
        第 1 轮就直接命中并返回，不会进入迭代。

        实在调不准时**宁可偏大也不要偏小**：截图会统一缩放到 1280x720，
        偏大只是缩小（依然清晰），偏小则要放大、画面变糊、模板匹配得分下降。
        """
        target = (int(width), int(height))
        request = target
        actual = None

        for _ in range(max(1, attempts)):
            with dpi_aware():
                hwnd = self.hwnd
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                client_w, client_h = self._client_size_or_raise()
                # MoveWindow 要的是整窗尺寸，补上标题栏与边框的厚度
                border_w = (right - left) - client_w
                border_h = (bottom - top) - client_h
                win32gui.MoveWindow(hwnd, left, top,
                                    request[0] + border_w, request[1] + border_h, True)
            time.sleep(0.3)

            actual = self.client_size()
            if self._size_matched(actual, target, tolerance):
                return actual
            # 按缺口反向修正请求值，再试一次
            request = (int(round(request[0] * target[0] / max(1, actual[0]))),
                       int(round(request[1] * target[1] / max(1, actual[1]))))

        actual = actual or self.client_size()
        if actual[0] < target[0] - tolerance:
            logger.warning(
                f'Desktop window is smaller than wanted after resizing '
                f'(want {target[0]}x{target[1]}, got {actual[0]}x{actual[1]}). '
                f'截图会被放大，识别率可能下降。'
            )
        return actual

    def _ensure_window_size(self) -> None:
        """开启了「自动调整窗口大小」时，把客户区拉到配置尺寸。

        客户区小于 1280x720 时截图会被放大，画面变糊、模板匹配得分下降
        （实测 I_MAIN_GOTO_TEAM 在客户区 702x395 下只有 0.7395，阈值 0.70）。
        """
        target = self.window_size
        if not target:
            return
        try:
            client = self._client_size_or_raise()
        except DesktopWindowError:
            return
        if self._size_matched(client, target):
            return

        # 客户端可能锁分辨率、或用户正在手动拖窗口，试几次就放弃，别反复折腾
        if self._resize_attempts >= 3:
            if not self._resize_warned:
                self._resize_warned = True
                logger.warning(
                    f'Desktop window keeps changing size, give up resizing '
                    f'(want {target[0]}x{target[1]}, got {client[0]}x{client[1]}). '
                    f'可能是客户端锁定了分辨率，或者你在手动调整窗口。'
                )
            return

        self._resize_attempts += 1
        actual = self.resize(*target)
        logger.info(f'Resize desktop window: want {target[0]}x{target[1]}, '
                    f'actual client {actual[0]}x{actual[1]}')

    def client_offset(self) -> tuple:
        """客户区左上角相对窗口左上角的偏移，用于裁掉标题栏与边框。"""
        with dpi_aware():
            win_left, win_top, _, _ = win32gui.GetWindowRect(self.hwnd)
            cli_left, cli_top = win32gui.ClientToScreen(self.hwnd, (0, 0))
            return cli_left - win_left, cli_top - win_top

    def to_client(self, x, y, size: tuple = SCREEN_SIZE) -> tuple:
        """把 1280x720 坐标映射为窗口客户区物理坐标。"""
        client_w, client_h = self._client_size_or_raise()
        client_x = int(round(float(x) * client_w / size[0]))
        client_y = int(round(float(y) * client_h / size[1]))
        return max(0, client_x), max(0, client_y)

    # ------------------------------------------------------------------ 截图
    def _print_window(self, hwnd: int, width: int, height: int) -> np.ndarray:
        """PrintWindow 抓取整个窗口，返回 RGB 图像。"""
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        try:
            src_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            mem_dc = src_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(src_dc, width, height)
            mem_dc.SelectObject(bitmap)
            try:
                # PW_RENDERFULLCONTENT = 2，可抓取 DirectX/Unity 渲染内容
                ok = _user32.PrintWindow(hwnd, mem_dc.GetSafeHdc(), 2)
                if not ok:
                    logger.info('PrintWindow(PW_RENDERFULLCONTENT) failed, fallback to BitBlt')
                    mem_dc.BitBlt((0, 0), (width, height), src_dc, (0, 0), win32con.SRCCOPY)
                info = bitmap.GetInfo()
                buffer = bitmap.GetBitmapBits(True)
            finally:
                win32gui.DeleteObject(bitmap.GetHandle())
                mem_dc.DeleteDC()
                src_dc.DeleteDC()
        finally:
            win32gui.ReleaseDC(hwnd, hwnd_dc)

        image = np.frombuffer(buffer, dtype=np.uint8)
        image = image.reshape((info['bmHeight'], info['bmWidth'], 4))
        # DIB 是 BGRA 顺序，而 task 里的图片统一是 RGB
        return cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)

    def ensure_visible(self) -> None:
        """最小化时恢复窗口。

        用 SW_SHOWNOACTIVATE 而非 SW_RESTORE：前者不激活窗口就能把它从最小化
        恢复出来（iconic 由 1 变 0 且不抢前台），既不打扰用户，也无需再压 Z 序。
        """
        hwnd = self.hwnd
        if not win32gui.IsIconic(hwnd):
            return
        if not self.restore_window:
            logger.warning('Desktop window is minimized and auto-restore is disabled, '
                           'screenshot will be invalid')
            return
        logger.info('Desktop window is minimized, restoring it without activating')
        win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
        time.sleep(0.5)

    def screenshot(self, size: tuple = SCREEN_SIZE) -> np.ndarray:
        """后台截取游戏画面并缩放到 size（默认 1280x720）。

        先抓整个窗口，再按客户区偏移裁掉标题栏/边框，最后缩放，
        这样即使窗口带边框或非整数倍缩放，画面也能对齐到目标尺寸。
        """
        with dpi_aware():
            self.ensure_visible()
            # 客户区小于 1280x720 时截图会被放大、画面变糊，开启后自动拉正
            self._ensure_window_size()
            hwnd = self.hwnd
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            win_w, win_h = right - left, bottom - top
            if win_w <= 1 or win_h <= 1:
                raise DesktopWindowError(f'Desktop window size invalid: {win_w}x{win_h}')

            image = self._print_window(hwnd, win_w, win_h)

            offset_x, offset_y = self.client_offset()
            client_w, client_h = self._client_size_or_raise()
            x1, y1 = max(0, offset_x), max(0, offset_y)
            x2, y2 = min(win_w, offset_x + client_w), min(win_h, offset_y + client_h)
            if x2 - x1 < 2 or y2 - y1 < 2:
                # 客户区信息不可靠时退回整窗，至少保证画面可用
                logger.info('Client area unreliable, using whole window as game screen')
                x1, y1, x2, y2 = 0, 0, win_w, win_h

            image = image[y1:y2, x1:x2]
            if (image.shape[1], image.shape[0]) != tuple(size):
                image = cv2.resize(image, tuple(size), interpolation=cv2.INTER_AREA)
            return image

    # ------------------------------------------------------------------ 控制
    def click(self, x, y, size: tuple = SCREEN_SIZE, press_time=(0.1, 0.2), fast: bool = False) -> None:
        """后台点击。按下/抬起之间加入微小位移，避免完全一致的坐标被识别为脚本。"""
        with dpi_aware():
            hwnd = self.hwnd
            client_x, client_y = self.to_client(x, y, size)
            hold = uniform(0.01, 0.04) if fast else ensure_time(press_time)
            down_pos = win32api.MAKELONG(client_x, client_y)
            up_pos = win32api.MAKELONG(max(0, client_x + randint(-2, 2)),
                                       max(0, client_y + randint(-2, 2)))

            win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, down_pos)
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, down_pos)
            time.sleep(hold)
            win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, up_pos)
            time.sleep(uniform(0.008, 0.020))
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, up_pos)

    def long_click(self, x, y, duration=0.8, size: tuple = SCREEN_SIZE) -> None:
        """后台长按。"""
        with dpi_aware():
            hwnd = self.hwnd
            pos = win32api.MAKELONG(*self.to_client(x, y, size))
            win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, pos)
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, pos)
            time.sleep(ensure_time(duration))
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, pos)

    def _bezier_trace(self, start_pos: list, end_pos: list) -> list:
        """生成一条接近真人手势的贝塞尔轨迹（客户区坐标）。"""
        # BezierTrajectory 以 x 为参数，横向跨度为 0 时会除零得到 NaN 并崩在
        # int() 转换上。纯垂直滑动（滚动列表）很常见，这里补几像素横向抖动。
        if abs(end_pos[0] - start_pos[0]) < 2:
            offset = 2 if end_pos[0] >= start_pos[0] else -2
            end_pos = [end_pos[0] + offset, end_pos[1]]

        interval = 8  # 每个轨迹点之间的间隔（毫秒）
        distance = ((end_pos[0] - start_pos[0]) ** 2 + (end_pos[1] - start_pos[1]) ** 2) ** 0.5
        number = max(4, int(distance / (1.5 * interval)))

        shape = random()
        if shape <= 0.8:
            curve_type = 3
        elif shape < 0.9:
            curve_type = 2
        else:
            curve_type = 1

        trace = BezierTrajectory.trackArray(
            start=list(start_pos), end=list(end_pos), numberList=number,
            le=randint(2, 4), deviation=randint(20, 40),
            bias=0.5, type=curve_type, cbb=0, yhh=20,
        )
        return trace or [list(start_pos), list(end_pos)]

    def _drag(self, start, end, size: tuple, hold: float = 0.0, duration: float = None) -> None:
        """按住后沿贝塞尔轨迹拖动到终点。

        Args:
            hold: 按下后、开始移动前的停留时长；0 表示立即开始移动。
            duration: 移动阶段的总时长（秒）。None 表示按默认速度（每点约 8ms）。
                调用方用 duration 控制翻页速度时必须传进来 —— 桌面滑动是按轨迹
                点数均分 sleep 的，不传就会瞬间滑完，导致列表翻过头。
        """
        with dpi_aware():
            hwnd = self.hwnd
            trace = self._bezier_trace(
                list(self.to_client(start[0], start[1], size)),
                list(self.to_client(end[0], end[1], size)),
            )
            if duration is None:
                delay = None
            else:
                delay = max(0.0, ensure_time(duration) / max(1, len(trace)))

            down_pos = win32api.MAKELONG(int(trace[0][0]), int(trace[0][1]))
            win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, down_pos)
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, down_pos)
            if hold > 0:
                time.sleep(hold)
            for point in trace:
                pos = win32api.MAKELONG(int(point[0]), int(point[1]))
                win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, pos)
                time.sleep(delay if delay is not None else (8 + randint(-2, 2)) / 1000.0)
            up_pos = win32api.MAKELONG(int(trace[-1][0]), int(trace[-1][1]))
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, up_pos)

    def swipe(self, start, end, size: tuple = SCREEN_SIZE, duration: float = None) -> None:
        """后台滑动。

        逐点 PostMessage(WM_MOUSEMOVE) 走贝塞尔轨迹，比直线更接近真人手势，
        否则游戏可能把滑动识别为点击。

        Args:
            duration: 整条轨迹的总时长（秒）；None 用默认速度。
        """
        self._drag(start, end, size=size, duration=duration)

    def press_and_drag(self, start, end, hold_duration=0.5, size: tuple = SCREEN_SIZE,
                       swipe_duration: float = None) -> None:
        """在起点按住一段时间再拖到终点。

        百鬼棋局（Chess）的手牌/棋盘/御魂操作依赖"先按住再移动"的语义，
        单纯 swipe 会被识别成普通滑动。
        """
        self._drag(start, end, size=size, hold=ensure_time(hold_duration),
                   duration=swipe_duration)

    # --------------------------------------------------------------- 生命周期
    def start(self) -> bool:
        """启动桌面版游戏（需要配置程序路径），已运行则只做恢复。"""
        if self.is_alive():
            self.ensure_visible()
            return True
        if not self.exe_path:
            logger.error('Desktop game is not running and no executable path configured')
            return False
        logger.info(f'Start desktop game: {self.exe_path}')
        try:
            subprocess.Popen([self.exe_path], close_fds=True)
        except Exception as e:
            logger.error(f'Failed to start desktop game: {e}')
            return False
        self.invalidate()
        return True

    def stop(self) -> bool:
        """关闭桌面版游戏窗口。"""
        if not self.is_alive():
            return True
        hwnd = self.hwnd
        logger.info(f'Close desktop game window: hwnd={hwnd}')
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        self.invalidate()
        return True
