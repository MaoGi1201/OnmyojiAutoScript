# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from module.logger import logger

from tasks.RichMan.mall.medal import Medal
from tasks.RichMan.mall.charisma import Charisma
from tasks.RichMan.mall.consignment import Consignment
from tasks.RichMan.mall.scales import Scales
from tasks.RichMan.mall.honor import Honor
from tasks.RichMan.mall.bondlings import Bondlings
from tasks.RichMan.progress import RichManProgress
from tasks.GameUi.page import page_main, page_mall


class Mall(RichManProgress, Medal, Charisma, Honor, Consignment, Scales, Bondlings):

    def execute_mall(self):
        logger.hr('Mall', 1)
        # 每个子模块单独记进度，报错重跑时只做还没完成的
        steps = [
            ('mall_consignment', self.execute_consignment),  # 寄售屋
            ('mall_scales', self.execute_scales),  # 蛇皮
            ('mall_bondlings', self.execute_bondlings),  # 契灵
            ('mall_special', self.execute_special),  # 杂货铺 特殊
            ('mall_honor', self.execute_honor),  # 杂货铺 荣誉
            ('mall_friendship', self.execute_friendship),  # 杂货铺 友情点
            ('mall_medal', self.execute_medal),  # 杂货铺 勋章
            ('mall_charisma', self.execute_charisma),  # 杂货铺 魅力
        ]
        pending = [(name, func) for name, func in steps if not self.is_step_done(name)]
        if not pending:
            logger.info('Mall: all steps are already done, skip')
            return

        self.goto_page(page_mall, confirm_wait=2.5)

        for name, func in pending:
            self.run_step(name, func)
            self.device.click_record_clear()

        # 退出
        self.back_mall()

        # 原顺序执行（无进度记录），保留备查：
        # self.goto_page(page_mall, confirm_wait=2.5)
        # # 寄售屋
        # self.execute_consignment()
        # self.device.click_record_clear()
        # # 蛇皮
        # self.execute_scales()
        # self.device.click_record_clear()
        # # 契灵
        # self.execute_bondlings()
        # self.device.click_record_clear()
        # # 杂货铺
        # self.execute_special()
        # self.device.click_record_clear()
        # self.execute_honor()
        # self.device.click_record_clear()
        # self.execute_friendship()
        # self.device.click_record_clear()
        # self.execute_medal()
        # self.device.click_record_clear()
        # self.execute_charisma()
        # self.device.click_record_clear()
        # # 退出
        # self.back_mall()

