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
    # 单次最多可兑换的御魂个数, 每 10 个骰子兑换一个
    MAX_EXCHANGE_PER_BATCH = 10

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
        """兑换御魂: 每10个神秘骰子兑换一个随机六星御魂, 单次最多兑10个。
        骰子可以跨天累计, 一批兑满后如果骰子还有剩余就回到活动界面再开一批"""
        config = self.config.frog_challenge.exchange_soul
        if not config.enable:
            return True

        logger.hr('Frog Challenge exchange soul', 1)

        # 1. 战斗结束后先等回到活动界面
        if not self._wait_activity():
            logger.warning('Frog Challenge cannot return to activity after battle, skip exchange soul')
            return False

        # 2. 分批兑换, 每批都会把购买数量拉满
        total = 0
        batch = 0
        exchange_timeout = Timer(600).start()
        while not exchange_timeout.reached():
            batch += 1
            self.screenshot()
            logger.info(f'Frog Challenge exchange batch {batch}')
            if self.appear(self.I_CHECK_SOUL):
                # 上次运行中断在选择页面, 直接接着选, 不要再点兑换
                logger.info('Frog Challenge resume from soul select page')
            elif not self._buy_souls():
                logger.info('Frog Challenge cannot buy souls, exchange finished')
                break
            count = self._select_batch_souls()
            total += count
            logger.info(f'Frog Challenge batch {batch}: {count}, total: {total}')
            # 每批都是拉满购买的, 没换够上限就说明骰子不够再开下一批了
            if count < self.MAX_EXCHANGE_PER_BATCH:
                logger.info(f'Frog Challenge dice used up, {count} in batch {batch}')
                break
            # 骰子可能还有剩余, 回到活动界面再开一批
            if not self._wait_activity():
                logger.warning('Frog Challenge cannot return to activity after batch, stop exchange')
                break

        logger.info(f'Exchange soul finished: {total}')
        return total > 0

    def _buy_souls(self) -> bool:
        """点兑换按钮买一批御魂
        :return: True 已就绪: 购买弹窗出现, 或者已经直接进到御魂选择界面"""
        timeout = Timer(12).start()
        while not timeout.reached():
            self.screenshot()
            # 已经进到御魂选择界面就不用再点兑换了
            if self.appear(self.I_CHECK_SOUL):
                logger.info('Frog Challenge already in soul select page')
                return True
            if self.appear(self.I_BUY_PLUS):
                break
            self.appear_then_click(self.I_EXCHANGE, interval=2)
        else:
            logger.info('Frog Challenge buy dialog not found')
            return False

        # 拉满购买数量: 两次点击之间必须留出间隔, 否则第二次会被 interval 抑制
        self.appear_then_click(self.I_BUY_PLUS, interval=0.4)
        self.device.sleep(0.5)
        self.appear_then_click(self.I_BUY_PLUS, interval=0.4)

        # 只点一次购买按钮, 之后交给选择页面处理
        self.click(self.C_BUY_MORE)
        logger.info('Frog Challenge buy souls')
        return True

    def _select_batch_souls(self) -> int:
        """逐个随机选择御魂: 在御魂选择页面就随机三选一
        :return: 本批成功兑换的个数"""
        count = 0
        timeout = Timer(300).start()
        idle = Timer(20).start()      # 选择页面迟迟不出现, 本批就没有可换的
        while not timeout.reached() and count < self.MAX_EXCHANGE_PER_BATCH:
            self.screenshot()

            # 结算页出现, 本批兑换完成, 点掉它
            if self.appear_then_click(self.I_REWARD, interval=1):
                logger.info('Frog Challenge batch exchange done')
                break

            # 不在选择页面: 购买后需要等它弹出
            if not self.appear(self.I_CHECK_SOUL):
                if idle.reached():
                    logger.info('Frog Challenge select page not appear')
                    break
                continue
            idle.reset()

            # 在御魂选择页面: 随机三选一
            target = random.choice([self.I_SELECT_1, self.I_SELECT_2, self.I_SELECT_3])
            if self.appear_then_click(target, interval=1):
                count += 1
                logger.info(f'Exchange soul {count}')
                # 等这一次的处理动画结束, 否则下一轮会把同一个再选一遍
                self.device.sleep(1)
        return count

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
