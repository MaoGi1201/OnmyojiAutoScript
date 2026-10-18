# This Python file uses the following encoding: utf-8
from datetime import timedelta
from time import sleep

from module.base.timer import Timer
from module.exception import TaskEnd
from module.logger import logger

from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import BattleAction, GeneralBattle, BattleContext
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.DemonMartialTrials.assets import DemonMartialTrialsAssets
from tasks.DemonMartialTrials.config import DMTMode
from tasks.DemonMartialTrials.page import page_demon_martial, page_demon_martial_challenge
from tasks.Delegation.script_task import ScriptTask as DelegationTask
from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.page import (page_battle, page_battle_prepare, page_battle_result,
                               page_main, page_reward, page_shikigami_records)
from tasks.GlobalGame.assets import GlobalGameAssets

# 委派
class ScriptTask(DelegationTask, GeneralBattle, GeneralRoom, GeneralInvite,
                 SwitchSoul, DemonMartialTrialsAssets):

    def _exit_matcher(self):
        """战斗结束标志：走过结算/奖励页之后再回到挑战页，或已经回到队伍房间。"""

        def reached_challenge(task) -> bool:
            context = task._battle_context
            if context is None or context.last_page not in (page_battle_result, page_reward):
                return False
            return task.appear(task.I_DEMON_CHALLENGE_CHECK) or task.is_in_room(False)

        return reached_challenge

    def _handle_reward(self, context: BattleContext, config: GeneralBattleConfig) -> BattleAction:
        if self.config.demon_martial_trials.dmt_config.mode == DMTMode.LEADER \
                and self.check_and_invite(self.config.demon_martial_trials.invite_config.default_invite):
            return BattleAction.CONTINUE
        return super()._handle_reward(context, config)

    def run(self):
        cfg = self.config.demon_martial_trials
        limit = cfg.dmt_config.limit_time
        seconds = timedelta(hours=limit.hour, minutes=limit.minute, seconds=limit.second)
        timeout = Timer(seconds.total_seconds()).start()
        limit_count = cfg.dmt_config.limit_count

        if cfg.switch_soul.enable:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul(cfg.switch_soul.switch_group_team)
        if cfg.switch_soul.enable_switch_by_name:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul_by_name(cfg.switch_soul.group_name, cfg.switch_soul.team_name)

        # 导航直达：庭院右栏入口 -> 逢魔演武
        self.goto_page(page_demon_martial)
        if cfg.dmt_config.delegate_enable:
            self._run_delegation()
        self.goto_page(page_demon_martial_challenge)
        if cfg.dmt_config.mode == DMTMode.LEADER:
            self._run_leader(timeout, limit_count)
        elif cfg.dmt_config.mode == DMTMode.MEMBER:
            self._run_member(timeout)
        else:
            self._run_challenges(timeout, limit_count)

        self.goto_page(page_main)
        self.set_next_run(task='DemonMartialTrials', success=True)
        raise TaskEnd('DemonMartialTrials')

    def _run_delegation(self):
        """活动页判断委派状态：委派中或次数用满（如5/5）则跳过，否则进式神委派执行一次。"""
        self.screenshot()
        if self.appear(self.I_DEMON_DELEGATE_TAG):
            logger.info('Delegation in progress, skip')
            return
        # 次数从0往上加，加到上限（如5/5）即表示委派次数用完
        done, remain, total = self.O_DEMON_DELEGATE_COUNT.ocr(self.device.image)
        if total <= 0:
            logger.warning(f'Delegation count ocr failed: {done}/{total}, skip')
            return
        if done >= total:
            logger.info(f'Delegation count exhausted: {done}/{total}, close delegate switch')
            self.config.demon_martial_trials.dmt_config.delegate_enable = False
            self.config.save()
            return
        logger.info(f'Delegation available: {done}/{total}')
        # 演武委派 -> 式神委派页面
        if not self.ui_click_until_appear_or_timeout(
                self.I_DEMON_DELEGATE_ENTRY, GameUiAssets.I_CHECK_DELEGATION,
                interval=2, timeout=15):
            logger.warning('Delegation page not reached')
            return
        # 先收掉已完成的委派（完成卡片、完美达成/差强人意弹窗）
        self.check_reward()
        # 本次活动委派任务 -> 进面板 -> 上阵出发，全部走原委派流程
        if self.open_delegation(self.I_DEMON_DELEGATE_TASK):
            self.dispatch()
        # 返回逢魔演武活动页
        self.ui_click_until_appear_or_timeout(
            GlobalGameAssets.I_UI_BACK_YELLOW, self.I_DEMON_CHECK, interval=2, timeout=10)

    def _run_leader(self, timeout: Timer, limit_count: int):
        """队长模式：建房后用通用邀请等队员进入并开打，打完留在房里继续。"""
        fail_count = 0
        while not timeout.reached():
            new_room = False
            if self.current_count >= limit_count:
                logger.info(f'Reach limit count: {self.current_count}/{limit_count}')
                break
            if not self.is_in_room():
                status = self._create_team_room()
                if status == 'exhausted':
                    logger.info('Challenge count exhausted in team page, finish task')
                    break
                if not status:
                    fail_count += 1
                    if fail_count >= 3:
                        logger.warning('Create team room failed 3 times in a row, abort')
                        break
                    continue
                new_room = True
            fail_count = 0
            # 通用邀请：填了名单时 run_invite 负责邀请、等队员进入并开火（成功即已进战斗）。
            # 勾了默认邀请后，同一房间的后续轮不用再手动邀请，等队友回来即开打
            invite_config = self.config.demon_martial_trials.invite_config
            if invite_config.friend_list_v:
                if self.run_invite(invite_config, is_first=new_room):
                    self.run_general_battle(
                        config=self.config.demon_martial_trials.general_battle_config)
                else:
                    logger.warning('No teammate joined, leave room')
                    self.exit_room()
            else:
                # 没填名单：等人进房没意义，等 3 秒直接开打
                sleep(3)
                self.click_fire()
                self.run_general_battle(
                    config=self.config.demon_martial_trials.general_battle_config)

    def _create_team_room(self):
        """挑战页点组队进列表页，按邀请名单建公开/私密队伍并等进房。

        :return: True 正常建房；False 建房失败（可重试）；'exhausted' 活动剩余次数用完。
        """
        if not self.ui_click_until_appear_or_timeout(
                self.I_DEMON_TEAM_ENTRY, self.I_DEMON_TEAM_CREATE, interval=2, timeout=15):
            logger.warning('Team page not reached')
            return False
        # 组队页顶部「剩余挑战次数： x/y」，用尽就收工（此时人正好在组队页）
        left, used, total = self.O_DEMON_TEAM_COUNT.ocr(self.device.image)
        if total > 0 and left <= 0:
            logger.info(f'Challenge count exhausted: {left}/{total}')
            return 'exhausted'
        if total == 0:
            logger.warning('Team page count ocr failed, continue creating room')
        if not self.create_room(create_room_rule=self.I_DEMON_TEAM_CREATE,
                                ensure_rules=[self.I_DEMON_TEAM_ENSURE]):
            return False
        # 填了邀请对象 → 建私密房（不公开，仅邀请）防路人；否则公开等人进。
        if self.config.demon_martial_trials.invite_config.friend_list_v:
            self.ensure_private()
        else:
            self.ensure_public()
        self.create_ensure(ensure_rules=[self.I_DEMON_TEAM_ENSURE])
        enter_timer = Timer(10).start()
        while not self.is_in_room() and not enter_timer.reached():
            pass
        if not self.is_in_room():
            logger.warning('Enter team room failed')
            return False
        logger.info('Team room created')
        return True

    def _run_member(self, timeout: Timer):
        """队员模式：等队长邀请，进房后等开打（房间倒计时会自动开始）。 """
        battle_config = self.config.demon_martial_trials.general_battle_config
        wait_time = self.config.demon_martial_trials.invite_config.wait_time
        while not timeout.reached():
            # 长时间等邀请不算卡住，否则设备会抛 GameStuckError 重启游戏（每轮续期）
            self.device.stuck_record_add('BATTLE_STATUS_S')
            self.screenshot()
            if self.check_then_accept():
                continue
            if self.is_in_battle(False):
                # 被秒开：直接接管战斗
                self.run_general_battle(config=battle_config)
                continue
            if self.is_in_room(False):
                # 通用等待：进战斗返回 True；房间销毁/超时/自己变队长则退房返回 False
                if self.wait_battle(wait_time):
                    # 返回 True 只说明"不在房间"：可能是被秒开进了战斗，
                    # 也可能是队长解散了房间。后者不会再有人来邀请，队员一并收工
                    where = self._settle_out_of_room()
                    if where == 'battle':
                        self.run_general_battle(config=battle_config)
                    elif where == 'dismissed':
                        logger.info('Team room dismissed, member task finished')
                        break
                    # 'room'：房间 UI 只是抖了一下，下一轮接着等开火
                continue
            # 邀请弹窗是全局的，停在哪个页面都能接，不需要回到组队页（与 Orochi / EvoZone 等一致）
        self.device.stuck_record_clear()

    def _settle_out_of_room(self, timeout: float = 10.0) -> str:
        """离开房间后等界面落定，判断去了哪里。

        `wait_battle` 是一退出房间就返回，此刻往往还在过场动画里，
        直接判页会什么都匹配不上（实测要 5s 左右才稳定成 page_battle_prepare）。

        :return: 'battle' 进了战斗页；'room' 又回到房间；'dismissed' 房间没了
        """
        timer = Timer(timeout).start()
        while not timer.reached():
            self.screenshot()
            if self._in_battle_page():
                return 'battle'
            if self.is_in_room(False):
                return 'room'
        return 'dismissed'

    def _in_battle_page(self) -> bool:
        """当前是否处于战斗相关页面（准备 / 战斗 / 结算 / 奖励）。

        用来分辨 `wait_battle` 返回 True 的两种可能：真被拉进战斗，还是房间没了。
        """

        return self.detect_page_in(
            page_battle_prepare, page_battle, page_battle_result, page_reward,
            include_global=False,
        ) is not None

    def _reach_exit(self, limit_count: int) -> bool:
        """退出判断：剩余次数耗尽 或 打满想打的次数。"""
        self.screenshot()
        # 「剩余次数2/15」DigitCounter 按 x/y 解析成 (x, y-x, y)，首数字是剩余
        left, used, total = self.O_DEMON_COUNT.ocr(self.device.image)
        if total > 0 and left <= 0:
            logger.info(f'Challenge count exhausted: {left}/{total}')
            return True
        if total == 0:
            logger.warning('Challenge count ocr failed, continue by time limit')
        if self.current_count >= limit_count:
            logger.info(f'Reach limit count: {self.current_count}/{limit_count}')
            return True
        return False

    def _run_challenges(self, timeout: Timer, limit_count: int):
        fail_count = 0
        while not timeout.reached():
            if self._reach_exit(limit_count):
                break
            # 点挑战进入战斗；连续点不动说明被弹窗挡住或次数已尽，止损退出
            if not self.appear_then_click(self.I_DEMON_CHALLENGE_FIRE, interval=2):
                fail_count += 1
                if fail_count >= 5:
                    logger.warning('Fire click failed 5 times in a row, abort')
                    break
                continue
            fail_count = 0
            self.run_general_battle(config=self.config.demon_martial_trials.general_battle_config)
