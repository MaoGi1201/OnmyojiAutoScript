# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

import cv2
import random
import numpy as np

from random import randint

from module.ocr.boxed_result import BoxedResult
from module.atom.ocr import RuleOcr
from module.atom.image import RuleImage
from module.image.rpc import get_image_client
from module.logger import logger


class RuleList:

    def __init__(self, folder: str, direction: str, mode: str, roi_back: tuple, size: tuple, array: list[str]) -> None:
        """
        初始化
        :param folder:
        :param direction:
        :param mode:
        :param roi_back:
        :param size:
        :param array:
        """
        self.folder = folder
        self.is_vertical = direction == "vertical"
        self.is_image = mode == "image"
        self.is_ocr = mode == "ocr"
        self.roi_back: list = list(roi_back)
        self.size: list = list(size)
        # 这个表示一个区域中一次所能显示的最大数量
        self.max_show: int = self.roi_back[3] // self.size[1] if self.is_vertical else self.roi_back[2] // self.size[0]

        self.array: list = array

        # 以下是需要计算的
        self.appear_area: list = None  # 出现的区域
        self.is_bottom = False  # 表示是否已经滑动到底部了
        self._target = None  # 目标
        self.targets = {}  # 目标列表 只是针对image

    @property
    def name(self):
        return f'RuleList[{self.__hash__()}]'

    def __hash__(self):
        return hash((self.folder, self.is_vertical, self.is_image, self.is_ocr, tuple(self.roi_back), tuple(self.size), tuple(self.array)))

    def swipe_pos(self, number: int=2, after: bool=True) -> tuple:
        """
        返回滑动的起始位置和终点位置
        :param number:
        :param after:
        :return:
        """
        center: tuple = self.roi_back[0] + self.roi_back[2] // 2, self.roi_back[1] + self.roi_back[3] // 2
        distance: int = self.size[1] * number if self.is_vertical else self.size[0] * number
        random_start: int = randint(- self.size[0] // 4, self.size[0] // 4) if self.is_vertical else randint(- self.size[1] // 4, self.size[1] // 4)
        random_end: int = randint(- self.size[0] // 4, self.size[0] // 4) if self.is_vertical else randint(- self.size[1] // 4, self.size[1] // 4)

        x1, y1, x2, y2 = None, None, None, None
        if self.is_vertical:
            if after:
                # 竖直方向向下滑动， 那就是起始点是在下面 终点是在上面
                x1, y1 = center[0]+random_start, center[1] + distance//2
                x2, y2 = center[0]+random_end, center[1] - distance//2
            else:
                # 竖直方向向上滑动， 那就是起始点是在上面 终点是在下面
                x1, y1 = center[0]+random_start, center[1] - distance//2
                x2, y2 = center[0]+random_end, center[1] + distance//2
        else:
            if after:
                # 水平方向向右滑动， 那就是起始点是在右面 终点是在左面
                x1, y1 = center[0] + distance//2, center[1]+random_start
                x2, y2 = center[0] - distance//2, center[1]+random_end
            else:
                # 水平方向向左滑动， 那就是起始点是在左面 终点是在右面
                x1, y1 = center[0] - distance//2, center[1]+random_start
                x2, y2 = center[0] + distance//2, center[1]+random_end

        if x1 is None or y1 is None or x2 is None or y2 is None:
            raise Exception("滑动位置计算错误")
        return int(x1), int(y1), int(x2), int(y2)

    def target_check(self, name: str) -> bool:
        """
        检查输入的名称
        :param name:
        :return:
        """
        # 首先获取构建类的信息
        # roi_front = None
        # for item in self.array:
        #     if item["itemName"] == name:
        #         roi_front = item["roiFront"].split(",")
        #         break
        # if roi_front is None:
        #     logger.error(f'Not found {name} in {self.array}')
        #     return False
        file = self.folder + "/" + name + ".png"

        # 保证匹配的目标 是正确的
        if self.is_image:
            if self._target is None or isinstance(self._target, RuleOcr):
                self._target = RuleImage(roi_front=self.roi_back, roi_back=self.roi_back, method="Template matching", threshold=0.8, file=file)
            # 如果不对的话，就重新构建
            elif self._target.name != name:
                self._target = RuleImage(roi_front=self.roi_back, roi_back=self.roi_back, method="Template matching", threshold=0.8, file=file)
            else:
                pass
        elif self.is_ocr:
            if self._target is None or isinstance(self._target, RuleImage):
                self._target = RuleOcr(roi=self.roi_back, area=(0, 0, 10, 10), mode="Full", method="Default",
                                       keyword=name, name=name)
            elif self._target.name != name:
                self._target.name = name
                self._target.keyword = name
        else:
            logger.error(f'Not found {name} in {self.array}')
            return False

    def targets_check(self, targets: list):
        """
        检查输入的图片名是缓存有
        :param targets:
        :return:
        """
        for item in targets:
            if item in self.targets:
                continue
            # 如果还没有缓存的话就先缓存
            file = self.folder + "/" + item + ".png"
            self.targets[item] = RuleImage(roi_front=self.roi_back, roi_back=self.roi_back,
                                           method="Template matching", threshold=0.8, file=file)

    def image_appear(self, image: np.array, name: str, frame_id: str = None) -> bool | tuple:
        """
        判断是否出现了某个图片
        :param image: 屏幕的截图
        :param name:
        :return: 如果在当前的显示中，返回可以点击的坐标.如果不是出现就是返回False
        """
        if self.is_image and isinstance(name, str):
            self.target_check(name)
            appear = self._target.match(image, frame_id=frame_id)
            if appear:
                return self._target.coord()
            else:
                return False
        elif self.is_image and isinstance(name, list):
            self.targets_check(name)
            rules = [self.targets[item] for item in name]
            results = get_image_client().match_many(
                rules_data=[rule.to_service_payload() for rule in rules],
                image=image,
                frame_id=frame_id,
            )
            for rule, result in zip(rules, results):
                if rule._apply_match_result(result):
                    return rule.coord()
            return False

        else:
            logger.error(f'Mode is not image')
            return False

    # 日服层数标签用的是异体字/新字体（如「壱階」「弐階」「参階」），
    # 而配置里写的是国服简体（「壹层」「贰层」「叁层」）。
    # 层数列表只靠**首字**（序号）区分，所以这里只需要覆盖序号用字。
    # 只收录已用真实日服截图核实过的映射；没核实过的不要凭猜测加，否则会引入误匹配。
    # 注意：壱/弐 虽然在这里，但中文模型字典里根本没有这两个字（输出不了），
    # 所以「壹层/贰层」在日服仍然无解，只能走图像匹配。
    NUMERAL_VARIANT = {
        '壹': '壱', '贰': '弐', '叁': '参', '肆': '肆', '伍': '伍',
        '陆': '陸', '柒': '漆', '捌': '捌', '玖': '玖', '拾': '拾',
    }

    @classmethod
    def _normalize_numeral(cls, char: str) -> str:
        """把日服序号异体字归一化回国服写法（参→叁），便于和 array 对齐。"""
        if not char:
            return char
        for cn, jp in cls.NUMERAL_VARIANT.items():
            if char == jp:
                return cn
        return char

    def _is_key_list(self, name: str) -> bool:
        """判断 array 存的是不是「首字」。

        两种列表形态：
        - 层数列表：array = ["壹","贰","叁","肆"]，存的是**首字**。
          日服把「肆层」渲染成「肆階」，OCR 末字常读错（階→楷/偕/皆），
          整串比较永远不等；但首字（层号）是稳的 → 按首字匹配。
        - 其它列表：array = ["道馆","首领"] / ["探索（困难）", ...] 等完整标签
          → 保持整串比较，行为不变。
        """
        return bool(name) and name[0] in self.array

    def _match_keys(self, name: str) -> tuple[str, ...]:
        """首字列表时，返回可接受的首字候选（国服写法 + 日服异体字）。"""
        if not self._is_key_list(name):
            return ()
        keys = [name[0]]
        variant = self.NUMERAL_VARIANT.get(name[0])
        if variant and variant not in keys:
            keys.append(variant)
        return tuple(keys)

    def _is_clipped(self, box) -> bool:
        """检测框是否被 ROI 上下边裁掉了一部分。

        列表可以滚动，滚到边缘时首/末项会被 ROI 裁掉。这种框的中心会偏离
        真实文字位置，点上去会落空（实测：神罚在列表底部被裁，检测框中心
        比真实文字高 30px，点击后层数没切换）。
        必须跳过这种框，让 list_find 继续滚动，把它滚进完整可见区再点。
        """
        roi_h = self.roi_back[3]
        y0, y1 = float(box[0][1]), float(box[2][1])
        return y0 <= 2 or y1 >= roi_h - 2

    def ocr_appear(self, image: np.array, name: str):
        """
        判断是否出现了某个文字,
        :param image: 屏幕的截图
        :param name:
        :return: 如果是出现的返回可以点击的坐标 x , y
        如果是在当前显示的前面则返回小于零的int, 如果是在当前显示的后面则返回大于零的int,
        无法判断方向时返回 False
        """
        if self.is_image:
            return False
        self.target_check(name)

        # 开始一次ocr的检测
        boxed_results: list[BoxedResult] = self._target.detect_and_ocr(image)
        if not boxed_results:
            logger.warning(f'Not angy result in image')
            return False

        # 首字列表（层数）走首字匹配，其余保持整串相等
        keys = self._match_keys(name)

        box = None
        for item in boxed_results:
            if not item.ocr_text or item.score <= RuleOcr.score:
                continue
            if keys and self._is_clipped(item.box):
                # 首字列表（层数）可以滚动：贴边的框中心不可信，
                # 跳过它让调用方继续滚动，滚到完整可见再点
                logger.info(f'Skip clipped item {item.ocr_text!r} '
                            f'(y {item.box[0][1]:.0f}..{item.box[2][1]:.0f}, roi_h={self.roi_back[3]})')
                continue
            if keys:
                # 只比首字：日服「肆階」会被读成「肆偕」，末字不可信但层号可信
                if item.ocr_text[0] in keys:
                    box = item.box
                    break
            elif item.ocr_text == name:
                box = item.box
                break

        if box is not None:
            rec_x, rec_y, rec_w, rec_h = box[0, 0], box[0, 1], box[1, 0] - box[0, 0], box[2, 1] - box[0, 1]
            x = rec_x + rec_w // 2 + self.roi_back[0]
            y = rec_y + rec_h // 2 + self.roi_back[1]
            logger.info(f'Ocr {name} appear in current screen, do not need to scroll')
            return x, y

        # 没有直接命中：用当前可见项推断目标在列表中的相对位置，决定往前还是往后翻
        visible_texts = [item.ocr_text for item in boxed_results
                         if item.ocr_text and item.score > RuleOcr.score]
        if keys:
            # 首字列表：把日服异体字归一化后再与 array 对齐
            visible = [self._normalize_numeral(text[0]) for text in visible_texts]
            visible = [char for char in visible if char in self.array]
            target_key = name[0]
        else:
            visible = [text for text in visible_texts if text in self.array]
            target_key = name

        if target_key not in self.array:
            # 配置里的目标和列表定义对不上，滑多少次都没用，直接放弃避免白滑
            logger.warning(f'{name} not in {self.array}, cannot decide swipe direction')
            return False

        logger.info(f'After list: {visible}')
        if not visible:
            logger.warning(f'Not found {name} in {self.array}')
            return 2

        start_index = self.array.index(visible[0])
        end_index = self.array.index(visible[-1])
        current_index = self.array.index(target_key)
        distance_start = 0
        distance_end = 0
        if current_index < start_index or current_index > end_index:
            distance_start = current_index - start_index
            distance_end = current_index - end_index
        # 如果目标的是在当前的显示的前面， 则distance为负的
        # 如果目标的是在当前的显示的后面， 则distance为正的
        # 所有前面返回的是负的，后面返回的是正的
        if distance_start == 0 and distance_end == 0:
            logger.error(f'{name} not found in {visible}')

        return (distance_start + distance_end) // 2


if __name__ == '__main__':
    L_N33AME = RuleList(folder="./tasks/Orochi/res", direction="vertical", mode="ocr", roi_back=(160, 130, 317, 500),
                        size=(301, 86),
                        array=["壹层", "贰层", "叁层", "肆层", "伍层", "陆层", "柒层", "捌层", "玖层", "拾层", "悲鸣", "神罚"])
    image = cv2.imread("D:/watu_list_text204237.png")
    print(L_N33AME.ocr_appear(image, "柒层"))
    print(L_N33AME.ocr_appear(image, "神罚"))
