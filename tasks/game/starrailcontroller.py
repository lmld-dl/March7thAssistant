import time
from typing import Literal, Optional
from module.config.config import Config
from module.game.local import LocalGameController
from module.game.resolution import (
    BASE_HEIGHT,
    BASE_WIDTH,
    accepted_resolution_message,
    is_supported_resolution,
    unsupported_resolution_message,
)
import sys
if sys.platform == 'win32':
    from utils.registry.star_rail_setting import get_game_resolution, set_game_resolution, get_auto_battle_open_setting, get_is_save_battle_speed_setting, get_user_speed_up_open_setting, set_auto_battle_open_setting, set_is_save_battle_speed_setting, set_user_speed_up_open_setting
    from utils.registry.game_auto_hdr import get_game_auto_hdr, set_game_auto_hdr
    from utils.registry.gameaccount import gamereg_uid
from utils.logger.logger import Logger


class StarRailController(LocalGameController):
    def __init__(self, cfg: Config, logger: Optional[Logger] = None) -> None:
        super().__init__(cfg=cfg, logger=logger)
        self.game_resolution = None
        self.game_auto_hdr = None
        import pyautogui
        self.screen_resolution = pyautogui.size()

    def change_resolution(self, width: int, height: int):
        """通过注册表修改游戏分辨率"""
        try:
            self.game_resolution = get_game_resolution()
            if self.game_resolution:
                screen_width, screen_height = self.screen_resolution
                is_fullscreen = False if screen_width > width or screen_height > height else True
                if self.game_resolution[0] == width and self.game_resolution[1] == height and self.game_resolution[2] == is_fullscreen:
                    self.game_resolution = None
                    return
                set_game_resolution(width, height, is_fullscreen)
                self.log_debug(f"修改游戏分辨率: {self.game_resolution[0]}x{self.game_resolution[1]} ({'全屏' if self.game_resolution[2] else '窗口'}) --> {width}x{height} ({'全屏' if is_fullscreen else '窗口'})")
        except FileNotFoundError:
            self.log_debug("指定的注册表项未找到")
        except Exception as e:
            self.log_error(f"读取注册表值时发生错误: {e}")

    def restore_resolution(self):
        """通过注册表恢复游戏分辨率"""
        try:
            if self.game_resolution:
                set_game_resolution(self.game_resolution[0], self.game_resolution[1], self.game_resolution[2])
                self.log_debug(f"恢复游戏分辨率: {self.game_resolution[0]}x{self.game_resolution[1]} ({'全屏' if self.game_resolution[2] else '窗口'})")
        except Exception as e:
            self.log_error(f"写入注册表值时发生错误: {e}")

    def change_auto_hdr(self, status: Literal["enable", "disable", "unset"] = "unset"):
        """通过注册表修改游戏自动 HDR 设置"""
        status_map = {"enable": "启用", "disable": "禁用", "unset": "未设置"}
        try:
            self.game_auto_hdr = get_game_auto_hdr(self.game_path)
            if self.game_auto_hdr == status:
                self.game_auto_hdr = None
                return
            set_game_auto_hdr(self.game_path, status)
            self.log_debug(f"修改游戏自动 HDR: {status_map.get(self.game_auto_hdr)} --> {status_map.get(status)}")
        except Exception as e:
            self.log_debug(f"修改游戏自动 HDR 设置时发生错误：{e}")

    def restore_auto_hdr(self):
        """通过注册表恢复游戏自动 HDR 设置"""
        status_map = {"enable": "启用", "disable": "禁用", "unset": "未设置"}
        try:
            if self.game_auto_hdr:
                set_game_auto_hdr(self.game_path, self.game_auto_hdr)
            self.log_debug(f"恢复游戏自动 HDR: {status_map.get(self.game_auto_hdr)}")
        except Exception as e:
            self.log_debug(f"恢复游戏自动 HDR 设置时发生错误：{e}")

    def check_resolution(self, target_width: int = BASE_WIDTH, target_height: int = BASE_HEIGHT) -> None:
        """
        检查游戏窗口是否为可用的 16:9 分辨率。

        1920×1080 与 2560×1440 可以直接运行。其他不小于 target 的 16:9
        也会接受，点击和 OCR 按宽度相对 1920 缩放。比例不对或小于 target
        时记录错误，重试后抛出异常。桌面小于 target 时额外给出提示。

        参数:
            target_width (int): 最低分辨率宽度，默认 1920。
            target_height (int): 最低分辨率高度，默认 1080。
        """
        max_checks = 5
        check_interval = 10
        screen_width, screen_height = self.screen_resolution
        minimum = (target_width, target_height)

        for attempt in range(1, max_checks + 1):
            resolution = self.get_resolution()
            if not resolution:
                raise RuntimeError("游戏分辨率获取失败")
            window_width, window_height = resolution

            if is_supported_resolution(window_width, window_height, minimum):
                self.log_debug(accepted_resolution_message(window_width, window_height))
                return

            self.log_error(unsupported_resolution_message(window_width, window_height))
            if screen_width < target_width or screen_height < target_height:
                self.log_error(f"桌面分辨率: {screen_width}x{screen_height}，你可能需要更大的显示器或使用 HDMI/VGA 显卡欺骗器（或尝试将显示器缩放修改为 100%）")

            if attempt < max_checks:
                self.log_error(f"将在 {check_interval} 秒后重新检查分辨率（第 {attempt}/{max_checks} 次）")
                time.sleep(check_interval)

        raise ValueError("游戏分辨率不正确")

    def check_resolution_ratio(self, target_width: int = BASE_WIDTH, target_height: int = BASE_HEIGHT) -> None:
        """
        检查游戏窗口的分辨率和比例是否符合目标设置。

        不小于 target 的 16:9（含 1920×1080 与 2560×1440）直接通过。
        分辨率过低或比例不是 16:9 时记录错误并抛出异常。
        """
        resolution = self.get_resolution()
        if not resolution:
            raise RuntimeError("游戏分辨率获取失败")
        window_width, window_height = resolution

        screen_width, screen_height = self.screen_resolution

        if is_supported_resolution(window_width, window_height, (target_width, target_height)):
            self.log_debug(accepted_resolution_message(window_width, window_height))
            self.log_debug(f"桌面分辨率: {screen_width}x{screen_height}")
            return

        if window_width < target_width or window_height < target_height:
            self.log_error(unsupported_resolution_message(window_width, window_height))
            if screen_width < BASE_WIDTH or screen_height < BASE_HEIGHT:
                self.log_error(f"桌面分辨率: {screen_width}x{screen_height} 你可能需要更大的显示器或使用 HDMI/VGA 显卡欺骗器")
            raise ValueError("游戏分辨率过低")
        self.log_error(unsupported_resolution_message(window_width, window_height))
        raise ValueError("游戏分辨率比例不正确")

    def change_auto_battle(self, status: bool) -> None:
        auto_battle_status = get_auto_battle_open_setting()
        if auto_battle_status is not None and auto_battle_status != status:
            set_auto_battle_open_setting(status)
            self.log_debug(f"修改自动战斗状态: {'开启' if auto_battle_status else '关闭'} --> {'开启' if status else '关闭'}")
        save_battle_status = get_is_save_battle_speed_setting()
        if save_battle_status is not None and save_battle_status != status:
            set_is_save_battle_speed_setting(status)
            self.log_debug(f"修改沿用自动战斗设置: {'启用' if save_battle_status else '禁用'} --> {'启用' if status else '禁用'}")
        gamereg_uid_value = gamereg_uid()
        if gamereg_uid_value:
            user_speed_up_status = get_user_speed_up_open_setting(str(gamereg_uid_value))
            if user_speed_up_status is not None and user_speed_up_status != status:
                set_user_speed_up_open_setting(str(gamereg_uid_value), status)
                self.log_debug(f"修改战斗二倍速状态: {'开启' if user_speed_up_status else '关闭'} --> {'开启' if status else '关闭'}")
        else:
            self.log_debug("未检测到 UID，跳过修改战斗二倍速设置")
