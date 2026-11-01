# This Python file uses the following encoding: utf-8
"""PP-OCRv5 mobile 文本检测 + 识别实现。

替代 ``module/ocr/ppocr.py`` 里 ppocronnx 的「v2 识别 + v3 检测」组合。
对外接口与 ``ppocronnx.predict_system.TextSystem`` 完全一致，因此
``module/ocr/rpc.py`` 和 tasks 下的 RuleOcr 都不需要改动：

- ``ocr_single_line(img) -> (text, score) | None``
- ``ocr_lines(img_list) -> list[tuple[str, float]]``
- ``detect_and_ocr(img, drop_score, unclip_ratio, box_thresh) -> list[BoxedResult]``
- ``set_char_whitelist(chars)``
- ``text_recognizer`` 必须是可调用对象：rpc.py 的竖排模式会临时替换它

模型放在 ``module/ocr/models/ppocrv5/``：

======================  ========  ==================================
ch_PP-OCRv5_det_mobile   4.8 MB   文本检测
ch_PP-OCRv5_rec_mobile  16.6 MB   文本识别（输出 18385 类）
ppocrv5_dict.txt          74 KB   字典 18383 字
======================  ========  ==================================

onnx 原始文件是 IR version 10，项目锁定的 onnxruntime 1.16.3 最高只支持
IR 9，所以仓库里的 onnx 已把 ModelProto.ir_version 从 10 降到 9
（文件头 ``08 0a`` -> ``08 09``）。日后若升级 onnxruntime 到 1.18+，
可以直接换回官方原件，用法不变。
"""

import math
import os

import cv2
import numpy as np
import onnxruntime as ort

from ppocronnx.det.postprocess import DBPostProcess
from ppocronnx.det.preprocess import (
    DetResizeForTest,
    NormalizeImage,
    ToCHWImage,
    KeepKeys,
)
from ppocronnx.rec.rec_decoder import CTCLabelDecode
from ppocronnx.predict_system import BoxedResult, get_rotate_crop_image

# sorted_boxes 沿用 ppocr.py 里那份（来自 PaddleOCR 2.6，比 ppocr-onnx 自带的好），
# 顺带避免两套排序逻辑产生不一致的阅读顺序。
from module.ocr.ppocr import sorted_boxes

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models', 'ppocrv5')

DET_MODEL_NAME = 'ch_PP-OCRv5_det_mobile.onnx'
REC_MODEL_NAME = 'ch_PP-OCRv5_rec_mobile.onnx'
DICT_NAME = 'ppocrv5_dict.txt'

# 检测模型的输入缩放。与 RapidOCR 的 PP-OCRv5 配置一致：短边补到 736。
# 注意 ppocronnx 的模块级 preprocess_op 把参数名写成 det_limit_type，
# 而 DetResizeForTest 读的是 limit_type，导致它永远退化成 min + 960，
# 小 ROI 会被放大到 960x960 白跑。这里显式传 limit_type，绕开那个坑。
DET_LIMIT_SIDE_LEN = 736
DET_LIMIT_TYPE = 'min'

# v5 识别模型输入高固定 48（v2/v3 是 32），宽度随长宽比动态。
REC_IMAGE_SHAPE = [3, 48, 320]
REC_BATCH_NUM = 6


def _read_dict(path: str) -> list:
    """按行读字典，与 ppocronnx 的 get_character_dict 保持一致（splitlines）。"""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().splitlines()


def _transform(data, ops):
    for op in ops:
        data = op(data)
        if data is None:
            return None
    return data


def _build_session(model_path: str, providers=None) -> tuple:
    if providers is None:
        providers = ['CPUExecutionProvider']
    so = ort.SessionOptions()
    so.log_severity_level = 3
    sess = ort.InferenceSession(model_path, so, providers=providers)
    return sess, sess.get_inputs()[0]


