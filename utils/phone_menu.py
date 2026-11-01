"""手机菜单是否已经打开。

三个点模板只有 35×15。大世界里第一次 ESC 常常只退出鼠标光标，菜单并没有留下；
菜单其实开着时，主界面那个更小的锚点又可能先被认出来，再按一次 ESC 就会把菜单关掉。
三个点，或手机菜单图标区里的指南图标，任意一个在就算菜单开着。
"""

MENU_DOTS = "./assets/images/share/menu/more.png"
GUIDE_ICON = "./assets/images/share/menu/guide.png"
MAIN_ANCHOR = "./assets/images/screen/main.png"
# 与 Screen.SCREEN_MATCH_THRESHOLD 同一档。
MATCH_THRESHOLD = 0.88
# 指南图标带透明通道，走 TM_SQDIFF，越低越好。
# 随机画面大约 1e8；图标还在、只是偏色几十级时大约 7e5。2e6 沿用原来的点击门槛。
GUIDE_SQDIFF_LIMIT = 2_000_000
# 手机菜单右侧图标区。不要扩到屏幕顶端，避免把主界面右上角的快捷图标当成菜单。
GUIDE_CROP = (1264.0 / 1920, 286.0 / 1080, 546.0 / 1920, 746.0 / 1080)
# 只有指南图标、没有三个点时的分数：高于勉强越过 0.88 的主界面误匹配，
# 低于清晰的主界面锚点，避免把大世界认成菜单。
GUIDE_ONLY_SCORE = 0.95


def _at_least(value, threshold):
    if isinstance(value, bool) or value is None:
        return False
    try:
        return float(value) >= threshold
    except (TypeError, ValueError):
        return False


def menu_match_score(find_element, *, take_screenshot):
    """返回手机菜单的匹配分数；没打开时返回 None。"""
    dots = find_element(
        MENU_DOTS,
        "image_threshold",
        MATCH_THRESHOLD,
        take_screenshot=take_screenshot,
    )
    if _at_least(dots, MATCH_THRESHOLD):
        return float(dots)
    guide = find_element(
        GUIDE_ICON,
        "image",
        GUIDE_SQDIFF_LIMIT,
        crop=GUIDE_CROP,
        take_screenshot=False,
    )
    if guide:
        return GUIDE_ONLY_SCORE
    return None
