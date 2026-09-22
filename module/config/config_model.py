# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from tasks.GuguArtStudio.config import GuguArtStudio
from tasks.GuildActivityMonitor.config import GuildActivityMonitor
from tasks.OtherWorldTwilight.config import OtherWorldTwilight
from typing import Dict, Any, ClassVar

import re
import inflection
# 注意：下面的 `from module.config.utils import *` 会把 `time` 覆盖成 datetime.time，
# 所以这里用别名，别改回 `import time`
import time as _time

from pathlib import Path
from pydantic import BaseModel, ValidationError, Field

from module.config.utils import *
from module.logger import logger

# 导入配置的Python文件
from tasks.Component.config_base import ConfigBase, TimeDelta, format_timedelta
from tasks.Exploration.config import Exploration
from tasks.RyouToppa.config import RyouToppa
from tasks.Dokan.config import Dokan
from tasks.Script.config import Script
from tasks.Restart.config import Restart
from tasks.GlobalGame.config import GlobalGame
# 每日任务-----------------------------------------------------------------------------------------------------
from tasks.AreaBoss.config import AreaBoss
from tasks.ExperienceYoukai.config import ExperienceYoukai
from tasks.GoldYoukai.config import GoldYoukai
from tasks.Nian.config import Nian
from tasks.KekkaiUtilize.config import KekkaiUtilize
from tasks.KekkaiActivation.config import KekkaiActivation
from tasks.DemonEncounter.config import DemonEncounter
from tasks.DailyTrifles.config import DailyTrifles
from tasks.TalismanPass.config import TalismanPass
from tasks.Pets.config import Pets
from tasks.SoulsTidy.config import SoulsTidy
from tasks.Delegation.config import Delegation
from tasks.WantedQuests.config import WantedQuests
from tasks.Tako.config import Tako
from tasks.AutoCheckinBigGod.config import AutoCheckinBigGod
# ----------------------------------------------------------------------------------------------------------------------
from tasks.Orochi.config import Orochi
from tasks.OrochiMoans.config import OrochiMoans
from tasks.Sougenbi.config import Sougenbi
from tasks.FallenSun.config import FallenSun
from tasks.EternitySea.config import EternitySea
from tasks.SixRealms.config import SixRealms
from tasks.RealmRaid.config import RealmRaid
from tasks.CollectiveMissions.config import CollectiveMissions
from tasks.Hunt.config import Hunt
from tasks.AbyssShadows.config import AbyssShadows
from tasks.GuildBanquet.config import GuildBanquet
from tasks.DemonRetreat.config import DemonRetreat
from tasks.GuildActivityMonitor.config import GuildActivityMonitor

# 这一部分是活动的配置-----------------------------------------------------------------------------------------------------
from tasks.ActivityShikigami.config import ActivityShikigami
from tasks.MartialTournament.config import MartialTournament
from tasks.MetaDemon.config import MetaDemon
from tasks.FrogBoss.config import FrogBoss
from tasks.FloatParade.config import FloatParade
from tasks.Quiz.config import Quiz
from tasks.KittyShop.config import KittyShop
from tasks.DyeTrials.config import DyeTrials
# ----------------------------------------------------------------------------------------------------------------------

# 肝帝专属---------------------------------------------------------------------------------------------------------------
from tasks.BondlingFairyland.config import BondlingFairyland
from tasks.EvoZone.config import EvoZone
from tasks.GoryouRealm.config import GoryouRealm
from tasks.Hyakkiyakou.config import Hyakkiyakou
from tasks.HeroTest.config import HeroTest
from tasks.FindJade.config import FindJade
from tasks.MemoryScrolls.config import MemoryScrolls
# ----------------------------------------------------------------------------------------------------------------------

# 每周任务---------------------------------------------------------------------------------------------------------------
from tasks.TrueOrochi.config import TrueOrochi
from tasks.RichMan.config import RichMan
from tasks.Secret.config import Secret
from tasks.WeeklyTrifles.config import WeeklyTrifles
from tasks.MysteryShop.config import MysteryShop
from tasks.Duel.config import Duel
from tasks.Chess.config import Chess
# ----------------------------------------------------------------------------------------------------------------------

