from PySide6.QtWidgets import QFileDialog
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import MessageBox
from app.common.icon import UiIcon
from app.card.comboboxsettingcard2 import ComboBoxSettingCard2
from app.card.switchsettingcard1 import SwitchSettingCard1
from app.card.game_path_setting_card import GamePathSettingCard
from app.card.adb_setting_cards import AdbDeviceCard, AdbEnvironmentCard, AdbStatusCard, AdbAdvancedCard
from app.card.rangesettingcard1 import RangeSettingCard1
from app.card.pushsettingcard1 import PushSettingCardEval
from app.card.expandable_switch_setting_card import ExpandableSwitchSettingCard, ExpandableComboBoxSettingCard
from module.config import cfg
from app.common.mascot import Mascot
from app.components.mascot_dialog import add_mascot
from module.localization import tr
from app.content.backend import block_while_running


def build(host):
    def choose_game_path():
        game_path, _ = QFileDialog.getOpenFileName(
            host.card_parent,
            tr("选择游戏路径"),
            "",
            tr("脚本或可执行文件 (*.exe *.bat *.cmd *.ps1)")
        )
        if not game_path or cfg.game_path == game_path:
            return
        cfg.set_value("game_path", game_path)
        host.gamePathCard.setContent(game_path)

    def confirm_local_mode(value):
        """切换到后台模式前说明限制；确认后才写入配置，取消则保留原模式。"""
        if value != 'background':
            return True
        confirm = MessageBox(
            tr("启用后台模式前请确认"),
            tr("后台模式下，任务运行时你可以继续使用电脑，但仍有以下限制：\n\n"
               "• 点击和拖动会短暂借用鼠标，完成后归还；你正在移动鼠标时，任务会等鼠标停下再操作。\n"
               "• 在大世界中按键时，光标会被短暂锁定在游戏窗口中央。\n"
               "• 游戏窗口可以放在其他窗口后面，但不能最小化；运行期间请保持系统解锁。\n"
               "• 锄大地、第三方模拟宇宙等独立程序不受此设置影响，仍需前台运行。\n\n"
               "设置在下次启动任务时生效，自动对话需重新开启。完整说明见使用文档“后台运行”。"),
            host.window
        )
        confirm.yesButton.setText(tr("我已了解，启用后台模式"))
        confirm.cancelButton.setText(tr("取消"))
        add_mascot(confirm, Mascot.SERIOUS)
        return bool(confirm.exec())

    host.gamePathCard = GamePathSettingCard(parent=host.card_parent)
    host.autoSetGamePathEnableCard = SwitchSettingCard1(
        FIF.GAME,
        tr('启用自动配置游戏路径'),
        tr("通过快捷方式、官方启动器、运行中的游戏进程等方式尝试自动配置游戏路径（支持国服和国际服）"),
        "auto_set_game_path_enable",
        parent=host.card_parent,
    )
    host.useBackgroundScreenshotCard = SwitchSettingCard1(
        FIF.CAMERA,
        tr('优先使用后台截图'),
        tr("默认开启，可以避免悬浮窗等干扰"),
        "use_background_screenshot",
        parent=host.card_parent,
    )
    host.localControlModeCard = ExpandableComboBoxSettingCard(
        'local_control_mode', FIF.GAME, tr('本地操作模式'),
        tr('后台操作遇到鼠标干扰时会等待并重试；下次启动任务生效。'),
        texts={tr('前台'): 'foreground', tr('后台'): 'background'},
        confirm=confirm_local_mode,
        parent=host.card_parent,
    )
    host.backgroundMouseProtectionCard = SwitchSettingCard1(
        FIF.GAME, tr('重试失败时短暂锁定鼠标'),
        tr('仅保护必要的鼠标操作，保留键盘和暂停热键。'),
        'background_mouse_protection',
        parent=host.card_parent,
    )
    host.adbDeviceCard = AdbDeviceCard(parent=host.card_parent)
    host.adbEnvironmentCard = AdbEnvironmentCard(blocker=lambda: block_while_running(host.window, tr("环境检查会占用设备，请等任务结束后再检查")), parent=host.card_parent)
    host.adbStatusCard = AdbStatusCard(parent=host.card_parent)
    host.adbAdvancedCard = AdbAdvancedCard(parent=host.card_parent)
    def refresh_mouse_protection_option(*_args):
        host.backgroundMouseProtectionCard.setEnabled(cfg.get_value('local_control_mode') == 'background')
    host.localControlModeCard.currentIndexChanged.connect(refresh_mouse_protection_option)
    host.refresh_mouse_option = refresh_mouse_protection_option
    refresh_mouse_protection_option()
    host.gamePathCard.clicked.connect(choose_game_path)
    host.adbDeviceCard.serialChanged.connect(lambda _serial: host.adbAdvancedCard.refreshSerial())
    host.adbAdvancedCard.serialChanged.connect(host.adbDeviceCard.setSelectedSerial)
    return host.finish("run_mode", (
        ("localControlModeCard", ('backgroundMouseProtectionCard',)),
    ))
