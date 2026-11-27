from module.logger import logger
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import GeneralBattle, BattleContext, BattleAction
from tasks.SixRealms.common import SixRealmsCommon
import tasks.SixRealms.pure_buddha_realm.page as pages


class BasePureBuddhaRealm(GeneralBattle, SixRealmsCommon):
    coin_num: int = 0

    def before_run(self):
        self.coin_num = 0
        pages.page_battle = self.navigator.resolve_page(pages.page_battle)
        pages.page_battle.recognizer = pages.any_of(self.I_BOSS_SKIP, pages.page_battle.recognizer)
        pages.page_battle_result = self.navigator.resolve_page(pages.page_battle_result)
        pages.page_battle_result.recognizer = pages.any_of(self.I_SR_BOSS_AGAIN, self.I_SR_BOSS_GIVEUP,
                                                           self.I_PB_SELECT_4, self.I_PB_WANSHOU,
                                                           self.I_UI_CONFIRM_SAMLL,
                                                           pages.page_battle_result.recognizer)
        pages.page_reward = self.navigator.resolve_page(pages.page_reward)
        pages.page_reward.recognizer = pages.any_of(self.I_COIN, self.I_SR_DOUBLE_REWARD_USE, self.I_SR_BOSS_GET_EXP,
                                                    self.I_PB_BOSS_SHARE, self.I_SR_SETTLE_SHUTU, self.I_SR_SETTLE_RYOU,
                                                    self.I_SR_SKILL_UNLOCK, pages.page_reward.recognizer)

    def _handle_result(self, context: BattleContext, config: GeneralBattleConfig) -> BattleAction:
        context.reward_no_battle_ts = None
        # boss 打输了: 和椒图一样点「諦める」退出这场战斗
        if self.appear(self.I_SR_BOSS_GIVEUP):
            context.is_win = False
            self.click(self.I_SR_BOSS_GIVEUP, interval=0.8)
            return BattleAction.CONTINUE
        # 放弃之后的2次弹窗确认
        if self.appear(self.I_UI_CONFIRM_SAMLL):
            self.click(self.I_UI_CONFIRM_SAMLL, interval=0.8)
            return BattleAction.CONTINUE
        # 四选一页: 标题认页(文字不闪), 再等最右那颗「選択」出现后点它
        if self.appear(self.I_PB_WANSHOU):
            context.is_win = True
            self.wait_until_appear_then_click(self.I_PB_SELECT_4, wait_time=3)
            return BattleAction.CONTINUE
        return BattleAction.CONTINUE

    def _handle_reward(self, context: BattleContext, config: GeneralBattleConfig) -> BattleAction:
        context.reward_no_battle_ts = None
        # 结算页只表示这轮打完了: 极/良 都算完成, 不区分
        if self.appear(self.I_SR_SETTLE_SHUTU) or self.appear(self.I_SR_SETTLE_RYOU):
            context.is_win = True
        if context.is_win and self.appear_then_click(self.I_SR_DOUBLE_REWARD_USE, interval=1.5):
            return BattleAction.CONTINUE
        if not context.is_win and self.appear_then_click(self.I_SR_DOUBLE_REWARD_CANCEL, interval=1.5):
            return BattleAction.CONTINUE
        if self.appear(self.I_SR_CHECK_BUY_BOX):  # 是否前往购买万相赐福
            if self.appear_then_click(self.I_SR_NOT_TIP, interval=1.5) and self.appear_then_click(self.I_UI_CANCEL):
                return BattleAction.CONTINUE
        if self.appear(self.I_COIN, interval=2):
            self.coin_num += self.get_coin_num(self.I_COIN)
            logger.info(f'Current coin: {self.coin_num}')
        self.click(pages.random_click(), interval=1.2)
        if context.last_page != pages.page_reward:
            self.device.click_record_clear()
        return BattleAction.CONTINUE
