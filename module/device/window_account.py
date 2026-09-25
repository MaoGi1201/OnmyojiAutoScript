# This Python file uses the following encoding: utf-8
"""
桌面版（PC 客户端）多开时的账号识别。
多开时两个窗口的标题、类名、exe 路径**完全相同**，除了账号 ID 没有任何可区分特征，
因此账号 ID 是唯一可靠的绑定依据。
"""
import re

import psutil

from module.logger import logger

# 游戏启动参数形如 /viewer_id=690806847
# 注意同一命令行里还有 /onetime_token=xxx，那个**每次启动都变**，不能拿来当标识
ACCOUNT_ID_PATTERN = re.compile(r'/viewer_id=(\d+)')

# 配置页下拉选项里的账号 ID 至少 5 位，避免把 "(45,462)" 里的数字误当账号
_ACCOUNT_DIGITS_PATTERN = re.compile(r'\d{5,}')

# 下拉选项的展示格式："690806847 · 窗口位置 (29,32)"
# 账号 ID 本身不含角色名，用窗口位置帮用户认出是哪一个窗口
OPTION_SEPARATOR = ' · '


def get_account_id(pid: int) -> str:
    """读取进程命令行里的账号 ID（游戏启动参数 /viewer_id=xxx）。

    读不到时返回空串：进程已退出、权限不足，或客户端换了启动参数。
    返回空串是**正常情况**，调用方要按"这个窗口没有账号信息"处理，不要当异常。
    """
    try:
        for arg in psutil.Process(pid).cmdline():
            match = ACCOUNT_ID_PATTERN.search(arg)
            if match:
                return match.group(1)
    except Exception as e:
        # 进程刚退出时 NoSuchProcess 很常见，不必刷 error 级日志
        logger.info(f'Read account id of pid {pid} failed: {e}')
    return ''


def parse_account_id(value) -> str:
    """从配置值里取出账号 ID。

    配置页的下拉选项是可读标签（形如 `"690806847 · 窗口位置 (29,32)"`），
    但也允许用户手填纯数字或从别处粘贴带噪音的字符串，两种都要能认出来。
    """
    match = _ACCOUNT_DIGITS_PATTERN.search(str(value or ''))
    return match.group(0) if match else ''


def format_account_option(account_id: str, rect) -> str:
    """把账号 ID 与窗口位置拼成下拉选项文本。

    Args:
        account_id: 账号 ID。
        rect: 窗口矩形 (left, top, right, bottom) 或 (left, top, width, height)，
            这里只取左上角坐标。
    """
    left, top = rect[0], rect[1]
    return f'{account_id}{OPTION_SEPARATOR}窗口位置 ({left},{top})'


def list_game_accounts() -> list:
    """列出当前正在运行的桌面版游戏账号，供配置页下拉选择。

    返回的是**去重后的账号 ID 列表**（同一账号开多个窗口只算一个）。
    延迟导入 DesktopWindow，避免与它形成循环依赖。
    """
    from module.device.env import IS_WINDOWS
    if not IS_WINDOWS:
        return []

    try:
        from module.device.desktop_window import DesktopWindow
        windows = DesktopWindow.list_game_windows()
    except Exception as e:
        logger.info(f'Scan desktop game windows failed: {e}')
        return []

    accounts = []
    for item in windows:
        account = item['account_id']
        if account and account not in accounts:
            accounts.append(account)
    return accounts


def list_game_account_options() -> list:
    """列出当前账号的下拉选项文本（含窗口位置，便于用户辨认）。

    延迟导入 DesktopWindow，避免与它形成循环依赖。
    """
    from module.device.env import IS_WINDOWS
    if not IS_WINDOWS:
        return []

    try:
        from module.device.desktop_window import DesktopWindow
        windows = DesktopWindow.list_game_windows()
    except Exception as e:
        logger.info(f'Scan desktop game windows failed: {e}')
        return []

    options = []
    for item in windows:
        account = item['account_id']
        if not account:
            continue
        option = format_account_option(account, item['rect'])
        if option not in options:
            options.append(option)
    return options
