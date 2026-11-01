# This Python file uses the following encoding: utf-8
"""OCR 后端：RapidOCR(onnxruntime) + PP-OCRv6，单模型同时支持简中、繁中、英文、日文。"""
from typing import List, Optional, Tuple

import cv2
import numpy as np
from rapidocr import RapidOCR

from module.ocr.boxed_result import BoxedResult

# 检测前把过小的图放大到短边 128：PP-OCRv6 检测对 ~14px 的小字
DET_MIN_SHORT_SIDE = 128


class TextSystem:
    def __init__(
            self,
            use_angle_cls=False,
            box_thresh=0.4,
            unclip_ratio=1.6,
    ):
        self.use_angle_cls = use_angle_cls
        self._engine = RapidOCR(params={
            'Global.log_level': 'error',
            # 竖排补边会把宽扁的 ROI 放大，游戏界面用不上
            'Global.use_vertical_padding': False,
            # 最长边超过 960 才缩小；过小的图由 _det_scale 放大到短边 128
            'Det.limit_side_len': 960,
            'Det.limit_type': 'max',
            'Det.box_thresh': box_thresh,
            'Det.unclip_ratio': unclip_ratio,
        })

    def ocr_single_line(self, image: np.ndarray) -> Tuple[str, float]:
        if image is None or image.size == 0:
            return '', 0.
        result = self._engine(image, use_det=False, use_cls=False, use_rec=True)
        txts = getattr(result, 'txts', None)
        if not txts:
            return '', 0.
        return txts[0], float(result.scores[0])

    def detect_and_ocr(
            self,
            image: np.ndarray,
            drop_score: float = 0.5,
            unclip_ratio: Optional[float] = None,
            box_thresh: Optional[float] = None,
            vertical: bool = False,
    ) -> List[BoxedResult]:
        if image is None or image.size == 0:
            return []
        scale = self._det_scale(image)
        if scale > 1.0:
            image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
        if vertical:
            results = self._detect_and_ocr_vertical(image, drop_score, unclip_ratio, box_thresh)
        else:
            results = self._detect_and_ocr_horizontal(image, drop_score, unclip_ratio, box_thresh)
        if scale > 1.0:
            for item in results:
                item.box = (item.box / scale).astype(np.int32)
        return results

    @staticmethod
    def _det_scale(image: np.ndarray) -> float:
        short_side = min(image.shape[:2])
        if short_side >= DET_MIN_SHORT_SIDE:
            return 1.0
        return DET_MIN_SHORT_SIDE / short_side

    def _detect_and_ocr_horizontal(
            self,
            image: np.ndarray,
            drop_score: float,
            unclip_ratio: Optional[float],
            box_thresh: Optional[float],
    ) -> List[BoxedResult]:
        result = self._engine(
            image,
            use_det=True,
            use_cls=self.use_angle_cls,
            use_rec=True,
            text_score=drop_score,
            unclip_ratio=unclip_ratio,
            box_thresh=box_thresh,
        )
        boxes = getattr(result, 'boxes', None)
        if boxes is None:
            return []
        return [
            BoxedResult(np.array(box, dtype=np.int32), None, txt, float(score))
            for box, txt, score in zip(boxes, result.txts, result.scores)
        ]

    def _detect_and_ocr_vertical(
            self,
            image: np.ndarray,
            drop_score: float,
            unclip_ratio: Optional[float],
            box_thresh: Optional[float],
    ) -> List[BoxedResult]:
        """竖排文本：整图旋转 90° 识别，再把框映射回原图。"""
        rotated = np.rot90(image)
        result = self._engine(
            rotated,
            use_det=True,
            use_cls=self.use_angle_cls,
            use_rec=True,
            text_score=drop_score,
            unclip_ratio=unclip_ratio,
            box_thresh=box_thresh,
        )
        boxes = getattr(result, 'boxes', None)
        if boxes is None:
            return []
        boxes = np.array(boxes, dtype=np.float32)
        width = image.shape[1]
        x = width - 1 - boxes[..., 1]
        y = boxes[..., 0].copy()
        boxes[..., 0], boxes[..., 1] = x, y
        return [
            BoxedResult(np.array(box, dtype=np.int32), None, txt, float(score))
            for box, txt, score in zip(boxes, result.txts, result.scores)
        ]
