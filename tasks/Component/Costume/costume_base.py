# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from typing import Optional

from module.atom.image import RuleImage
from module.logger import logger

from tasks.Component.Costume.config import (
    MainType,
    CostumeConfig,
    ShikigamiType,
    BattleType,
    CourtyardAffairType,
)
from tasks.Component.Costume.assets import CostumeAssets
from tasks.Component.CostumeBattle.assets import CostumeBattleAssets
from tasks.Component.CostumeShikigami.assets import CostumeShikigamiAssets
from tasks.Component.CustomCourtyardAffair.assets import CustomCourtyardAffairAssets

# 庭院皮肤
# 主界面皮肤（使用字典推导式动态生成）
def _main_costume_assets(i: int) -> dict:
    """第 i 套庭院皮肤的「基准名 → 资产名」映射。

    值可以是 str（单模板），也可以是 list（**多状态候选**：动态庭院里同一个按钮在不同
    时段/场景下配色不同，一张模板覆盖不了，运行时会按当前画面挑一张能命中的）。
    """
    return {
        'I_CHECK_MAIN': f'I_CHECK_MAIN_{i}',
        'I_MAIN_GOTO_EXPLORATION': f'I_MAIN_GOTO_EXPLORATION_{i}',
        'I_MAIN_GOTO_SUMMON': f'I_MAIN_GOTO_SUMMON_{i}',
        'I_MAIN_GOTO_TOWN': f'I_MAIN_GOTO_TOWN_{i}',
        'I_PET_HOUSE': f'I_PET_HOUSE_{i}',
        'I_WQ_DONE': f'I_WQ_DONE_{i}',  # 该条及以下非强制更改, 若对应庭院内容识别不到可以添加
        'I_HARVEST_SIGN': f'I_HARVEST_SIGN_{i}',
        'I_HARVEST_JADE': f'I_HARVEST_JADE_{i}',
        'I_HARVEST_MAIL': f'I_HARVEST_MAIL_{i}',
        'I_HARVEST_SOUL': f'I_HARVEST_SOUL_{i}',
        'I_HARVEST_GUILD_REWARD': f'I_HARVEST_GUILD_REWARD_{i}',
    }


main_costume_model = {
    getattr(MainType, f'COSTUME_MAIN_{i}'): _main_costume_assets(i)
    for i in range(1, 18)
}
# 动态庭院（画面随时段变）：每个按钮都从三个时段各裁一份模板当候选。
# 顺序 = 优先级（night 那张最独特、不会误命中别的时段，放最前）。
# 回退到第一张时点击位置依然是对的。
main_costume_model[MainType.COSTUME_MAIN_18] = {
    **_main_costume_assets(18),
    **{key: [f'{key}_18_NIGHT', f'{key}_18_DUSK', f'{key}_18_DAY']
       for key in ('I_CHECK_MAIN', 'I_MAIN_GOTO_EXPLORATION', 'I_MAIN_GOTO_SUMMON',
                   'I_MAIN_GOTO_TOWN', 'I_PET_HOUSE')},
}

# 战斗主题（使用循环处理常规情况 + 特例处理）
battle_theme_model = {}
for i in range(1, 16):
    entry = {
        'I_LOCAL': f'I_LOCAL_{i}',
        'I_EXIT': f'I_EXIT_{i}',
        'I_FRIENDS': f'I_FRIENDS_{i}',
        'I_BATTLE_INFO': f'I_BATTLE_INFO_{i}',
    }
    if i in [8, 12, 13, 14, 15]:  # 特殊处理
        entry.update(
            {
                'I_WIN': f'I_WIN_{i}',
                'I_DE_WIN': f'I_DE_WIN_{i}',
                'I_FALSE': f'I_FALSE_{i}',
            }
        )
    battle_theme_model[getattr(BattleType, f'COSTUME_BATTLE_{i}')] = entry

# 幕间主题
shikigami_costume_model = {
    getattr(ShikigamiType, f'COSTUME_SHIKIGAMI_{i}'): {
        # GameUi 进出式神录
        'I_CHECK_RECORDS': f'I_CHECK_RECORDS_{i}',
        'I_RECORD_SOUL_BACK': f'I_RECORD_SOUL_BACK_{i}',
        # SwitchSoul 相关
        'I_SOUL_PRESET': f'I_SOUL_PRESET_{i}',
        'I_SOU_CHECK_IN': f'I_SOU_CHECK_IN_{i}',
        'I_SOU_TEAM_PRESENT': f'I_SOU_TEAM_PRESENT_{i}',
        'I_SOU_CLICK_PRESENT': f'I_SOU_CLICK_PRESENT_{i}',
        'I_SOU_SWITCH_SURE': f'I_SOU_SWITCH_SURE_{i}',
        # SwitchSoul 分组相关 (1-7组)
        **{f'I_SOU_CHECK_GROUP_{g}': f'I_SOU_CHECK_GROUP_{g}_{i}' for g in range(1, 8)},
        # SwitchSoul 队伍相关 (1-4队)
        **{f'I_SOU_SWITCH_{t}': f'I_SOU_SWITCH_{t}_{i}' for t in range(1, 5)},
        # SoulsTidy 相关
        'I_ST_SOULS': f'I_ST_SOULS_{i}',
        'I_ST_REPLACE': f'I_ST_REPLACE_{i}',
    }
    for i in range(1, 13)  # 目前支持 COSTUME_SHIKIGAMI_1 到 COSTUME_SHIKIGAMI_12
}

