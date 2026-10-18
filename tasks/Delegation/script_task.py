# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import time, datetime, timedelta

from module.logger import logger
from module.exception import TaskEnd
from module.base.timer import Timer

from module.atom.ocr import RuleOcr
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_delegation
from tasks.Delegation.config import DelegationConfig
from tasks.Delegation.assets import DelegationAssets


class ScriptTask(GameUi, DelegationAssets):

    def run(self):
        self.goto_page(page_delegation)
        self.check_reward()
        con: DelegationConfig = self.config.delegation.delegation_config
        if con.miyoshino_painting:
            self.delegate_one('画')
        if con.bird_feather:
            self.delegate_one('鸟羽')
        if con.find_earring:
            self.delegate_one('寻找耳环')
        if con.cat_boss:
            self.delegate_one('猫老大')
        if con.miyoshino:
            self.delegate_one('接送')
        if con.strange_trace:
            self.delegate_one('痕迹')


        self.set_next_run(task='Delegation', success=True, finish=True)
        raise TaskEnd

    def delegate_one(self, name: str) -> bool:
        """
        委派一个任务
        :param name:
        :return:
        """
        logger.hr('Delegation one', 2)
        self.O_D_NAME.keyword = name
        self.screenshot()
        if not self.ocr_appear(self.O_D_NAME):
            logger.warning(f'Delegation: {name} not found')
            return False
        if not self.open_delegation(self.O_D_NAME):
            return False
        logger.info(f'Enter Delegation: {name}')
        self.dispatch()
        return True

    def open_delegation(self, enter) -> bool:
        """点任务（名字OCR/卡片/地图气泡）直到出发按钮出现。

        :param enter: 点击目标，RuleOcr 按名字点，RuleImage 按图点
        :return: 是否进入委派面板
        """
        timer = Timer(15).start()
        chat_click = 0
        while not timer.reached():
            self.screenshot()
            if self.appear(self.I_D_START):
                return True
            # 如果出现’召回‘ ’返回‘ 说明这个是现在委派中，需要退出
            if self.appear(self.I_D_BACK):
                logger.warning('Delegation: task is in delegation')
                self.ui_click_until_disappear(self.I_D_BACK)
                self.wait_until_appear(self.I_REWARDS_MIN)
                return False
            if self.appear_then_click(self.I_D_SKIP, interval=0.8):
                continue
            if self.appear_then_click(self.I_D_CONFIRM, interval=0.8):
                continue
            if isinstance(enter, RuleOcr):
                if self.ocr_appear_click(enter, interval=1):
                    continue
            elif self.appear_then_click(enter, interval=2):
                continue
            # 没有跳过按钮的对话框：点屏幕中部推进
            if self.click(self.C_D_CHAT, interval=0.8):
                chat_click += 1
                if chat_click >= 6:
                    logger.warning('Delegation chat too long, reset click record')
                    chat_click = 0
                    self.device.click_record_clear()
        logger.warning('Delegation task not opened')
        return False

    def dispatch(self) -> bool:
        """上阵式神并出发：默认一键选择，出发不动时退回逐个选人。"""
        if self.config.delegation.delegation_config.auto_select_enable:
            if not self.appear_then_click(self.I_D_AUTO_SELECT, interval=1):
                logger.warning('Delegation: auto select not found, fallback to manual')
            if self.click_start():
                return True
            logger.warning('Delegation: start failed after auto select, fallback to manual')
        self.select_shikigami()
        return self.click_start()

    def select_shikigami(self):
        """逐个点候选位上阵，选不动（槽位已满）即停。"""
        for click, selected in ((self.C_D_1, self.I_D_SELECT_1), (self.C_D_2, self.I_D_SELECT_2),
                                (self.C_D_3, self.I_D_SELECT_3), (self.C_D_4, self.I_D_SELECT_4),
                                (self.C_D_5, self.I_D_SELECT_5)):
            if not self.ui_click_until_appear_or_timeout(click, selected, interval=1, timeout=6):
                break

    def click_start(self) -> bool:
        """点出发直到面板关闭（含确认弹窗），返回是否成功出发。"""
        timer = Timer(10).start()
        while not timer.reached():
            self.screenshot()
            if not self.appear(self.I_D_START):
                return True
            if self.appear_then_click(self.I_D_CONFIRM, interval=1.5):
                continue
            self.appear_then_click(self.I_D_START, interval=1.8)
        return False

    def check_reward(self):
        check_timer = Timer(3)
        check_timer.start()
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_REWARDS_GET, interval=1):
                check_timer.reset()
                continue
            if self.appear_then_click(self.I_REWARDS_CHAT, interval=1):
                check_timer.reset()
                continue
            if self.appear_then_click(self.I_CHAT_1, interval=1):
                check_timer.reset()
                continue
            if self.appear_then_click(self.I_CHAT_2, interval=1):
                check_timer.reset()
                continue
            if self.appear_then_click(self.I_REWARDS_DONE, interval=1):
                check_timer.reset()
                continue
            if self.appear_then_click(self.I_REWARDS_FALSE, interval=1):
                check_timer.reset()
                continue


            if not self.appear(self.I_REWARDS_MIN):
                continue
            if check_timer.reached():
                break
            if self.ocr_appear(self.O_D_DONE, interval=1):
                x, y, w, h = self.O_D_DONE.area
                self.device.click(x=int(x + w // 2), y=int(y + 68),
                                  control_name='D_DONE')
                check_timer.reset()
                continue


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    from memory_profiler import profile
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    # t.delegate_one('弥助的画')
    t.run()




