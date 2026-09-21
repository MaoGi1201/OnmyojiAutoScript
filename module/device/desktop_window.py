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
from module.logger import logger

# 所有 task 的资源都按 1280x720 制作，桌面端截图统一缩放到这个尺寸
SCREEN_SIZE = (1280, 720)

# 窗口标题分隔符，支持 "阴阳师-网易游戏|阴阳师-MuMu模拟器专版" 这种多候选写法
TITLE_SEPARATOR = '|'

# 查找窗口的重试次数与间隔：客户端重启时窗口会短暂消失，不能一找不到就判定游戏没开
FIND_RETRIES = 4
FIND_RETRY_INTERVAL = 0.5

_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
_user32 = ctypes.windll.user32
try:
    _user32.SetThreadDpiAwarenessContext.argtypes = [wintypes.HANDLE]
    _user32.SetThreadDpiAwarenessContext.restype = wintypes.HANDLE
except Exception:
    pass


class DesktopWindowError(Exception):
    """桌面端窗口不可用（未找到 / 已关闭 / 尺寸异常）。"""


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


class DesktopWindow:
    """一个桌面版游戏窗口的句柄、几何信息与后台操作方法。"""

    def __init__(self, title: str = '', class_name: str = '', pid: int = 0,
                 restore_window: bool = True, exe_path: str = ''):
        self.title = str(title or '')
        self.class_name = str(class_name or '')
        self.pid = int(pid or 0)
        self.restore_window = bool(restore_window)
        self.exe_path = str(exe_path or '')
        self._hwnd = 0

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

    @cached_property
    def title_candidates(self) -> list:
        return [t.strip() for t in self.title.split(TITLE_SEPARATOR) if t.strip()]

    def _find_once(self) -> int:
        """查找一次，找不到返回 0。优先级：标题完全匹配 > 标题包含匹配 > 仅按 PID 匹配。"""
        candidates = self.title_candidates
        best_hwnd = 0
        best_score = -1
        for hwnd, title, class_name, pid in self.list_windows():
            if self.pid and pid != self.pid:
                continue
            if self.class_name and class_name != self.class_name:
                continue

            if candidates:
                if title in candidates:
                    score = 3
                elif any(c in title for c in candidates):
                    score = 2
                else:
                    continue
            else:
                score = 1

            if score > best_score:
                best_hwnd, best_score = hwnd, score
        return best_hwnd

    def find(self, retries: int = FIND_RETRIES, interval: float = FIND_RETRY_INTERVAL) -> int:
        """找到目标窗口句柄，重试若干次再放弃。

        客户端重启、切换画质、多开器切换实例时窗口会短暂消失几百毫秒；
        直接判定"游戏没开"会误触发 Restart，进而因未配置程序路径而中断脚本。
        """
        for attempt in range(retries):
            hwnd = self._find_once()
            if hwnd:
                logger.info(f'Desktop window found: hwnd={hwnd} '
                            f'title={win32gui.GetWindowText(hwnd)!r} '
                            f'class={win32gui.GetClassName(hwnd)!r}')
                return hwnd
            if attempt < retries - 1:
                time.sleep(interval)

        message = (f'Desktop window not found '
                   f'(title={self.title!r}, class={self.class_name!r}, pid={self.pid}). '
                   f'请确认桌面版游戏已启动、窗口没有隐藏到托盘；'
                   f'也可以在「桌面版」设置里核对窗口标题与类名。')
        if self.pid:
            message += f' 当前指定了 PID {self.pid}，游戏重启后 PID 会变，请重新填写。'
        raise DesktopWindowError(message)

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
        """
        if self._hwnd and win32gui.IsWindow(self._hwnd):
            return True
        try:
            self._hwnd = self.find(retries=retries)
            return True
        except DesktopWindowError:
            return False

    # ------------------------------------------------------------------ 几何
    def window_rect(self) -> tuple:
        """窗口在屏幕上的矩形 (left, top, right, bottom)，物理像素。"""
        return win32gui.GetWindowRect(self.hwnd)

    def client_size(self) -> tuple:
        """客户区（游戏画面）尺寸 (width, height)，物理像素。"""
        left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
        return right - left, bottom - top

    def _client_size_or_raise(self) -> tuple:
        """客户区尺寸；不可用时抛错（窗口最小化或尚未完成渲染）。"""
        client_w, client_h = self.client_size()
        if client_w <= 1 or client_h <= 1:
            raise DesktopWindowError(f'Desktop window client size invalid: {client_w}x{client_h}')
        return client_w, client_h

    def client_offset(self) -> tuple:
        """客户区左上角相对窗口左上角的偏移，用于裁掉标题栏与边框。"""
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
