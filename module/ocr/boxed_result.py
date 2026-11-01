# This Python file uses the following encoding: utf-8
from dataclasses import dataclass

import numpy as np


@dataclass
class BoxedResult:
    box: np.ndarray
    text_img: np.ndarray
    ocr_text: str
    score: float
