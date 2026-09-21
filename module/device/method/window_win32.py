# This Python file uses the following encoding: utf-8
"""
桌面端（PC 客户端）设备方法的入口。

与 `method/windows.py` 一样，把平台相关实现隔离在 `*_impl` 里，
非 Windows 平台提供一个空实现，避免导入 win32 相关依赖时报错。
"""

from module.device.env import IS_WINDOWS

if IS_WINDOWS:
    from module.device.method.window_win32_impl import WindowWin32

else:
    class WindowWin32:
        pass
