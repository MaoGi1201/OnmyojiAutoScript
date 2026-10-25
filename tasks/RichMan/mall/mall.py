# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime

from module.logger import logger

from tasks.RichMan.mall.medal import Medal
from tasks.RichMan.mall.consignment import Consignment
from tasks.RichMan.mall.scales import Scales
from tasks.RichMan.mall.honor import Honor
from tasks.RichMan.mall.bondlings import Bondlings
from tasks.GameUi.page import page_main, page_mall


class Mall(Medal, Honor, Consignment, Scales, Bondlings):

    # ---------------- 购买进度：卡死重跑时跳过已完成的段 ----------------
    # 存在已有配置文件里（rich_man.saved_params），配置页用 dynamic_hide 隐藏。
    # 跨天自动清空；全部跑完也会清空。

    def _saved_params(self):
        sp = self.config.model.rich_man.saved_params
        today = datetime.now().strftime('%Y-%m-%d')
        if sp.save_date != today:
            if sp.done:
                logger.info(f'RichMan progress: {sp.save_date} -> {today}, reset')
            sp.save_date = today
            sp.done = ''
            self.config.save()
        return sp

    @staticmethod
    def _parse_done(done: str) -> list[str]:
        return [item for item in done.split(';') if item]

    def run_step(self, key: str, func):
        """跑一个购买段。

        已打标记的直接跳过；只有正常跑完才打标记，
        中途抛异常（含卡死）不会标记，下次重跑会从这一段继续。
        """
        sp = self._saved_params()
        done = self._parse_done(sp.done)
        if key in done:
            logger.info(f'RichMan: skip [{key}], already done today')
            return
        func()
        done.append(key)
        sp.done = ';'.join(done)
        self.config.save()
        logger.info(f'RichMan progress: mark [{key}] done')

    def progress_clear(self):
        """全部跑完，清空进度。"""
        sp = self.config.model.rich_man.saved_params
        if not sp.done:
            return
        sp.done = ''
        self.config.save()
        logger.info('RichMan progress: all done, cleared')

    def execute_mall(self):
        logger.hr('Mall', 1)
        self.goto_page(page_mall, confirm_wait=2.5)

        # 寄售屋
        self.run_step('mall.consignment', self.execute_consignment)
        self.device.click_record_clear()
        # 蛇皮
        self.run_step('mall.scales', self.execute_scales)
        self.device.click_record_clear()
        # 契灵
        self.run_step('mall.bondlings', self.execute_bondlings)
        self.device.click_record_clear()

        # 杂货铺
        self.run_step('mall.special', self.execute_special)
        self.device.click_record_clear()
        self.run_step('mall.honor', self.execute_honor)
        self.device.click_record_clear()
        self.run_step('mall.friendship', self.execute_friendship)
        self.device.click_record_clear()
        self.run_step('mall.medal', self.execute_medal)
        self.device.click_record_clear()

        # 退出
        self.back_mall()
