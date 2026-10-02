# This Python file uses the following encoding: utf-8
import random
from datetime import timedelta

from module.base.timer import Timer
from module.exception import TaskEnd
from module.logger import logger
from tasks.Component.Buy.buy import Buy
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.RightActivity.right_activity import RightActivity
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.FrogChallenge.assets import FrogChallengeAssets
from tasks.GameUi.page import page_main


class ScriptTask(RightActivity, GeneralBattle, SwitchSoul, Buy, FrogChallengeAssets):
    # 兑换御魂是否已结束
    soul_exchange_done = False

    def run(self):
        if not self._enter_activity():
            logger.warning('Frog Challenge is unavailable')
            self._finish()

        if not self._switch_soul():
            logger.warning('Cannot return to Frog Challenge after switching souls')
            self._finish()

        config = self.config.frog_challenge.frog_challenge_config
        limit = config.limit_time
        timeout = Timer(timedelta(
            hours=limit.hour,
            minutes=limit.minute,
            seconds=limit.second,
        ).total_seconds()).start()

        # 只按时间控制, 次数上限由活动自身的奖励次数决定(挑战按钮出现"免费"即停止)
        while not timeout.reached():
            if not self._enter_battle():
                logger.info('Frog Challenge cannot start another battle')
                break
            self.run_general_battle(
                config=self.config.frog_challenge.general_battle_config,
                battle_key='frog_challenge',
                exit_matcher=self.I_TITLE,
            )

        self._exchange_soul()

        self._finish()

    def _enter_activity(self) -> bool:
        self.goto_page(page_main)
        if not self.ui_click_until_appear_or_timeout(
                self.I_TOGGLE_BUTTON, self.I_ENTRY, interval=2, timeout=20):
            return False

        timeout = Timer(10).start()
        while not timeout.reached():
            self.screenshot()
            if not self.appear(self.I_ENTRY):
                return self._wait_activity()
            self.appear_then_click(self.I_ENTRY, interval=2)
        return False

    def _wait_activity(self) -> bool:
        """等待回到活动界面: 跳过活动剧情, 直到出现活动标题"""
        timeout = Timer(30).start()
        while not timeout.reached():
            self.screenshot()
            if self.appear_then_click(self.I_SKIP, interval=2):
                continue
            if self.appear(self.I_TITLE):
                return True
        return False

    def _switch_soul(self) -> bool:
        config = self.config.frog_challenge.switch_soul
        if not config.enable and not config.enable_switch_by_name:
            return True

        if not self.ui_click_until_appear_or_timeout(
                self.I_SHIKIGAMI_RECORDS, self.I_CHECK_RECORDS, interval=2, timeout=15):
            return False
        if config.enable:
            self.run_switch_soul(config.switch_group_team)
        if config.enable_switch_by_name:
            self.run_switch_soul_by_name(config.group_name, config.team_name)
        self.exit_shikigami_records()
        return self._wait_activity()

    def _enter_battle(self) -> bool:
        """点击挑战按钮进入战斗
        挑战按钮下出现"免费"标签时表示奖励次数已达上限, 停止挑战"""
        timeout = Timer(20).start()
        click_count = 0
        while not timeout.reached():
            self.screenshot()
            if self.is_in_battle(False):
                return True
            if self.appear(self.I_FREE):
                logger.info('Frog Challenge reward count reached limit (free)')
                return False
            if click_count < 3 and self.appear_then_click(self.I_CHALLENGE, interval=2):
                click_count += 1
                continue
        return False

    def _exchange_soul(self) -> bool:
        """兑换御魂: 用神秘骰子积分兑换随机六星御魂, 每10积分兑换一次"""
        config = self.config.frog_challenge.exchange_soul
        if not config.enable:
            return True

        logger.hr('Frog Challenge exchange soul', 1)
        self.soul_exchange_done = False

        # 1. 战斗结束后先等回到活动界面
        if not self._wait_activity():
            logger.warning('Frog Challenge cannot return to activity after battle, skip exchange soul')
            return False

        # 2. 购买:
        if not self._buy_souls():
            logger.warning('Frog Challenge buy souls failed')
            return False

        # 3. 逐个随机选择御魂, 以页面实际状态为准
        success = 0
        select_timeout = Timer(300).start()
        while not select_timeout.reached() and success < 50:
            if self.soul_exchange_done:
                break
            # 等选择页面出现, 购买后第一波需要等它弹出
            if not self._wait_select_page(20):
                if self.appear(self.I_EXCHANGE) and not self.appear(self.I_CHECK_SOUL):
                    # 兜底: 已回到活动界面且选择页面消失
                    logger.info('Frog Challenge back to activity, all souls selected')
                    break
                logger.warning('Frog Challenge soul select page not found')
                break
            if not self._select_soul_once():
                logger.warning(f'Exchange soul {success + 1} failed')
                break
            success += 1
            logger.info(f'Exchange soul {success}')
        logger.info(f'Exchange soul finished: {success}')
        return success > 0

    def _buy_souls(self) -> bool:
        # 点10兑换, 等购买弹窗出现
        timeout = Timer(20).start()
        while not timeout.reached():
            self.screenshot()
            if self.appear(self.I_BUY_PLUS):
                break
            self.appear_then_click(self.I_EXCHANGE, interval=2)
        else:
            logger.warning('Frog Challenge buy dialog not found')
            return False

        # 拉满购买数量
        for _ in range(2):
            self.screenshot()
            self.appear_then_click(self.I_BUY_PLUS, interval=1)

        # 只点一次购买按钮, 之后交给选择页面处理
        self.screenshot()
        self.click(self.C_BUY_MORE)
        logger.info('Frog Challenge buy souls')
        return True

    def _wait_select_page(self, timeout: int = 20) -> bool:
        """等待随机御魂选择页面(check_soul)出现
        结算展示页只在最后一个御魂选完时出现, 由 _select_soul_once 处理, 此处不判断"""
        timer = Timer(timeout).start()
        while not timer.reached():
            self.screenshot()
            if self.appear(self.I_CHECK_SOUL):
                return True
        logger.warning('Frog Challenge soul select page not found')
        return False

    def _select_soul_once(self) -> bool:
        # 随机三选一
        target = random.choice([self.I_SELECT_1, self.I_SELECT_2, self.I_SELECT_3])
        timer = Timer(10).start()
        while not timer.reached():
            self.screenshot()
            if self.appear_then_click(target, interval=1):
                break
        else:
            logger.warning('Frog Challenge select soul failed')
            return False

        timer = Timer(30).start()
        while not timer.reached():
            self.screenshot()
            if self.ui_reward_appear_click():
                continue
            if self.appear(self.I_REWARD):
                # 结算展示页: 出现即代表御魂已兑换完
                logger.info('Frog Challenge soul exchange done')
                self.soul_exchange_done = True
                self._close_reward_page()
                return True
            if self.appear(self.I_CHECK_SOUL) and (
                    self.appear(self.I_SELECT_1)
                    or self.appear(self.I_SELECT_2)
                    or self.appear(self.I_SELECT_3)):
                # 下一批随机御魂已加载
                return True
            if self.appear(self.I_EXCHANGE) and not self.appear(self.I_CHECK_SOUL):
                # 兜底: 全部选择完成, 回到活动界面
                return True
        logger.warning('Frog Challenge exchange page load timeout')
        return False

    def _close_reward_page(self):
        """点击结算展示页直到其关闭"""
        timer = Timer(5).start()
        while not timer.reached():
            self.screenshot()
            if not self.appear(self.I_REWARD):
                return
            self.appear_then_click(self.I_REWARD, interval=1)

    def _finish(self):
        self.set_next_run(task='FrogChallenge', success=True)
        raise TaskEnd('FrogChallenge')


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
