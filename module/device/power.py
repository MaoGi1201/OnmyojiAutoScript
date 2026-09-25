# This Python file uses the following encoding: utf-8
"""Windows 电源管理：阻止系统休眠与显示器关闭。

为什么需要：
桌面版靠 ``PrintWindow(PW_RENDERFULLCONTENT)`` 抓窗口内容。显示器一旦关闭只能拿到黑图或
最后一帧旧画面 —— OCR 与图片匹配会全部失败，任务判定成"卡住"，
进而触发反复重启。所以跑桌面版时必须让显示器保持点亮、系统保持唤醒。

实现用 ``SetThreadExecutionState``：
- 状态是**线程级**的，但系统会汇总所有线程的请求，所以任一线程请求即可；
- 带 ``ES_CONTINUOUS`` 时会一直生效，直到该线程退出或再次调用重置；
- 因此必须在**长生命周期线程**（脚本进程主线程）里调用。
"""

import sys

from module.logger import logger

# SetThreadExecutionState 的标志位
ES_CONTINUOUS = 0x80000000         # 状态持续生效，直到再次调用重置
ES_SYSTEM_REQUIRED = 0x00000001    # 阻止系统进入睡眠
ES_DISPLAY_REQUIRED = 0x00000002   # 重置显示器空闲计时器，阻止息屏


def keep_display_awake(enable: bool = True) -> bool:
    """
    开启/关闭「保持唤醒」状态。

    :param enable: True 阻止息屏与休眠；False 恢复系统默认电源策略
    :return: 是否调用成功（非 Windows 或调用失败时返回 False）
    """
    if sys.platform != 'win32':
        return False
    try:
        import ctypes
        flags = ES_CONTINUOUS
        if enable:
            flags |= ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        # 返回值为上一次的执行状态；0 表示调用失败
        result = ctypes.windll.kernel32.SetThreadExecutionState(flags)
        if not result:
            logger.warning('SetThreadExecutionState failed, '
                           'the screen may still turn off during the task')
            return False
        if enable:
            logger.info('Keep display awake: screen off and system sleep are blocked')
        else:
            logger.info('Keep display awake: restored to the system power policy')
        return True
    except Exception as e:
        logger.warning(f'SetThreadExecutionState error: {e}')
        return False
