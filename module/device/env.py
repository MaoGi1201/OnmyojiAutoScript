# This Python file uses the following encoding: utf-8
# https://github.com/LmeSzinc/StarRailCopilot/blob/master/module/device/env.py
import sys
from enum import Enum

IS_WINDOWS = sys.platform == 'win32'
IS_MACINTOSH = sys.platform == 'darwin'
IS_LINUX = sys.platform == 'linux'

# 桌面版（PC 客户端）模式下的取值，用于判断当前目标是桌面窗口还是模拟器
DESKTOP_MODE = 'desktop'


def enum_value(value):
    """取出枚举成员的原始值，非枚举原样返回。

    Python 3.10 下 `str(SomeStrEnum.MEMBER)` 得到的是 `'SomeStrEnum.MEMBER'` 而非
    它的值。配置从 JSON 读入时 pydantic 会转成枚举成员，所以判断枚举字段必须走
    `.value`，不能直接 `str()`，否则会静默判断失败。
    """
    if isinstance(value, Enum):
        return value.value
    return value


def is_desktop_mode(config) -> bool:
    """当前配置是否使用桌面版（PC 客户端）模式。

    刻意不依赖 pydantic 模型的具体类型，避免设备初始化早期（模型可能尚未构建）出错。
    """
    try:
        mode = config.script.device.emulator_control
    except Exception:
        return False
    return str(enum_value(mode)).strip().lower() == DESKTOP_MODE
