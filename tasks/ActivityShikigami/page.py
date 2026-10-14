"""活动爬塔的静态页面图。

这里只定义**所有形态共享**的页面骨架：主页、中转页、四个爬塔页，以及主页与庭院
之间的固定往返边。
"""
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.Component.GeneralBattle.assets import GeneralBattleAssets
from tasks.Component.RightActivity.assets import RightActivityAssets
from tasks.GameUi.action import conditional_action
from tasks.GameUi.default_pages import random_click
from tasks.GameUi.page import (
    Page,
    page_main,
    sequence,
    page_battle,
    page_battle_prepare,
    page_reward,
    page_battle_result,
    any_of,
)
from tasks.GlobalGame.assets import GlobalGameAssets

# 爬塔活动主界面
page_act = Page(ActivityShikigamiAssets.I_TO_BATTLE_MAIN)
page_act.add_enter_failure_hooks(
    RightActivityAssets.I_TOGGLE_BUTTON,
    conditional_action(GlobalGameAssets.I_UI_REWARD, random_click),
    GlobalGameAssets.I_UI_BACK_RED,
    # 点「跳过」后还会弹一个确认框，必须再点「确定跳过」才真的跳过去；
    # 只点第一个会一直被弹窗挡着，页面识别不出来。
    sequence(
        ActivityShikigamiAssets.I_SKIP_BUTTON,
        ActivityShikigamiAssets.I_CONFIRM_SKIP,
    ),
)
page_act.connect(
    page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act->page_main"
)
page_main.connect(
    page_act, ActivityShikigamiAssets.I_MAIN_GOTO_ACT, key="page_main->page_act"
)
# 是否存在特殊活动界面标志(点击一次无法进入体力爬塔界面，存在中转界面的情况，False表示没有中转界面，True表示有中转界面)
special_act_Flag = True
if special_act_Flag:
    # 特殊活动中转地图页面
    page_act_map = Page(ActivityShikigamiAssets.I_MAP_GOTO_BATTLE)
    page_act_map.connect(
        page_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_map->page_act"
    )
    page_act.connect(
        page_act_map,
        ActivityShikigamiAssets.I_TO_BATTLE_MAIN,
        key="page_act->page_act_map",
    )

# 体力爬塔页面
page_act_ap = Page(ActivityShikigamiAssets.I_CLIMB_MODE_AP)
# 存在特殊活动界面
if special_act_Flag:
    page_act_ap.connect(
        page_act_map, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_ap->page_act_map"
    )
# 不存在特殊活动界面
else:
    page_act_ap.connect(
        page_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_ap->page_act"
    )

# 门票爬塔页面
page_act_pass = Page(ActivityShikigamiAssets.I_CLIMB_MODE_PASS)
# 存在特殊活动界面
if special_act_Flag:
    page_act_pass.connect(
        page_act_map,
        GlobalGameAssets.I_UI_BACK_YELLOW,
        key="page_act_pass->page_act_map",
    )
# 不存在特殊活动界面
else:
    page_act_pass.connect(
        page_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_pass->page_act"
    )

# 100体爬塔页面
page_act_ap100 = Page(ActivityShikigamiAssets.I_CLIMB_MODE_AP100)
page_act_ap100.add_enter_failure_hooks(GlobalGameAssets.I_UI_BACK_RED)
# BOSS爬塔页面
page_act_boss = Page(ActivityShikigamiAssets.I_CHECK_BATTLE_BOSS)
page_act_boss.connect(
    page_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_boss->page_act"
)
page_act.connect(
    page_act_boss,
    ActivityShikigamiAssets.I_TO_BATTLE_BOSS,
    key="page_act->page_act_boss",
)
