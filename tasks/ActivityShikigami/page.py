"""活动爬塔的静态页面图。
只定义所有形态共享的骨架；连线与识别器的形态差异由各 Act 在 before_run 里改动。"""
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
page_act = Page(ActivityShikigamiAssets.I_TO_BATTLE_PASS)
page_act.add_enter_failure_hooks(
    RightActivityAssets.I_TOGGLE_BUTTON,
    conditional_action(GlobalGameAssets.I_UI_REWARD, random_click),
)
page_act.connect(
    page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act->page_main"
)
page_main.connect(
    page_act, ActivityShikigamiAssets.I_MAIN_GOTO_ACT, key="page_main->page_act"
)
# 是否存在特殊活动界面标志(点击一次无法进入体力爬塔界面，存在中转界面的情况，False表示没有中转界面，True表示有中转界面)
# 本期体力入口一步直达，无中转页；原值 True，需要中转时改回。
special_act_Flag = False

# 门票地图页：活动页点 as_to_battle_pass 抵达，再点 as_pass_map_goto_battle 进战斗页。
page_act_pass_map = Page(ActivityShikigamiAssets.I_CHECK_PASS_MAP)
if special_act_Flag:
    # 特殊活动中转地图页面（与门票地图页同一块界面，只做别名）
    # page_act_map = Page(ActivityShikigamiAssets.I_CHECK_PASS_MAP)
    page_act_map = page_act_pass_map
    page_act_map.connect(
        page_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_map->page_act"
    )
    page_act.connect(
        page_act_map,
        ActivityShikigamiAssets.I_TO_BATTLE_PASS,
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

# 门票爬塔页面（战斗页）
page_act_pass = Page(ActivityShikigamiAssets.I_CLIMB_MODE_PASS)
# 门票地图页：活动页点 as_to_battle_pass 抵达，再点 as_pass_map_goto_battle 进战斗页。
# page_act_pass_map = Page(ActivityShikigamiAssets.I_CHECK_PASS_MAP)
page_act_pass.connect(
    page_act_pass_map,
    GlobalGameAssets.I_UI_BACK_YELLOW,
    key="page_act_pass->page_act_pass_map",
)
# 存在特殊活动界面
# page_act_map 就是 page_act_pass_map，回程边已由上面那条覆盖
if not special_act_Flag:
    page_act_pass.connect(
        page_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_pass->page_act"
    )

# 100体爬塔页面
page_act_ap100 = Page(ActivityShikigamiAssets.I_CHECK_AP100)
# BOSS爬塔页面
page_act_boss = Page(ActivityShikigamiAssets.I_CHECK_BATTLE_BOSS)
page_act_boss.connect(
    page_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_boss->page_act"
)
# 本期只有体力入口，boss 入口先注释掉；恢复时取消注释即可。
# page_act.connect(
#     page_act_boss,
#     ActivityShikigamiAssets.I_TO_BATTLE_BOSS,
#     key="page_act->page_act_boss",
# )