# pydantic 把 timedelta 的默认值序列化成 ISO 8601 时长，例如 PT0S / PT2H / P1DT2H30M / P1W
_ISO_DURATION_RE = re.compile(
    r'^(?P<sign>-)?P'
    r'(?:(?P<weeks>\d+(?:\.\d+)?)W)?'
    r'(?:(?P<days>\d+(?:\.\d+)?)D)?'
    r'(?:T'
    r'(?:(?P<hours>\d+(?:\.\d+)?)H)?'
    r'(?:(?P<minutes>\d+(?:\.\d+)?)M)?'
    r'(?:(?P<seconds>\d+(?:\.\d+)?)S)?'
    r')?$'
)


def parse_iso_duration(text):
    """
    把 ISO 8601 时长解析成 timedelta，不是合法时长则返回 None。

    Args:
        text: 例如 'PT0S'、'PT2H'、'P1DT2H30M'、'P1W'

    Returns:
        datetime.timedelta | None
    """
    if not isinstance(text, str):
        return None
    match = _ISO_DURATION_RE.match(text.strip())
    if not match:
        return None
    parts = match.groupdict()
    if not any(parts[key] is not None for key in ('weeks', 'days', 'hours', 'minutes', 'seconds')):
        return None
    delta = timedelta(
        weeks=float(parts['weeks'] or 0),
        days=float(parts['days'] or 0),
        hours=float(parts['hours'] or 0),
        minutes=float(parts['minutes'] or 0),
        seconds=float(parts['seconds'] or 0),
    )
    return -delta if parts['sign'] else delta


def format_schema_default(field_type, default):
    """
    把 schema 里的 default 统一成应用自己的显示格式。

    pydantic 生成的 default 用的是 ISO 8601，而字段的实际值用的是应用格式，
    两者不一致会让前端把 default 当占位提示时显示成 PT2H / 2023-01-01T00:00:00 这种
    看不懂的东西：

    - time_delta : 'PT2H'                  -> '00 02:00:00'
    - date_time  : '2023-01-01T00:00:00'   -> '2023-01-01 00:00:00'
    - time       : '09:00:00'              -> 本来就是应用格式，不动

    转换失败（不是 ISO 格式）时原样返回，避免误伤。

    Args:
        field_type: schema 里的 type
        default: schema 里的 default

    Returns:
        转换后的 default
    """
    if not isinstance(default, str):
        return default
    if field_type == 'time_delta':
        delta = parse_iso_duration(default)
        return format_timedelta(delta) if delta is not None else default
    if field_type == 'date_time':
        try:
            return datetime.fromisoformat(default).strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            return default
    return default


def to_gui_schema(schema: dict) -> dict:
    """
    把 pydantic v2 的 JSON Schema 归一化成前端(QML ModelParse.js)期望的 v1 结构。

    背景：`module/gui/qml/Component/ModelParse.js` 是按 pydantic v1 的产物写的，
    而项目依赖 pydantic 2.x，两者结构不同，导致设置页的枚举字段拿不到
    title/type，整组渲染失败：

    - 定义区   : v2 用 `$defs`，v1 用 `definitions`
    - 引用前缀 : v2 是 `#/$defs/X`，v1 是 `#/definitions/X`
    - 枚举字段 : v2 直接给 `$ref`，v1 用 `allOf: [{$ref: ...}]` 包裹，
                 而前端只识别 `allOf`（见 ModelParse.js::parseArgument）

    同时把 default 里的 ISO 8601 时间格式统一成应用格式（见 format_schema_default）。

    Args:
        schema: pydantic 生成的 JSON Schema

    Returns:
        dict: v1 结构的 JSON Schema
    """
    def convert(node):
        if isinstance(node, dict):
            result = {}
            for key, value in node.items():
                if key == '$defs':
                    result['definitions'] = {k: convert(v) for k, v in value.items()}
                elif key == '$ref' and isinstance(value, str):
                    result['$ref'] = value.replace('#/$defs/', '#/definitions/')
                else:
                    result[key] = convert(value)
            return result
        if isinstance(node, list):
            return [convert(item) for item in node]
        return node

    result = convert(schema)

    for definition in (result.get('definitions') or {}).values():
        properties = definition.get('properties')
        if not isinstance(properties, dict):
            continue
        for name, prop in properties.items():
            if not isinstance(prop, dict):
                continue
            # 枚举字段：把裸 $ref 包成 allOf，前端才会识别为 enum 下拉框
            if '$ref' in prop and 'allOf' not in prop:
                ref = prop.pop('$ref')
                new_prop = {'allOf': [{'$ref': ref}]}
                new_prop.update(prop)
                properties[name] = prop = new_prop
            # 时间字段：把 ISO 8601 的 default 换成应用显示格式
            if 'default' in prop:
                prop['default'] = format_schema_default(prop.get('type'), prop['default'])
    return result


