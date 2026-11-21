"""逢魔演武（限时活动）页面定义。

层级：庭院 --右栏入口--> 逢魔演武界面 --演武挑战--> 演武挑战界面。
两个活动页左上角均为黄色返回。
"""

from tasks.Component.RightActivity.assets import RightActivityAssets
from tasks.DemonMartialTrials.assets import DemonMartialTrialsAssets
from tasks.GameUi.action import conditional_action
from tasks.GameUi.default_pages import random_click
from tasks.GameUi.page import Page, not_, page_main, sequence
from tasks.GlobalGame.assets import GlobalGameAssets

# 逢魔演武主界面
page_demon_martial = Page(DemonMartialTrialsAssets.I_DEMON_CHECK, priority=70)
page_demon_martial.add_enter_failure_hooks(
    RightActivityAssets.I_TOGGLE_BUTTON,
    conditional_action(GlobalGameAssets.I_UI_REWARD, random_click),
)
# 演武挑战界面（点演武挑战进入，挑战按钮在此页）
page_demon_martial_challenge = Page(DemonMartialTrialsAssets.I_DEMON_CHALLENGE_CHECK, priority=68)

# 侧栏收起时入口匹配不到，动作循环内先翻侧栏，入口出现再点
page_main.connect(
    page_demon_martial,
    sequence(
        conditional_action(
            not_(DemonMartialTrialsAssets.I_DEMON_ENTRY),
            RightActivityAssets.I_TOGGLE_BUTTON,
        ),
        DemonMartialTrialsAssets.I_DEMON_ENTRY,
        success_index=1,
    ),
    key='main->dmt',
)
page_demon_martial.connect(
    page_demon_martial_challenge, DemonMartialTrialsAssets.I_DEMON_YANWU_CHALLENGE, key='dmt->dmt_challenge')
page_demon_martial.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key='dmt->main')
page_demon_martial_challenge.connect(
    page_demon_martial, GlobalGameAssets.I_UI_BACK_YELLOW, key='dmt_challenge->dmt')
