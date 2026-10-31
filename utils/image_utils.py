import math
import os
import threading
import cv2
import numpy as np


class ImageUtils:
    # 半分辨率粗搜只在大画面上划算。小裁图继续全分辨率匹配，分数和坐标保持原样。
    # 模板最短边小于 24 时，缩半后特征不够，也走全分辨率。
    _PYRAMID_MIN_WIDTH = 960
    _PYRAMID_MIN_HEIGHT = 540
    _PYRAMID_MIN_TEMPLATE = 24
    _PYRAMID_SCALE = 0.5
    _PYRAMID_PAD = 24
    _half_frame_cache = None
    _half_frame_lock = threading.Lock()

    @staticmethod
    def read_image(image_path, flags=cv2.IMREAD_COLOR):
        path = image_path
        try:
            path = os.fspath(image_path)
            image_data = np.fromfile(path, dtype=np.uint8)
        except (OSError, TypeError, ValueError):
            return cv2.imread(path, flags)

        if image_data.size == 0:
            return None

        return cv2.imdecode(image_data, flags)

    @staticmethod
    def get_image_info(image_path):
        """
        获取图片的信息，如尺寸。
        :param image_path: 图片路径。
        :return: 图片的宽度和高度。
        """
        template = ImageUtils.read_image(image_path, cv2.IMREAD_GRAYSCALE)
        return template.shape[::-1]

    @staticmethod
    def scale_and_match_template(screenshot, template, threshold=None, scale_range=None, mask=None):
        """
        对模板进行缩放并匹配至截图，找出最佳匹配位置。
        :param screenshot: 截图。
        :param template: 模板图片。
        :param threshold: 匹配阈值，小于此值的匹配将被忽略。
        :param scale_range: 缩放范围，格式为(start_scale, end_scale)。
        :param mask: 模板的掩码，用于匹配透明区域。
        :return: 最大匹配值和最佳匹配位置。
        """
        if mask is not None:
            # 我不知道为什么这里要用低分匹配方法，这导致了部分文件识别设置阈值要设置的很大很大（如界域锚点要设置到3,000,000)
            # 另外，就是用mask的图片和不用mask的图片判断逻辑是完全相反的，一个阈值要设置的高一个阈值要设置的低 带mask的是越低越好
            # 但是这个代码耦合的内容太多了，我不知道还有什么地方会受到影响，姑且就先这么用着了
            result = cv2.matchTemplate(screenshot, template, cv2.TM_SQDIFF, mask=mask)
            min_val, _, min_loc, _ = cv2.minMaxLoc(result)
            return min_val, min_loc

        max_val, max_loc = ImageUtils._match_ccoeff_normed(screenshot, template)

        if scale_range and (math.isinf(max_val) or threshold is None or max_val < threshold):
            for scale in np.arange(scale_range[0], scale_range[1] + 0.0001, 0.05):
                scaled_template = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
                local_max_val, local_max_loc = ImageUtils._match_ccoeff_normed(screenshot, scaled_template)

                if local_max_val > max_val:
                    max_val = local_max_val
                    max_loc = local_max_loc

        return max_val, max_loc

    @staticmethod
    def _match_ccoeff_normed(screenshot, template):
        """返回与 cv2.matchTemplate(..., TM_CCOEFF_NORMED) 相同坐标系下的最佳分数和位置。

        大画面先在半分辨率上找峰，再在全分辨率的一小块邻域里复核。复核分数就是
        全分辨率相关分数，阈值不用改。界面模板在 1080p 上整表匹配大约能快 3 倍，
        位置与直接全图匹配一致。掩码匹配不走这里。
        """
        if not ImageUtils._can_pyramid_match(screenshot, template):
            return ImageUtils._full_ccoeff(screenshot, template)

        scale = ImageUtils._PYRAMID_SCALE
        small = ImageUtils._half_screenshot(screenshot, scale)
        template_h, template_w = template.shape[:2]
        small_template = cv2.resize(
            template,
            (max(1, int(template_w * scale)), max(1, int(template_h * scale))),
            interpolation=cv2.INTER_AREA,
        )
        if (
            min(small_template.shape[:2]) < 8
            or small_template.shape[0] >= small.shape[0]
            or small_template.shape[1] >= small.shape[1]
        ):
            return ImageUtils._full_ccoeff(screenshot, template)

        _, _, _, coarse_loc = cv2.minMaxLoc(
            cv2.matchTemplate(small, small_template, cv2.TM_CCOEFF_NORMED)
        )
        origin_x = int(round(coarse_loc[0] / scale))
        origin_y = int(round(coarse_loc[1] / scale))
        pad = ImageUtils._PYRAMID_PAD
        screen_h, screen_w = screenshot.shape[:2]
        x1 = max(0, origin_x - pad)
        y1 = max(0, origin_y - pad)
        x2 = min(screen_w, origin_x + template_w + pad)
        y2 = min(screen_h, origin_y + template_h + pad)
        roi = screenshot[y1:y2, x1:x2]
        if roi.shape[0] < template_h or roi.shape[1] < template_w:
            return ImageUtils._full_ccoeff(screenshot, template)

        max_val, max_loc = ImageUtils._full_ccoeff(roi, template)
        return max_val, (x1 + max_loc[0], y1 + max_loc[1])

    @staticmethod
    def _can_pyramid_match(screenshot, template):
        screen_h, screen_w = screenshot.shape[:2]
        template_h, template_w = template.shape[:2]
        if screen_w < ImageUtils._PYRAMID_MIN_WIDTH or screen_h < ImageUtils._PYRAMID_MIN_HEIGHT:
            return False
        if min(template_h, template_w) < ImageUtils._PYRAMID_MIN_TEMPLATE:
            return False
        if template_h >= screen_h or template_w >= screen_w:
            return False
        return True

    @staticmethod
    def _half_screenshot(screenshot, scale):
        with ImageUtils._half_frame_lock:
            cached = ImageUtils._half_frame_cache
            if cached is not None and cached[0] is screenshot and cached[1] == scale:
                return cached[2]
            half = cv2.resize(
                screenshot,
                (max(1, int(screenshot.shape[1] * scale)), max(1, int(screenshot.shape[0] * scale))),
                interpolation=cv2.INTER_AREA,
            )
            # 只留最新一帧。界面扫描会用同一张截图匹配几十个模板。
            ImageUtils._half_frame_cache = (screenshot, scale, half)
            return half

    @staticmethod
    def _full_ccoeff(screenshot, template):
        _, max_val, _, max_loc = cv2.minMaxLoc(
            cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        )
        return max_val, max_loc

    @staticmethod
    def scale_and_match_template_with_multiple_targets(screenshot, template, threshold=None, scale=None, mask_top_right_ratio=None):
        """
        对模板进行缩放并匹配至截图，找出最佳匹配位置。
        :param screenshot: 截图。
        :param template: 模板图片。
        :param threshold: 匹配阈值，小于此值的匹配将被忽略。
        :param scale: 缩放值。
        :param mask_top_right_ratio: 忽略模板右上角的正方形区域，边长为模板短边的指定比例。
        :return: 匹配位置。
        """
        if scale is not None:
            template = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        mask = None
        if mask_top_right_ratio is not None:
            side = max(1, round(min(template.shape[:2]) * mask_top_right_ratio))
            mask = np.full(template.shape[:2], 255, dtype=np.uint8)
            mask[:side, -side:] = 0

        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED, mask=mask)
        if mask is not None:
            result[~np.isfinite(result)] = -1  # 掩码匹配在低方差区域可能产生 NaN/Inf
        locations = np.where(result >= threshold)
        matches = ImageUtils.filter_overlapping_matches(locations, template.shape[::-1])
        return ImageUtils.convert_np_int64_to_int(matches)

    @staticmethod
    def read_template_with_mask(target):
        """
        读取模板图片，并根据需要生成掩码。
        :param target: 目标图片路径。
        :return: 掩码（如果有透明通道）。
        """
        template = ImageUtils.read_image(target, cv2.IMREAD_UNCHANGED)  # 保留图片的透明通道
        if template is None:
            raise ValueError(f"读取图片失败：{target}")

        mask = None
        if template.shape[-1] == 4:  # 检查通道数是否为4（含有透明通道）
            alpha_channel = template[:, :, 3]
            if np.any(alpha_channel < 255):  # 检查是否存在非完全透明的像素
                mask = alpha_channel

        return mask

    @staticmethod
    def intersected(top_left1, botton_right1, top_left2, botton_right2):
        """判断两个矩形是否相交。

        参数:
        - top_left1: 第一个矩形的左上角坐标 (x, y)。
        - botton_right1: 第一个矩形的右下角坐标 (x, y)。
        - top_left2: 第二个矩形的左上角坐标 (x, y)。
        - botton_right2: 第二个矩形的右下角坐标 (x, y)。

        返回:
        - bool: 如果矩形相交返回True，否则返回False。

        逻辑说明:
        - 如果一个矩形在另一个矩形的右侧或左侧，它们不相交。
        - 如果一个矩形在另一个矩形的上方或下方，它们也不相交。
        - 否则，矩形相交。
        """
        # 检查矩形1是否在矩形2的右侧或矩形2是否在矩形1的右侧
        if top_left1[0] > botton_right2[0] or top_left2[0] > botton_right1[0]:
            return False
        # 检查矩形1是否在矩形2的下方或矩形2是否在矩形1的下方
        if top_left1[1] > botton_right2[1] or top_left2[1] > botton_right1[1]:
            return False
        # 上述条件都不成立，则矩形相交
        return True

    @staticmethod
    def is_match_non_overlapping(top_left, matches, width, height):
        """检查给定的匹配位置是否与已有的匹配重叠。

        参数:
        - top_left: 当前匹配的左上角坐标。
        - matches: 已有的匹配位置列表。
        - width: 模板宽度。
        - height: 模板高度。

        返回:
        - bool: 是否不重叠。
        """
        botton_right = (top_left[0] + width, top_left[1] + height)
        for match_top_left in matches:
            match_botton_right = (match_top_left[0] + width, match_top_left[1] + height)
            if ImageUtils.intersected(top_left, botton_right, match_top_left, match_botton_right):
                return False
        return True

    @staticmethod
    def filter_overlapping_matches(locations, template_size):
        """过滤掉重叠的匹配。

        参数:
        - locations: 匹配的位置数组。
        - template_size: 模板图片的大小 (宽度, 高度)。

        返回:
        - matches: 不重叠的匹配位置列表。
        """
        matches = []
        width, height = template_size
        for top_left in zip(*locations[::-1]):
            if ImageUtils.is_match_non_overlapping(top_left, matches, width, height):
                matches.append(top_left)
        return matches

    @staticmethod
    def count_template_matches(target, template, threshold):
        """使用模板匹配计算目标图片中的匹配数。

        参数:
        - target: 目标图片数组。
        - template: 模板图片数组。
        - threshold: 匹配阈值，用于决定哪些结果被认为是匹配。

        返回:
        - match_count: 匹配的数量。
        """
        # 执行模板匹配
        result = cv2.matchTemplate(target, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)

        matches = ImageUtils.filter_overlapping_matches(locations, template.shape[::-1])

        # 返回匹配数量
        return len(matches)

    @staticmethod
    def convert_np_int64_to_int(matches):
        return [(int(a), int(b)) for a, b in matches]
