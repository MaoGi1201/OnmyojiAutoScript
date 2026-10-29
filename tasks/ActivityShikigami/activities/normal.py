"""爬塔活动的通用 Act：主页入口 / 到达跳转 / 查票 / 锁容全部由类常量配置。"""
from module.logger import logger
from tasks.ActivityShikigami.base_act import BaseAct
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import ExitMatcher
import tasks.ActivityShikigami.page as pages


class NormalClimbAct(BaseAct):
    """通用爬塔 Act。"""

    # 主页额外判据，一般留空。
    HOME_MARKERS: tuple[str, ...] = ()

    # 本次活动开放的爬塔模式
    SUPPORTED_CLIMB_TYPES: tuple[str, ...] = ('ap',)
    # 三入口形态（ap100 / boss 各自独立，ap 与 pass 共用 pass 入口）长这样：
    #   ENTRY_GROUPS = (
    #       (('ap100',), ('I_TO_BATTLE_AP100',), None),
    #       (('boss',), ('I_TO_BATTLE_BOSS',), None),
    #       (('ap', 'pass'), ('I_TO_BATTLE_PASS',), 'I_CLIMB_MODE_SWITCH'),
    #   )
    # 启用时记得把 'pass' 加进 SUPPORTED_CLIMB_TYPES 和 PAGE_CHECKS。
    ENTRY_GROUPS: tuple[tuple[tuple[str, ...], tuple[str, ...], str | None], ...] = (
        # (('ap100',), ('I_TO_BATTLE_AP100',), None),
        (('ap',), ('I_TO_BATTLE_AP',), None),
        # (('pass',), ('I_TO_BATTLE_PASS',), None),
        # (('boss',), ('I_TO_BATTLE_BOSS',), None),
        # (('ap', 'pass'), ('I_TO_BATTLE_PASS',), 'I_CLIMB_MODE_SWITCH'),

    )

    # （页面图里只有 page_act_pass_map 一个地图页节点，page_act_map 仅是 flag=True 时的别名）。
    DETACH_MAP_ROUTES: bool = True

    # 跳转后等待目标页出现的上限（秒）
    page_arrive_timeout: float = 2.0

    # 四个爬塔页各自的「上锁图 / 未上锁图」，判定顺序在通用图之后。
    # 某项 asset 未配置时 `_own_lock_names()` 返回 None，该轮跳过。
    LOCK_RULES: dict[str, tuple[str, str]] = {
        # 'ap100': ('I_AP100_LOCK', 'I_AP100_UNLOCK'),
        #'ap': ('I_AP_LOCK', 'I_AP_UNLOCK'),
        # 'pass': ('I_PASS_LOCK', 'I_PASS_UNLOCK'),
        # 'boss': ('I_BOSS_LOCK', 'I_BOSS_UNLOCK'),
    }

    # 通用的那一对锁图，判定优先用它，失败后再退到各页专属的那一对。
    # 置 None 则只用专属图。
    LOCK_FALLBACK: tuple[str, str] | None = ('I_LOCK', 'I_UNLOCK')

    # 单轮锁容点击的超时（秒）；基类 `ui_click` 是死循环
    LOCK_CLICK_TIMEOUT: float = 5.0

    # 到达层：哪些类型的目标页只是地图页，还要再点一次才到真正的战斗页。
    # 本期体力页进页即战斗页，不需要二次点击；原门票规则注释保留，恢复时取消注释。
    BATTLE_PAGE_ENTER: dict[str, tuple[str, str]] = {
        # 'pass': ('I_PASS_MAP_GOTO_BATTLE', 'I_CLIMB_MODE_PASS'),
    }

    # 地图页上各类型的进入按钮：pass 先跑时，切到 ap / ap100 只要退回地图页点一下。
    # 本期没有地图页；恢复时取消注释。
    MAP_GOTO_BATTLE: dict[str, str] = {
        # 'pass': 'I_PASS_MAP_GOTO_BATTLE',
        # 'ap': 'I_AP_MAP_GOTO_BATTLE',
        # 'ap100': 'I_AP100_MAP_GOTO_BATTLE',
    }

    # 四个爬塔页各自的进入后 check 图。
    PAGE_CHECKS: dict[str, str] = {
        # 'ap100': 'I_CHECK_AP100',
         #'ap': 'I_CLIMB_MODE_AP',
        # 'pass': 'I_CLIMB_MODE_PASS',
        # 'boss': 'I_CHECK_BOSS',
    }

    # 同一爬塔类型存在多个页面时，主 check 图之外的补充判据。
    PAGE_EXTRA_CHECKS: dict[str, tuple[str, ...]] = {}

    # check 图与旧识别器的合并策略：
    #   'extend'  = 追加，旧模式图标仍参与识别（推荐，边补图边跑）
    #   'replace' = 只用新 check 图，旧图标作废（各页外观已彻底分开时切换）
    PAGE_CHECK_MODE: str = 'extend'

    # 各爬塔类型的「余量读取规则」：OCR asset + 取值方式。
    TICKET_OCR_RULES: dict[str, tuple[str, str]] = {
        # 'ap100': ('O_REMAIN_AP100', 'digit'),
         #'ap': ('O_REMAIN_AP', 'digit'),
        # 'pass': ('O_REMAIN_PASS', 'digit'),
        # 'boss': ('O_REMAIN_BOSS', 'counter'),
    }

    # 逻辑复用：把某个类型的余量读取委派给另一个类型。
    # 置空 dict 则四个类型各自读各自的。
    REUSE_SOURCE: dict[str, str] = {}

    # 单次挑战消耗的体力。右上角 `O_CHECK_AP_NUM`低于100就不打了
    # 直接结束该类型。只对配置了的类型生效，未配置的不检测。
    AP_COST: dict[str, int] = {
        'ap': 100,
    }

    def _exit_matcher(self) -> ExitMatcher | None:
        return pages.any_of(self.I_ACT_FIRE, self.I_AS_BOSS_FIRE)

    def before_run(self):
        super().before_run()
        page_act = self.navigator.resolve_page(pages.page_act)
        if page_act is None:
            logger.warning('Climb: page_act not found, keep static page graph')
            return

        self._patch_home_recognizer(page_act)
        self._patch_page_recognizers()
        self._detach_map_routes(page_act)
        self._wire_entries(page_act)

    def _patch_home_recognizer(self, page_act) -> None:
        """活动页识别器 = 各组入口按钮的第一跳 + `HOME_MARKERS`。
        """

        names = [buttons[0] for _, buttons, _ in self.ENTRY_GROUPS if buttons]
        names += [name for name in self.HOME_MARKERS if name not in names]
        markers = [getattr(self, name, None) for name in names]
        markers = [marker for marker in markers if marker is not None]
        if not markers:
            return
        page_act.recognizer = pages.any_of(*markers, page_act.recognizer)

    def _patch_page_recognizers(self) -> None:
        """给四个爬塔页补各自的 check 图。"""

        for climb_type, asset_name in self.PAGE_CHECKS.items():
            page = self.navigator.resolve_page(getattr(pages, f'page_act_{climb_type}', None))
            if page is None:
                logger.warning(f'Climb: page_act_{climb_type} not registered')
                continue
            wanted = [asset_name]
            wanted += [name for name in self.PAGE_EXTRA_CHECKS.get(climb_type, ()) if name not in wanted]
            markers = []
            for name in wanted:
                marker = getattr(self, name, None)
                if marker is None:
                    logger.warning(f'Climb: check asset {name} missing, skip')
                    continue
                markers.append(marker)
            if not markers:
                logger.warning(
                    f'Climb: no check asset for {climb_type}, keep original recognizer'
                )
                continue
            if self.PAGE_CHECK_MODE == 'replace':
                page.recognizer = pages.any_of(*markers)
                continue
            page.recognizer = pages.any_of(*markers, page.recognizer)

    def check_tickets_enough(self) -> bool:
        """判断当前爬塔门票是否足够。"""

        logger.hr(f'Check {self.climb_type} tickets')
        source = self._ticket_source()
        if source != self.climb_type:
            logger.info(f'Climb: {self.climb_type} reuses ticket ocr of {source}')
        self.screenshot()
        if not self.check_ap_enough():
            logger.info(f'Climb: ap not enough for {self.climb_type}, finish')
            return False

        rule = self.TICKET_OCR_RULES.get(source)
        if rule is None:
            #  ap 的剩余次数不参与判断，未登记规则是正常配置。
            logger.info(f'Climb: {source} ticket check disabled, skip')
            return True
        asset_name, mode = rule
        ocr = getattr(self, asset_name, None)
        if ocr is None:
            logger.warning(f'Climb: ticket ocr {asset_name} missing, skip check')
            return True

        if mode == 'counter':
            _, remain_times, _ = ocr.ocr_digit_counter(self.device.image)
        else:
            remain_times = ocr.ocr_digit(self.device.image)

        remain_times = remain_times or 0  # OCR 空值统一当成 0
        # 上一次识别的票的数量和这一次识别的数量差距大于1, 则认为票数量有误, 允许继续挑战
        if self.pre_tickets_map[self.climb_type] - remain_times > 1:
            self.pre_tickets_map[self.climb_type] -= 1
            return True
        self.pre_tickets_map[self.climb_type] = remain_times
        return remain_times > 0

    def check_ap_enough(self) -> bool:
        """右上角体力是否够打一次（`AP_COST` 里没配的类型不检测）。 """

        cost = self.AP_COST.get(self.climb_type, 0)
        if cost <= 0:
            return True
        ap_num = int(self.O_CHECK_AP_NUM.ocr(self.device.image) or 0)
        logger.info(f'Climb: ap num {ap_num}, {self.climb_type} cost {cost}')
        return ap_num >= cost

    def _ticket_source(self) -> str:
        """当前爬塔类型的余量读数来源，可能被 `REUSE_SOURCE` 委派。"""

        return self.REUSE_SOURCE.get(self.climb_type, self.climb_type)

    def lock_team(self, battle_conf: GeneralBattleConfig):
        """执行上锁或解锁。
        判定顺序：通用的一对（`LOCK_FALLBACK`）优先，失败再退到本页专属的。"""

        if self._lock_team_should_defer():
            return

        # 第一轮：通用的 lock / unlock
        if self.LOCK_FALLBACK is not None:
            if self._lock_with(self.LOCK_FALLBACK, battle_conf, stage='通用'):
                return
            logger.warning(f'Climb: {self.climb_type} generic lock failed')
        # 第二轮：当前爬塔页专属的锁图
        own_names = self._own_lock_names()
        if own_names is None:
            return
        self._lock_with(own_names, battle_conf, stage='专属')

    def _lock_with(self, names: tuple[str, str], battle_conf: GeneralBattleConfig,
                   stage: str = '') -> bool:
        """用指定的一对锁图执行上锁或解锁，返回是否成功。
        names: (上锁图, 解锁图)；stage 仅用于日志区分通用图还是专属图。"""

        lock_name, unlock_name = names
        lock = getattr(self, lock_name, None)
        unlock = getattr(self, unlock_name, None)
        if lock is None or unlock is None:
            logger.warning(f'Climb: {stage}lock assets missing {names}')
            return False
        if battle_conf.lock_team_enable:
            logger.info(f'Lock {self.climb_type} team with {stage}图 {names}')
            return self._click_until_locked(unlock, lock)
        logger.info(f'Unlock {self.climb_type} team with {stage}图 {names}')
        return self._click_until_locked(lock, unlock)

    def _click_until_locked(self, click, stop) -> bool:
        """点 `click` 图直到出现 `stop` 图，带超时返回是否达成。"""

        return self.ui_click_until_appear_or_timeout(
            click, stop, interval=1.5, timeout=self.LOCK_CLICK_TIMEOUT
        )

    def _own_lock_names(self) -> tuple[str, str] | None:
        """读出当前爬塔类型**专属**的锁图 asset 名；缺失或未配置时返回 None。"""

        names = self.LOCK_RULES.get(self.climb_type)
        if not names:
            logger.warning(f'Climb: no lock rule for {self.climb_type}')
            return None
        if any(getattr(self, name, None) is None for name in names):
            logger.warning(f'Climb: {self.climb_type} 专属锁图 {names} 未配置, skip')
            return None
        return names