# 庭院事务皮肤
courtyard_affair_model = {
    getattr(CourtyardAffairType, f'CUSTOM_COURTYARD_AFFAIR_{i}'): {
        'I_CHECK_COURTYARD_AFFAIRS': f'I_CHECK_COURTYARD_AFFAIRS_{i}',
        'I_ONE_COMPLETE': f'I_ONE_COMPLETE_{i}',
        'I_ENTER_DAILY': f'I_ENTER_DAILY_{i}',
        'I_CHECK_IN_DAILY': f'I_CHECK_IN_DAILY_{i}',
    }
    for i in range(1, 2)
}


class CostumeBase:
    def check_costume(self, config: CostumeConfig = None):
        if config is None:
            config: CostumeConfig = self.config.model.global_game.costume_config
        self.check_costume_main(config.costume_main_type)
        self.check_costume_battle(config.costume_battle_type)
        self.check_costume_shikigami(config.costume_shikigami_type)
        self.check_custom_courtyard_affair(config.custom_courtyard_affair)

    def replace_img(
        self, asset_before: str, asset_after: RuleImage, rp_roi_back: bool = True
    ):
        if not hasattr(self, asset_before):
            return
        # setattr(self, asset_before, asset_after)
        asset_before_object: RuleImage = getattr(self, asset_before)
        asset_before_object.roi_front = asset_after.roi_front
        if rp_roi_back:
            asset_before_object.roi_back = asset_after.roi_back
        asset_before_object.threshold = asset_after.threshold
        asset_before_object.file = asset_after.file

    def _pick_multi_state_rule(self, names: list) -> Optional[RuleImage]:
        """多状态候选里挑一张当前画面能命中的（动态庭院每个时段配色不同）。

        顺序即优先级，命中第一张就返回；一张都命中不了（或还没有截图）就用第一张兜底。
        """
        rules = [r for r in (getattr(CostumeAssets(), n, None) for n in names) if r is not None]
        if not rules:
            return None
        image = self.device.image
        if image is not None:
            for rule in rules:
                if rule.match(image, frame_id=self.device.image_frame_id):
                    return rule
        return rules[0]

    def check_costume_main(self, main_type: MainType):
        if main_type == MainType.COSTUME_MAIN:
            return
        logger.info(f'Switch main costume to {main_type}')
        costume_assets = CostumeAssets()
        for key, value in main_costume_model[main_type].items():
            if isinstance(value, (list, tuple)):
                picked = self._pick_multi_state_rule(value)
                if picked is None:
                    continue
                logger.info(f'{key} uses {picked.name} (multi-state)')
                self.replace_img(key, picked)
                continue
            assert_value: RuleImage = getattr(costume_assets, value, None)
            if assert_value is None:
                continue
            self.replace_img(key, assert_value)

    def check_costume_battle(self, battle_type: BattleType):
        if battle_type == BattleType.COSTUME_BATTLE_DEFAULT:
            return
        logger.info(f'Switch battle theme {battle_type}')
        costume_battle_assets = CostumeBattleAssets()
        for key, value in battle_theme_model[battle_type].items():
            assert_value: RuleImage = getattr(costume_battle_assets, value)
            # 绿标的坐标点范围不变
            if key == 'I_LOCAL':
                self.replace_img(key, assert_value, rp_roi_back=False)
            else:
                self.replace_img(key, assert_value)

    def check_costume_shikigami(self, shikigami_type: ShikigamiType):
        if shikigami_type == ShikigamiType.COSTUME_SHIKIGAMI_DEFAULT:
            return
        logger.info(f'Switch shikigami theme {shikigami_type}')
        shikigami_assets = CostumeShikigamiAssets()
        model = shikigami_costume_model.get(shikigami_type, {})
        for key, value in model.items():
            if not hasattr(shikigami_assets, value):
                # 尚未采集完成的资产，跳过
                continue
            assert_value: RuleImage = getattr(shikigami_assets, value)
            # 一般不需要固定 back ROI，如确有需要可在此为特例设置 rp_roi_back=False
            self.replace_img(key, assert_value)

    def check_custom_courtyard_affair(self, courtyard_affair_type: CourtyardAffairType):
        if courtyard_affair_type == CourtyardAffairType.CUSTOM_COURTYARD_AFFAIR_DEFAULT:
            return
        logger.info(f'Switch courtyard affair {courtyard_affair_type}')
        courtyard_affair_assets = CustomCourtyardAffairAssets()
        for key, value in courtyard_affair_model[courtyard_affair_type].items():
            assert_value: RuleImage = getattr(courtyard_affair_assets, value)
            self.replace_img(key, assert_value)


if __name__ == '__main__':
    c = CostumeBase()
    c.check_costume_main(MainType.COSTUME_MAIN_2)
