"""ActivityShikigami

    入口层   主页 → 目标爬塔页      由 `ENTRY_GROUPS` 描述（可能经中转页）
    到达层   目标页 → 真正的战斗页   由 `BATTLE_PAGE_ENTER` 描述（可能还要点一次）
    战斗层   查票 → 换魂 → 挑战 → 通用战斗  `_run_common()`，四个类型完全共用

每一层的差异都外置成类常量，因此换一期活动通常只需要改配置与图片
"""
import time

from datetime import datetime
import random
from tasks.Component.GeneralBattle.general_battle import (
    GeneralBattle,
    ExitMatcher,
    BattleContext,
    BattleAction,
)
from cached_property import cached_property

from module.atom.image import RuleImage
from module.base.protect import random_sleep
from module.exception import TaskEnd
from module.logger import logger

from tasks.base_task import BaseTask
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.ActivityShikigami.config import GeneralBattleConfig, ActivityShikigami
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
import tasks.ActivityShikigami.page as pages
from typing import Optional, Callable


class LimitTimeOut(Exception):
    pass


class LimitCountOut(Exception):
    pass


class TicketsNotEnough(Exception):
    pass


class StateMachine(BaseTask):
    """爬塔类型游标与计数状态。

    外层循环按 `run_sequence_v` 逐个切换爬塔类型，这里保存游标与每类型的计次。
    """

    # 当前爬塔类型在 `run_sequence_v` 中的下标
    run_idx: int = 0
    _count_map = None
    _pre_tickets_map = None
    # 每种爬塔类型本轮是否已换过御魂。
    switch_souled: dict[str, bool] = {}

    @cached_property
    def conf(self) -> ActivityShikigami:
        return self.config.model.activity_shikigami

    @property
    def climb_type(self) -> str:
        if self.run_idx >= len(self.conf.general_climb.run_sequence_v):
            return self.conf.general_climb.run_sequence_v[-1]
        return self.conf.general_climb.run_sequence_v[self.run_idx]

    @property
    def count_map(self) -> dict[str, int]:
        """
        :return: key: climb type, value: run count
        """
        if not getattr(self, "_count_map", None):
            self._count_map = {
                climb_type: 0 for climb_type in self.conf.general_climb.run_sequence_v
            }
        return self._count_map

    @property
    def pre_tickets_map(self) -> dict[str, int]:
        """
        :return: key: climb type, value: pre tickets num
        """
        if not getattr(self, "_pre_tickets_map", None):
            self._pre_tickets_map = {
                climb_type: -1 for climb_type in self.conf.general_climb.run_sequence_v
            }
        return self._pre_tickets_map

    def update_status(self):
        """
        更新全局状态
        """

        def get_count() -> int:
            return self.count_map[self.climb_type]

        def get_limit() -> int:
            limit = getattr(self.conf.general_climb, f"{self.climb_type}_limit", 0)
            return 0 if not limit else limit

        # 超过运行时间
        if datetime.now() - self.start_time >= self.conf.general_climb.limit_time_v:
            logger.info(f"Climb type {self.climb_type} time out")
            raise LimitTimeOut
        # 次数达到限制
        if get_count() >= get_limit():
            logger.info(f"Climb type {self.climb_type} count limit reached")
            raise LimitCountOut

    def switch_next(self):
        """推进到下一个爬塔类型。

        Returns:
            bool: True 还有下一个类型，False 表示全部跑完。
        """

        self.run_idx += 1
        if self.run_idx >= len(self.conf.general_climb.run_sequence_v):
            logger.info("All climbing activities have been completed")
            return False
        # 切换爬塔类型了, 恢复所有状态
        self.current_count = 0
        logger.hr(f"Climb switch to {self.climb_type}", 2)
        return True


