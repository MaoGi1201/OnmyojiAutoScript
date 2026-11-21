from tasks.MartialTournament.assets import MartialTournamentAssets
from tasks.Component.RightActivity.assets import RightActivityAssets
from tasks.GameUi.action import conditional_action
from tasks.GameUi.default_pages import random_click
from tasks.GameUi.page import (Page, page_main, page_battle, page_battle_prepare, page_reward,
                               page_battle_result, any_of, not_, sequence)
from tasks.GlobalGame.assets import GlobalGameAssets

# 武道大会活动主界面
page_mt = Page(MartialTournamentAssets.I_MT_CHECK)
page_mt.add_enter_failure_hooks(RightActivityAssets.I_TOGGLE_BUTTON,
                                conditional_action(GlobalGameAssets.I_UI_REWARD, random_click),
                                GlobalGameAssets.I_UI_BACK_RED,MartialTournamentAssets.I_MT_REWARD)
page_mt.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_mt->page_main")
# 侧栏收起时入口匹配不到，动作循环内先翻侧栏，入口出现再点
page_main.connect(
    page_mt,
    sequence(
        conditional_action(
            not_(MartialTournamentAssets.I_MT_ENTER),
            RightActivityAssets.I_TOGGLE_BUTTON,
        ),
        MartialTournamentAssets.I_MT_ENTER,
        success_index=1,
    ),
    key="page_main->page_mt",
)

# 日清门票界面 (挑战boss为浮窗, 不单独建page)
page_mt_pass = Page(MartialTournamentAssets.I_MT_PASS_CHECK)
page_mt_pass.connect(page_mt, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_mt_pass->page_mt")
page_mt.connect(page_mt_pass, MartialTournamentAssets.I_MT_PASS, key="page_mt->page_mt_pass")

# 体力爬塔界面
page_mt_ap = Page(MartialTournamentAssets.I_MT_CHALLENGE_AP)
page_mt_ap.connect(page_mt, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_mt_ap->page_mt")
page_mt.connect(page_mt_ap, MartialTournamentAssets.I_MT_AP, key="page_mt->page_mt_ap")
