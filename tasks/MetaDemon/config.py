# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta, time
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.QuickLoadout.config import parse_named_presets

from tasks.Component.config_base import ConfigBase, TimeDelta, Time, dynamic_hide
from pydantic import Field, field_validator, model_validator
from module.cooperation import instance_name
from enum import IntEnum, Enum
from tasks.Component.config_scheduler import Scheduler


class BossType(IntEnum):
    ONE_STAR = 1
    TWO_STARS = 2
    THREE_STARS = 3
    FOUR_STARS = 4
    FIVE_STARS = 5
    SIX_STARS = 6
    MONEY = 7


class MetaDemonMode(str, Enum):
    BOSS_BATTLE = '鬼王战斗'
    BOSS_ASSIST = '鬼王协助'


def mode_values(value) -> list[str]:
    """兼容旧配置里的列表写法（["鬼王战斗"]），统一成取值列表。"""
    if isinstance(value, str):
        return [value]
    return [getattr(item, 'value', item) for item in (value or [])]


class MetaDemonConfig(ConfigBase):
    mode: MetaDemonMode = Field(default=MetaDemonMode.BOSS_BATTLE,
        description='鬼王协助：协同双方须启用鬼王协助，并分别配置上供和协助身份')

    @field_validator('mode', mode='before')
    @classmethod
    def parse_mode(cls, value):
        """运行模式为单选，兼容旧配置里的列表写法。"""
        if isinstance(value, MetaDemonMode):
            return value
        if isinstance(value, (list, tuple, set)):
            value = next(iter(value), None)
            if isinstance(value, MetaDemonMode):
                return value
        text = '' if value is None else str(value).strip()
        if text in ('', '[]'):
            return MetaDemonMode.BOSS_BATTLE
        return MetaDemonMode(text)

    limit_time: Time = Field(default=Time(minute=45), description='limit_time_help')
    limit_count: int = Field(default=50, description='limit_count_help')
    auto_tea: bool = Field(default=False, description='疲劳度满时是否自动喝茶, 关闭则自动根据调度器等待间隔时间安排下一次调度')
    fire_sequence: str = Field(default='1 2 3 4', description='攻击顺序:从左到右,空格分隔(1:一星鬼王,2:二星鬼王...)\n例:3 2(先攻击三星鬼王然后二星鬼王)')
    high_star_powerful_enable: bool = Field(
        default=False, title='启用高星强力追击', description='仅对五星、六星鬼王生效。',
    )
    powerful_count: int = Field(
        default=1, ge=1, title='强力追击次数', description='每只高星鬼王的前几次挑战使用强力追击，之后改用普通追击。',
    )
    synthesis_list: str = Field(default='1', description='鬼王合成列表(空格分隔),支持1-5星合成,例:1 2 3(合成一星,二星,三星鬼王)')

    @model_validator(mode='before')
    @classmethod
    def migrate_powerful_list(cls, data):
        if isinstance(data, dict) and 'powerful_list' in data and 'high_star_powerful_enable' not in data:
            stars = str(data['powerful_list']).split()
            return {**data, 'high_star_powerful_enable': '5' in stars or '6' in stars}
        return data

    @property
    def limit_time_v(self) -> timedelta:
        if isinstance(self.limit_time, time):
            return timedelta(hours=self.limit_time.hour, minutes=self.limit_time.minute, seconds=self.limit_time.second)
        return self.limit_time

    @property
    def fire_sequence_v(self) -> list[BossType]:
        sequence_text = self.fire_sequence.strip()
        if sequence_text == '':
            return []
        fire_num_list = sequence_text.split(' ')
        fire_boss_type_list = [BossType(int(num_text)) for num_text in fire_num_list]
        return fire_boss_type_list

    @property
    def synthesis_list_v(self) -> list[BossType]:
        synthesis_list_text = self.synthesis_list.strip()
        if synthesis_list_text == '':
            return []
        synthesis_num_list = synthesis_list_text.split(' ')
        synthesis_boss_type_list = [BossType(int(num_text)) for num_text in synthesis_num_list]
        return synthesis_boss_type_list


def loadout_group(boss_type: BossType | None) -> str:
    if boss_type is None:
        return 'low_star'
    return 'low_star' if int(boss_type) <= 4 else 'high_star'


