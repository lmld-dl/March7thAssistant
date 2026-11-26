from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import MessageBox, PushSettingCard
from utils.desktop_twin import in_desktop_twin
from app.common.icon import UiIcon
from app.card.comboboxsettingcard2 import ComboBoxSettingCard2, ComboBoxSettingCardLog
from app.card.switchsettingcard1 import SwitchSettingCard1, SwitchSettingCardWithAction
from app.card.autostart_setting_card import AutostartSettingCard
from app.card.uac_free_setting_card import UacFreeSettingCard
from module.localization import tr
import sys


def build(host):
    host.setupWizardCard = PushSettingCard(
        tr("打开向导"), FIF.BOOK_SHELF, tr("首次配置向导"),
        tr("重新设置游戏位置、每天要做的任务、运行时间和通知"), parent=host.card_parent,
    )
    host.setupWizardCard.setDisabled(in_desktop_twin())
    host.setupWizardCard.clicked.connect(lambda: host.window.openSetup())
    host.logLevelCard = ComboBoxSettingCardLog(
        "log_level",
        FIF.TAG,
        tr('日志等级'),
        "",
        texts={tr('简洁'): 'INFO', tr('详细'): 'DEBUG'},
        parent=host.card_parent,
    )
    host.ocrGpuAccelerationCard = ComboBoxSettingCard2(
        "ocr_gpu_acceleration",
        FIF.SPEED_HIGH,
        tr('OCR 加速模式'),
        tr("设置 OCR 引擎与加速后端。自动模式会优先尝试 DirectML，若不可用则回退到 CPU 引擎。"),
        texts={
            tr('自动'): 'auto',
            tr('GPU'): 'gpu',
            tr('ONNXRuntime（DirectML）'): 'onnx_dml',
            tr('CPU'): 'cpu',
            tr('OpenVINO（CPU）'): 'openvino_cpu',
            tr('ONNXRuntime（CPU）'): 'onnx_cpu',
        },
        parent=host.card_parent,
    )
    if sys.platform == 'win32':
        host.autostartCard = AutostartSettingCard(
            FIF.GAME,
            tr('在用户登录时启动'),
            tr("登录后自动启动，点击「配置」进行详细设置；无人值守可能需要自行配置 Windows 自动登录"),
            parent=host.card_parent,
        )
        host.uacFreeCard = UacFreeSettingCard(
            FIF.COMMAND_PROMPT,
            tr('免 UAC 运行'),
            tr("开启后，AI 助手或脚本通过 m7a.exe 运行任务时不再弹出 UAC 确认，适合让 AI 助手远程运行任务"),
            parent=host.card_parent,
        )
        host.debugModeEnableCard = SwitchSettingCard1(
            FIF.DEVELOPER_TOOLS,
            tr('启用调试模式'),
            tr("开启后会在屏幕上实时绘制检测范围框（透明悬浮窗），用于调试自动化识别效果。仅 Windows 生效。"),
            "debug_mode_enable",
            parent=host.card_parent,
        )
    return host.finish("advanced")
