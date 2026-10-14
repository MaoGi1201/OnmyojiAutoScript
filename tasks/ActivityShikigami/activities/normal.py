"""中转式爬塔活动。

适用形态：活动主页上只有三个入口（ap 与 pass 合并成一个），
点进去是同一张爬塔页，靠 `I_CLIMB_MODE_SWITCH` 在体力/门票之间切换。

与 `DirectClimbAct`（四入口各自直达）的差别只在入口分组方式，
两层执行逻辑（到达层、战斗层）完全共用。
"""
from module.logger import logger
from tasks.ActivityShikigami.base_act import BaseAct
import tasks.ActivityShikigami.page as pages
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import ExitMatcher


class NormalClimbAct(BaseAct):
    """三入口、ap 与 pass 共用入口的爬塔活动。

    连线不再自己手写，改由基类 `_wire_entries()` 按 `ENTRY_GROUPS` 铺；
    进错模式的自救 hook 与组内互切边也是基类统一处理的。
    """

    # 三入口形态：ap 与 pass 一组，共用主页入口，经中转页进入，靠切换按钮纠正。
    # 若某期活动没有中转页（`pages.special_act_Flag = False`），
    # 把按钮列表改成一项即可：`('I_TO_BATTLE_MAIN',)`
    ENTRY_GROUPS: tuple[tuple[tuple[str, ...], tuple[str, ...], str | None], ...] = (
        (('ap', 'pass'), ('I_TO_BATTLE_MAIN', 'I_MAP_GOTO_BATTLE'), 'I_CLIMB_MODE_SWITCH'),
    )

    def _exit_matcher(self) -> ExitMatcher | None:
        return pages.any_of(self.I_ACT_FIRE, self.I_AS_BOSS_FIRE)

    def before_run(self):
        super().before_run()
        page_act = self.navigator.resolve_page(pages.page_act)
        if page_act is None:
            logger.warning("Normal climb: page_act not found, keep static page graph")
            return
        self._wire_entries(page_act)

    def lock_team(self, battle_conf: GeneralBattleConfig):
        """按类型取锁图并执行上锁/解锁。

        中转形态下 ap 与 pass 是同一张页面，锁按钮位置相同，
        因此只有 boss 单独用通用的 `I_LOCK` / `I_UNLOCK`，其余都用 `I_AP_LOCK`。
        （`DirectClimbAct` 则给四个类型各配了一对专属图，策略不同。）

        配了到达层的类型，锁按钮只在战斗页上，这里先推迟，等切过去之后再补做。
        """

        if self._lock_team_should_defer():
            return
        enable = battle_conf.lock_team_enable
        match self.climb_type:
            case "boss":
                lock_rule = self.I_LOCK
                unlock_rule = self.I_UNLOCK
            case _:
                lock_rule = self.I_AP_LOCK
                unlock_rule = self.I_AP_UNLOCK
        if enable:
            logger.info(f"Lock {self.climb_type} team")
            self.ui_click(unlock_rule, stop=lock_rule, interval=1.5)
            return
        logger.info(f"Unlock {self.climb_type} team")
        self.ui_click(lock_rule, stop=unlock_rule, interval=1.5)