class BaseAct(StateMachine, GameUi, GeneralBattle, SwitchSoul, ActivityShikigamiAssets):
    """爬塔活动基类。

    - 入口层：`ENTRY_GROUPS` / `MODE_ICONS` / `DETACH_MAP_ROUTES` / `BACK_BUTTONS`
    - 到达层：`BATTLE_PAGE_ENTER`（含等待与超时）
    - 战斗层：`check_tickets_enough()` 的读数规则、`xxx_battle_conf` 战斗配置
    """

    # ══════════════════════════ 入口层配置 ══════════════════════════
    # 决定「从主页怎么到达某个爬塔类型的页面」。

    # 入口层配置：主页到各爬塔页的连线规则。
    # 每项 = (该组包含的爬塔类型, 从主页出发依次点击的按钮, 组内模式切换按钮)
    #   - 组里 1 个类型  -> 该类型独占一个入口，点进去就是它
    #   - 组里多个类型   -> 共用一个入口，进哪个由游戏当前模式决定，靠切换按钮纠正
    #   - 按钮列表 1 项  -> 主页一点直达目标页
    #   - 按钮列表 2 项  -> 主页先到中转页 page_act_map，再由中转页进目标页
    # 四入口与三入口的差别只是分组方式不同，因此都用这张表表达，不需要两个类。
    ENTRY_GROUPS: tuple[tuple[tuple[str, ...], tuple[str, ...], str | None], ...] = ()

    # 仅组里多于一个类型时才用到：进错模式时靠它识别出来再点切换。
    MODE_ICONS: dict[str, str] = {
        'ap': 'I_CLIMB_MODE_AP',
        'pass': 'I_CLIMB_MODE_PASS',
        'ap100': 'I_CLIMB_MODE_AP100',
    }

    DETACH_MAP_ROUTES: bool = False

    # 爬塔页返回时依次尝试的按钮。
    # 不同页面的返回键样式不一样：有的是黄色箭头，有的是弯曲箭头，
    # 两者都在左上角，同一时刻只会出现一个，因此按顺序都试一遍即可。
    BACK_BUTTONS: tuple[str, ...] = ("I_UI_BACK_YELLOW", "I_UI_BACK_CIRCLE")

   
   
    # 某些活动的目标页只是地图页，还要再点一次才到真正的战斗页。
    # 格式 climb_type -> (跳转按钮 asset 名, 到达确认图 asset 名)。
    # 不在表里的类型视为「进目标页即战斗页」，什么都不做。
    BATTLE_PAGE_ENTER: dict[str, tuple[str, str]] = {}

    # 进入战斗页前的等待时长（秒），给页面切换留时间。
    BATTLE_PAGE_ENTER_WAIT: float = 1.0

    # 点跳转按钮后等待确认图出现的上限（秒）。
    BATTLE_PAGE_ENTER_TIMEOUT: float = 5.0

    # 是否已经到达战斗页；决定锁容是否需要推迟。
    _battle_page_ready: bool = False

    # 锁容是否被推迟到战斗页（到达层存在时，锁按钮只在战斗页上）。
    _lock_team_deferred: bool = False

    def _exit_matcher(self) -> ExitMatcher | None:
        return self.I_ACT_FIRE

    def _handle_result(
        self, context: BattleContext, config: GeneralBattleConfig
    ) -> BattleAction:
        if self.climb_type == "boss":
            self.appear_then_click(self.I_UI_BACK_RED, interval=1.5)
        return super()._handle_result(context, config)

    def before_run(self):
        pages.page_battle_result = self.navigator.resolve_page(pages.page_battle_result)
        pages.page_battle_result.recognizer = pages.any_of(
            self.I_UI_BACK_RED, pages.page_battle_result.recognizer
        )
        # 点「跳过」后还会弹一个确认框，必须再点「确定跳过」才真的跳过去。
        # closers（排在全局之前），一次点完。
        self.navigator.add_unknown_closer(
            pages.sequence(self.I_SKIP_BUTTON, self.I_CONFIRM_SKIP)
        )

    def _page_of(self, climb_type: str):
        """取该爬塔类型在本次 session 里的页面副本。"""

        return self.navigator.resolve_page(getattr(pages, f"page_act_{climb_type}", None))

    def _resolve_back_action(self):
        """回程动作：依次尝试 `BACK_BUTTONS`，任一按钮点中即算成功。

        """

        buttons = [getattr(self, name, None) for name in self.BACK_BUTTONS]
        buttons = [button for button in buttons if button is not None]
        if not buttons:
            logger.warning("Climb: no back button configured")
            return None
        if len(buttons) == 1:
            return buttons[0]
        return pages.sequence(*buttons, success_index=len(buttons))

    def _detach_map_routes(self, page_act) -> None:
        """断开中转地图相关的边。

        """

        if not self.DETACH_MAP_ROUTES:
            return
        page_act_map = self.navigator.resolve_page(getattr(pages, "page_act_map", None))
        if page_act_map is None:
            return
        logger.info("Climb: detach intermediate map page")
        page_act.remove_transition(destination=page_act_map)
        for name in ("page_act_ap", "page_act_pass", "page_act_ap100", "page_act_boss"):
            page = self.navigator.resolve_page(getattr(pages, name, None))
            if page is None:
                continue
            page.remove_transition(destination=page_act_map)

    def _wire_entries(self, page_act) -> None:
        """按 `ENTRY_GROUPS` 铺主页到各爬塔页的连线。

        一个组 = 一个入口按钮（或主页→中转页→目标页两跳）+ 可选的模式切换按钮。
        组里承载多个类型时，额外挂两样东西：
        进错模式的自救 hook（看到别的类型的模式图标就点切换），以及组内互切边。
        """

        if not self.ENTRY_GROUPS:
            logger.warning("Climb: ENTRY_GROUPS is empty, no entry route wired")
            return
        back_action = self._resolve_back_action()
        for climb_types, button_names, switch_name in self.ENTRY_GROUPS:
            if not climb_types or not button_names:
                continue
            switch = getattr(self, switch_name, None) if switch_name else None
            source = page_act
            # 逐跳铺线；最后一跳连到组内各目标页，中间跳都落在中转页上
            for index, button_name in enumerate(button_names):
                button = getattr(self, button_name, None)
                if button is None:
                    logger.warning(f"Climb: entry asset {button_name} missing, skip this hop")
                    break
                last_hop = index == len(button_names) - 1
                if not last_hop:
                    map_page = self.navigator.resolve_page(getattr(pages, "page_act_map", None))
                    if map_page is None:
                        logger.warning("Climb: page_act_map not registered, skip intermediate hop")
                        break
                    source.connect(map_page, button, key="page_act->page_act_map")
                    source = map_page
                    continue
                for climb_type in climb_types:
                    target = self._page_of(climb_type)
                    if target is None:
                        logger.warning(f"Climb: page_act_{climb_type} not registered")
                        continue
                    source.connect(
                        target, button, key=f"{source.name}->page_act_{climb_type}"
                    )
                    # 回程只在直连形态补；经中转页的回程由 page.py 静态定义，
                    # 再连一条到主页会让导航挑错路径（返回键其实落在中转页上）
                    if source is page_act and back_action is not None:
                        target.connect(
                            page_act,
                            back_action,
                            key=f"page_act_{climb_type}->page_act",
                        )
                    logger.info(
                        f"Climb wired: {source.name} -> page_act_{climb_type} via {button_name}"
                    )
            # 组内多个类型：进错模式时自救 + 互切
            if switch is None or len(climb_types) < 2:
                continue
            for climb_type in climb_types:
                target = self._page_of(climb_type)
                if target is None:
                    continue
                for other in climb_types:
                    if other == climb_type:
                        continue
                    icon_name = self.MODE_ICONS.get(other)
                    icon = getattr(self, icon_name, None) if icon_name else None
                    if icon is not None:
                        target.add_enter_failure_hooks(
                            pages.conditional_action(condition=icon, action=switch)
                        )
                    other_page = self._page_of(other)
                    if other_page is None:
                        continue
                    target.connect(
                        other_page, switch, key=f"page_act_{climb_type}->page_act_{other}"
                    )

    @property
    def act_page_handle_dict(self) -> dict[pages.Page, Callable]:
        """活动页面和处理器的映射"""
        return {
            pages.page_act_pass: self._run_pass,
            pages.page_act_ap: self._run_ap,
            pages.page_act_ap100: self._run_ap100,
            pages.page_act_boss: self._run_boss,
            pages.page_battle_prepare: lambda: self.run_general_battle(
                getattr(self.conf, f"{self.climb_type}_battle_conf"),
                battle_key=f"act_{self.climb_type}",
            ),
            pages.page_battle: lambda: self.run_general_battle(
                getattr(self.conf, f"{self.climb_type}_battle_conf"),
                battle_key=f"act_{self.climb_type}",
            ),
            pages.page_reward: lambda: self.click(
                pages.random_click(ltrb=(False, False, True, False)), interval=1.5
            ),
        }

    def run(self):
        self.before_run()
        for climb_type in self.conf.general_climb.run_sequence_v:
            logger.hr(f"Start run {self.climb_type}", 1)
            dest_page: Optional[pages.Page] = getattr(
                pages, f"page_act_{climb_type}", None
            )
            if not dest_page:
                logger.warning(f"{climb_type} page is not supported")
                continue
            self.goto_page(dest_page)
            cur_battle_conf = getattr(self.conf, f"{climb_type}_battle_conf")
            if cur_battle_conf is None:
                logger.warning(f"{climb_type} battle config is not supported")
                continue
            self.lock_team(cur_battle_conf)
            try:
                while True:
                    self.screenshot()
                    self.update_status()
                    current_page = self.get_current_page()
                    if current_page is None:
                        time.sleep(0.5)
                        continue
                    handle = self.act_page_handle_dict.get(current_page, None)
                    if handle is None:
                        self.goto_page(dest_page)
                        continue
                    handle()
            except (LimitCountOut, LimitTimeOut, TicketsNotEnough):
                pass
            finally:
                self.switch_next()  # 切换下一个爬塔类型
        self.goto_page(pages.page_main)
        if self.conf.general_climb.active_souls_clean:
            self.set_next_run(
                task="SoulsTidy", success=False, finish=False, target=datetime.now()
            )
        self.set_next_run(task="ActivityShikigami", success=True)
        raise TaskEnd

    def _run_pass(self):
        self._run_climb()

    def _run_ap(self):
        self._run_climb()

    def _run_ap100(self):
        self._run_climb()

    def _run_boss(self):
        self._run_climb()

    def _run_climb(self):
        """四个爬塔类型共用的单局执行体。

        分两段：先按 `BATTLE_PAGE_ENTER` 把当前页切到战斗页（需要的话），
        再走通用的锁容/查票/换魂/挑战流程。
        """

        if not self._ensure_battle_page():
            return
        if self._lock_team_deferred:
            self._lock_team_deferred = False
            battle_conf = getattr(self.conf, f"{self.climb_type}_battle_conf", None)
            if battle_conf is not None:
                self.lock_team(battle_conf)
        self._run_common()

    def _ensure_battle_page(self) -> bool:
        """到达层：目标页不是战斗页时，点跳转按钮切过去，用确认图判定到位。

        表里没配置的类型直接返回 True，行为与原来一致。
        已经在战斗页时确认图会立刻命中，因此这段是幂等的。
        """

        rule = self.BATTLE_PAGE_ENTER.get(self.climb_type)
        if rule is None:
            self._battle_page_ready = True
            return True
        button_name, confirm_name = rule
        button = getattr(self, button_name, None)
        confirm = getattr(self, confirm_name, None)
        if button is None or confirm is None:
            logger.warning(f"Climb: battle page enter assets missing: {rule}")
            return False
        time.sleep(self.BATTLE_PAGE_ENTER_WAIT)
        self.screenshot()
        # 地图页偶尔会弹提示框（红色叉），不关掉会挡住下面的跳转按钮
        if self.appear(self.I_UI_BACK_RED):
            logger.info(f"Climb: dismiss red close button on {self.climb_type} page")
            self.ui_click_until_disappear(self.I_UI_BACK_RED, interval=1.5)
        arrived = self.ui_click_until_appear_or_timeout(
            button, confirm, interval=1.5, timeout=self.BATTLE_PAGE_ENTER_TIMEOUT
        )
        if not arrived:
            logger.warning(f"Climb: {self.climb_type} did not reach battle page in time")
            return False
        self._battle_page_ready = True
        return True

    def _run_common(self):
        if not self.check_tickets_enough():
            logger.warning(f"No tickets left, wait for next time")
            raise TicketsNotEnough
        self.switch_soul(self.I_BATTLE_MAIN_TO_RECORDS)
        if self.conf.general_climb.random_sleep:
            random_sleep(probability=0.2)
        if self.enter_battle():
            self.count_map[self.climb_type] += 1
            self.run_general_battle(
                getattr(self.conf, f"{self.climb_type}_battle_conf"),
                battle_key=f"act_{self.climb_type}",
            )

    def enter_battle(self):
        click_times, max_times = 0, random.randint(3, 5)
        while True:
            self.screenshot()
            if self.is_in_battle(False):
                return True
            if click_times >= max_times:
                logger.warning(
                    f"{self.climb_type} cannot enter battle, click reach max times"
                )
                raise TicketsNotEnough
            if self.appear(self.I_UI_BACK_RED, interval=1):
                logger.warning(
                    f"{self.climb_type} cannot enter battle, appear red close button, maybe not enough tickets"
                )
                raise TicketsNotEnough
            if self.appear_then_click(
                self.I_UI_CONFIRM_SAMLL, interval=1
            ) or self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                continue
            if self.ocr_appear_click(self.O_FIRE, interval=1.5):
                self.device.click_record_clear()
                click_times += 1
                logger.info(f"Try click fire, remain times[{max_times - click_times}]")
                continue

    def switch_soul(self, enter_button: RuleImage):
        if self.switch_souled.get(self.climb_type, False):
            return
        self.switch_souled[self.climb_type] = True
        conf = self.conf.switch_soul_config
        enable_switch = getattr(conf, f"enable_switch_{self.climb_type}", False)
        enable_by_name = getattr(
            conf, f"enable_switch_{self.climb_type}_by_name", False
        )
        if not enable_switch and not enable_by_name:
            return
        logger.hr("Start switch soul", 2)
        conf.validate_switch_soul()
        self.ui_click(enter_button, stop=self.I_CHECK_RECORDS, interval=1)
        if enable_by_name:
            group, team = getattr(conf, f"{self.climb_type}_group_team_name").split(",")
            self.run_switch_soul_by_name(group, team)
        elif enable_switch:
            group_team = getattr(conf, f"{self.climb_type}_group_team")
            self.run_switch_soul(group_team)
        self.goto_page(getattr(pages, f"page_act_{self.climb_type}"))

    def lock_team(self, battle_conf: GeneralBattleConfig):
        """
        根据配置判断当前爬塔类型是否锁定阵容, 并执行锁定或解锁

        当前类型配了到达层时，锁按钮只存在于战斗页，而这里是在刚到达目标页
        （地图页）时被调用的，必然点不到，因此推迟到 `_run_climb()` 切过去之后补做。
        """
        if self._lock_team_should_defer():
            return
        enable = battle_conf.lock_team_enable
        if enable:
            logger.info(f"Lock {self.climb_type} team")
            match self.climb_type:
                case "ap" | "boss":
                    self.ui_click(self.I_AP_UNLOCK, stop=self.I_AP_LOCK, interval=1.5)
                case _:
                    self.ui_click(self.I_UNLOCK, stop=self.I_LOCK, interval=1.5)
            return
        logger.info(f"Unlock {self.climb_type} team")
        match self.climb_type:
            case "ap" | "boss":
                self.ui_click(self.I_AP_LOCK, stop=self.I_AP_UNLOCK, interval=1.5)
            case _:
                self.ui_click(self.I_LOCK, stop=self.I_UNLOCK, interval=1.5)

    def _lock_team_should_defer(self) -> bool:
        """锁按钮是否只在战斗页上：配了到达层且还没切过去。

        子类覆写 `lock_team()` 时也要在开头调一下，否则推迟逻辑会被绕过，
        补做的时机就落在地图页上了。
        """

        if self.climb_type not in self.BATTLE_PAGE_ENTER or self._battle_page_ready:
            return False
        logger.info(f"Climb: {self.climb_type} lock team deferred to battle page")
        self._lock_team_deferred = True
        return True

    def check_tickets_enough(self) -> bool:
        """
        判断当前爬塔门票是否足够
        :return: True 可以运行 or False
        """
        logger.hr(f"Check {self.climb_type} tickets")
        self.screenshot()
        remain_times = 0
        if self.climb_type == "pass":
            remain_times = self.O_REMAIN_PASS.ocr_digit(self.device.image)
        if self.climb_type == "ap":
            remain_times = self.O_REMAIN_AP.ocr_digit(self.device.image)
        if self.climb_type == "boss":
            cur, remain_times, total = self.O_REMAIN_BOSS.ocr_digit_counter(
                self.device.image
            )
        if self.climb_type == "ap100":
            remain_times = self.O_REMAIN_AP100.ocr_digit(self.device.image)
        # 上一次识别的票的数量和这一次识别的数量差距大于1, 则认为票数量有误, 允许继续挑战
        if self.pre_tickets_map[self.climb_type] - remain_times > 1:
            self.pre_tickets_map[self.climb_type] -= 1
            return True
        self.pre_tickets_map[self.climb_type] = remain_times
        return remain_times > 0
