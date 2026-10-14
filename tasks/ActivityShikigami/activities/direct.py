# This Python file uses the following encoding: utf-8
"""主页直连式爬塔活动。

适用形态：庭院进入活动主页后，主页上同时摆着四个入口
（100 体 / 体力 / 门票 / boss），各自直达，既不需要经过体力-门票的中转地图，
也不需要在爬塔页里再点 `I_CLIMB_MODE_SWITCH` 切换模式。

中转模式仍完整保留在 `NormalClimbAct` 中。两者共用同一套静态 `Page` 定义，
差异只体现在 `before_run()` 里对 **session 副本**重新接线，因此互不干扰：
`session._snapshot_pages()` 会把静态页面深拷贝成任务级副本，
runtime 的 `connect()` / `remove_transition()` 只改动副本，不会污染全局 registry。
"""
import time

import tasks.ActivityShikigami.page as pages
from module.logger import logger
from tasks.ActivityShikigami.base_act import BaseAct
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import ExitMatcher


class DirectClimbAct(BaseAct):
    """主页直连四入口的爬塔活动。

    默认复用 `BaseAct` 的整套执行逻辑（双层循环、页面路由、换御魂、查票、通用战斗），
    这里只负责把页面图改成"主页星形直连"的形状。
    """

    # 主页额外的识别标志（在四个入口之外的补充图腾）。
    # `page_act` 的默认识别器是 `I_TO_BATTLE_MAIN`（旧主页"进入主要战斗界面"的图腾），
    # 直达形态下主页的特征是同时摆着四个入口，因此 `_patch_home_recognizer()`
    # 会自动把 `DIRECT_ENTRIES` 里的入口一并作为主页判据，这里只填额外需要的。
    HOME_MARKERS: tuple[str, ...] = ()

    # (主页入口按钮 asset 名, 目标页面变量名)，按主页上从左往右的顺序写。
    # 尚未截图的入口请整行注释掉，缺失时会打 warning 并跳过，不影响其它入口。
    DIRECT_ENTRIES: tuple[tuple[str, str], ...] = (
        ('I_TO_BATTLE_AP100', 'page_act_ap100'),
        ('I_TO_BATTLE_AP', 'page_act_ap'),
        ('I_TO_BATTLE_PASS', 'page_act_pass'),
        ('I_TO_BATTLE_BOSS', 'page_act_boss'),
    )

    # 入口分组（四入口形态）：每个类型独占一个入口，一步到位，不需要切换。
    # 连线由基类 `_wire_entries()` 统一铺，这里只描述数据。
    ENTRY_GROUPS: tuple[tuple[tuple[str, ...], tuple[str, ...], str | None], ...] = (
        (('ap100',), ('I_TO_BATTLE_AP100',), None),
        (('ap',), ('I_TO_BATTLE_AP',), None),
        (('pass',), ('I_TO_BATTLE_PASS',), None),
        (('boss',), ('I_TO_BATTLE_BOSS',), None),
    )

    # 四入口形态下不存在中转页，摘掉 page.py 静态注册的中转页边。
    DETACH_MAP_ROUTES: bool = True

    # 四个爬塔页各自的「上锁图 / 未上锁图」。
    # 活动换皮时只需替换对应 asset 的模板与 roi，不必改这里；
    # asset 还没截图时 getattr 拿到 None，会自动降级到 LOCK_FALLBACK。
    LOCK_RULES: dict[str, tuple[str, str]] = {
        'ap100': ('I_AP100_LOCK', 'I_AP100_UNLOCK'),
        'ap': ('I_AP_LOCK', 'I_AP_UNLOCK'),
        'pass': ('I_PASS_LOCK', 'I_PASS_UNLOCK'),
        'boss': ('I_BOSS_LOCK', 'I_BOSS_UNLOCK'),
    }

    # 专属锁图缺失、或判定失败时的兜底（通用的那一对）。置为 None 则跳过锁容操作。
    LOCK_FALLBACK: tuple[str, str] | None = ('I_LOCK', 'I_UNLOCK')

    # 单次锁容点击的超时（秒）。
    # 基类 `ui_click` 是 while 1 死循环，专属图匹配不上时会一直空转，
    # 因此这里统一走带超时的 ui_click_until_appear_or_timeout，超时后再用兜底图判断一轮。
    LOCK_CLICK_TIMEOUT: float = 5.0

    # 到达层：哪些类型的目标页只是地图页，还要再点一次才到真正的战斗页。
    # 格式 climb_type -> (跳转按钮, 到达确认图)。不在表里的类型视为进页即战斗页。
    # 门票就是这种：主页点入口先进 pass_map，再点按钮才到能挑战的战斗页。
    # 不能用共用的 `I_MAP_GOTO_BATTLE` 当按钮：那张图同时是 `page_act_map` 的识别判据，
    # 在门票页用它会把当前页误判成中转地图页。
    #
    # ── 调整方式（详细字段照抄 as/pages.json 里现有条目即可）──────────────────
    #   · 某类型从「直达」改成「地图页」：这里加一行，再到 pages.json 补
    #     <type>_map_goto_battle（跳转按钮）与 check_<type>_2（到达确认图）两条，
    #     截两张图放进 as/，重新生成 assets.py；
    #     并把 check_<type>_2 加进 PAGE_EXTRA_CHECKS，否则战斗结束后页面认不出来，
    #     主循环会静默空转直到卡死。
    #   · 某类型从「地图页」改回「直达」：删掉这里对应的一行即可，图片不用动。
    #   · 锁容无需另外处理，基类 `_lock_team_should_defer()` 会自动推迟到战斗页。

    BATTLE_PAGE_ENTER: dict[str, tuple[str, str]] = {
        'pass': ('I_PASS_MAP_GOTO_BATTLE', 'I_CHECK_PASS_2'),
    }

    # 四个爬塔页「进入后」的页面标志 check 图。
    # 中转形态下四个目标是同一张爬塔地图，靠 I_CLIMB_MODE_* 模式图标区分；
    # 直达形态下它们彼此独立，需要各自的 check 图。
    # 补好一张就多一份识别依据，未截图的项会跳过并保持原识别器。
    PAGE_CHECKS: dict[str, str] = {
        'ap100': 'I_CHECK_AP100',
        'ap': 'I_CHECK_AP',
        'pass': 'I_CHECK_PASS',
        'boss': 'I_CHECK_BOSS',
    }

    # 同一爬塔类型存在多个页面时，主 check 图之外的补充判据。
    # 门票就是典型：pass_map 页的标题在顶部中间（check_pass），
    # 点进战斗页后标题挪到左上角（check_pass_2）。主 check 只覆盖其中一个位置，
    # 另一个页面会「谁都认不出来」，`get_current_page()` 静默返回 None，
    # 主循环就空转到卡死。这里补的图与主 check 一起参与该类型的页面识别。
    PAGE_EXTRA_CHECKS: dict[str, tuple[str, ...]] = {
        'pass': ('I_CHECK_PASS_2',),
    }

    # check 图与旧识别器的合并策略：
    #   'extend'  = 追加，旧模式图标仍参与识别（推荐，边补图边跑）
    #   'replace' = 只用新 check 图，旧图标作废（各页外观已彻底分开时切换）
    PAGE_CHECK_MODE: str = 'extend'

    # 各爬塔类型的「余量读取规则」：OCR asset + 取值方式。
    #   digit   -> ocr_digit()          单纯一个数字
    #   counter -> ocr_digit_counter()  "当前/总" 形式，取中间那个
    TICKET_OCR_RULES: dict[str, tuple[str, str]] = {
        'ap100': ('O_REMAIN_AP100', 'digit'),
        'ap': ('O_REMAIN_AP', 'digit'),
        'pass': ('O_REMAIN_PASS', 'digit'),
        'boss': ('O_REMAIN_BOSS', 'counter'),
    }

    # 逻辑复用：把某个爬塔类型的余量读取委派给另一个类型。
    # 100 体在很多期活动里其实就是体力页的高倍率版本，UI 完全一致，
    # 这时不必再单独截 O_REMAIN_AP100，直接借用体力的读数即可。
    # 置空 dict 则四个类型各自读各自的。
    REUSE_SOURCE: dict[str, str] = {
        'ap100': 'ap',
    }

    def _exit_matcher(self) -> ExitMatcher | None:
        return pages.any_of(self.I_ACT_FIRE, self.I_AS_BOSS_FIRE)

    def _ticket_source(self) -> str:
        """当前爬塔类型的余量读数来源，可能被 `REUSE_SOURCE` 委派。"""

        return self.REUSE_SOURCE.get(self.climb_type, self.climb_type)

    def check_tickets_enough(self) -> bool:
        """判断当前爬塔门票是否足够。

        基类按 `climb_type` 硬分支选 OCR，这里改成查表 + 可委派，
        目的是让 UI 相同的类型（如 100 体与体力）能共用一套读数，省一张图。
        计次、战斗配置、换御魂等仍按各自的 climb_type 独立走。
        """

        logger.hr(f'Check {self.climb_type} tickets')
        source = self._ticket_source()
        if source != self.climb_type:
            logger.info(f'Direct climb: {self.climb_type} reuses ticket ocr of {source}')
        self.screenshot()

        rule = self.TICKET_OCR_RULES.get(source)
        if rule is None:
            logger.warning(f'Direct climb: no ticket ocr rule for {source}, skip check')
            return True
        asset_name, mode = rule
        ocr = getattr(self, asset_name, None)
        if ocr is None:
            logger.warning(f'Direct climb: ticket ocr {asset_name} missing, skip check')
            return True

        if mode == 'counter':
            _, remain_times, _ = ocr.ocr_digit_counter(self.device.image)
        else:
            remain_times = ocr.ocr_digit(self.device.image)

        # 上一次识别的票的数量和这一次识别的数量差距大于1, 则认为票数量有误, 允许继续挑战
        if self.pre_tickets_map[self.climb_type] - remain_times > 1:
            self.pre_tickets_map[self.climb_type] -= 1
            return True
        self.pre_tickets_map[self.climb_type] = remain_times
        return remain_times > 0

    def lock_team(self, battle_conf: GeneralBattleConfig):
        """按当前爬塔类型取对应的锁图，执行上锁或解锁。

        四个页面的锁按钮坐标各不相同，因此各自维护一对图。
        专属图缺失时降级到 LOCK_FALLBACK，避免还没补图就整个跑不起来。

        凡是配了到达层的类型（锁按钮只在战斗页上），锁容会自动推迟到
        切进战斗页之后由 `_run_climb()` 补做。因为这里覆写了 `lock_team()`，
        必须显式调一次，否则推迟逻辑被绕过、会在地图页上白点一轮。
        """

        if self._lock_team_should_defer():
            return

        lock_name, unlock_name = self._resolve_lock_names()
        if lock_name is None:
            return
        lock = getattr(self, lock_name, None)
        unlock = getattr(self, unlock_name, None)
        if lock is None or unlock is None:
            logger.warning(f'Direct climb: lock assets missing {lock_name}/{unlock_name}')
            return
        if battle_conf.lock_team_enable:
            logger.info(f'Lock {self.climb_type} team')
            if self._click_until_locked(unlock, lock):
                return
        else:
            logger.info(f'Unlock {self.climb_type} team')
            if self._click_until_locked(lock, unlock):
                return
        # 专属图判定失败（超时/匹配不上），最后用通用的 lock/unlock 再判断一轮
        self._lock_team_fallback(battle_conf)

    def _click_until_locked(self, click, stop) -> bool:
        """点 `click` 图直到出现 `stop` 图，带超时返回是否达成。"""

        return self.ui_click_until_appear_or_timeout(
            click, stop, interval=1.5, timeout=self.LOCK_CLICK_TIMEOUT
        )

    def _lock_team_fallback(self, battle_conf: GeneralBattleConfig) -> None:
        """用 `LOCK_FALLBACK` 指定的通用锁图再判定一轮。"""

        if self.LOCK_FALLBACK is None:
            return
        lock_name, unlock_name = self.LOCK_FALLBACK
        lock = getattr(self, lock_name, None)
        unlock = getattr(self, unlock_name, None)
        if lock is None or unlock is None:
            logger.warning(f'Direct climb: fallback lock assets missing {self.LOCK_FALLBACK}')
            return
        logger.warning(
            f'Direct climb: {self.climb_type} lock judgement failed, '
            f'retry with {self.LOCK_FALLBACK}'
        )
        if battle_conf.lock_team_enable:
            self._click_until_locked(unlock, lock)
            return
        self._click_until_locked(lock, unlock)

    def _resolve_lock_names(self) -> tuple[str, str] | tuple[None, None]:
        """读出当前爬塔类型的锁图 asset 名，缺失时回退或放弃。"""

        names = self.LOCK_RULES.get(self.climb_type)
        if names and all(getattr(self, name, None) is not None for name in names):
            return names
        if names:
            logger.warning(
                f'Direct climb: {self.climb_type} 专属锁图 {names} 未配置, '
                f'fallback to {self.LOCK_FALLBACK}'
            )
        else:
            logger.warning(f'Direct climb: no lock rule for {self.climb_type}')
        if self.LOCK_FALLBACK is None:
            logger.warning(f'Direct climb: skip lock team for {self.climb_type}')
            return None, None
        return self.LOCK_FALLBACK

    def before_run(self):
        super().before_run()
        page_act = self.navigator.resolve_page(pages.page_act)
        if page_act is None:
            logger.warning('Direct climb: page_act not found, keep static page graph')
            return

        self._patch_home_recognizer(page_act)
        self._patch_page_recognizers()
        self._detach_map_routes(page_act)
        self._wire_entries(page_act)

    def _patch_home_recognizer(self, page_act) -> None:
        """主页识别器 = `DIRECT_ENTRIES` 四个入口任一 + `HOME_MARKERS` 额外图腾。

        直达形态下主页的特征就是同时摆着四个入口，任一出现即视为到达主页。
        extend 模式下原识别器仍然保留，所以旧主页也能认出来。
        """

        names = [asset_name for asset_name, _ in self.DIRECT_ENTRIES]
        names += [name for name in self.HOME_MARKERS if name not in names]
        markers = [getattr(self, name, None) for name in names]
        markers = [marker for marker in markers if marker is not None]
        if not markers:
            return
        logger.info(f'Direct climb: extend page_act recognizer with {names}')
        page_act.recognizer = pages.any_of(*markers, page_act.recognizer)

    def _patch_page_recognizers(self) -> None:
        """给四个爬塔页补各自的进入后 check 图。

        `Page.recognizer` 直接决定 `get_current_page()` 能否把当前帧认出来，
        进而决定路由表里能不能命中对应的 handler，所以这一步比连线更基础。

        一个类型可能有多个页面（主 check + `PAGE_EXTRA_CHECKS`），
        任一命中都算该类型的页面，handler 内部靠幂等逻辑区分当前在哪一层。
        """

        for climb_type, asset_name in self.PAGE_CHECKS.items():
            page = self.navigator.resolve_page(getattr(pages, f'page_act_{climb_type}', None))
            if page is None:
                logger.warning(f'Direct climb: page_act_{climb_type} not registered')
                continue
            wanted = [asset_name]
            wanted += [name for name in self.PAGE_EXTRA_CHECKS.get(climb_type, ()) if name not in wanted]
            markers, applied = [], []
            for name in wanted:
                marker = getattr(self, name, None)
                if marker is None:
                    logger.warning(f'Direct climb: check asset {name} missing, skip')
                    continue
                markers.append(marker)
                applied.append(name)
            if not markers:
                logger.warning(
                    f'Direct climb: no check asset for {climb_type}, keep original recognizer'
                )
                continue
            if self.PAGE_CHECK_MODE == 'replace':
                page.recognizer = pages.any_of(*markers)
                logger.info(f'Direct climb: {climb_type} recognizer replaced by {applied}')
                continue
            page.recognizer = pages.any_of(*markers, page.recognizer)
            logger.info(f'Direct climb: {climb_type} recognizer extended by {applied}')