class TextDetector(object):
    """v5 检测。前后处理复用 ppocronnx 的实现，只换模型和缩放策略。"""

    def __init__(self, box_thresh=0.6, unclip_ratio=1.6, det_model_path=None,
                 ort_providers=None,
                 limit_side_len=DET_LIMIT_SIDE_LEN, limit_type=DET_LIMIT_TYPE):
        self.det_algorithm = 'DB'
        self.box_thresh = box_thresh
        self.unclip_ratio = unclip_ratio
        self.preprocess_op = [
            DetResizeForTest(limit_side_len=limit_side_len, limit_type=limit_type),
            NormalizeImage(mean=[0.485, 0.456, 0.406],
                           std=[0.229, 0.224, 0.225],
                           scale='1./255.', order='hwc'),
            ToCHWImage(),
            KeepKeys(keep_keys=['image', 'shape']),
        ]
        self.postprocess_op = DBPostProcess(thresh=0.3, max_candidates=1000,
                                            use_dilation=True)
        model_path = det_model_path or os.path.join(MODEL_DIR, DET_MODEL_NAME)
        self.predictor, self.input_tensor = _build_session(model_path, ort_providers)
        self.output_tensors = None

    def order_points_clockwise(self, pts):
        x_sorted = pts[np.argsort(pts[:, 0]), :]
        left_most = x_sorted[:2, :]
        right_most = x_sorted[2:, :]
        left_most = left_most[np.argsort(left_most[:, 1]), :]
        (tl, bl) = left_most
        right_most = right_most[np.argsort(right_most[:, 1]), :]
        (tr, br) = right_most
        return np.array([tl, tr, br, bl], dtype='float32')

    def filter_tag_det_res(self, dt_boxes, image_shape):
        img_height, img_width = image_shape[0:2]
        dt_boxes_new = []
        for box in dt_boxes:
            box = self.order_points_clockwise(box)
            for pno in range(box.shape[0]):
                box[pno, 0] = int(min(max(box[pno, 0], 0), img_width - 1))
                box[pno, 1] = int(min(max(box[pno, 1], 0), img_height - 1))
            rect_width = int(np.linalg.norm(box[0] - box[1]))
            rect_height = int(np.linalg.norm(box[0] - box[3]))
            if rect_width <= 3 or rect_height <= 3:
                continue
            dt_boxes_new.append(box)
        return np.array(dt_boxes_new)

    def __call__(self, img, unclip_ratio=None, box_thresh=None):
        if unclip_ratio is None:
            unclip_ratio = self.unclip_ratio
        if box_thresh is None:
            box_thresh = self.box_thresh
        ori_im = img.copy()
        data = _transform({'image': img}, self.preprocess_op)
        if data is None:
            return None, 0
        img, shape_list = data
        img = np.expand_dims(img, axis=0)
        shape_list = np.expand_dims(shape_list, axis=0)
        img = img.copy()

        outputs = self.predictor.run(self.output_tensors,
                                     {self.input_tensor.name: img})
        preds = {'maps': outputs[0]}
        post_result = self.postprocess_op(preds, shape_list, unclip_ratio, box_thresh)
        dt_boxes = post_result[0]['points']
        dt_boxes = self.filter_tag_det_res(dt_boxes, ori_im.shape)
        return dt_boxes, 0


