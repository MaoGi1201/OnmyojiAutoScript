from tasks.GameUi.action import sequence
from tasks.GameUi.default_pages import random_click, page_battle, page_battle_prepare, page_battle_result, page_reward
from tasks.GameUi.matcher import any_of
from tasks.GameUi.page_definition import Page
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.SixRealms.assets import SixRealmsAssets
from tasks.SixRealms.page import (handle_six_realms_popup_hook, page_pure_buddha_realm, page_sr_prepare_exit,
                                  page_sr_open_store)

# 净佛刹准备界面(阵容 -> 法器秘宝 -> 开局技能)
page_pb_prepare = Page(any_of(SixRealmsAssets.I_PB_START_CONFIRM, SixRealmsAssets.I_PB_START_CONFIRM2,
                              SixRealmsAssets.I_PB_START_THIRD_SKILL, SixRealmsAssets.I_PB_SELECT_3))
# 净佛刹主界面
page_pb_main = Page(any_of(SixRealmsAssets.I_PB_CHECK_MAIN, SixRealmsAssets.I_PB_BOSS_PREPARE),
                          category="pure_buddha_realm", priority=25)
page_pb_prepare.connect(page_pb_main, sequence(SixRealmsAssets.I_PB_START_CONFIRM,
                                               SixRealmsAssets.I_PB_START_CONFIRM2, SixRealmsAssets.I_PB_START_THIRD_SKILL,
                                               SixRealmsAssets.I_PB_SELECT_3, success_index=3),
                        key="page_pb_prepare->page_pb_main")

# 挑战页面
page_pb_challenge = Page(SixRealmsAssets.I_PB_BATTLE_FIRE, category="pure_buddha_realm", priority=25)

# 安息之岛
page_pb_shop_land = Page(SixRealmsAssets.I_PB_STORE_EXIT, category="pure_buddha_realm")
page_pb_shop_land.connect(page_pb_main, SixRealmsAssets.I_PB_STORE_EXIT, key="page_pb_shop_land->page_pb_main")

# 神秘之屿(用左上角岛名认页: 面板有模造/转换两种文案, 只有岛名是固定的)
page_pb_mistery_land = Page(SixRealmsAssets.I_PB_MYSTERY_TITLE, category="pure_buddha_realm")
page_pb_mistery_land.connect(page_pb_main, SixRealmsAssets.I_PB_MYSTERY_BACK,
                             key="page_pb_mistery_land->page_pb_main")

# 混沌之屿
page_pb_chaos_land = Page(any_of(SixRealmsAssets.I_PB_CHAOS_BOX, SixRealmsAssets.I_PB_CHAOS_ELITE_FLAG),
                          category="pure_buddha_realm")
page_pb_chaos_land.connect(page_pb_main, SixRealmsAssets.I_PB_CHAOS_EXIT, key="page_pb_chaos_land->page_pb_main")
page_pb_chaos_land.connect(page_pb_challenge, SixRealmsAssets.C_NPC_FIRE_CENTER, key="page_pb_chaos_land->page_pb_challenge")
page_pb_challenge.connect(page_pb_chaos_land, GlobalGameAssets.I_UI_BACK_BLUE, key="page_pb_challenge->page_pb_chaos_land")

# 绽放之屿
page_pb_bloom_land = Page(SixRealmsAssets.I_PB_BLOOM_EXIT, category="pure_buddha_realm")
page_pb_bloom_land.connect(page_pb_main, SixRealmsAssets.I_PB_BLOOM_EXIT, key="page_pb_bloom_land->page_pb_main")

# 激战之屿
page_pb_battle_land = Page(SixRealmsAssets.I_PB_BATTLE_COMMON, category="pure_buddha_realm")
page_pb_battle_land.connect(page_pb_challenge, SixRealmsAssets.C_NPC_FIRE_RIGHT, key="page_pb_battle_land->page_pb_challenge")
page_pb_challenge.connect(page_pb_battle_land, GlobalGameAssets.I_UI_BACK_BLUE, key="page_pb_challenge->page_pb_battle_land")

# 净佛刹地图
page_pb_map = Page(SixRealmsAssets.I_PB_CHECK_MAP, category="pure_buddha_realm")
page_pb_map.connect(page_pb_main, GlobalGameAssets.I_UI_BACK_BLUE, key="page_pb_map->page_pb_main")

# 主界面退出弹窗
page_pb_exit = Page(SixRealmsAssets.I_PB_EXIT_MAIN, category="pure_buddha_realm", priority=88)
page_pb_exit.connect(page_pure_buddha_realm, SixRealmsAssets.I_PB_EXIT_MAIN, key="page_pb_exit->page_moon_sea")
page_pb_exit.connect(page_pb_shop_land, random_click(ltrb=(True, True, True, True)), key="page_pb_exit->page_pb_shop_land")
page_pb_exit.connect(page_pb_main, random_click(ltrb=(True, True, True, True)), key="page_pb_exit->page_pb_main")
page_pb_exit.connect(page_pb_chaos_land, random_click(ltrb=(True, True, True, True)), key="page_pb_exit->page_pb_chaos_land")
page_pb_main.connect(page_pb_exit, GlobalGameAssets.I_UI_BACK_BLUE, key="page_pb_main->page_pb_exit")
page_pb_battle_land.connect(page_pb_exit, GlobalGameAssets.I_UI_BACK_BLUE, key="page_pb_battle_land->page_pb_exit")

# 准备界面退出
page_sr_prepare_exit.connect(page_pure_buddha_realm, GlobalGameAssets.I_UI_CONFIRM, key="page_sr_prepare_exit->page_moon_sea")
page_sr_prepare_exit.connect(page_pb_prepare, GlobalGameAssets.I_UI_CANCEL, key="page_sr_prepare_exit->page_pb_prepare")
page_pb_prepare.connect(page_sr_prepare_exit, GlobalGameAssets.I_UI_BACK_BLUE, key="page_pb_prepare->page_sr_prepare_exit")
page_sr_prepare_exit.add_enter_failure_hooks(GlobalGameAssets.I_UI_BACK_BLUE)

# 商店打开弹窗
page_sr_open_store.connect(page_pb_main, GlobalGameAssets.I_UI_CANCEL, key="page_sr_open_store->page_pb_main")
page_pb_main.connect(page_sr_open_store, SixRealmsAssets.I_M_STORE_ACTIVITY, key="page_pb_main->page_sr_open_store")

# 这些弹窗会挡住"离开本页"的跳转(弹窗出现在 goto_page 内部时 run 循环够不着), 逐页兜底
for _page in (page_pb_prepare, page_pb_main, page_pb_shop_land, page_pb_mistery_land, page_pb_chaos_land,
              page_pb_bloom_land, page_pb_battle_land, page_pb_map, page_pb_challenge, page_pb_exit):
    _page.add_enter_failure_hooks(handle_six_realms_popup_hook)
    _page.add_leave_failure_hooks(handle_six_realms_popup_hook)
