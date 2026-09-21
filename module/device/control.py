import time

# from module.base.button import Button
from module.base.decorator import cached_property
from module.base.timer import Timer
from module.base.utils import *
from module.device.env import IS_WINDOWS
# from module.device.method.hermit import Hermit
# from module.device.method.maatouch import MaaTouch
from module.device.method.minitouch import Minitouch
from module.device.method.adb import Adb
from module.device.method.scrcpy import Scrcpy
from module.device.method.windows import Window
from module.device.method.window_win32 import WindowWin32
from module.logger import logger


class Control(Minitouch, Adb, Scrcpy, Window, WindowWin32):
    def handle_control_check(self, button):
        # Will be overridden in Device
        pass

    @staticmethod
    def _format_action_duration(duration_seconds: float) -> str:
        return f'[{duration_seconds:.2f}s] '

    def _invalidate_image_batch_cache(self) -> None:
        invalidate = getattr(self, 'invalidate_image_batch_cache', None)
        if callable(invalidate):
            invalidate()

    @cached_property
    def click_methods(self):
        methods = {
            'ADB': self.click_adb,
            'uiautomator2': self.click_uiautomator2,
            'minitouch': self.click_minitouch,
            # 'Hermit': self.click_hermit,
            # 'MaaTouch': self.click_maatouch,
        }
        if IS_WINDOWS:
            methods['window_message'] = self.click_window_message
            # 桌面版（PC 客户端）后台点击，不依赖 ADB
            methods['window_win32'] = self.click_window_win32
        return methods

    @cached_property
    def long_click_methods(self):
        methods = {
            'ADB': self.long_click_adb,
            'uiautomator2': self.long_click_uiautomator2,
            'minitouch': self.long_click_minitouch,
            'scrcpy': self.long_click_scrcpy
            # 'Hermit': self.click_hermit,
            # 'MaaTouch': self.click_maatouch,
        }
        if IS_WINDOWS:
            methods['window_message'] = self.long_click_window_message
            # 桌面版（PC 客户端）后台长按，不依赖 ADB
            methods['window_win32'] = self.long_click_window_win32
        return methods

    def click(self, x: int, y: int, control_check=True, control_name='Click') -> None:
        """

        :param control_name:
        :param x:
        :param y:
        :param control_check:
        :return:
        """
        if control_check:
            self.handle_control_check(control_name)
        x, y = ensure_int(x, y)
        self._invalidate_image_batch_cache()
        method = self.click_methods.get(
            self.control_method,
            self.click_adb
        )
        start = time.perf_counter()
        method(x, y)
        elapsed = time.perf_counter() - start
        logger.info(f'{self._format_action_duration(elapsed)}Click {point2str(x, y)} @ {control_name}')


    def multi_click(self, button, n, interval=(0.1, 0.2)):
        """
        也是不能用button的逻辑
        :param button:
        :param n:
        :param interval:
        :return:
        """
        self.handle_control_check(button)
        click_timer = Timer(0.1)
        for _ in range(n):
            remain = ensure_time(interval) - click_timer.current()
            if remain > 0:
                self.sleep(remain)
            click_timer.reset()

            self.click(button, control_check=False)

    def long_click(self, x: int, y: int, duration=(0.5, 2), control_name='LongClick') -> None:
        """

        :param control_name:
        :param x:
        :param y:
        :param duration: 单位是s
        :return:
        """
        self.handle_control_check(control_name)
        x, y = ensure_int(x, y)
        if duration is None:
            duration = 0.8
        duration = ensure_time(duration)
        self._invalidate_image_batch_cache()
        method = self.long_click_methods.get(
            self.control_method,
            self.long_click_adb)
        start = time.perf_counter()
        method(x, y, duration)
        elapsed = time.perf_counter() - start
        logger.info(f'{self._format_action_duration(elapsed)}Click {point2str(x, y)} @ {control_name} {duration}')

    def swipe_adb(self, p1, p2, duration=0.1):
        """桌面模式下没有 ADB，把对底层原语的直接调用重定向到窗口滑动。

        项目里有几个 task 为了精确控制滑动时长，直接调用了 `swipe_adb`
        （绕过了 swipe() 的模式分发，如 RyouToppa 的调参值 0.352s）。
        桌面模式下这行代码会直接抛 EmulatorNotRunningError 打断脚本，
        所以在这里统一兜住：桌面模式走窗口滑动，模拟器模式行为完全不变
        （仍然交给 Adb.swipe_adb，duration 不做任何缩放）。

        新增代码请优先用 swipe()，它会自动按当前模式分发。
        """
        if self.is_desktop:
            self.swipe_window_win32(p1, p2, duration=duration)
            return
        super().swipe_adb(p1, p2, duration=duration)

    def swipe(self, p1, p2, duration=(0.1, 0.2), control_name='SWIPE', distance_check=True):
        self.handle_control_check(control_name)
        p1, p2 = ensure_int(p1, p2)
        duration = ensure_time(duration)
        method = self.control_method
        swipe_log = None
        if method == 'minitouch':
            swipe_log = 'Swipe %s -> %s' % (point2str(*p1), point2str(*p2))
        elif method == 'window_message':
            swipe_log = 'Swipe %s -> %s' % (point2str(*p1), point2str(*p2))
        elif method == 'uiautomator2':
            swipe_log = 'Swipe %s -> %s, %s' % (point2str(*p1), point2str(*p2), duration)
        elif method == 'scrcpy':
            swipe_log = 'Swipe %s -> %s' % (point2str(*p1), point2str(*p2))
        elif method == 'window_win32':
            swipe_log = 'Swipe %s -> %s' % (point2str(*p1), point2str(*p2))
        # elif method == 'MaaTouch':
        #     logger.info('Swipe %s -> %s' % (point2str(*p1), point2str(*p2)))
        else:
            # ADB needs to be slow, or swipe doesn't work
            duration *= 2.5
            swipe_log = 'Swipe %s -> %s, %s ' % (point2str(*p1), point2str(*p2), duration)

        if distance_check:
            if p1[0] == p2[0]:
                logger.info('Swipe x distance is 0')
                p1[0] += 1
            if p1[1] == p2[1]:
                logger.info('Swipe y distance is 0')
                p1[1] += 1

            if np.linalg.norm(np.subtract(p1, p2)) < 10:
                # Should swipe a certain distance, otherwise AL will treat it as click.
                # uiautomator2 should >= 6px, minitouch should >= 5px
                logger.info('Swipe distance < 10px, dropped')
                return

        self._invalidate_image_batch_cache()
        start = time.perf_counter()
        if method == 'minitouch':
            self.swipe_minitouch(p1, p2)
        elif method == 'window_message':
            self.swipe_window_message(p1, p2)
        elif method == 'uiautomator2':
            self.swipe_uiautomator2(p1, p2, duration=duration)
        elif method == 'scrcpy':
            self.swipe_scrcpy(p1, p2)
        elif method == 'window_win32':
            # 桌面滑动按 duration 均分轨迹点间隔，不传会瞬间滑完导致翻过头
            self.swipe_window_win32(p1, p2, duration=duration)
        # elif method == 'MaaTouch':
        #     self.swipe_maatouch(p1, p2)
        else:
            self.swipe_adb(p1, p2, duration=duration)
        elapsed = time.perf_counter() - start
        logger.info(f'{self._format_action_duration(elapsed)}{swipe_log}')

    def swipe_vector(self, vector, box=(123, 159, 1175, 628), random_range=(0, 0, 0, 0), padding=15,
                     duration=(0.1, 0.2), whitelist_area=None, blacklist_area=None, name='SWIPE', distance_check=True):
        """Method to swipe.

        Args:
            box (tuple): Swipe in box (upper_left_x, upper_left_y, bottom_right_x, bottom_right_y).
            vector (tuple): (x, y).
            random_range (tuple): (x_min, y_min, x_max, y_max).
            padding (int):
            duration (int, float, tuple):
            whitelist_area: (list[tuple[int]]):
                A list of area that safe to click. Swipe path will end there.
            blacklist_area: (list[tuple[int]]):
                If none of the whitelist_area satisfies current vector, blacklist_area will be used.
                Delete random path that ends in any blacklist_area.
            name (str): Swipe name
            distance_check: (bool):
        """
        p1, p2 = random_rectangle_vector_opted(
            vector,
            box=box,
            random_range=random_range,
            padding=padding,
            whitelist_area=whitelist_area,
            blacklist_area=blacklist_area
        )
        self.swipe(p1, p2, duration=duration, control_name=name, distance_check=distance_check)

    def drag(self, p1, p2, segments=1, shake=(0, 15), point_random=(-10, -10, 10, 10), shake_random=(-5, -5, 5, 5),
             swipe_duration=0.25, shake_duration=0.1, name='DRAG'):
        self.handle_control_check(name)
        p1, p2 = ensure_int(p1, p2)
        drag_log = 'Drag %s -> %s' % (point2str(*p1), point2str(*p2))
        # 原先这里误写成 self.config.script.emulator，会直接抛 AttributeError
        method = self.control_method
        start = time.perf_counter()
        if method == 'minitouch':
            self.drag_minitouch(p1, p2, point_random=point_random)
        elif method == 'uiautomator2':
            self.drag_uiautomator2(
                p1, p2, segments=segments, shake=shake, point_random=point_random, shake_random=shake_random,
                swipe_duration=swipe_duration, shake_duration=shake_duration)
        elif method == 'scrcpy':
            self.drag_scrcpy(p1, p2, point_random=point_random)
        elif method == 'window_win32':
            self.swipe_window_win32(p1, p2, duration=ensure_time(swipe_duration))
        # elif method == 'MaaTouch':
        #     self.drag_maatouch(p1, p2, point_random=point_random)
        else:
            logger.warning(f'Control method {method} does not support drag well, '
                           f'falling back to ADB swipe may cause unexpected behaviour')
            self.swipe_adb(p1, p2, duration=ensure_time(swipe_duration * 2))
            # self.click(Button(area=(), color=(), button=area_offset(point_random, p2), name=name))
        elapsed = time.perf_counter() - start
        logger.info(f'{self._format_action_duration(elapsed)}{drag_log}')
