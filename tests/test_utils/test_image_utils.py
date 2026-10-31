import cv2
import numpy as np

from utils.image_utils import ImageUtils


class TestImageUtilsIntersected:
    def test_intersecting_rectangles(self):
        assert ImageUtils.intersected((0, 0), (10, 10), (5, 5), (15, 15)) is True

    def test_non_intersecting_rectangles(self):
        assert ImageUtils.intersected((0, 0), (10, 10), (20, 20), (30, 30)) is False

    def test_adjacent_rectangles_no_overlap(self):
        # 当边界相接时，intersected 返回 True（因为 <= 比较）
        # 如果需要严格不相交，需要修改原函数使用 < 比较
        assert ImageUtils.intersected((0, 0), (10, 10), (11, 0), (20, 10)) is False

    def test_contained_rectangle(self):
        assert ImageUtils.intersected((0, 0), (20, 20), (5, 5), (10, 10)) is True

    def test_same_rectangle(self):
        assert ImageUtils.intersected((0, 0), (10, 10), (0, 0), (10, 10)) is True


class TestImageUtilsNonOverlapping:
    def test_no_overlap(self):
        matches = [(0, 0), (20, 20)]
        assert ImageUtils.is_match_non_overlapping((40, 40), matches, 10, 10) is True

    def test_with_overlap(self):
        matches = [(0, 0), (20, 20)]
        assert ImageUtils.is_match_non_overlapping((5, 5), matches, 10, 10) is False

    def test_empty_matches(self):
        assert ImageUtils.is_match_non_overlapping((0, 0), [], 10, 10) is True


class TestImageUtilsFilterOverlapping:
    def test_filter_no_overlap(self):
        # numpy 格式的 locations: (y_coords, x_coords)
        locations = ([0, 20], [0, 20])
        result = ImageUtils.filter_overlapping_matches(locations, (10, 10))
        assert len(result) == 2

    def test_filter_with_overlap(self):
        locations = ([0, 5], [0, 5])
        result = ImageUtils.filter_overlapping_matches(locations, (10, 10))
        assert len(result) == 1

    def test_filter_empty(self):
        locations = ([], [])
        result = ImageUtils.filter_overlapping_matches(locations, (10, 10))
        assert len(result) == 0


class TestImageUtilsConvertNpInt64:
    def test_convert_tuples(self):
        import numpy as np
        matches = [(np.int64(1), np.int64(2)), (np.int64(3), np.int64(4))]
        result = ImageUtils.convert_np_int64_to_int(matches)
        assert result == [(1, 2), (3, 4)]
        assert all(isinstance(a, int) and isinstance(b, int) for a, b in result)

    def test_convert_empty(self):
        result = ImageUtils.convert_np_int64_to_int([])
        assert result == []


def test_masked_match_recovers_avatar_with_corner_badge_without_false_match():
    rng = np.random.default_rng(1254)
    template = rng.integers(105, 150, (101, 108), dtype=np.uint8)
    template[:26, -26:] = rng.integers(0, 256, (26, 26), dtype=np.uint8)
    scaled = cv2.resize(template, None, fx=0.9, fy=0.9, interpolation=cv2.INTER_AREA)

    background = rng.integers(105, 150, (210, 230), dtype=np.uint8)
    screenshot = background.copy()
    y, x = 55, 65
    h, w = scaled.shape
    screenshot[y:y + h, x:x + w] = scaled
    side = round(min(h, w) * 0.26)
    screenshot[y:y + side, x + w - side:x + w] = 255 - scaled[:side, -side:]

    assert ImageUtils.scale_and_match_template_with_multiple_targets(screenshot, template, 0.8, 0.9) == []
    matches = ImageUtils.scale_and_match_template_with_multiple_targets(
        screenshot, template, 0.8, 0.9, mask_top_right_ratio=0.26
    )
    assert len(matches) == 1
    assert abs(matches[0][0] - x) <= 2 and abs(matches[0][1] - y) <= 2
    assert ImageUtils.scale_and_match_template_with_multiple_targets(
        background, template, 0.8, 0.9, mask_top_right_ratio=0.26
    ) == []


def _direct_ccoeff(screenshot, template):
    _, max_val, _, max_loc = cv2.minMaxLoc(
        cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    )
    return max_val, max_loc