# ------------------------- 桌面版「选择账号」下拉框 -------------------------
# 选项由正在运行的游戏窗口动态生成，用户不用手抄账号 ID。
# 配置页一次渲染会多次取 schema，所以扫描结果缓存几秒 —— 每次扫描都要
# 枚举全部窗口并读各进程命令行，不缓存会明显拖慢设置页。
_DESKTOP_ACCOUNT_OPTIONS_CACHE: dict = {'at': 0.0, 'options': []}
_DESKTOP_ACCOUNT_OPTIONS_TTL = 3.0


def desktop_account_options() -> list:
    """扫描正在运行的桌面版游戏窗口，返回下拉选项（带几秒缓存）。

    选项形如 `"690806847 · 窗口位置 (29,32)"`：
    - 账号 ID 取自游戏启动参数 `/viewer_id=xxx`，**游戏重启后不变**，选一次就能一直用
    - 带上窗口位置，是因为 ID 里不含角色名，用户需要靠位置认出是哪个窗口

    写入配置时会用 `window_account.parse_account_id()` 把纯 ID 取出来，
    所以标签怎么写都不影响绑定结果。
    """
    now = _time.time()
    if now - _DESKTOP_ACCOUNT_OPTIONS_CACHE['at'] < _DESKTOP_ACCOUNT_OPTIONS_TTL:
        return _DESKTOP_ACCOUNT_OPTIONS_CACHE['options']

    from module.device.window_account import list_game_account_options
    options = list_game_account_options()

    _DESKTOP_ACCOUNT_OPTIONS_CACHE['at'] = now
    _DESKTOP_ACCOUNT_OPTIONS_CACHE['options'] = options
    return options


def _options_with_current(options: list, current) -> list:
    """把当前已选值并入选项列表。

    已选账号当前没在运行时也要留在选项里，否则下拉框会显示空白，
    用户会以为配置丢了。
    """
    values = list(options)
    if current and current not in values:
        values.insert(0, current)
    return values


def inject_desktop_account_options(items: list) -> list:
    """Web UI 路径（script_task）：把 account_id 变成带选项的 enum 字段。"""
    options = desktop_account_options()
    if not options:
        return items
    for item in items:
        if item.get('name') != 'account_id':
            continue
        item['type'] = 'enum'
        item['enumEnum'] = _options_with_current(options, item.get('value'))
    return items


def inject_desktop_account_options_v1(schema: dict) -> dict:
    """Qt GUI 路径（gui_args）：同样注入，但要写成 v1 结构。

    ModelParse.js 只认 allOf + definitions[类名].enum，所以这里现造一个同名定义。
    """
    options = desktop_account_options()
    definitions = schema.get('definitions')
    if not options or not definitions:
        return schema
    prop = definitions.get('Desktop', {}).get('properties', {}).get('account_id')
    if prop is None:
        return schema

    current = prop.get('default')
    values = _options_with_current(options, current)

    definitions['DesktopAccountId'] = {
        'title': 'DesktopAccountId',
        'type': 'string',
        'enum': values,
    }
    prop.pop('type', None)
    prop['allOf'] = [{'$ref': '#/definitions/DesktopAccountId'}]
    prop['default'] = current if current else (values[0] if values else '')
    return schema


