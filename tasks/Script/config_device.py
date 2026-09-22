# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from typing import Union
from pydantic import BaseModel, ValidationError, Field

from module.logger import logger


class PackageName(str, Enum):
    AUTO = 'auto'
    NETEASE_ONMYOJI = 'com.netease.onmyoji.wyzymnqsd_cps'  # 网易官方扫码版
    NETEASE_MI = 'com.netease.onmyoji.mi'  # 小米
    NETEASE = 'com.netease.onmyoji'     # 网易官方非扫码版
    NETEASE_HUAWEI = 'com.netease.onmyoji.huawei'
    NETEASE_BILIBILI = 'com.netease.onmyoji.bili' #哔哩哔哩渠道服
    NETEASE_VIVO = 'com.netease.onmyoji.vivo'  # vivo渠道服
    NETEASE_M4399 = 'com.netease.onmyoji.m4399'  # 4399渠道服
    NETEASE_NEARME = 'com.netease.onmyoji.nearme.gamecenter'  # OPPO渠道服
    TENCENT_YYS = 'com.tencent.tmgp.yys.zqb'  # 腾讯应用宝渠道阴阳师
    NETEASE_NA = 'com.netease.onmyoji.na'  # 日服

class ScreenshotMethod(str, Enum):
    """模拟器截图方案。桌面版方案见 DesktopScreenshotMethod，两者互不混用。"""
    AUTO = 'auto'
    ADB = 'ADB'
    ADB_NC = 'ADB_nc'
    UIAUTOMATOR2 = 'uiautomator2'
    DROIDCAST = 'DroidCast'
    DROIDCAST_RAW = 'DroidCast_raw'
    SCRCPY = 'scrcpy'
    WINDOW_BACKGROUND = 'window_background'
    NEMU_IPC = 'nemu_ipc'


class ControlMethod(str, Enum):
    """模拟器控制方案。桌面版方案见 DesktopControlMethod，两者互不混用。"""
    ADB = 'adb'
    UIAUTOMATOR2 = 'uiautomator2'
    MINITOUCH = 'minitouch'
    WINDOW_MESSAGE = 'window_message'


class EmulatorControl(str, Enum):
    """脚本操作的目标：模拟器（ADB）或桌面版游戏窗口（Win32）。"""
    EMULATOR = 'emulator'
    DESKTOP = 'desktop'


class DesktopScreenshotMethod(str, Enum):
    """桌面版（PC 客户端）截图方案：PrintWindow 后台截图，窗口被遮挡也能抓。"""
    WINDOW_WIN32 = 'window_win32'


class DesktopControlMethod(str, Enum):
    """桌面版（PC 客户端）控制方案：PostMessage 后台点击，不移动真实鼠标、不抢焦点。"""
    WINDOW_WIN32 = 'window_win32'


class EmulatorInfoType(str, Enum):
    # module.device.platform2.emulator_base.EmulatorBase
    AUTO = 'auto'
    NoxPlayer = 'NoxPlayer'
    NoxPlayer64 = 'NoxPlayer64'
    BlueStacks4 = 'BlueStacks4'
    BlueStacks5 = 'BlueStacks5'
    BlueStacks4HyperV = 'BlueStacks4HyperV'
    BlueStacks5HyperV = 'BlueStacks5HyperV'
    LDPlayer3 = 'LDPlayer3'
    LDPlayer4 = 'LDPlayer4'
    LDPlayer9 = 'LDPlayer9'
    MuMuPlayer = 'MuMuPlayer'
    MuMuPlayerX = 'MuMuPlayerX'
    MuMuPlayer12 = 'MuMuPlayer12'
    MEmuPlayer = 'MEmuPlayer'


class Device(BaseModel):
    """模拟器（ADB）相关设置。运行方式选 desktop 时本组除 emulator_control 外都不生效。"""
    emulator_control: EmulatorControl = Field(default=EmulatorControl.EMULATOR, description='emulator_control_help')
    serial: str = Field(default="auto", description='serial_help')
    handle: str = Field(default='', description='handle_help')
    package_name: PackageName = Field(title='Package Name', default=PackageName.AUTO, description='package_name_help')
    screenshot_method: ScreenshotMethod = Field(default=ScreenshotMethod.AUTO, description='screenshot_method_help')
    control_method: ControlMethod = Field(default=ControlMethod.MINITOUCH, description='control_method_help')
    adb_restart: bool = Field(default=False, description='adb_restart_help')
    emulatorinfo_type: EmulatorInfoType = Field(default=EmulatorInfoType.AUTO, description='emulatorinfo_type_help')
    emulatorinfo_name: str = Field(default='', description='emulatorinfo_name_help')
    emulatorinfo_path: str = Field(default='', description='emulatorinfo_path_help')
    # 举例, E:\ProgramFiles\MuMuPlayer-12.0\shell\MuMuPlayer.exe
    emulator_window_minimize: bool = Field(default=False, description='emulator_window_minimize_help')
    run_background_only: bool = Field(default=False, description='run_background_only_help')


class Desktop(BaseModel):
    """桌面版（PC 客户端）设置。

    与模拟器配置完全独立：运行方式选 desktop 后，截图/控制方案直接跟随本组，
    不需要也不应该再去改模拟器那两个下拉框。字段说明见 zh_CN.xml。
    """
    screenshot_method: DesktopScreenshotMethod = Field(
        default=DesktopScreenshotMethod.WINDOW_WIN32, description='desktop_screenshot_method_help')
    control_method: DesktopControlMethod = Field(
        default=DesktopControlMethod.WINDOW_WIN32, description='desktop_control_method_help')
    window_title: str = Field(default='陰陽師Onmyoji|阴阳师', description='desktop_window_title_help')
    account_id: str = Field(default='', description='desktop_account_id_help')
    window_class: str = Field(default='Win32Window', description='desktop_window_class_help')
    window_pid: int = Field(default=0, description='desktop_window_pid_help')
    exe_path: str = Field(default='', description='desktop_exe_path_help')
    restore_window: bool = Field(default=True, description='desktop_restore_window_help')
    resize_window: bool = Field(default=False, description='desktop_resize_window_help')
    window_width: int = Field(default=1280, ge=320, le=7680, description='desktop_window_width_help')
    window_height: int = Field(default=720, ge=240, le=4320, description='desktop_window_height_help')


if __name__ == '__main__':
    d = Device()
    print(d.json())
    print(d.schema_json())
    try:
        d.control_method = 'adb'
    except ValidationError as e:
        print(e)
