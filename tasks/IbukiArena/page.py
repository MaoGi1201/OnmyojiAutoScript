from tasks.Component.RightActivity.assets import RightActivityAssets
from tasks.GameUi.action import conditional_action
from tasks.GameUi.page import Page, any_of, not_, page_main, page_shikigami_records, sequence
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.IbukiArena.assets import IbukiArenaAssets

# 伊吹之擂主界面
page_ibuki = Page(any_of(IbukiArenaAssets.I_CHECK_ACT, IbukiArenaAssets.I_GOTO_ARENA))
page_ibuki.add_enter_failure_hooks(RightActivityAssets.I_TOGGLE_BUTTON)
page_ibuki.connect(
    page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_ibuki->page_main"
)
# 侧栏收起时入口匹配不到，动作循环内先翻侧栏，入口出现再点
page_main.connect(
    page_ibuki,
    sequence(
        conditional_action(
            not_(IbukiArenaAssets.I_MAIN_TO_IBUKI),
            RightActivityAssets.I_TOGGLE_BUTTON,
        ),
        IbukiArenaAssets.I_MAIN_TO_IBUKI,
        success_index=1,
    ),
    key="page_main->page_ibuki",
)

# 狭间幻境挑战界面
page_ibuki_arena = Page(
    any_of(IbukiArenaAssets.I_CHECK_ARENA, IbukiArenaAssets.I_CHALLENGE)
)
page_ibuki_arena.connect(
    page_ibuki, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_ibuki_arena->page_ibuki"
)
page_ibuki.connect(
    page_ibuki_arena, IbukiArenaAssets.I_GOTO_ARENA, key="page_ibuki->page_ibuki_arena"
)
