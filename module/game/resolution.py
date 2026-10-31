"""16:9 game resolutions and scaling from the 1920×1080 coordinate base.

Templates, OCR crops, and most click offsets are authored at 1920×1080.
A wider 16:9 client is scaled onto that base for recognition, then mapped
back by ``window_width / 1920`` (4/3 at 2560×1440) for clicks.
"""

from fractions import Fraction

BASE_WIDTH = 1920
BASE_HEIGHT = 1080
# Named sizes the UI and error text call out. Any other 16:9 size at or
# above the base is accepted as well; these two are the common ones.
FIRST_CLASS_RESOLUTIONS = ((BASE_WIDTH, BASE_HEIGHT), (2560, 1440))
ASPECT_TOLERANCE = 0.01


def scale_to_base(window_width: int) -> float:
    """Map window pixels onto the 1920-wide screenshot used for OCR and templates.

    Returns 1 at or below 1920. At 2560 this is 1920/2560 = 3/4.
    """
    if window_width <= 0:
        raise ValueError("窗口宽度无效")
    if window_width > BASE_WIDTH:
        return BASE_WIDTH / window_width
    return 1.0


def scale_from_base(window_width: int) -> float:
    """Map a 1920-base pixel onto the window. At 2560 this is 4/3."""
    if window_width <= 0:
        raise ValueError("窗口宽度无效")
    return window_width / BASE_WIDTH


def format_scale_from_base(window_width: int) -> str:
    """Human-readable ``window_width / 1920``, such as ``4/3`` at 2560."""
    ratio = Fraction(window_width, BASE_WIDTH)
    if ratio.denominator == 1:
        return str(ratio.numerator)
    return f"{ratio.numerator}/{ratio.denominator}"


def scale_base_point(x: float, y: float, screenshot_scale: float) -> tuple[float, float]:
    """Convert one point from the scaled screenshot back to window pixels."""
    scale = screenshot_scale or 1
    return (x / scale, y / scale)


def scale_base_box(box, screenshot_scale: float):
    """Convert a ``((x1, y1), (x2, y2))`` box from base pixels to window pixels."""
    (x1, y1), (x2, y2) = box
    return (scale_base_point(x1, y1, screenshot_scale), scale_base_point(x2, y2, screenshot_scale))


def scaled_capture_size(captured_width: int, captured_height: int, window_width: int) -> tuple[int, int]:
    """Size of a capture after it is scaled onto the 1920-wide base.

    A full 2560×1440 frame becomes 1920×1080. A 1920×1080 frame is unchanged.
    """
    scale = scale_to_base(window_width)
    if scale == 1:
        return captured_width, captured_height
    return (
        max(1, int(round(captured_width * scale))),
        max(1, int(round(captured_height * scale))),
    )


def is_16_9(width: int, height: int, tolerance: float = ASPECT_TOLERANCE) -> bool:
    if width <= 0 or height <= 0:
        return False
    return abs(width / height - (BASE_WIDTH / BASE_HEIGHT)) <= tolerance


def is_supported_resolution(
    width: int,
    height: int,
    minimum: tuple[int, int] = (BASE_WIDTH, BASE_HEIGHT),
    tolerance: float = ASPECT_TOLERANCE,
) -> bool:
    """True for 16:9 clients at least ``minimum`` (default 1920×1080).

    1920×1080 and 2560×1440 are included. Smaller or non-16:9 sizes are not.
    """
    min_width, min_height = minimum
    if width < min_width or height < min_height:
        return False
    if min_height <= 0:
        return False
    target_aspect = min_width / min_height
    if height <= 0:
        return False
    return abs(width / height - target_aspect) <= tolerance


def window_ratio_crop(
    origin_x: float,
    origin_y: float,
    base_width: float,
    base_height: float,
    window_width: int,
    window_height: int,
) -> tuple[float, float, float, float]:
    """Build an Automation crop from a window-pixel origin and a 1920×1080 size.

    The origin is already in the live window's pixels (OCR boxes are scaled
    before they are stored). The width and height stay ratios of the 1920×1080
    base, which match the window when the client is 16:9.
    """
    if window_width <= 0 or window_height <= 0:
        raise ValueError("窗口尺寸无效")
    return (
        origin_x / window_width,
        origin_y / window_height,
        base_width / BASE_WIDTH,
        base_height / BASE_HEIGHT,
    )


def accepted_resolution_message(width: int, height: int) -> str:
    if width == BASE_WIDTH and height == BASE_HEIGHT:
        return f"游戏分辨率: {width}x{height}"
    return (
        f"游戏分辨率: {width}x{height}，按 {format_scale_from_base(width)} "
        f"缩放 {BASE_WIDTH}x{BASE_HEIGHT} 坐标"
    )


def unsupported_resolution_message(width: int, height: int) -> str:
    return (
        f"游戏分辨率: {width}x{height}，请在游戏设置内手动切换为 16:9 窗口"
        f"（支持 1920x1080、2560x1440，或其他不小于 1920x1080 的 16:9；"
        f"没有窗口再选择全屏幕）运行"
    )