class ConfigModel(ConfigBase):
    config_name: str = "oas"
    running_task: str = ''
    script: Script = Field(default_factory=Script)
    restart: Restart = Field(default_factory=Restart)
    global_game: GlobalGame = Field(default_factory=GlobalGame)

    # 这些是每日任务的
    area_boss: AreaBoss = Field(default_factory=AreaBoss)
    experience_youkai: ExperienceYoukai = Field(default_factory=ExperienceYoukai)
    gold_youkai: GoldYoukai = Field(default_factory=GoldYoukai)
    nian: Nian = Field(default_factory=Nian)
    realm_raid: RealmRaid = Field(default_factory=RealmRaid)
    ryou_toppa: RyouToppa = Field(default_factory=RyouToppa)
    kekkai_utilize: KekkaiUtilize = Field(default_factory=KekkaiUtilize)
    kekkai_activation: KekkaiActivation = Field(default_factory=KekkaiActivation)
    demon_encounter: DemonEncounter = Field(default_factory=DemonEncounter)
    daily_trifles: DailyTrifles = Field(default_factory=DailyTrifles)
    talisman_pass: TalismanPass = Field(default_factory=TalismanPass)
    pets: Pets = Field(default_factory=Pets)
    souls_tidy: SoulsTidy = Field(default_factory=SoulsTidy)
    delegation: Delegation = Field(default_factory=Delegation)
    exploration: Exploration = Field(default_factory=Exploration)
    wanted_quests: WantedQuests = Field(default_factory=WantedQuests)
    tako: Tako = Field(default_factory=Tako)
    auto_checkin_big_god: AutoCheckinBigGod = Field(default_factory=AutoCheckinBigGod)

    # 这些是刷御魂的
    orochi: Orochi = Field(default_factory=Orochi)
    orochi_moans: OrochiMoans = Field(default_factory=OrochiMoans)
    sougenbi: Sougenbi = Field(default_factory=Sougenbi)
    fallen_sun: FallenSun = Field(default_factory=FallenSun)
    eternity_sea: EternitySea = Field(default_factory=EternitySea)
    six_realms: SixRealms = Field(default_factory=SixRealms)
    other_world_twilight : OtherWorldTwilight = Field(default_factory=OtherWorldTwilight)

    # 这些是活动的
    activity_shikigami: ActivityShikigami = Field(default_factory=ActivityShikigami)
    martial_tournament: MartialTournament = Field(default_factory=MartialTournament)
    meta_demon: MetaDemon = Field(default_factory=MetaDemon)
    frog_boss: FrogBoss = Field(default_factory=FrogBoss)
    float_parade: FloatParade = Field(default_factory=FloatParade)
    quiz: Quiz = Field(default_factory=Quiz)
    kitty_shop: KittyShop = Field(default_factory=KittyShop)
    dye_trials: DyeTrials = Field(default_factory=DyeTrials)
    gugu_art_studio: GuguArtStudio = Field(default_factory=GuguArtStudio)

    # 这些是肝帝专属
    bondling_fairyland: BondlingFairyland = Field(default_factory=BondlingFairyland)
    evo_zone: EvoZone = Field(default_factory=EvoZone)
    goryou_realm: GoryouRealm = Field(default_factory=GoryouRealm)
    hyakkiyakou: Hyakkiyakou = Field(default_factory=Hyakkiyakou)
    hero_test: HeroTest = Field(default_factory=HeroTest)
    find_jade: FindJade = Field(default_factory=FindJade)
    memory_scrolls: MemoryScrolls = Field(default_factory=MemoryScrolls)

    # 这些是每周任务
    true_orochi: TrueOrochi = Field(default_factory=TrueOrochi)
    rich_man: RichMan = Field(default_factory=RichMan)
    secret: Secret = Field(default_factory=Secret)
    weekly_trifles: WeeklyTrifles = Field(default_factory=WeeklyTrifles)
    mystery_shop: MysteryShop = Field(default_factory=MysteryShop)
    duel: Duel = Field(default_factory=Duel)
    chess: Chess = Field(default_factory=Chess)

    # 阴阳寮
    collective_missions: CollectiveMissions = Field(default_factory=CollectiveMissions)
    hunt: Hunt = Field(default_factory=Hunt)
    dokan: Dokan = Field(default_factory=Dokan)
    abyss_shadows: AbyssShadows = Field(default_factory=AbyssShadows)
    guild_banquet: GuildBanquet = Field(default_factory=GuildBanquet)
    demon_retreat: DemonRetreat = Field(default_factory=DemonRetreat)
    guild_activity_monitor: GuildActivityMonitor = Field(default_factory=GuildActivityMonitor)

    # 早期版本的桌面版方案被写进了模拟器字段，现在归属到 script.desktop 下，需要迁移
    # 注意必须声明为 ClassVar，否则 pydantic 会把下划线开头的类属性当成私有字段
    _LEGACY_DESKTOP_FIELDS: ClassVar[dict] = {
        'desktop_window_title': 'window_title',
        'desktop_window_class': 'window_class',
        'desktop_window_pid': 'window_pid',
        'desktop_exe_path': 'exe_path',
        'desktop_restore_window': 'restore_window',
    }
    # window_win32 现在是桌面版专用方案，不再属于模拟器的枚举，遇到就归位
    _LEGACY_DEVICE_METHODS: ClassVar[dict] = {
        'screenshot_method': 'auto',
        'control_method': 'minitouch',
    }

    @classmethod
    def migrate_legacy_config(cls, data: dict) -> dict:
        """
        迁移旧配置。

        1. `script.device.desktop_*` 搬到 `script.desktop.*`（桌面版设置独立成组）
        2. 模拟器的 screenshot_method / control_method 若残留 window_win32，
           归位到默认值 —— 该值现在只属于桌面版，留在模拟器字段里会导致校验失败
        """
        if not isinstance(data, dict):
            return data
        script = data.get('script')
        if not isinstance(script, dict):
            return data

        device = script.get('device')
        if not isinstance(device, dict):
            return data

        # 1. 桌面版字段搬迁
        desktop = script.get('desktop')
        if not isinstance(desktop, dict):
            desktop = {}
        moved = {}
        for old_key, new_key in cls._LEGACY_DESKTOP_FIELDS.items():
            if old_key in device:
                value = device.pop(old_key)
                # 新字段已有值时以新字段为准
                desktop.setdefault(new_key, value)
                moved[old_key] = new_key
        if moved:
            logger.info(f'Migrate legacy desktop config: {moved}')
        script['desktop'] = desktop

        # 2. 模拟器字段里的桌面版方案归位
        for key, default in cls._LEGACY_DEVICE_METHODS.items():
            if device.get(key) == 'window_win32':
                logger.warning(f'Migrate legacy desktop method: script.device.{key} '
                               f'window_win32 -> {default}')
                device[key] = default
        return data

    def __init__(self, config_name: str=None, **data) -> None:
        """

        :param config_name:
        """
        if data:
            if config_name:
                data["config_name"] = config_name
            super().__init__(**data)
            return
        if not config_name:
            super().__init__()
            return
        data = self.read_json(config_name)
        data = self.migrate_legacy_config(data)
        data["config_name"] = config_name
        super().__init__(**data)

    def __setattr__(self, key, value):
        """
        只要修改属性就会触发这个函数 自动保存
        :param key:
        :param value:
        :return:
        """
        super().__setattr__(key, value)
        logger.info("auto save config")
        self.save()

    @staticmethod
    def read_json(config_name: str) -> dict:
        """
        读文件 没有额外操作
        :param config_name:  不带后缀
        :return:
        """
        filepath = Path.cwd() / "config" / f"{config_name}.json"
        return read_file(filepath)

    @staticmethod
    def write_json(config_name: str, data) -> None:
        """

        :param config_name: 不带后缀
        :param data:  字典而不是字符串
        :return:
        """
        filepath = Path.cwd() / "config" / f"{config_name}.json"
        write_file(filepath, data)

    def gui_args(self, task: str) -> str:
        """
        返回提供给gui显示的参数
        :param task: 输入的是任务的名称英文 如'Script' 或者是'script'都是可以的
        :return: 返回的是pydantic给我们结构化的输出的信息, 如果不能获取就返回空的str
        """
        task = convert_to_underscore(task)
        task_gui = getattr(self, task, None)
        if task_gui is None:
            logger.warning(f'{task} is no inexistence')
            return ''

        # pydantic v2 输出的是 $defs / 裸 $ref，前端 ModelParse.js 只认 v1 的
        # definitions / allOf，这里先归一化，否则设置页会整组渲染失败
        schema2 = to_gui_schema(task_gui.schema())
        # 桌面版：给 account_id 注入当前检测到的账号，配置页直接下拉选择
        inject_desktop_account_options_v1(schema2)
        # https://github.com/pydantic/pydantic/discussions/5687
        if 'definitions' in schema2:
            if 'Scheduler' in schema2['definitions']:
                if 'properties' in schema2['definitions']['Scheduler']:
                    properties = schema2['definitions']['Scheduler']['properties']
                    if 'success_interval' in properties:
                        properties['success_interval']['type'] = 'string'
                    if 'failure_interval' in properties:
                        properties['failure_interval']['type'] = 'string'
        return json.dumps(schema2)

    def gui_task(self, task: str) -> str:
        """
        返回提供给gui显示的参数
        :param task:
        :return:
        """
        task_name = convert_to_underscore(task)
        task = getattr(self, task_name, None)
        if task is None:
            logger.warning(f'{task_name} is no inexistence')
            return ''
        return task.json()

    def save(self) -> None:
        """

        :return:
        """
        self.write_json(self.config_name, self.model_dump())

    @staticmethod
    def type(key: str) -> str:
        """
        输入模型的键值，获取这个字段对象的类型 比如输入是orochi输出是Orochi
        :param key:
        :return:
        """
        field_type: str = str(ConfigModel.__annotations__[key])
        # return field_type
        if '.' in field_type:
            classname = field_type.split('.')[-1][:-2]
            return classname
        else:
            classname = re.findall(r"'([^']*)'", field_type)[0]
            return classname

    @staticmethod
    def deep_get(obj, keys: str, default=None):
        """
        递归获取模型的值
        :param obj:
        :param keys:
        :param default:
        :return:
        """
        if not isinstance(keys, list):
            keys = keys.split('.')
        value = obj
        try:
            for key in keys:
                value = getattr(value, key)
        except AttributeError:
            return default
        return value

    @staticmethod
    def deep_set(obj, keys: str, value) -> bool:
        if not isinstance(keys, list):
            keys = keys.split('.')
        current_obj = obj
        try:
            for key in keys[:-1]:
                current_obj = getattr(current_obj, key)
            setattr(current_obj, keys[-1], value)
            return True
        except (AttributeError, KeyError):
            return False

    # ----------------------------------- fastapi -----------------------------------
    def script_task(self, task: str) -> dict:
        """

        :param task: 同gui_args函数
        :return:
        """
        task = convert_to_underscore(task)
        task = getattr(self, task, None)
        if task is None:
            logger.warning(f'{task} is no inexistence')
            return {}

        def extract_groups(sch):
            # 从schema 中提取未解析的group的数据
            # properties = properties_groups(sch)
            results = {}
            properties = {}
            for key, value in sch["properties"].items():
                if 'items' in value:
                    properties[key] = re.search(r"/([^/]+)$", value['items']['$ref']).group(1)
                else:
                    properties[key] = re.search(r"/([^/]+)$", value['$ref']).group(1)

            for key, value in properties.items():
                results[key] = sch["$defs"][value]
            return results

        def merge_value(groups, jsons, definitions) -> list[dict]:
            # 将 groups的参数，同导出的json一起合并, 用于前端显示
            result = []
            for key, value in groups["properties"].items():
                # deal with exclude 
                if key in jsons and jsons[key] == 0xABCDEF:
                    continue

                item = {}
                item["name"] = key
                item["title"] = value["title"] if "title" in value else inflection.underscore(key)
                if "description" in value:
                    item["description"] = value["description"]
                item["default"] = value["default"]
                item["value"] = jsons[key] if key in jsons else value["default"]
                item["type"] = value["type"] if "type" in value else "enum"
                if '$ref' in value:  # list
                    enum_key = re.search(r"/([^/]+)$", value['$ref']).group(1)
                    item["enumEnum"] = definitions[enum_key]["enum"]
                # if 'allOf' in value:
                #     enum_key = re.search(r"/([^/]+)$", value['allOf'][0]['$ref']).group(1)
                #     item["enumEnum"] = definitions[enum_key]["enum"]
                result.append(item)
            return result

        schema = task.model_json_schema()
        groups = extract_groups(schema)
        groups_value = groups.copy()

        result: dict[str, list] = {}
        for key, value in task.model_dump(context={'hide': True}).items():
            if value == 0xABCDEF:
                continue
            if key not in groups:
                for group_name in groups.keys():
                    if group_name in key:
                        groups_value[key] = groups[group_name]
            result[key] = merge_value(groups_value[key], value, schema["$defs"])

        # 桌面版：给 account_id 注入当前检测到的账号，配置页直接下拉选择（不用手抄 ID）
        if 'desktop' in result:
            inject_desktop_account_options(result['desktop'])

        return result

    def script_set_arg(self, task: str, group: str, argument: str, value) -> bool:
        # 验证参数
        task = convert_to_underscore(task)
        group = convert_to_underscore(group)
        argument = convert_to_underscore(argument)

        # pandtic验证
        if isinstance(value, str) and len(value) == 8:
            try:
                value = datetime.strptime(value, '%H:%M:%S').time()
            except ValueError:
                pass
        if isinstance(value, str) and len(value) == 11:
            try:
                date_time = datetime.strptime(value, '%d %H:%M:%S')
                value = TimeDelta(days=date_time.day, hours=date_time.hour, minutes=date_time.minute, seconds=date_time.second)
            except ValueError:
                pass
        if isinstance(value, str) and len(value) == 19:
            try:
                value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        if isinstance(value, str) and value == 'true':
            value = True
        if isinstance(value, str) and value == 'false':
            value = False

        task_object = getattr(self, task, None)
        group_object = getattr(task_object, group, None)
        if group_object is None:  # deal list
            matchs = re.findall(r'\d+', group)
            index = int(matchs[-1]) - 1 if matchs else None
            task_object_list = list(dict(task_object))
            for k, v in dict(task_object).items():
                if k not in group:
                    continue
                group_object = v[index] if group_object is None else None
        argument_object = getattr(group_object, argument, None)

        if argument_object is None:
            logger.error(f'Set arg {task}.{group}.{argument}.{value} failed')
            return False

        # XXX temp implementation to enable oasx control the datetime configuration globally rather than a single task
        if task == "restart" and group == "task_config" and argument == "reset_task_datetime_enable" and value == True:
            date_time = self.restart.task_config.reset_task_datetime
            logger.info(f"reset_task_datetime={date_time}")
            self.reset_datetime_for_all_enabled_tasks(date_time)

        # 设置参数
        try:
            setattr(group_object, argument, value)
            logger.info(f'Set arg {self.config_name}.{task}.{group}.{argument}.{value}')
            self.save()  # 我是没有想到什么方法可以使得属性改变自动保存的
            return True
        except ValidationError as e:
            logger.error(e)
            return False

    def copy_script_task(self, task_name: str, source_task: BaseModel) -> bool:
        model_task_name = convert_to_underscore(task_name)
        try:
            setattr(self, model_task_name, source_task)
            self.save()
            logger.info(f'Copy task {model_task_name} success')
            return True
        except ValidationError as e:
            logger.error(e)
            return False

    def copy_task_group(self, task_name: str, group_name: str, source_task: BaseModel) -> bool:
        model_task_name = convert_to_underscore(task_name)
        model_group_name = convert_to_underscore(group_name)
        task_object = getattr(self, model_task_name, None)
        if not task_object:
            return False
        source_group_obj = getattr(source_task, model_group_name, None)
        if not source_group_obj:
            return False
        try:
            setattr(task_object, model_group_name, source_group_obj)
            self.save()
            logger.info(f'Copy task group {model_task_name}.{model_group_name} success')
            return True
        except ValidationError as e:
            logger.error(e)
            return False

    def replace_next_run(self, d, dt: datetime):
        for k, v in d.items():
            if isinstance(v, dict):
                self.replace_next_run(v, dt=dt)
            elif k == "next_run":
                d[k] = dt
                # convert value to datetime if it's a str
                if isinstance(v, str):
                    current_time = datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
                    if current_time != dt:
                        d[k] = dt.strftime("%Y-%m-%d %H:%M:%S")
                # already a datetime value
                elif isinstance(v, datetime) and v != dt:
                    d[k] = dt.strftime("%Y-%m-%d %H:%M:%S")

    def reset_datetime_for_all_enabled_tasks(self, task_datetime: datetime):
        logger.warn(f"trying to reset datetime of all tasks to: {task_datetime}")
        # logger.info(f"current config: {self.dict()}")
        data = self.dict()
        self.replace_next_run(data, task_datetime)
        # logger.info(f"new config: {data}")

        # write to json config  file
        self.write_json(self.config_name, data)

        # reload from the newly modified json config file
        data = self.read_json(self.config_name)
        super().__init__(**data)


if __name__ == "__main__":
    try:
        c = ConfigModel("oas1")
    except ValidationError as e:
        print(e)
        c = ConfigModel()

    print(c.script_task('GuildBanquet'))