class MetaDemonGeneralConfig(ConfigBase):
    high_star_quick_loadout_enable: bool = Field(default=False, title="高星鬼王启用快速上阵", description="仅五星、六星鬼王战斗生效；使用对应御魂配置中的分组名、预设名快速上阵，跳过式神录切魂与战斗准备预设。")


class MetaDemonSwitchSoulConfig(ConfigBase):
    low_star_enable: bool = Field(default=False, title='按编号切换')
    low_star_group_team: str = Field(default='-1,-1', title='分组、队号', description='switch_group_team_help')
    low_star_by_name: bool = Field(default=False, title='按名称切换', description='enable_switch_by_name_help')
    low_star_group_team_name: str = Field(default='', title='分组名、预设名')
    high_star_enable: bool = Field(default=False, title='按编号切换')
    high_star_group_team: str = Field(default='-1,-1', title='分组、队号', description='switch_group_team_help')
    high_star_by_name: bool = Field(default=False, title='按名称切换', description='enable_switch_by_name_help')
    high_star_group_team_name: str = Field(default='', title='分组名、预设名')

    def switch_for(self, category: str):
        from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
        names = getattr(self, f'{category}_group_team_name').split(',')
        by_name = getattr(self, f'{category}_by_name')
        group_name, team_name = (part.strip() for part in names) if len(names) == 2 else ('', '')
        return SwitchSoulConfig(
            enable=getattr(self, f'{category}_enable') and not by_name,
            switch_group_team=getattr(self, f'{category}_group_team'),
            enable_switch_by_name=by_name, group_name=group_name, team_name=team_name,
        )


class MetaDemonQuickPresetConfig(ConfigBase):
    high_star_custom_preset_enable: bool = Field(default=False, title='指定高星切换预设',
        description='新首领使用对应预设；与上次成功上阵相同时复用当前阵容。')
    high_star_custom_preset: str = Field(default='预设组1:ALL', title='自定义配置上阵预设',
        description='示例：预设组1:月读,雪御前;预设组2:ALL。首领名以半角逗号分隔，规则以半角分号分隔；ALL 表示其他未指定的怪物。')
    preset_groups: str = Field(default='预设组1,默认分组,队伍1', title='预设组列表',
        description='格式：预设组名,御魂分组名,队伍名；例如：预设组1,队伍租借,第4日单体通用阵容。不同预设组以半角分号分隔。')
    skip_equip_soul: bool = Field(default=False, title='不装配御魂',
        description='启用高星快速上阵时，选中预设后直接点击出战。')

    def named_presets(self) -> dict[str, tuple[str, str]]:
        return parse_named_presets(self.preset_groups, self.high_star_custom_preset)

    @model_validator(mode='before')
    @classmethod
    def migrate_legacy_presets(cls, value):
        if not isinstance(value, dict):
            return value
        rule = value.get('high_star_custom_preset', '')
        if '(' not in rule:
            return value
        import ast
        import re
        groups, rules, targets = [], [], {}
        for row in re.split(r'[;；]+', rule):
            if not row.strip():
                continue
            parts = re.split(r'[:：]', row, maxsplit=1)
            if len(parts) != 2:
                return value
            try:
                target = ast.literal_eval(parts[1].strip())
            except (ValueError, SyntaxError):
                return value
            if not isinstance(target, (tuple, list)) or len(target) != 2:
                return value
            if tuple(target) == (1, 1):
                target = ('默认分组', '队伍1')
            if not all(isinstance(part, str) and part.strip() for part in target):
                return value
            target = tuple(part.strip() for part in target)
            if target not in targets:
                name = f'预设组{len(targets) + 1}'
                targets[target] = name
                groups.append(','.join((name, *target)))
            rules.append(f'{targets[target]}:{parts[0].strip()}')
        return {**value, 'preset_groups': ';'.join(groups), 'high_star_custom_preset': ';'.join(rules)}


class AssistanceRole(str, Enum):
    ASSIST = '协助'
    OFFERING = '上供'


