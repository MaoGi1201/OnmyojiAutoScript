# This Python file uses the following encoding: utf-8
"""同一设备的互斥锁 —— 防止两个东西同时驱动同一个账号。
"""

import hashlib
from pathlib import Path

from filelock import FileLock, Timeout

from module.logger import logger

# 锁文件放在 config/.locks/ 下：
# config/ 目录会被 ConfigManager 用 *.json 扫成配置列表，用子目录可以避开
_LOCK_DIR = Path.cwd() / 'config' / '.locks'

# 本进程当前持有的锁：device_key -> (FileLock, owner 文件路径)
_HELD: dict[str, tuple[FileLock, Path]] = {}


class DeviceBusyError(RuntimeError):
    """设备（账号）正被别的进程占用。

    这是一个**预期内的状态**，调用方应该记一条明确的日志
    """

    def __init__(self, label: str, holder: str) -> None:
        self.holder = holder
        super().__init__(f'{label} 正在运行中（占用者：{holder}）')


def device_key(config) -> str | None:
    """
    当前配置指向的「设备」唯一标识。

    :return: 形如 ``desktop:XXXXXX`` / ``emulator:127.0.0.1:16384``；
             无法判定时返回 None（此时不做互斥，避免误锁）
    """
    try:
        from module.device.env import is_desktop_mode
        if is_desktop_mode(config):
            raw = str(getattr(config.script.desktop, 'account_id', '') or '').strip()
            from module.device.window_account import parse_account_id
            # 未绑定时的「不绑定（按窗口标题匹配）」），只有能解析出纯账号 ID 才算绑了账号
            account = parse_account_id(raw)
            if not account:
                # 没绑账号 → 按标题匹配，无法确定是哪个账号，不做互斥
                return None
            return f'desktop:{account}'

        serial = str(getattr(config.script.device, 'serial', '') or '').strip()
        if not serial or serial == 'auto':
            return None
        return f'emulator:{serial}'
    except Exception as e:
        logger.debug(f'Resolve device key failed: {e}')
        return None


def device_label(config) -> str:
    """给日志用的可读描述。"""
    key = device_key(config)
    if key is None:
        return '当前设备'
    kind, _, value = key.partition(':')
    return f'账号 {value}' if kind == 'desktop' else f'设备 {value}'


def _paths(key: str) -> tuple[Path, Path]:
    digest = hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]
    return _LOCK_DIR / f'{digest}.lock', _LOCK_DIR / f'{digest}.owner'


def _read_owner(owner_path: Path) -> str:
    try:
        return owner_path.read_text(encoding='utf-8').strip()
    except OSError:
        return '未知'


def _write_owner(owner_path: Path, owner: str) -> None:
    try:
        owner_path.write_text(owner, encoding='utf-8')
    except OSError as e:
        logger.debug(f'Write owner file failed: {e}')


def acquire(config, owner: str) -> tuple[bool, str]:
    """
    尝试占用当前配置指向的设备（非阻塞）。

    :param config: 配置对象
    :param owner: 占用者描述，如 ``脚本 XXXXX`` / ``标注工具``
    :return: ``(是否拿到, 占用者描述)``；拿到时第二个值为空串
    """
    key = device_key(config)
    if key is None:
        return True, ''
    if key in _HELD:
        return True, ''

    lock_path, owner_path = _paths(key)
    try:
        _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.debug(f'Create lock dir failed: {e}')
        return True, ''

    lock = FileLock(str(lock_path), timeout=0)
    try:
        lock.acquire()
    except Timeout:
        return False, _read_owner(owner_path)
    except OSError as e:
        # 拿不到锁文件本身不该阻塞业务
        logger.debug(f'Acquire device lock failed: {e}')
        return True, ''

    _write_owner(owner_path, owner)
    _HELD[key] = (lock, owner_path)
    logger.debug(f'Device lock acquired: {key} by {owner}')
    return True, ''


def release(config) -> None:
    """释放当前配置指向设备的锁（没持有则什么都不做）。
    """
    key = device_key(config)
    if key is None:
        return
    item = _HELD.pop(key, None)
    if item is None:
        return
    lock, _owner_path = item
    try:
        lock.release()
    except Exception as e:
        logger.warning(f'Release device lock failed: {e}')
        return
    logger.debug(f'Device lock released: {key}')