class TextRecognizer(object):
    """v5 识别。复用 ppocronnx 的 CTC 解码，换字典和输入高（32 -> 48）。"""

    def __init__(self, rec_model_path=None, dict_path=None, ort_providers=None):
        self.rec_image_shape = list(REC_IMAGE_SHAPE)
        self.rec_batch_num = REC_BATCH_NUM
        self.rec_algorithm = 'CRNN'
        self.character_dict = _read_dict(dict_path or os.path.join(MODEL_DIR, DICT_NAME))

        # use_space_char=True 时 CTCLabelDecode 组出 ['blank'] + 字典 + [' ']，
        # 长度 1 + 18383 + 1 = 18385，与模型输出类数一致。
        self.postprocess_op = CTCLabelDecode(character_dict=self.character_dict,
                                             character_type='ch',
                                             use_space_char=True)
        model_path = rec_model_path or os.path.join(MODEL_DIR, REC_MODEL_NAME)
        self.predictor, self.input_tensor = _build_session(model_path, ort_providers)
        self.output_tensors = None

    def resize_norm_img(self, img, max_wh_ratio):
        img_c, img_h, _ = self.rec_image_shape
        assert img_c == img.shape[2]
        img_w = int(img_h * max_wh_ratio)
        h, w = img.shape[:2]
        ratio = w / float(h)
        resized_w = min(img_w, int(math.ceil(img_h * ratio)))
        if resized_w <= 0:
            resized_w = 1
        resized_image = cv2.resize(img, (resized_w, img_h))
        resized_image = resized_image.astype('float32')
        resized_image = resized_image.transpose((2, 0, 1)) / 255
        resized_image -= 0.5
        resized_image /= 0.5
        padding_im = np.zeros((img_c, img_h, img_w), dtype=np.float32)
        padding_im[:, :, 0:resized_w] = resized_image
        return padding_im

    def set_char_whitelist(self, chars):
        self.postprocess_op.set_char_mask(chars)

    def __call__(self, img_list):
        img_num = len(img_list)
        if img_num == 0:
            return [], 0
        width_list = [img.shape[1] / float(img.shape[0]) for img in img_list]
        indices = np.argsort(np.array(width_list))

        rec_res = [['', 0.0]] * img_num
        batch_num = self.rec_batch_num
        for beg_img_no in range(0, img_num, batch_num):
            end_img_no = min(img_num, beg_img_no + batch_num)
            max_wh_ratio = 0
            for ino in range(beg_img_no, end_img_no):
                h, w = img_list[indices[ino]].shape[0:2]
                max_wh_ratio = max(max_wh_ratio, w * 1.0 / h)

            norm_img_batch = []
            for ino in range(beg_img_no, end_img_no):
                norm_img = self.resize_norm_img(img_list[indices[ino]], max_wh_ratio)
                norm_img_batch.append(norm_img[np.newaxis, :])
            norm_img_batch = np.concatenate(norm_img_batch).copy()

            outputs = self.predictor.run(self.output_tensors,
                                         {self.input_tensor.name: norm_img_batch})
            rec_result = self.postprocess_op(outputs[0])
            for rno in range(len(rec_result)):
                rec_res[indices[beg_img_no + rno]] = rec_result[rno]
        return rec_res, 0


class TextSystem(object):
    """接口与 ppocronnx.predict_system.TextSystem 一致。"""

    def __init__(self,
                 use_angle_cls=False,
                 box_thresh=0.6,
                 unclip_ratio=1.6,
                 rec_model_path=None,
                 det_model_path=None,
                 ort_providers=None,
                 dict_path=None,
                 limit_side_len=DET_LIMIT_SIDE_LEN,
                 limit_type=DET_LIMIT_TYPE):
        self.text_detector = TextDetector(box_thresh=box_thresh,
                                          unclip_ratio=unclip_ratio,
                                          det_model_path=det_model_path,
                                          ort_providers=ort_providers,
                                          limit_side_len=limit_side_len,
                                          limit_type=limit_type)
        self.text_recognizer = TextRecognizer(rec_model_path=rec_model_path,
                                              dict_path=dict_path,
                                              ort_providers=ort_providers)
        # v5 的方向分类模型输入尺寸是 80x160，与仓库里的 v3 cls 不通用；
        # 项目所有调用点（rpc.py）都不开方向分类，这里不做兜底加载。
        self.use_angle_cls = use_angle_cls
        if self.use_angle_cls:
            raise NotImplementedError(
                'PP-OCRv5 cls model is not bundled; keep use_angle_cls=False')

    def set_char_whitelist(self, chars):
        self.text_recognizer.set_char_whitelist(chars)

    def ocr_single_line(self, img):
        res = self.ocr_lines([img])
        if res:
            return res[0]

    def ocr_lines(self, img_list):
        tmp_img_list = []
        for img in img_list:
            img_height, img_width = img.shape[0:2]
            if img_width and img_height * 1.0 / img_width >= 1.5:
                img = np.rot90(img)
            tmp_img_list.append(img)
        rec_res, _ = self.text_recognizer(tmp_img_list)
        return rec_res

    def detect_and_ocr(self, img, drop_score=0.5, unclip_ratio=None, box_thresh=None):
        ori_im = img.copy()
        dt_boxes, _ = self.text_detector(img, unclip_ratio, box_thresh)
        if dt_boxes is None or len(dt_boxes) == 0:
            return []

        dt_boxes = sorted_boxes(dt_boxes)

        img_crop_list = []
        for bno in range(len(dt_boxes)):
            img_crop = get_rotate_crop_image(ori_im, dt_boxes[bno].copy())
            img_crop_list.append(img_crop)

        rec_res, _ = self.text_recognizer(img_crop_list)
        res = []
        for box, rec_result, img_crop in zip(dt_boxes, rec_res, img_crop_list):
            text, score = rec_result
            if score >= drop_score:
                res.append(BoxedResult(box, img_crop, text, score))
        return res
