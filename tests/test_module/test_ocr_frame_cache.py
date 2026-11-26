from types import SimpleNamespace
from unittest.mock import MagicMock

import cv2
import numpy as np
from PIL import Image

from module.automation.automation import Automation
from module.automation.match_frame import frame_for_match


def test_match_frame_reuses_conversion_until_screenshot_changes():
    owner = SimpleNamespace(screenshot=Image.new("RGB", (16, 12), (10, 20, 30)))
    first = frame_for_match(owner, cv2.COLOR_BGR2RGB)
    second = frame_for_match(owner, cv2.COLOR_BGR2RGB)
    gray = frame_for_match(owner, cv2.COLOR_BGR2GRAY)

    assert first is second
    assert gray.shape == (12, 16)
    assert gray.ndim == 2

    owner.screenshot = Image.new("RGB", (16, 12), (1, 2, 3))
    third = frame_for_match(owner, cv2.COLOR_BGR2RGB)
    assert third is not first
    assert not np.array_equal(third, first)




def test_perform_ocr_does_not_cache_failures(monkeypatch):
    auto = Automation.__new__(Automation)
    auto.logger = MagicMock()
    auto.screenshot = Image.new("RGB", (8, 8), "white")
    calls = []

    def recognize(image):
        calls.append(1)
        raise RuntimeError("ocr down")

    monkeypatch.setattr("module.automation.automation.ocr.recognize_multi_lines", recognize)

    auto.perform_ocr()
    auto.perform_ocr()
    assert calls == [1, 1]
    assert auto.ocr_result == []
