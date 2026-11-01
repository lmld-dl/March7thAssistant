"""手机菜单锚点和货币战争入口模板的匹配门槛。"""
import json
from pathlib import Path

import cv2
import numpy as np

from utils.phone_menu import (
    GUIDE_CROP,
    GUIDE_ICON,
    GUIDE_ONLY_SCORE,
    GUIDE_SQDIFF_LIMIT,
    MATCH_THRESHOLD,
    menu_match_score,
)
from utils.image_utils import ImageUtils

ROOT = Path(__file__).parents[2]


def test_menu_score_trusts_the_three_dots_above_the_screen_threshold():
    def find_element(target, find_type=None, threshold=None, **kwargs):
        assert target.endswith("more.png")
        assert find_type == "image_threshold"
        assert threshold == MATCH_THRESHOLD
        return 0.93

    assert menu_match_score(find_element, take_screenshot=False) == 0.93


def test_menu_score_accepts_the_guide_icon_when_the_three_dots_miss():
    def find_element(target, find_type=None, threshold=None, **kwargs):
        if target.endswith("more.png"):
            return None
        assert target == GUIDE_ICON
        assert threshold == GUIDE_SQDIFF_LIMIT
        assert kwargs["crop"] == GUIDE_CROP
        assert kwargs["take_screenshot"] is False
        return ((1, 2), (3, 4))

    assert menu_match_score(find_element, take_screenshot=True) == GUIDE_ONLY_SCORE


def test_menu_score_is_absent_when_neither_anchor_matches():
    def find_element(target, find_type=None, threshold=None, **kwargs):
        return None

    assert menu_match_score(find_element, take_screenshot=False) is None


def test_guide_icon_threshold_hits_the_icon_and_ignores_noise():
    """2e6 要能点中还在的指南图标，又不能在随机画面上乱点。"""
    template = cv2.imread(str(ROOT / GUIDE_ICON), cv2.IMREAD_COLOR)
    mask = ImageUtils.read_template_with_mask(str(ROOT / GUIDE_ICON))
    assert template is not None and mask is not None

    rng = np.random.default_rng(4)
    noise = rng.integers(0, 255, (720, 1280, 3), dtype=np.uint8)
    absent, _ = ImageUtils.scale_and_match_template(noise, template, mask=mask)
    assert absent > GUIDE_SQDIFF_LIMIT

    present = noise.copy()
    y, x = 180, 700
    height, width = template.shape[:2]
    region = present[y:y + height, x:x + width]
    for channel in range(3):
        region[:, :, channel] = np.where(mask > 0, template[:, :, channel], region[:, :, channel])
    score, location = ImageUtils.scale_and_match_template(present, template, mask=mask)
    assert score <= GUIDE_SQDIFF_LIMIT
    assert location == (x, y)


def test_currency_wars_tab_click_is_not_stricter_than_screen_detection():
    screens = json.loads((ROOT / "assets/config/screens.json").read_text(encoding="utf-8"))
    menu = next(screen for screen in screens if screen["id"] == "menu")
    action = next(item["actions_list"] for item in menu["actions"] if item["target_screen"] == "guide5")
    tab_click = action[2]
    assert "enter_guide5.png', 'image', 0.88" in tab_click
    assert "旷宇纷争" in tab_click
    assert "or auto.click_element('指南', 'text'" in action[0]
