"""货币战争主界面进入模式选择。

失败截图里，橙色「双倍晋升点模式已开启」条贴在「开始「货币战争」」上方。
旧的 homepage.png 在文字上方留了约 4 行纯浅色。横幅比这段留白更靠近文字时，
最佳匹配仍落在按钮上，但相似度掉进界面阈值 0.88 和点击阈值 0.9 之间：
主界面认得出，点击却 10 次都失败，于是一直停在主界面。
"""
import json
import re
from pathlib import Path

import cv2
import numpy as np

from utils.image_utils import ImageUtils

ROOT = Path(__file__).parents[2]
TEMPLATE_PATH = ROOT / "assets/images/screen/currency_wars/homepage.png"
SCREENS_PATH = ROOT / "assets/config/screens.json"
SCREEN_PY = ROOT / "module/screen/screen.py"

LIGHT_BGR = (240, 222, 220)
ORANGE_BGR = (20, 130, 255)
PURPLE_BGR = (80, 48, 40)


def _screen_match_threshold():
    match = re.search(r"SCREEN_MATCH_THRESHOLD = ([0-9.]+)", SCREEN_PY.read_text(encoding="utf-8"))
    assert match, "找不到界面匹配阈值"
    return float(match.group(1))


def _mode_select_action():
    screens = json.loads(SCREENS_PATH.read_text(encoding="utf-8"))
    homepage = next(screen for screen in screens if screen["id"] == "currency_wars_homepage")
    action = next(
        item for item in homepage["actions"] if item["target_screen"] == "currency_wars_mode_select"
    )
    return action["actions_list"][0]


def _banner_scene(glyphs, gap):
    """橙色横幅下方 gap 像素处放上按钮文字，周围再放一块不像按钮的浅色干扰。"""
    height, width = glyphs.shape[:2]
    canvas = np.full((1080, 1920, 3), PURPLE_BGR, np.uint8)
    banner_bottom = 960
    origin_x = 1460
    canvas[banner_bottom - 80:banner_bottom, 1200:1900] = ORANGE_BGR
    canvas[banner_bottom:banner_bottom + 100, 1240:1880] = LIGHT_BGR
    origin_y = banner_bottom + gap
    canvas[origin_y:origin_y + height, origin_x:origin_x + width] = glyphs

    decoy = np.full((height, width, 3), LIGHT_BGR, np.uint8)
    noise = np.random.default_rng(1).integers(0, 255, (height, width), dtype=np.uint8)
    decoy[noise > 180] = (15, 15, 15)
    canvas[200:200 + height, 100:100 + width] = decoy
    return canvas, (origin_x, origin_y)


def _match(canvas, template):
    return ImageUtils.scale_and_match_template(canvas, template, threshold=0.8)


def test_start_button_template_ignores_the_promotion_banner():
    template = cv2.imread(str(TEMPLATE_PATH), cv2.IMREAD_COLOR)
    assert template is not None
    # 文字要顶到模板上沿。留白一旦回到横幅里，相似度就会掉到 0.9 以下。
    assert template[0].std() > 10

    for gap in (0, 1):
        canvas, origin = _banner_scene(template, gap)
        score, location = _match(canvas, template)
        assert score >= 0.9, f"横幅距文字 {gap}px 时相似度只有 {score:.3f}"
        assert abs(location[0] - origin[0]) <= 1
        assert abs(location[1] - origin[1]) <= 1


def test_banner_overlap_on_padded_template_falls_between_detect_and_click():
    """还原修之前的模板：文字上方再补回 4 行浅色，横幅只隔 1 像素。"""
    glyphs = cv2.imread(str(TEMPLATE_PATH), cv2.IMREAD_COLOR)
    width = glyphs.shape[1]
    padding = np.full((4, width, 3), LIGHT_BGR, np.uint8)
    padded = np.vstack([padding, glyphs, padding])

    canvas, glyph_origin = _banner_scene(glyphs, gap=1)
    score, location = _match(canvas, padded)
    screen_threshold = _screen_match_threshold()

    assert screen_threshold <= score < 0.9
    assert location == (glyph_origin[0], glyph_origin[1] - padding.shape[0])


def test_mode_select_click_is_not_stricter_than_screen_detection():
    action = _mode_select_action()
    image_click = re.search(
        r"currency_wars/homepage\.png', 'image', ([0-9.]+), (\d+)",
        action,
    )
    assert image_click, action
    click_threshold = float(image_click.group(1))
    assert click_threshold <= _screen_match_threshold()
    # 模板对不上时改点右下角按钮上的「货币战争」，避免点到左上角标题。
    assert "or auto.click_element('货币战争', 'text'" in action
    assert "include=True" in action
    crop = re.search(
        r"crop=\(([0-9.]+) / 1920, ([0-9.]+) / 1080, ([0-9.]+) / 1920, ([0-9.]+) / 1080\)",
        action,
    )
    assert crop, action
    origin_y = float(crop.group(2))
    height = float(crop.group(4))
    assert origin_y >= 800
    assert origin_y + height <= 1080
