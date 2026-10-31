"""16:9 resolution acceptance and 1920×1080 coordinate scaling."""

from unittest.mock import Mock

import pytest

from module.game.resolution import (
    BASE_HEIGHT,
    BASE_WIDTH,
    accepted_resolution_message,
    format_scale_from_base,
    is_supported_resolution,
    scale_base_box,
    scale_base_point,
    scale_from_base,
    scale_to_base,
    scaled_capture_size,
    unsupported_resolution_message,
    window_ratio_crop,
)


class TestScaleFromBase:
    def test_1080p_is_identity(self):
        assert scale_to_base(1920) == 1
        assert scale_from_base(1920) == 1
        assert scale_base_point(100, 50, scale_to_base(1920)) == (100, 50)
        assert scaled_capture_size(1920, 1080, 1920) == (1920, 1080)

    def test_1440p_uses_four_thirds(self):
        assert scale_from_base(2560) == pytest.approx(4 / 3)
        assert scale_to_base(2560) == pytest.approx(1920 / 2560)
        assert format_scale_from_base(2560) == "4/3"
        assert scale_base_point(960, 540, scale_to_base(2560)) == pytest.approx((1280, 720))
        # A 1080p pixel offset grows by 4/3. 510 base pixels is 680 window pixels.
        assert scale_base_point(-510, 68, scale_to_base(2560)) == pytest.approx((-680, 90 + 2 / 3))
        assert scale_base_point(150, -68, 1) == pytest.approx((150, -68))
        assert scaled_capture_size(2560, 1440, 2560) == (1920, 1080)

    def test_partial_capture_scales_with_the_window(self):
        assert scaled_capture_size(1280, 720, 2560) == (960, 540)

    def test_4k_scales_by_two(self):
        assert format_scale_from_base(3840) == "2"
        assert scaled_capture_size(3840, 2160, 3840) == (1920, 1080)

    def test_box_scales_both_corners(self):
        box = ((48, 477), (156, 578))
        scaled = scale_base_box(box, scale_to_base(2560))
        assert scaled[0] == pytest.approx((64, 636))
        assert scaled[1] == pytest.approx((208, 770 + 2 / 3))

    def test_narrower_than_base_is_not_upscaled(self):
        assert scale_to_base(1280) == 1
        assert scaled_capture_size(1280, 720, 1280) == (1280, 720)


class TestSupportedResolutions:
    @pytest.mark.parametrize(
        "size",
        [(1920, 1080), (2560, 1440), (3840, 2160), (1280 * 2, 720 * 2)],
    )
    def test_16_9_at_or_above_1080p_is_accepted(self, size):
        assert is_supported_resolution(*size)

    @pytest.mark.parametrize(
        "size",
        [(1280, 720), (1600, 900), (1920, 1200), (2560, 1080), (2560, 1600), (0, 0), (1920, 0)],
    )
    def test_small_or_non_16_9_is_rejected(self, size):
        assert not is_supported_resolution(*size)

    def test_crop_ratio_is_stable_between_1080p_and_1440p(self):
        crop_1080 = window_ratio_crop(100, 50, 792, 254, 1920, 1080)
        crop_1440 = window_ratio_crop(100 * 4 / 3, 50 * 4 / 3, 792, 254, 2560, 1440)
        assert crop_1440 == pytest.approx(crop_1080)
        assert crop_1080[0] == pytest.approx(100 / BASE_WIDTH)
        assert crop_1080[1] == pytest.approx(50 / BASE_HEIGHT)

    def test_messages_name_both_first_class_sizes(self):
        accepted = accepted_resolution_message(2560, 1440)
        assert "2560x1440" in accepted
        assert "4/3" in accepted
        assert accepted_resolution_message(1920, 1080) == "游戏分辨率: 1920x1080"
        rejected = unsupported_resolution_message(1280, 720)
        assert "1920x1080" in rejected
        assert "2560x1440" in rejected
        assert "16:9" in rejected
        assert "手动切换为 1920x1080 窗口" not in rejected


def _controller(resolution, screen=(2560, 1440)):
    from tasks.game.starrailcontroller import StarRailController

    controller = StarRailController.__new__(StarRailController)
    controller.screen_resolution = screen
    controller.get_resolution = lambda: resolution
    controller.log_debug = Mock()
    controller.log_error = Mock()
    return controller


class TestResolutionCheck:
    def test_1440p_does_not_block(self, monkeypatch):
        import tasks.game.starrailcontroller as module

        sleep = Mock()
        monkeypatch.setattr(module.time, "sleep", sleep)
        controller = _controller((2560, 1440))

        controller.check_resolution(1920, 1080)

        sleep.assert_not_called()
        controller.log_error.assert_not_called()
        assert "4/3" in controller.log_debug.call_args[0][0]

    def test_1080p_still_passes(self, monkeypatch):
        import tasks.game.starrailcontroller as module

        monkeypatch.setattr(module.time, "sleep", Mock())
        controller = _controller((1920, 1080), screen=(1920, 1080))

        controller.check_resolution(1920, 1080)

        module.time.sleep.assert_not_called()
        assert controller.log_debug.call_args[0][0] == "游戏分辨率: 1920x1080"

    def test_wrong_resolution_retries_with_16_9_hint(self, monkeypatch):
        import tasks.game.starrailcontroller as module

        sleep = Mock()
        monkeypatch.setattr(module.time, "sleep", sleep)
        controller = _controller((2560, 1080), screen=(2560, 1440))

        with pytest.raises(ValueError, match="游戏分辨率不正确"):
            controller.check_resolution(1920, 1080)

        assert sleep.call_count == 4
        message = controller.log_error.call_args_list[0][0][0]
        assert "2560x1080" in message
        assert "2560x1440" in message
        assert "1920x1080" in message

    def test_missing_window_fails_immediately(self, monkeypatch):
        import tasks.game.starrailcontroller as module

        sleep = Mock()
        monkeypatch.setattr(module.time, "sleep", sleep)
        controller = _controller(None)

        with pytest.raises(RuntimeError, match="游戏分辨率获取失败"):
            controller.check_resolution()

        sleep.assert_not_called()

    def test_ratio_check_accepts_1440p_without_warning(self, monkeypatch):
        import tasks.game.starrailcontroller as module

        sleep = Mock()
        monkeypatch.setattr(module.time, "sleep", sleep)
        controller = _controller((2560, 1440))

        controller.check_resolution_ratio(1920, 1080)

        sleep.assert_not_called()
        controller.log_error.assert_not_called()
        assert "4/3" in controller.log_debug.call_args_list[0][0][0]
