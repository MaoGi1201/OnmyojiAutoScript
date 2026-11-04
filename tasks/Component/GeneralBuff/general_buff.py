# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from tasks.Component.GeneralBuff.assets import GeneralBuffAssets
from module.atom.ocr import RuleOcr
from module.atom.image import RuleImage
from tasks.base_task import BaseTask
from module.logger import logger
from typing import Optional


class GeneralBuff(BaseTask, GeneralBuffAssets):

    def open_buff(self):
        """
        打开buff的总界面
        :return:
        """
        logger.info('Open buff')
        while 1:
            self.screenshot()
            if self.appear(self.I_CLOUD):
                break
            if self.appear_then_click(self.I_BUFF_1, interval=2):
                continue

        check_image = self.I_AWAKE
        while 1:
            self.screenshot()
            if self.appear(check_image):
                break

            self.swipe(self.S_BUFF_UP, interval=2)

    def close_buff(self):
        """
        关闭buff的总界面, 但是要确保buff界面已经打开了
        :return:
        """
        logger.info('Close buff')
        while 1:
            self.screenshot()
            if not self.appear(self.I_CLOUD):
                break
            if self.appear_then_click(self.I_BUFF_1, interval=2):
                continue

    def get_area(self, buff: RuleOcr) -> Optional[tuple[int, int, int, int]]:
        """
        获取要点击的开关buff的区域
        :param cls:
        :param image:
        :param buff:
        :return:  如果没有就返回None
        """
        # 防止邀请框挡住BUFF框架
        self.reject_invite()
        self.screenshot()
        result_list = buff.detect_and_ocr(self.device.image)
        area = None
        # 关键词只取稳定的后缀部分（如 "货UP100%"）。
        keyword = buff.keyword.replace(' ', '')
        for result in result_list:
            if keyword in result.ocr_text.replace(' ', ''):
                area = (buff.roi[0] + result.box[0, 0], buff.roi[1] + result.box[0, 1],
                        result.box[1, 0] - result.box[0, 0], result.box[2, 1] - result.box[0, 1])
                break
        if area is None:
            logger.warning(f'Buff [{buff.name}] not matched by {keyword!r}, ocr: '
                           f'{[r.ocr_text for r in result_list]}')
            return None
        # 日服「獲得銭貨UP100%」文字右端 x=608, 开关块在 x=773, 差了 165px,
        # 按 "文字右边+10" 算出来的区域整块落在空白处(实测两枚模板 0.09 / 0.10)。
        # 只取行高度由 OCR 决定, x 固定到开关列。
        start_x = buff.roi[0] + buff.roi[2] - 10
        start_y = area[1] - 10
        width = 130
        height = 45
        return int(start_x), int(start_y), int(width), int(height)

    def set_switch_area(self, area):
        """
        设置开关的区域
        :param area:
        :return:
        """
        self.I_OPEN_YELLOW.roi_back = list(area)  # 动态设置roi
        self.I_CLOSE_RED.roi_back = list(area)

    def gold_50(self, is_open: bool = True) -> bool:
        """
        金币50buff
        :param is_open: 是否打开
        :return: 识别到且操作成功True
        """
        logger.info('Gold 50 buff')
        self.screenshot()
        area = self.get_area(self.O_GOLD_50)
        if not area:
            logger.warning('No gold 50 buff')
            return False
        self.set_switch_area(area)
        if is_open:
            logger.info('Start open gold50 buff')
            self.ui_click(self.I_CLOSE_RED, self.I_OPEN_YELLOW, interval=1)
            return True
        logger.info('Start close gold50 buff')
        self.ui_click(self.I_OPEN_YELLOW, self.I_CLOSE_RED, interval=1)
        return True

    def gold_100(self, is_open: bool = True) -> bool:
        """
        金币100buff
        :param is_open: 是否打开
        :return:
        """
        logger.info('Gold 100 buff')
        self.screenshot()
        area = self.get_area(self.O_GOLD_100)
        if not area:
            logger.warning('No gold 100 buff')
            return False
        self.set_switch_area(area)
        if is_open:
            logger.info('Start open gold100 buff')
            self.ui_click(self.I_CLOSE_RED, self.I_OPEN_YELLOW, interval=1)
            return True
        logger.info('Start close gold100 buff')
        self.ui_click(self.I_OPEN_YELLOW, self.I_CLOSE_RED, interval=1)
        return True

    def exp_50(self, is_open: bool = True) -> bool:
        """
        经验50buff
        :param is_open: 是否打开
        :return:
        """
        logger.info('Exp 50 buff')
        max_swipe = 2
        while True:
            self.screenshot()
            if max_swipe <= 0:
                logger.warning('No exp 50 buff')
                return False
            area = self.get_area(self.O_EXP_50)
            if area:
                self.set_switch_area(area)
            if not area or (not self.appear(self.I_CLOSE_RED) and not self.appear(self.I_OPEN_YELLOW)):
                self.device.swipe(p2=(530, 240), p1=(580, 320))
                max_swipe -= 1
                time.sleep(1)
                continue
            break
        if is_open:
            logger.info('Start open exp50 buff')
            self.ui_click(self.I_CLOSE_RED, self.I_OPEN_YELLOW, interval=1)
            return True
        logger.info('Start close exp50 buff')
        self.ui_click(self.I_OPEN_YELLOW, self.I_CLOSE_RED, interval=1)
        return True

    def exp_100(self, is_open: bool = True) -> bool:
        """
        经验100buff
        :param is_open: 是否打开
        :return:
        """
        logger.info('Exp 100 buff')
        max_swipe = 2
        while True:
            if max_swipe <= 0:
                logger.warning('No exp 100 buff')
                return False
            self.screenshot()
            area = self.get_area(self.O_EXP_100)
            if area:
                self.set_switch_area(area)
            if not area or (not self.appear(self.I_CLOSE_RED) and not self.appear(self.I_OPEN_YELLOW)):
                self.device.swipe(p2=(530, 240), p1=(580, 320))
                max_swipe -= 1
                time.sleep(1)
                continue
            break
        if is_open:
            logger.info('Start open exp100 buff')
            self.ui_click(self.I_CLOSE_RED, self.I_OPEN_YELLOW, interval=1)
            return True
        logger.info('Start close exp100 buff')
        self.ui_click(self.I_OPEN_YELLOW, self.I_CLOSE_RED, interval=1)
        return True

    def get_area_image(self, target: RuleImage) -> Optional[tuple[int, int, int, int]]:
        """
        获取觉醒加成或者是御魂加成所要点击的区域
        因为实在的图片比ocr快
        :param image:
        :param target:
        :return:
        """
        self.reject_invite()
        self.screenshot()

        if not self.appear(target):
            logger.warning(f'No {target.name} buff')
            return None
        start_x = int(target.roi_front[0] + 390)
        start_y = int(target.roi_front[1])
        width = 80
        height = int(target.roi_front[3])
        return start_x, start_y, width, height

    def awake(self, is_open: bool = True):
        """
        觉醒buff
        :param is_open: 是否打开
        :return:
        """
        logger.info('Awake buff')
        self.screenshot()
        area = self.get_area_image(self.I_AWAKE)
        if not area:
            logger.warning('No awake buff')
            return None
        self.set_switch_area(area)
        if is_open:
            logger.info('Start open awake buff')
            self.ui_click(self.I_CLOSE_RED, self.I_OPEN_YELLOW, interval=1)
            return True
        logger.info('Start close awake buff')
        self.ui_click(self.I_OPEN_YELLOW, self.I_CLOSE_RED, interval=1)
        return True

    def soul(self, is_open: bool = True):
        """
        御魂buff
        :param is_open: 是否打开
        :return:
        """
        logger.info('Soul buff')
        self.screenshot()
        area = self.get_area_image(self.I_SOUL)
        if not area:
            logger.warning('No soul buff')
            return None
        self.set_switch_area(area)
        if is_open:
            logger.info('Start open soul buff')
            self.ui_click(self.I_CLOSE_RED, self.I_OPEN_YELLOW, interval=1)
            return True
        logger.info('Start close soul buff')
        self.ui_click(self.I_OPEN_YELLOW, self.I_CLOSE_RED, interval=1)
        return True

    def reject_invite(self):
        from tasks.Component.GeneralInvite.assets import GeneralInviteAssets as gia
        while 1:
            self.screenshot()
            if not (self.appear(gia.I_I_REJECT_1) or self.appear(gia.I_I_REJECT_2) or self.appear(gia.I_I_REJECT_3)):
                break
            if self.appear(gia.I_I_REJECT_3):
                self.click(gia.I_I_REJECT_3, 6)
                continue
            if self.appear(gia.I_I_REJECT_2):
                self.click(gia.I_I_REJECT_2, 6)
                continue
            if self.appear(gia.I_I_REJECT_1):
                self.click(gia.I_I_REJECT_1, 6)
                continue


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('日常2')
    d = Device(c)
    t = GeneralBuff(c, d)

    t.awake(is_open=True)
