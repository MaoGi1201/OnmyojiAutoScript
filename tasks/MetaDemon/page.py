import time

from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.page import (
    Page,
    page_act_list,
    page_battle,
    page_battle_result,
    page_main,
    page_reward,
    page_shikigami_records,
    random_click,
)
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.MetaDemon.assets import MetaDemonAssets

page_act_list_meta_demon = Page(MetaDemonAssets.I_CHECK_ACT_LIST_METADEMON_ACT)
page_act_list.connect(page_act_list_meta_demon, MetaDemonAssets.L_GOTO_METADEMON_LIST, key="page_act_list->page_act_list_meta_demon")
page_act_list_meta_demon.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_list_meta_demon->page_main")

page_meta_demon = Page(MetaDemonAssets.I_MD_CHECK_MAIN_PAGE)
page_meta_demon.add_enter_success_hooks(MetaDemonAssets.I_MD_GET_YESTERDAY_REWARD, MetaDemonAssets.I_MD_CLOSE_POPUP)
page_meta_demon.connect(page_act_list_meta_demon, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_meta_demon->page_act_list_meta_demon")

# 进入超鬼王主页（I_MD_CHECK_MAIN_PAGE）的过场等待
META_DEMON_ENTER_SETTLE_TIMEOUT: float = 12.0
META_DEMON_ENTER_SETTLE_INTERVAL: float = 0.5


def enter_meta_demon_settle(action):
    """包装进入超鬼王主页的入口动作：点完后等过场结束、主页稳定识别再返回。"""

    def _action(task) -> bool:
        if not task._execute_action(action):
            return False
        deadline = time.time() + META_DEMON_ENTER_SETTLE_TIMEOUT
        while time.time() < deadline:
            # 过场动画中途不判成功，也不判失败，只继续等
            if task.confirm_page(page_meta_demon, skip_first_screenshot=False):
                return True
            time.sleep(META_DEMON_ENTER_SETTLE_INTERVAL)
        # 过场结束仍未认出来：交回导航器按原失败流程处理（降权 / 重新规划）
        return True

    # 日志里显示成 enter_meta_demon_settle(MD_MAIN_GOTO_METADEMON) 便于排查
    _action.__name__ = f"enter_meta_demon_settle({getattr(action, 'name', action)!s})"
    return _action


page_act_list_meta_demon.connect(page_meta_demon, enter_meta_demon_settle(GameUiAssets.I_ACT_LIST_GOTO_ACT),
                                 key="page_act_list_meta_demon->page_meta_demon")
# 庭院主页右侧活动栏的超鬼王入口直达超鬼王主页
page_main.connect(page_meta_demon, enter_meta_demon_settle(MetaDemonAssets.I_MAIN_GOTO_METADEMON),
                  key="page_main->page_meta_demon")

page_meta_demon_boss = Page(MetaDemonAssets.I_CHECK_BOSS_PAGE)
page_meta_demon_boss.add_enter_success_hooks(MetaDemonAssets.I_MD_CLOSE_POPUP)
page_meta_demon_boss.connect(page_meta_demon, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_meta_demon_boss->page_meta_demon")
page_meta_demon.connect(page_meta_demon_boss, MetaDemonAssets.I_MD_CHECK_MAIN_PAGE, key="page_meta_demon->page_meta_demon_boss")

page_reward.connect(page_meta_demon_boss, random_click(), key="page_reward->page_meta_demon_boss")
page_battle_result.connect(page_meta_demon_boss, random_click(), key="page_battle_result->page_meta_demon_boss")