class MetaDemonAssistanceConfig(ConfigBase):
    cooperation_script: str = Field(default='', title='唤醒实例配置名',
        description='留空则不启用协同，只运行本实例。\n'
                    '两端身份须分别为上供（召唤六星鬼王并分享）和协助（在好友分享列表中找到同一只鬼王并挑战）')
    role: AssistanceRole = Field(default=AssistanceRole.OFFERING, title='鬼王协助身份',
        description='上供召唤六星鬼王并分享；协助从超鬼王主页寻找好友分享的鬼王并挑战。')
    friend_names: str = Field(default='', title='分享好友名字',
        description='填写游戏内好友完整名字；多个名字用分号或换行分隔，按名称精确匹配，不使用近似名字。')
    poll_interval: int = Field(default=5, ge=2, le=60, title='协助轮询间隔（秒）',
        description='上供按此间隔检查是否已击杀，协助按此间隔重新寻找好友分享。')

    @field_validator('cooperation_script')
    @classmethod
    def validate_cooperation_script(cls, value: str) -> str:
        return instance_name(value)

    @property
    def friends(self) -> list[str]:
        import re
        return list(dict.fromkeys(name.strip() for name in re.split(r'[;；\n\r]+', self.friend_names) if name.strip()))


class MetaDemonScheduler(Scheduler):
    wait_interval: TimeDelta = Field(default=TimeDelta(hours=1, minutes=40), description='疲劳度满时等多长时间后再次运行本任务,建议设置等待完全恢复疲劳度所需的时间\n例:100分钟恢复100点疲劳度,再次运行必定可以继续战斗')

    hide_fields = dynamic_hide('server_update', 'delay_date')


class MetaDemon(ConfigBase):
    scheduler: MetaDemonScheduler = Field(default_factory=MetaDemonScheduler)
    meta_demon_config: MetaDemonConfig = Field(default_factory=MetaDemonConfig)
    general_config: MetaDemonGeneralConfig = Field(default_factory=MetaDemonGeneralConfig)
    switch_soul_config: MetaDemonSwitchSoulConfig = Field(default_factory=MetaDemonSwitchSoulConfig)
    quick_preset_config: MetaDemonQuickPresetConfig = Field(default_factory=MetaDemonQuickPresetConfig)
    assistance_config: MetaDemonAssistanceConfig = Field(default_factory=MetaDemonAssistanceConfig)
    low_star_battle_conf: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    high_star_battle_conf: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)

    def battle_config(self, category: str) -> GeneralBattleConfig:
        config = getattr(self, f'{category}_battle_conf')
        if category == 'high_star' and self.general_config.high_star_quick_loadout_enable:
            return config.model_copy(update={'preset_enable': False})
        return config

    @model_validator(mode='before')
    @classmethod
    def migrate_flat_presets(cls, data):
        if not isinstance(data, dict):
            return data
        data = dict(data)
        old = data.pop('preset_config', None)
        if isinstance(old, dict):
            for category in ('low_star', 'high_star'):
                data.setdefault(f'{category}_battle_conf', {
                    'preset_enable': old.get(f'{category}_enable', False) if category != 'high_star' else False,
                    'preset_group': old.get(f'{category}_group', 1),
                    'preset_team': old.get(f'{category}_team', 1),
                })
            # Preserve the previously entered OCR target without enabling quick loadout implicitly.
            souls = dict(data.get('switch_soul_config', {}))
            if old.get('high_star_group_name') and old.get('high_star_preset_name'):
                souls.setdefault('high_star_group_team_name', f"{old['high_star_group_name']},{old['high_star_preset_name']}")
            data['switch_soul_config'] = souls
        return data

    @model_validator(mode='before')
    @classmethod
    def migrate_legacy_loadouts(cls, data):
        if not isinstance(data, dict):
            return data
        data = dict(data)
        old = data.pop('switch_soul', None)
        if not isinstance(old, dict) or 'switch_soul_config' in data:
            return data
        souls, presets = {}, {}
        for category, stars in (('low_star', ('one_star','two_stars','three_stars','four_stars')),
                                ('high_star', ('five_stars','six_stars'))):
            star = next((key for key in stars if str(old.get(key, '')).strip()), stars[0])
            text = str(old.get(star, '')).strip()
            if text == '-1,-1':
                text = ''
            parts = [part.strip() for part in text.split(',')]
            numbered = len(parts) == 2 and all(part.isdigit() for part in parts)
            souls[f'{category}_enable'] = bool(old.get('enable') and text and numbered)
            souls[f'{category}_by_name'] = bool(old.get('enable') and text and not numbered)
            souls[f'{category}_group_team' if numbered else f'{category}_group_team_name'] = text
            if category == 'low_star' and numbered:
                presets.update(low_star_enable=bool(old.get(f'enable_{star}_preset')),
                               low_star_group=int(parts[0]), low_star_team=int(parts[1]))
        data['switch_soul_config'] = souls
        data.setdefault('preset_config', presets)
        return data
