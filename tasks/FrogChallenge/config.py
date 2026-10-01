# This Python file uses the following encoding: utf-8
from pydantic import BaseModel, Field

from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig


class FrogChallengeConfig(BaseModel):
    limit_time: Time = Field(default=Time(minute=30), description='limit_time_help')
    limit_count: int = Field(default=2, description='limit_count_help', ge=1)


class ExchangeSoulConfig(BaseModel):
    enable: bool = Field(default=False, description='exchange_soul_enable_help')


class FrogChallenge(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    frog_challenge_config: FrogChallengeConfig = Field(default_factory=FrogChallengeConfig)
    switch_soul: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
    exchange_soul: ExchangeSoulConfig = Field(default_factory=ExchangeSoulConfig)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
