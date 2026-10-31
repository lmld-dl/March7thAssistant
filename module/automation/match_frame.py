"""同一帧上的模板匹配共用一次颜色转换。

界面扫描会拿同一张截图对几十个模板做 matchTemplate。每次都 np.array + cvtColor
会重复拷贝整帧。按截图对象身份缓存转换结果，截图换成新对象后自动失效。
"""
import threading

import cv2
import numpy as np


_frame_lock = threading.Lock()


def frame_for_match(owner, conversion):
    """返回 owner.screenshot 按 conversion 转好的数组。同一截图对象重复调用返回同一数组。"""
    screenshot = owner.screenshot
    with _frame_lock:
        cache = getattr(owner, "_match_frame_cache", None)
        if cache is None or cache[0] is not screenshot:
            cache = (screenshot, {})
            owner._match_frame_cache = cache
        frame = cache[1].get(conversion)
        if frame is None:
            frame = cv2.cvtColor(np.array(screenshot), conversion)
            cache[1][conversion] = frame
        return frame
