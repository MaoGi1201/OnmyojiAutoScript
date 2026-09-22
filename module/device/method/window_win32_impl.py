# This Python file uses the following encoding: utf-8
"""
桌面端（PC 客户端）设备方法实现。

这些方法通过 `WindowWin32` mixin 混入 `Device`，与模拟器的 ADB 方法并列，
对上层（tasks/*）完全透明：仍然只调用 device.screenshot() / click() / swipe()，
因此既有 task 的资源与逻辑都能直接复用。
"""
import time
from contextlib import contextmanager

import numpy as np
import win32gui
from cached_property import cached_property

from module.device.desktop_window import (DesktopWindow, DesktopWindowAmbiguous,
                                          DesktopWindowError, SCREEN_SIZE)
from module.exception import GameNotRunningError, RequestHumanTakeover
from module.logger import logger


@contextmanager
def _translate_window_errors(exc_type: type, message: str, include_ambiguous: bool = False):
    """把 DesktopWindowError 翻译成上层认识的异常类型。

    Args:
        exc_type: 翻译成哪种异常。
        message: 给用户看的说明。
        include_ambiguous: 是否也翻译 DesktopWindowAmbiguous（配置有歧义）。
            默认不翻译 —— 歧义是**配置问题，不是"游戏没开"**，让它原样抛出去，
            调用方（如 is_alive）才不会被误导成"游戏没开"而去反复重启。
            只有确定要把歧义直接交给用户的场景才传 True。
    """
    try:
        yield
    except DesktopWindowAmbiguous as e:
        if not include_ambiguous:
            raise
        logger.critical(e)
        raise RequestHumanTakeover(f'Desktop window binding is ambiguous: {e}') from e
    except DesktopWindowError as e:
        logger.warning(e)
        raise exc_type(message) from e


class WindowWin32:
    """桌面版游戏窗口的后台截图 / 控制 / 生命周期。"""

    @cached_property
    def desktop_window(self) -> DesktopWindow:
        desktop = self.config.script.desktop
        window = DesktopWindow(
            title=desktop.window_title,
            class_name=desktop.window_class,
            pid=desktop.window_pid,
            restore_window=desktop.restore_window,
            exe_path=desktop.exe_path,
            account_id=getattr(desktop, 'account_id', ''),
            window_size=(desktop.window_width, desktop.window_height) if desktop.resize_window else None,
        )
        logger.attr('DesktopWindow', f'title={window.title!r} class={window.class_name!r} '
                                     f'pid={window.pid} account={window.account_id!r} '
                                     f'size={window.window_size}')
        return window

    # ------------------------------------------------------------------ 截图
    def screenshot_window_win32(self) -> np.ndarray:
        """后台截取桌面版画面，输出 1280x720 RGB（最小化时自动恢复）。"""
        with _translate_window_errors(GameNotRunningError, 'Desktop game window is not available'):
            return self.desktop_window.screenshot(SCREEN_SIZE)

    # ------------------------------------------------------------------ 控制
    def click_window_win32(self, x: int, y: int) -> None:
        with _translate_window_errors(RequestHumanTakeover, 'Failed to click desktop game window'):
            self.desktop_window.click(x, y, SCREEN_SIZE)

    def long_click_window_win32(self, x: int, y: int, duration: float) -> None:
        with _translate_window_errors(RequestHumanTakeover, 'Failed to long click desktop game window'):
            self.desktop_window.long_click(x, y, duration, SCREEN_SIZE)

    def swipe_window_win32(self, p1, p2, duration: float = None) -> None:
        with _translate_window_errors(RequestHumanTakeover, 'Failed to swipe desktop game window'):
            self.desktop_window.swipe(p1, p2, SCREEN_SIZE, duration=duration)

    def press_and_drag_window_win32(self, p1, p2, hold_duration=0.5, swipe_duration: float = None) -> None:
        """先按住再拖动（百鬼棋局等需要"按住"语义的场景）。"""
        with _translate_window_errors(RequestHumanTakeover, 'Failed to press and drag desktop game window'):
            self.desktop_window.press_and_drag(p1, p2, hold_duration=hold_duration,
                                               size=SCREEN_SIZE, swipe_duration=swipe_duration)

    # --------------------------------------------------------------- 生命周期
    def app_is_alive_win32(self) -> bool:
        """游戏窗口是否存在。

        Raises:
            RequestHumanTakeover: 多开但没绑账号 —— 这种配置歧义重试没用，也不能猜，
                直接请用户去改配置。
        """
        with _translate_window_errors(
                RequestHumanTakeover, 'Desktop game window is not available',
                include_ambiguous=True):
            alive = self.desktop_window.is_alive()
        logger.attr('DesktopGameAlive', alive)
        return alive

    def app_is_running_win32(self) -> bool:
        """游戏窗口是否可操作，即存在且未最小化。

        刻意不判断"是否在前台"：桌面版是后台运行方案，窗口被挡住是常态。
        若按前台判断，prepare_task_execution 每个任务前都会误判"游戏没开"并
        反复跑 Restart 恢复，形成死循环，任务永远起不来。

        Raises:
            RequestHumanTakeover: 多开但没绑账号。**必须**让它抛出去 ——
                若被下面的兜底分支吞掉，会退化成"游戏没开" → 反复 Restart 的死循环。
        """
        with _translate_window_errors(
                RequestHumanTakeover, 'Desktop game window is not available',
                include_ambiguous=True):
            try:
                if not self.desktop_window.is_alive():
                    running = False
                else:
                    running = not win32gui.IsIconic(self.desktop_window.hwnd)
            except Exception as e:
                logger.info(f'app_is_running_win32 failed: {e}')
                running = False
        logger.attr('DesktopGameRunning', running)
        return running

    def app_start_win32(self) -> None:
        """启动 / 唤醒桌面版游戏；已在运行则只确保可截图，不重开。"""
        logger.info('Desktop mode: start game window')
        if not self.desktop_window.start():
            logger.critical('Unable to start desktop game, please configure its executable path '
                            '(Desktop Exe Path) or start it manually')
            raise RequestHumanTakeover
        # 循环本身就在重试，单次探测用 retries=1 即可
        for _ in range(30):
            if self.desktop_window.is_alive(retries=1):
                break
            time.sleep(1)
        else:
            logger.warning('Desktop game window did not appear within 30s')

    def app_stop_win32(self) -> None:
        logger.info('Desktop mode: close game window')
        self.desktop_window.stop()
