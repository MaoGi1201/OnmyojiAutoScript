# This Python file uses the following encoding: utf-8
from pydantic import BaseModel, Field


class QuickLoadoutConfig(BaseModel):
    """按分组名称和预设名称识别的一键配置。"""

    enable: bool = Field(default=False, description='quick_loadout_enable_help')
    group_name: str = Field(default='', description='quick_loadout_group_name_help')
    preset_name: str = Field(default='', description='quick_loadout_preset_name_help')

    def validate_target(self) -> None:
        if not self.group_name.strip():
            raise ValueError('Quick loadout group name cannot be empty in OCR mode')
        if not self.preset_name.strip():
            raise ValueError('Quick loadout preset name cannot be empty in OCR mode')


class NamedQuickLoadoutConfig(QuickLoadoutConfig):
    """支持按任务关卡名称选择不同预设的一键配置。"""

    custom_preset_enable: bool = Field(
        default=False,
        description='quick_loadout_custom_preset_enable_help',
    )
    custom_preset: str = Field(
        default='',
        description='quick_loadout_custom_preset_help',
    )


def parse_named_presets(preset_groups: str, custom_preset: str) -> dict[str, tuple[str, str]]:
    """解析「预设组名,御魂分组名,队伍名」与「预设组名:怪物名」两段配置。"""
    groups = {}
    for row in preset_groups.split(';'):
        if not row.strip():
            continue
        parts = [part.strip() for part in row.split(',')]
        if len(parts) != 3 or not all(parts):
            raise ValueError(f'预设组需填写：预设组名,御魂分组名,队伍名：{row}')
        name, group, team = parts
        if name in groups:
            raise ValueError(f'预设组名重复：{name}')
        groups[name] = (group, team)
    presets = {}
    for row in custom_preset.split(';'):
        if not row.strip():
            continue
        name, separator, targets = row.partition(':')
        name = name.strip()
        if not separator or name not in groups:
            raise ValueError(f'规则引用了不存在的预设组或缺少半角冒号：{row}')
        for boss in targets.split(','):
            boss = boss.strip()
            if not boss:
                raise ValueError(f'首领名不能为空：{row}')
            boss = 'ALL' if boss.upper() == 'ALL' else boss
            if boss in presets:
                raise ValueError(f'首领规则重复：{boss}')
            presets[boss] = groups[name]
    if not presets:
        raise ValueError('请填写至少一条上阵预设规则')
    return presets
