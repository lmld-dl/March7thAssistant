from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import MessageBox
from app.common.icon import UiIcon
from app.card.comboboxsettingcard2 import ComboBoxSettingCard2
from app.card.switchsettingcard1 import SwitchSettingCard1
from app.card.rangesettingcard1 import RangeSettingCard1
from app.card.expandable_switch_setting_card import ExpandableSwitchSettingCard
from app.card.stationprioritysettingcard import StationPrioritySettingCard
from app.common.mascot import Mascot
from app.components.mascot_dialog import add_mascot
from module.localization import tr, translations_of
from module.search.setting_text import choice_texts
from module.config import cfg
from PySide6.QtCore import QSignalBlocker


def confirm_external_enable(window):
    confirm = MessageBox(
        tr("启用前请确认用途"),
        tr("此选项及其子选项用于配置反复刷取遗器经验和灵之珠泪，直到达到每周上限。\n默认运行次数为每周 34 次。\n请确认你已经清楚了解这个功能的作用，并确保知道自己在做什么后再开启。"),
        window
    )
    confirm.yesButton.setText(tr("我已了解，继续开启"))
    confirm.cancelButton.setText(tr("取消"))
    add_mascot(confirm, Mascot.SERIOUS)

    return bool(confirm.exec())


def build(host):
    def confirm_external(checked):
        if checked and not confirm_external_enable(host.window):
            host.universeEnableCard.switchButton.setChecked(False)

    host.weeklyDivergentTypeCard = ComboBoxSettingCard2(
        "weekly_divergent_type",
        UiIcon.OPTIONS,
        tr('类别'),
        '',
        texts=choice_texts("weekly_divergent_type"),
        parent=host.card_parent,
    )
    host.weeklyDivergentBonusEnableCard = SwitchSettingCard1(
        UiIcon.DIAMOND,
        tr('自动执行饰品提取'),
        tr("在领取积分奖励后自动执行饰品提取消耗沉浸器"),
        "weekly_divergent_bonus_enable",
        parent=host.card_parent,
    )
    host.weeklyDivergentLevelCard = ComboBoxSettingCard2(
        "weekly_divergent_level",
        UiIcon.GAUGE,
        tr("难度等级"),
        "",
        texts={f"{tr('难度')} Ⅰ": 1, f"{tr('难度')} Ⅱ": 2, f"{tr('难度')} Ⅲ": 3, f"{tr('难度')} Ⅳ": 4, f"{tr('难度')} Ⅴ": 5, f"{tr('难度')} Ⅹ{tr('（星阶模式）')}": 6},
        parent=host.card_parent,
    )
    host.stationPriorityCard = StationPrioritySettingCard(
        UiIcon.LIST,
        tr('站点优先级'),
        tr("自定义差分宇宙「选择下一站」的站点优先级"),
        parent=host.card_parent,
    )
    host.weeklyDivergentStableModeCard = SwitchSettingCard1(
        FIF.SPEED_OFF,
        tr('启用低性能兼容模式'),
        tr("建议仅在低性能设备开启，可以提高事件和随意门交互的成功率（云游戏强制使用此模式）"),
        "weekly_divergent_stable_mode",
        parent=host.card_parent,
    )
    host.divergentAutoSaveCard = SwitchSettingCard1(
        FIF.SAVE_AS,
        tr("自动记录差分宇宙存档"),
        tr("探索成功后保存到第一个空存档位；存档已满时跳过"),
        "divergent_auto_save_enable",
        parent=host.card_parent,
    )
    return host.finish("universe")
