"""ActivityShikigami
入口层 / 到达层 / 战斗层的差异都外置成类常量，换活动通常只需改配置与图片。"""
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
    """爬塔类型游标与计数状态：按 `run_sequence_v` 切换类型并记次。"""

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
        """推进到下一个爬塔类型，返回 True 表示还有下一个。"""

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
    入口层 / 到达层 / 战斗层的差异分别是 `ENTRY_GROUPS`、`BATTLE_PAGE_ENTER`、查票与战斗配置。"""

    ENTRY_GROUPS: tuple[tuple[tuple[str, ...], tuple[str, ...], str | None], ...] = ()

    # 仅组里多于一个类型时才用到：进错模式时靠它识别出来再点切换。
    MODE_ICONS: dict[str, str] = {
        'ap': 'I_CLIMB_MODE_AP',
        'pass': 'I_CLIMB_MODE_PASS',
        'ap100': 'I_CLIMB_MODE_AP100',
    }

    DETACH_MAP_ROUTES: bool = False

    # 爬塔页返回时依次尝试的按钮。
    BACK_BUTTONS: tuple[str, ...] = ("I_UI_BACK_YELLOW", "I_UI_BACK_CIRCLE")

    # 地图页退回活动页那一跳的返回键候选。
    MAP_BACK_BUTTONS: tuple[str, ...] = None

    # 地图页上各类型「进入战斗」的按钮。
    MAP_GOTO_BATTLE: dict[str, str] = {}

   
   
    # 某些活动的目标页只是地图页，还要再点一次才到真正的战斗页。
    BATTLE_PAGE_ENTER: dict[str, tuple[str, str]] = {}
    
    # 进入战斗页前的等待时长（秒），给页面切换留时间。
    
    BATTLE_PAGE_ENTER_WAIT: float = 1.0
    
    # 点跳转按钮后等待确认图出现的上限（秒）。
    BATTLE_PAGE_ENTER_TIMEOUT: float = 5.0
    
    # 进界面时统一清一遍的干扰元素：每项 = (要处理的图, 处理方式)。
    POPUP_CLEARS: tuple[tuple[tuple[str, ...], str], ...] = (
        (("I_UI_BACK_RED",), "disappear"),
        (("I_SKIP_BUTTON", "I_CONFIRM_SKIP"), "chain"),
    )

    # 清理干扰元素时的点击/等待间隔（秒）。
    POPUP_CLEAR_INTERVAL: float = 1.5

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
            self.clear_popups()
        return super()._handle_result(context, config)

    def clear_popups(self) -> bool:

        handled = False
        for names, mode in self.POPUP_CLEARS:
            images = [getattr(self, name, None) for name in names]
            if any(image is None for image in images):
                logger.warning(f"Climb: popup clear asset missing {names}, skip")
                continue
            self.screenshot()
            if not self.appear(images[0]):
                continue
            logger.info(f"Climb: clear popup {names} with {mode}")
            if mode == "disappear":
                self.ui_click_until_disappear(
                    images[0], interval=self.POPUP_CLEAR_INTERVAL
                )
            else:
                self._click_popup_chain(images)
            handled = True
        return handled

    def _click_popup_chain(self, images) -> None:
        """依次点一组图：后面的图要点完前面的才会冒出来。"""

        for index, image in enumerate(images):
            if index:
                time.sleep(self.POPUP_CLEAR_INTERVAL)
            self.screenshot()
            if not self.appear_then_click(image, interval=self.POPUP_CLEAR_INTERVAL):
                logger.warning(f"Climb: popup chain stopped at {index}: {image.name}")
                return

    def _register_popup_hooks(self) -> None:

        for name in (
            "page_act",
            "page_act_ap",
            "page_act_pass",
            "page_act_ap100",
            "page_act_boss",
        ):
            page = self.navigator.resolve_page(getattr(pages, name, None))
            if page is None:
                continue
            page.add_enter_failure_hooks(self.clear_popups)

    def before_run(self):
        pages.page_battle_result = self.navigator.resolve_page(pages.page_battle_result)
        pages.page_battle_result.recognizer = pages.any_of(
            self.I_UI_BACK_RED, pages.page_battle_result.recognizer
        )
        self.navigator.add_unknown_closer(self.clear_popups)
        self._register_popup_hooks()

    def _page_of(self, climb_type: str):
        """取该爬塔类型在本次 session 里的页面副本。"""

        return self.navigator.resolve_page(getattr(pages, f"page_act_{climb_type}", None))

    def _resolve_map_back_action(self):
        """地图页回程动作"""

        names = self.MAP_BACK_BUTTONS
        if names is None:
            names = self.BACK_BUTTONS
        buttons = [getattr(self, name, None) for name in names]
        buttons = [button for button in buttons if button is not None]
        if not buttons:
            logger.warning("Climb: no map back button configured")
            return None
        if len(buttons) == 1:
            return buttons[0]
        return pages.sequence(*buttons, success_index=len(buttons))

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
        page_act.remove_transition(destination=page_act_map)
        for name in ("page_act_ap", "page_act_pass", "page_act_ap100", "page_act_boss"):
            page = self.navigator.resolve_page(getattr(pages, name, None))
            if page is None:
                continue
            page.remove_transition(destination=page_act_map)

    def _wire_map_goto_battles(self, map_page) -> None:
        """地图页 -> 各类型战斗页：组内切换时在地图页点一下就进，不用退回活动页。"""

        for climb_type, button_name in self.MAP_GOTO_BATTLE.items():
            button = getattr(self, button_name, None)
            target = self._page_of(climb_type)
            if button is None or target is None:
                logger.warning(f"Climb: map goto battle {climb_type} missing, skip")
                continue
            if target is map_page:
                continue
            map_page.connect(
                target, button, key=f"{map_page.key}->page_act_{climb_type}"
            )

    def _wire_entries(self, page_act) -> None:
        """按 `ENTRY_GROUPS` 铺主页到各爬塔页的连线。"""

        if not self.ENTRY_GROUPS:
            logger.warning("Climb: ENTRY_GROUPS is empty, no entry route wired")
            return
        back_action = self._resolve_back_action()
        map_pages: list = []
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
                    # 有中间层的类型（到达层还要再点一次才到战斗页）：
                    mid_page = None
                    if climb_type in self.BATTLE_PAGE_ENTER:
                        mid_page = self.navigator.resolve_page(
                            getattr(pages, f"page_act_{climb_type}_map", None)
                        )
                        if mid_page is None:
                            logger.warning(
                                f"Climb: page_act_{climb_type}_map not registered, wire to battle page"
                            )
                        else:
                            target = mid_page
                            if mid_page not in map_pages:
                                map_pages.append(mid_page)
                            # 地图页 -> 活动页：候选返回键轮流判断，哪个存在点哪个
                            mid_back = self._resolve_map_back_action()
                            if mid_back is None:
                                logger.warning(
                                    f"Climb: no map back button for {climb_type}, "
                                    f"page_act_{climb_type}_map has no way back"
                                )
                            else:
                                mid_page.connect(
                                    page_act,
                                    mid_back,
                                    key=f"page_act_{climb_type}_map->page_act",
                                )
                    source.connect(
                        target, button, key=f"{source.name}->{target.key}"
                    )
                    # 回程只在直连形态补；经中转页的回程由 page.py 静态定义
                    if source is page_act and back_action is not None and mid_page is None:
                        target.connect(
                            page_act,
                            back_action,
                            key=f"page_act_{climb_type}->page_act",
                        )
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

        # 地图页上直接进各类型战斗页（组内切换用，省掉退回活动页再进来）
        for map_page in map_pages:
            self._wire_map_goto_battles(map_page)

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
        先按 `BATTLE_PAGE_ENTER` 切到战斗页，再走通用的锁容/查票/换魂/挑战。"""

        if not self._ensure_battle_page():
            return
        if self._lock_team_deferred:
            self._lock_team_deferred = False
            battle_conf = getattr(self.conf, f"{self.climb_type}_battle_conf", None)
            if battle_conf is not None:
                self.lock_team(battle_conf)
        self._run_common()

    def _ensure_battle_page(self) -> bool:
        """到达层：点跳转按钮切到战斗页，用确认图判定到位。"""

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
        # 地图页上的红叉弹窗、跳过框统一在这一步清掉
        self.clear_popups()
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
            # 这里的红叉不是挡路的弹窗，而是"票不够"的提示
            # 关掉它只会让这一轮反复重试，交给 `TicketsNotEnough` 直接结束该类型。
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
        """按配置执行上锁或解锁。"""
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
        """锁按钮是否只在战斗页上：配了到达层且还没切过去。"""

        if self.climb_type not in self.BATTLE_PAGE_ENTER or self._battle_page_ready:
            return False
        logger.info(f"Climb: {self.climb_type} lock team deferred to battle page")
        self._lock_team_deferred = True
        return True

    def check_tickets_enough(self) -> bool:
        """判断当前爬塔门票是否足够。"""
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
        remain_times = remain_times or 0  # OCR 空值统一当成 0
        # 上一次识别的票的数量和这一次识别的数量差距大于1, 则认为票数量有误, 允许继续挑战
        if self.pre_tickets_map[self.climb_type] - remain_times > 1:
            self.pre_tickets_map[self.climb_type] -= 1
            return True
        self.pre_tickets_map[self.climb_type] = remain_times
        return remain_times > 0
