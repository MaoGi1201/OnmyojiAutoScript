from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.default_pages import (page_exploration, page_six_gates, random_click, page_battle, page_battle_prepare,
                                        page_battle_result, page_reward)
from tasks.GameUi.page_definition import Page
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.SixRealms.assets import SixRealmsAssets

# 准备界面退出弹窗
page_sr_prepare_exit = Page(SixRealmsAssets.I_MS_CHECK_EXIT_PREPARE, priority=88)
# 商店打开弹窗
page_sr_open_store = Page(SixRealmsAssets.I_MS_CHECK_OPEN_STORE, priority=88)


# ----------------弹窗兜底 hook----------------
def handle_six_realms_popup_hook(task) -> bool:
    """六道里到处都会弹的弹窗(过场「跳过」/ 带「非表示」勾选框的确认框)。

    挂到各页的 enter/leave failure hook 上兜底: 弹窗出现在 goto_page 内部时,
    run 循环里的统一入口够不着。page_six_gates 等是全局页, 别的任务也可能触发, 所以做兜底。
    """
    handler = getattr(task, 'handle_six_realms_popup', None)
    return bool(handler()) if handler else False


# 探索 -> 六道之门(进入失败) / 六道之门 -> 副本(离开失败) 都会卡在同一批弹窗上
page_six_gates.add_enter_failure_hooks(handle_six_realms_popup_hook)
page_six_gates.add_leave_failure_hooks(handle_six_realms_popup_hook)


# ----------------月之海----------------
def handle_enter_moon_sea(task) -> bool:
    """六道之门页面切换到月之海"""
    task.ui_click(SixRealmsAssets.I_SR_SWITCH, SixRealmsAssets.I_SR_TO_MOON_SEA, interval=1.5)
    return task.appear_then_click(SixRealmsAssets.I_SR_TO_MOON_SEA)

def switch_moon_sea_shikigami(task) -> bool:
    """切换月之海式神"""
    if task.appear(SixRealmsAssets.I_MSHOUZU):
        return True
    task.ui_click(SixRealmsAssets.C_SR_SWITCH_SHIKIGAMI, SixRealmsAssets.I_MSHOUZU_SELECT, interval=1.5)
    return task.appear_then_click(SixRealmsAssets.I_MSHOUZU_SELECT)

page_moon_sea = Page(SixRealmsAssets.I_SR_MOON_SEA_INFO)
page_moon_sea.connect(page_six_gates, GlobalGameAssets.I_UI_BACK_BLUE, key="page_moon_sea->page_six_gates")
page_six_gates.connect(page_moon_sea, GameUiAssets.I_CHECK_MOON_SEA, key="page_six_gates->page_moon_sea")
page_moon_sea.add_enter_failure_hooks(handle_enter_moon_sea)
page_moon_sea.add_enter_success_hooks(switch_moon_sea_shikigami)



# ----------------孔雀国----------------
def handle_enter_peacock_kingdom(task) -> bool:
    """六道之门页面切换到孔雀国"""
    task.ui_click(SixRealmsAssets.I_SR_SWITCH, SixRealmsAssets.I_SR_TO_PEACOCK_KINGDOM, interval=1.5)
    return task.appear_then_click(SixRealmsAssets.I_SR_TO_PEACOCK_KINGDOM)

page_peacock_kingdom = Page(SixRealmsAssets.I_SR_PEACOCK_KINGDOM_INFO)
page_peacock_kingdom.connect(page_six_gates, GlobalGameAssets.I_UI_BACK_BLUE, key="page_peacock_kingdom->page_six_gates")
page_six_gates.connect(page_peacock_kingdom, GameUiAssets.I_CHECK_PEACOCK_KINGDOM, key="page_six_gates->page_peacock_kingdom")
page_peacock_kingdom.add_enter_failure_hooks(handle_enter_peacock_kingdom)



# ----------------香行域----------------
def handle_enter_incense_realm(task) -> bool:
    """六道之门页面切换到香行域"""
    task.ui_click(SixRealmsAssets.I_SR_SWITCH, SixRealmsAssets.I_SR_TO_INCENSE_REALM, interval=1.5)
    return task.appear_then_click(SixRealmsAssets.I_SR_TO_INCENSE_REALM)

page_incense_realm = Page(SixRealmsAssets.I_SR_INCENSE_REALM_INFO)
page_incense_realm.connect(page_six_gates, GlobalGameAssets.I_UI_BACK_BLUE, key="page_incense_realm->page_six_gates")
page_six_gates.connect(page_incense_realm, GameUiAssets.I_CHECK_INCENSE_REALM, key="page_six_gates->page_incense_realm")



# ----------------错季森----------------
def handle_enter_seasonrift_forest(task) -> bool:
    """六道之门页面切换到错季森"""
    task.ui_click(SixRealmsAssets.I_SR_SWITCH, SixRealmsAssets.I_SR_TO_SEASONRIFT_FOREST, interval=1.5)
    return task.appear_then_click(SixRealmsAssets.I_SR_TO_SEASONRIFT_FOREST)

page_seasonrift_forest = Page(SixRealmsAssets.I_SR_SEASONRIFT_FOREST_INFO)
page_seasonrift_forest.connect(page_six_gates, GlobalGameAssets.I_UI_BACK_BLUE, key="page_seasonrift_forest->page_six_gates")
page_six_gates.connect(page_seasonrift_forest, GameUiAssets.I_CHECK_SEASONRIFT_FOREST, key="page_six_gates->page_seasonrift_forest")
page_seasonrift_forest.add_enter_failure_hooks(handle_enter_seasonrift_forest)



# ----------------净佛刹----------------
def handle_enter_pure_buddha_realm(task) -> bool:
    """六道之门页面切换到净佛刹"""
    task.ui_click(SixRealmsAssets.I_SR_SWITCH, SixRealmsAssets.I_SR_TO_PURE_BUDDHA_REALM, interval=1.5)
    return task.appear_then_click(SixRealmsAssets.I_SR_TO_PURE_BUDDHA_REALM)

page_pure_buddha_realm = Page(SixRealmsAssets.I_SR_PURE_BUDDHA_REALM_INFO)
page_pure_buddha_realm.connect(page_six_gates, GlobalGameAssets.I_UI_BACK_BLUE, key="page_pure_buddha_realm->page_six_gates")
page_six_gates.connect(page_pure_buddha_realm, GameUiAssets.I_CHECK_PURE_BUDDHA_REALM, key="page_six_gates->page_pure_buddha_realm")
page_pure_buddha_realm.add_enter_failure_hooks(handle_enter_pure_buddha_realm)



# ----------------真言塔----------------
def handle_enter_mantra_tower(task) -> bool:
    """六道之门页面切换到真言塔"""
    task.ui_click(SixRealmsAssets.I_SR_SWITCH, SixRealmsAssets.I_SR_TO_MANTRA_TOWER, interval=1.5)
    return task.appear_then_click(SixRealmsAssets.I_SR_TO_MANTRA_TOWER)

page_mantra_tower = Page(SixRealmsAssets.I_SR_MANTRA_TOWER_INFO)
page_mantra_tower.connect(page_six_gates, GlobalGameAssets.I_UI_BACK_BLUE, key="page_mantra_tower->page_six_gates")
page_six_gates.connect(page_mantra_tower, GameUiAssets.I_CHECK_MANTRA_TOWER, key="page_six_gates->page_mantra_tower")
page_mantra_tower.add_enter_failure_hooks(handle_enter_mantra_tower)