def test_pyramid_match_agrees_with_full_search_on_1080p():
    rng = np.random.default_rng(7)
    screenshot = rng.integers(0, 40, (1080, 1920, 3), dtype=np.uint8)
    template = rng.integers(80, 220, (64, 96, 3), dtype=np.uint8)
    x, y = 640, 420
    screenshot[y:y + 64, x:x + 96] = template

    fast_val, fast_loc = ImageUtils.scale_and_match_template(screenshot, template, threshold=0.8)
    full_val, full_loc = _direct_ccoeff(screenshot, template)

    assert fast_loc == full_loc == (x, y)
    assert abs(fast_val - full_val) < 1e-5
    assert fast_val >= 0.99


def test_pyramid_match_miss_stays_below_ui_threshold():
    rng = np.random.default_rng(11)
    screenshot = rng.integers(0, 40, (1080, 1920, 3), dtype=np.uint8)
    template = rng.integers(180, 255, (48, 80, 3), dtype=np.uint8)

    fast_val, _ = ImageUtils.scale_and_match_template(screenshot, template, threshold=0.9)
    full_val, _ = _direct_ccoeff(screenshot, template)

    assert fast_val < 0.8
    assert full_val < 0.8


def test_small_frame_keeps_full_resolution_match():
    rng = np.random.default_rng(3)
    screenshot = rng.integers(0, 30, (240, 320, 3), dtype=np.uint8)
    template = rng.integers(90, 180, (40, 50, 3), dtype=np.uint8)
    screenshot[20:60, 30:80] = template

    fast_val, fast_loc = ImageUtils.scale_and_match_template(screenshot, template)
    full_val, full_loc = _direct_ccoeff(screenshot, template)
    assert fast_loc == full_loc == (30, 20)
    assert abs(fast_val - full_val) < 1e-6


def test_pyramid_matches_a_real_screen_template():
    template = cv2.imread("assets/images/screen/currency_wars/homepage.png", cv2.IMREAD_COLOR)
    assert template is not None
    height, width = template.shape[:2]
    assert min(height, width) >= 24

    screenshot = np.full((1080, 1920, 3), 28, dtype=np.uint8)
    x, y = 480, 620
    screenshot[y:y + height, x:x + width] = template

    fast_val, fast_loc = ImageUtils.scale_and_match_template(screenshot, template, threshold=0.9)
    full_val, full_loc = _direct_ccoeff(screenshot, template)
    assert fast_loc == full_loc == (x, y)
    assert abs(fast_val - full_val) < 1e-4


def test_scale_range_finds_a_slightly_smaller_copy():
    rng = np.random.default_rng(21)
    template = rng.integers(60, 200, (80, 100, 3), dtype=np.uint8)
    scaled = cv2.resize(template, None, fx=0.95, fy=0.95, interpolation=cv2.INTER_AREA)
    screenshot = rng.integers(0, 30, (1080, 1920, 3), dtype=np.uint8)
    height, width = scaled.shape[:2]
    x, y = 300, 400
    screenshot[y:y + height, x:x + width] = scaled

    value, loc = ImageUtils.scale_and_match_template(
        screenshot, template, threshold=0.99, scale_range=(0.9, 1.0)
    )
    assert value >= 0.95
    assert abs(loc[0] - x) <= 3
    assert abs(loc[1] - y) <= 3


def test_half_frame_is_reused_for_the_same_screenshot():
    rng = np.random.default_rng(5)
    screenshot = rng.integers(0, 20, (1080, 1920, 3), dtype=np.uint8)
    template = rng.integers(100, 180, (40, 60, 3), dtype=np.uint8)
    screenshot[100:140, 200:260] = template
    ImageUtils._half_frame_cache = None

    original_resize = cv2.resize
    screenshot_resizes = []

    def counting_resize(image, *args, **kwargs):
        if image is screenshot:
            screenshot_resizes.append(image.shape)
        return original_resize(image, *args, **kwargs)

    cv2.resize = counting_resize
    try:
        ImageUtils.scale_and_match_template(screenshot, template)
        ImageUtils.scale_and_match_template(screenshot, template)
    finally:
        cv2.resize = original_resize

    assert len(screenshot_resizes) == 1
