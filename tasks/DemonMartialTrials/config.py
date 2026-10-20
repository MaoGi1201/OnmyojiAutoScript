# This Python file uses the following encoding: utf-8
from enum import Enum

from pydantic import BaseModel, Field

from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.GeneralInvite.config_invite import InviteConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig


class DMTMode(str, Enum):
    SOLO = '单刷'
    LEADER = '队长'
    MEMBER = '队员'


class DMTConfig(BaseModel):
    # 限制时间
    limit_time: Time = Field(default=Time(minute=30), description='limit_time_help')
    # 限制次数（想打的次数，与活动剩余次数无关）
    limit_count: int = Field(default=15, description='limit_count_help')
    # 是否执行演武委派（上阵方式沿用「式神委派」配置里的一键上阵开关）
    delegate_enable: bool = Field(default=False, description='delegate_enable_help')
    # 运行模式（单刷/队长/队员，参照 LBS）
    mode: DMTMode = Field(default=DMTMode.SOLO, description='dmt_mode_help')


class DemonMartialTrials(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    dmt_config: DMTConfig = Field(default_factory=DMTConfig)
    # 队长模式的邀请对象（填了就点队伍界面的 + 号邀请，不填则直接开打）
    invite_config: InviteConfig = Field(default_factory=InviteConfig)
    switch_soul: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
