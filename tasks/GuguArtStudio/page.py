from tasks.Component.RightActivity.assets import RightActivityAssets
from tasks.GameUi.action import conditional_action, sequence
from tasks.GameUi.default_pages import page_main, page_shikigami_records
from tasks.GameUi.matcher import any_of, not_
from tasks.GameUi.page_definition import Page
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.GuguArtStudio.assets import GuguArtStudioAssets

# 呱呱画室主页面
page_gugu = Page(any_of(GuguArtStudioAssets.I_CHECK_GUGU_ACT, GuguArtStudioAssets.I_SUBMIT_PAINT,
                        GuguArtStudioAssets.I_OBTAIN_PAINT))
page_gugu.add_enter_failure_hooks(RightActivityAssets.I_TOGGLE_BUTTON)
page_gugu.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_gugu->page_main")
# 侧栏收起时入口匹配不到，动作循环内先翻侧栏，入口出现再点
page_main.connect(
    page_gugu,
    sequence(
        conditional_action(
            not_(GuguArtStudioAssets.I_GAS_MAIN_TO_GUGU),
            RightActivityAssets.I_TOGGLE_BUTTON,
        ),
        GuguArtStudioAssets.I_GAS_MAIN_TO_GUGU,
        success_index=1,
    ),
    key="page_main->page_gugu",
)

# 呱呱画室挑战页面
page_gugu_fire = Page(any_of(GuguArtStudioAssets.I_GAS_CAN_FIRE, GuguArtStudioAssets.I_GAS_CANNOT_FIRE))
page_gugu_fire.connect(page_gugu, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_gugu_fire->page_gugu")
page_gugu.connect(page_gugu_fire, GuguArtStudioAssets.I_OBTAIN_PAINT, key="page_gugu->page_gugu_fire")
