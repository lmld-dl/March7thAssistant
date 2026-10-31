from PySide6.QtCore import Qt, QUrl, QObject, QEvent, QPoint, QThread, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget, QLabel, QFileDialog, QVBoxLayout, QStackedWidget, QSpacerItem, QScroller, QScrollerProperties, QScrollArea, QFrame, QApplication
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import SettingCardGroup, PushSettingCard, ScrollArea, InfoBar, InfoBarPosition, PrimaryPushSettingCard, MessageBox, PushButton, StateToolTip
from app.sub_interfaces.accounts_interface import accounts_interface
from .common.style_sheet import StyleSheet
from .common.icon import UiIcon, BrandIcon
from .components.pivot import SettingPivot
from .card.comboboxsettingcard1 import ComboBoxSettingCard1
from .card.comboboxsettingcard2 import ComboBoxSettingCard2, ComboBoxSettingCardUpdateSource, ComboBoxSettingCardLog, ComboBoxSettingCardLanguage
from .card.switchsettingcard1 import SwitchSettingCard1, SwitchSettingCardWithAction, TimestampSwitchSettingCard, SwitchSettingCardTeam, SwitchSettingCardImmersifier, SwitchSettingCardGardenofplenty, SwitchSettingCardEchoofwar, SwitchSettingCardHotkey, SwitchSettingCardCloudGameStatus
from .card.autostart_setting_card import AutostartSettingCard
from .card.game_path_setting_card import GamePathSettingCard
from .card.rangesettingcard1 import RangeSettingCard1
from .card.pushsettingcard1 import CustomPushSettingCard, DualPushSettingCard, TriplePushSettingCard, PushSettingCardAction, PushSettingCardInstance, PushSettingCardInstanceChallengeCount, PushSettingCardNotifyTemplate, PushSettingCardMirrorchyan, PushSettingCardStr, PushSettingCardEval, PushSettingCardDate, PushSettingCardKey, PushSettingCardTeam, PushSettingCardFriends, PushSettingCardTeamWithSwap, PushSettingCardPowerPlan, InstanceTeamSettingCard
from .card.timepickersettingcard1 import TimePickerSettingCard1
from .card.expandable_switch_setting_card import ExpandableSwitchSettingCard, ExpandableWeeklyRelicSettingCard, ExpandableTimestampSwitchSettingCard, ExpandableComboBoxSettingCardUpdateSource, ExpandableComboBoxSettingCard, ExpandableComboBoxSettingCardInstanceType, ExpandableSwitchSettingCardEchoofwar
from .card.messagebox_custom import MessageBoxEdit
from .challenge_config_dialog import ChallengeConfigCard
from .card.stationprioritysettingcard import StationPrioritySettingCard
from module.config import cfg
from module.notification import init_notifiers
from module.localization import tr, tn
from module.localization.languages import AUTO_LANGUAGE, available_languages
from tasks.weekly.divergent_universe import DivergentUniverse
from tasks.base.tasks import start_task
from .tools.agent_prompt import build_agent_prompt
from utils import clipboard
import os
import random
import sys
import platform


class _PivotScrollFilter(QObject):
    """为 pivot 及其所有子控件（tab 按钮）提供横向拖拽滚动支持。

    安装方式（在所有 addItem 完成后）：
        self.pivot.installEventFilter(filter)
        for child in self.pivot.findChildren(QWidget):
            child.installEventFilter(filter)

    拖拽后防止误切 tab 的机制：
        进入拖拽模式后立即对 pivot 调用 grabMouse()，把后续所有鼠标事件
        路由到 pivot 而非 tab 子控件。松开时 releaseMouse() 还原路由，
        并对 pivot 发送 Leave 事件重置 hover 状态，完全杜绝误切 tab。
    """
    _DRAG_THRESHOLD = 5  # px；低于此值视为点击，不进入拖拽模式

    def __init__(self, scroll_area: QScrollArea, pivot):
        super().__init__(scroll_area)
        self._sa = scroll_area
        self._pivot = pivot
        self._press_global: QPoint | None = None
        self._drag_origin: int = 0
        self._is_dragging: bool = False

    def eventFilter(self, obj, event: QEvent) -> bool:
        t = event.type()

        # ── 滚轮 → 横向滚动（消费，不冒泡给外层纵向 ScrollArea）───────
        if t == QEvent.Type.Wheel:
            delta = event.angleDelta()
            scroll = delta.x() if delta.x() != 0 else delta.y()
            sb = self._sa.horizontalScrollBar()
            sb.setValue(sb.value() - scroll // 3)
            return True

        # ── 按下 → 记录全局起点，放行（tab 正常 press/hover）────────────
        if t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._drag_origin = self._sa.horizontalScrollBar().value()
            self._is_dragging = False
            return False

        # ── 移动 → 超阈值进入拖拽，grabMouse 接管后续事件 ───────────────
        if t == QEvent.Type.MouseMove and (event.buttons() & Qt.MouseButton.LeftButton):
            if self._press_global is not None:
                dx = event.globalPosition().toPoint().x() - self._press_global.x()
                if not self._is_dragging and abs(dx) > self._DRAG_THRESHOLD:
                    self._is_dragging = True
                    # grabMouse：把所有后续鼠标事件路由到 pivot，
                    # 子控件（tab 按钮）不再收到 Release/Click，彻底防止误切 tab
                    self._pivot.grabMouse(Qt.CursorShape.ClosedHandCursor)
                if self._is_dragging:
                    self._sa.horizontalScrollBar().setValue(self._drag_origin - dx)
                    return True
            return False

        # ── 释放 → 拖拽：releaseMouse + 发送 Leave，清理状态 ────────────
        if t == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            if self._press_global is not None:
                was_dragging = self._is_dragging
                self._press_global = None
                self._is_dragging = False
                if was_dragging:
                    self._pivot.releaseMouse()
                    # 发送 Leave 事件让 pivot 及子控件重置 hover 样式
                    leave = QEvent(QEvent.Type.Leave)
                    QApplication.sendEvent(self._pivot, leave)
                    return True  # 消费 Release，不触发 tab 切换
            return False

        return False


class SettingInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self._ignoreUniverseEnableCardSwitchChanged = False
        self._ignoreCheckUpdateCardSwitchChanged = False
        self.scrollWidget = QWidget()
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        # self.title_area = QScrollArea(self)
        self.pivot = SettingPivot(self)
        self.stackedWidget = QStackedWidget(self)

        self.settingLabel = QLabel(tr("设置"), self)

        self.__initWidget()
        self.__initCard()
        self.__initLayout()
        self.__connectSignalToSlot()

    def __initWidget(self):
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setViewportMargins(0, 140, 0, 5)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # self.title_area.setWidget(self.pivot)
        # self.title_area.setWidgetResizable(True)
        # self.title_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        # self.title_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.title_area.setMinimumSize(800, 50)
        # self.title_area.setStyleSheet("""
        #     QScrollBar:horizontal {
        #         height: 4px;
        #         background: #f0f0f0;
        #         border-radius: 10px;
        #     }

        #     QScrollBar::handle:horizontal {
        #         background: #888;
        #         border-radius: 10px;
        #     }

        #     QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        #         background: none;
        #     }

        #     QScrollBar::handle:horizontal:hover {
        #         background: #555;
        #     }
        # """)
        self.setObjectName('settingInterface')
        self.scrollWidget.setObjectName('scrollWidget')
        self.settingLabel.setObjectName('settingLabel')
        StyleSheet.SETTING_INTERFACE.apply(self)

        # ── 选项卡滚动容器 ──────────────────────────────────────────────
        # 当标签文字较长（如英语）时允许横向滚动。滚动条隐藏，仅保留拖拽交互。
        # 注意：不在此处安装 _PivotScrollFilter，因为 pivot 的 tab 子控件
        # 尚未创建（addItem 在 __initLayout 中调用）。filter 在 __initLayout
        # 最后通过 pivot.findChildren(QWidget) 递归安装，覆盖所有 tab 子控件。
        self.pivotScrollArea = QScrollArea(self)
        self.pivotScrollArea.setWidget(self.pivot)
        self.pivotScrollArea.setWidgetResizable(False)
        self.pivotScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.pivotScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.pivotScrollArea.setFrameShape(QFrame.Shape.NoFrame)

        QScroller.grabGesture(self.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)
        scroller = QScroller.scroller(self.viewport())
        scroller_props = scroller.scrollerProperties()
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootDragDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootScrollDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, 0.5)
        scroller.setScrollerProperties(scroller_props)

    def __initCard(self):
        self.PowerGroup = SettingCardGroup(tr("体力设置"), self.scrollWidget)
        self.powerPlanCard = PushSettingCardPowerPlan(
            tr('配置'),
            FIF.CALENDAR,
            tr("体力计划"),
            "power_plan"
        )
        self.instanceTypeCard = ExpandableComboBoxSettingCardInstanceType(
            "instance_type",
            UiIcon.LIST,
            tr("副本类型"),
            None,
            texts=[tr('拟造花萼（金）'), tr('拟造花萼（赤）'), tr('凝滞虚影'), tr('侵蚀隧洞'), tr('饰品提取')]
        )
        # self.calyxGoldenPreferenceCard = ComboBoxSettingCard2(
        #     "calyx_golden_preference",
        #     FIF.PIE_SINGLE,
        #     '拟造花萼（金）偏好地区',
        #     '',
        #     texts={'雅利洛-VI': 'Jarilo-VI', '仙舟「罗浮」': 'XianzhouLuofu', '匹诺康尼': 'Penacony'}
        # )
        self.instanceNameCard = PushSettingCardInstance(
            tr('修改'),
            UiIcon.BOOKMARK,
            tr("副本名称"),
            "instance_names"
        )
        # self.maxCalyxPerRoundNumOfAttempts = RangeSettingCard1(
        #     "max_calyx_per_round_num_of_attempts",
        #     [1, 6],
        #     FIF.HISTORY,
        #     "每轮拟造花萼挑战次数",
        #     '',
        # )
        self.instanceTeamEnableCard = InstanceTeamSettingCard(
            UiIcon.PEOPLE_SWAP,
            tr("自动切换队伍"),
            None
        )
        self.tpBeforeInstanceEnableCard = SwitchSettingCard1(
            UiIcon.PIN,
            tr("清体力前传送至任意锚点"),
            "",
            "tp_before_instance"
        )
        self.powerEnableCard = SwitchSettingCard1(
            UiIcon.FLASH,
            tr("启用清体力"),
            tr("仅影响完整运行和“日常”中的历战余响与清体力，不影响单独执行“清体力”任务"),
            "power_enable"
        )
        # self.instanceTeamNumberCard = ComboBoxSettingCard1(
        #     "instance_team_number",
        #     FIF.FLAG,
        #     '队伍编号',
        #     None,
        #     texts=['3', '4', '5', '6', '7']
        # )
        self.useReservedTrailblazePowerEnableCard = SwitchSettingCard1(
            UiIcon.BATTERY_CHARGE,
            tr("使用后备开拓力"),
            tr("单次上限300点，全部使用需要将“任务完成后”选项修改为“循环”，然后点击“完整运行”"),
            "use_reserved_trailblaze_power"
        )
        self.useFuelEnableCard = SwitchSettingCard1(
            UiIcon.DROP,
            tr("使用燃料"),
            tr("单次上限5个，全部使用需要将“任务完成后”选项修改为“循环”，然后点击“完整运行”"),
            "use_fuel"
        )
        self.weeklyRelicCleanupEnableCard = ExpandableWeeklyRelicSettingCard(
            "break_down_level_four_relicset",
            "weekly_relic_cleanup_day_of_week",
            FIF.FILTER,
            tr("每周清理遗器"),
        )
        self.smartRelicDiscardEnableCard = SwitchSettingCard1(
            FIF.DELETE,
            tr("启用智能弃置"),
            tr("按不匹配推荐角色和副属性 0 次筛选，分解已弃置及四星以下遗器"),
            "weekly_relic_smart_discard_enable",
        )
        self.mergeImmersifierEnableCard = SwitchSettingCardImmersifier(
            UiIcon.BEAKER,
            tr("体力优先合成沉浸器（建议直接通过饰品提取获取位面饰品）"),
            tr("达到指定上限后停止"),
            "merge_immersifier"
        )
        self.instanceNameChallengeCountCard = PushSettingCardInstanceChallengeCount(
            tr('修改'),
            UiIcon.REPEAT,
            tr("副本最大连续挑战次数（通常不建议修改保持默认即可）"),
            "instance_names_challenge_count"
        )
        self.borrowEnableCard = ExpandableSwitchSettingCard(
            "borrow_enable",
            UiIcon.PEOPLE,
            tr("启用使用支援角色"),
            ''
        )
        self.borrowCharacterEnableCard = SwitchSettingCard1(
            UiIcon.PEOPLE_CHECKMARK,
            tr("强制使用支援角色"),
            tr("无论何时都要使用支援角色，即使日常实训中的要求已经完成"),
            "borrow_character_enable"
        )
        self.borrowFriendsCard = PushSettingCardFriends(
            tr('修改'),
            UiIcon.PEOPLE_LIST,
            tr("支援列表"),
            "borrow_friends"
        )
        self.borrowScrollTimesCard = RangeSettingCard1(
            "borrow_scroll_times",
            [1, 10],
            UiIcon.REPEAT,
            tr("滚动查找次数"),
            '',
        )
        self.buildTargetEnableCard = ExpandableSwitchSettingCard(
            "build_target_enable",
            UiIcon.TARGET,
            tr("启用培养目标"),
            tr("根据培养目标刷取行迹与遗器副本，如果无法获取培养目标则回退到默认的副本设置")
        )
        self.buildTargetSchemeCard = ComboBoxSettingCard2(
            "build_target_scheme",
            FIF.SEARCH,
            tr("识别方案"),
            tr("副本名称识别会进入挑战页读取副本信息；掉落物识别根据列表中的掉落物匹配副本，异常时可尝试切换方案"),
            texts={
                tr("副本名称识别"): "instance",
                tr("掉落物识别"): "drop"
            }
        )
        self.buildTargetPlanarOrnamentWeeklyCountCard = RangeSettingCard1(
            "build_target_ornament_weekly_count",
            [0, 7],
            UiIcon.DIAMOND,
            tr("每周饰品提取次数"),
            tr("目标有足够资源后，执行饰品提取的次数，其余时间执行侵蚀隧洞"),
        )
        self.buildTargetUseUserInstanceWhenOnlyErosionAndOrnamentCard = SwitchSettingCard1(
            FIF.SYNC,
            tr("仅识别到侵蚀隧洞/饰品提取时使用自定义副本"),
            tr("开启后，当培养目标仅包含侵蚀隧洞和饰品提取时，清体力将改用你在体力设置中配置的副本"),
            "build_target_use_user_instance_when_only_erosion_and_ornament"
        )
        self.echoofwarEnableCard = ExpandableSwitchSettingCardEchoofwar(
            "echo_of_war_enable",
            UiIcon.TARGET_ARROW,
            tr("启用历战余响"),
            tr("每周体力优先完成三次「历战余响」，支持配置从周几后开始执行，仅限完整运行生效"),
        )
        self.echoofwarRunTimeCard = PushSettingCardDate(
            tr('修改'),
            FIF.DATE_TIME,
            tr("上次完成历战余响的时间"),
            "echo_of_war_timestamp"
        )
        # self.echoofwarStartDayOfWeekCard = RangeSettingCard1(
        #     "echo_of_war_start_day_of_week",
        #     [1, 7],
        #     FIF.HISTORY,
        #     "周几开始执行【历战余响】",
        #     "假设值为4，那么周1、2、3不执行「历战余响」，周4、5、6、7则执行",
        # )
        # self.borrowCharacterFromCard = PushSettingCardEval(
        #     '修改',
        #     FIF.PEOPLE,
        #     "指定好友的支援角色（填写用户名，模糊匹配模式）",
        #     "borrow_character_from"
        # )
        # self.borrowCharacterInfoCard = PrimaryPushSettingCard(
        #     '打开角色文件夹',
        #     FIF.INFO,
        #     "↓↓支援角色↓↓",
        #     "角色对应的英文名字可以在 \"March7thAssistant\\assets\\images\\share\\character\" 中查看"
        # )
        # self.borrowCharacterCard = PushSettingCardEval(
        #     '修改',
        #     FIF.ARROW_DOWN,
        #     "支援角色优先级（从高到低）",
        #     "borrow_character"
        # )

        self.DailyGroup = SettingCardGroup(tr("日常设置"), self.scrollWidget)
        self.dailyEnableCard = ExpandableTimestampSwitchSettingCard(
            "daily_enable",
            "last_run_timestamp",
            FIF.CALENDAR,
            tr("启用每日实训"),
            tr("上次检测到完成日常的时间"),
            ""
        )
        self.dailyMaterialEnableCard = SwitchSettingCard1(
            FIF.CHECKBOX,
            tr('通过 “合成材料” 完成任务'),
            tr("请确保背包中有足够的 “熄灭原核” 用于合成 “微光原核” "),
            "daily_material_enable"
        )
        # self.dailyHimekoTryEnableCard = SwitchSettingCard1(
        #     FIF.CHECKBOX,
        #     '通过 “姬子试用” 完成任务',
        #     "",
        #     "daily_himeko_try_enable"
        # )
        self.dailyMemoryOneEnableCard = SwitchSettingCard1(
            FIF.CHECKBOX,
            tr('通过 “回忆一” 完成任务'),
            tr("请解锁混沌回忆并配置了队伍后再打开该选项"),
            "daily_memory_one_enable"
        )
        self.dailyMemoryOneTeamCard = PushSettingCardTeam(
            tr('修改'),
            FIF.FLAG,
            tr("回忆一队伍"),
            "daily_memory_one_team"
        )
        self.activityEnableCard = ExpandableSwitchSettingCard(
            "activity_enable",
            UiIcon.SPARKLE,
            tr('启用活动检测'),
            None
        )
        self.activityDailyCheckInEnableCard = SwitchSettingCard1(
            FIF.COMPLETED,
            tr('每日签到'),
            tr("自动领取「星轨专票」或「星琼」，包含巡星之礼、巡光之礼和庆典祝礼活动"),
            "activity_dailycheckin_enable"
        )
        self.activityGardenOfPlentyEnableCard = SwitchSettingCardGardenofplenty(
            UiIcon.LEAF,
            tr('花藏繁生'),
            tr("存在双倍次数时体力优先「拟造花萼」"),
            "activity_gardenofplenty_enable"
        )
        self.activityRealmOfTheStrangeEnableCard = SwitchSettingCard1(
            UiIcon.DIAMOND,
            tr('异器盈界'),
            tr("存在双倍次数时体力优先「侵蚀隧洞」"),
            "activity_realmofthestrange_enable"
        )
        self.activityPlanarFissureEnableCard = SwitchSettingCard1(
            UiIcon.CUBE,
            tr('位面分裂'),
            tr("存在双倍次数时体力优先「饰品提取」"),
            "activity_planarfissure_enable"
        )
        self.activityJourneyHighlightsNotificationEnableCard = SwitchSettingCard1(
            FIF.CALENDAR,
            tr('活动热点通知'),
            tr("每次运行时发送带有活动热点截图的通知"),
            "activity_journey_highlights_notification_enable"
        )
        self.rewardEnableCard = ExpandableSwitchSettingCard(
            "reward_enable",
            UiIcon.GIFT,
            tr('启用奖励领取'),
            ""
        )
        self.dispatchEnableCard = SwitchSettingCard1(
            UiIcon.SEND,
            tr('委托'),
            None,
            "reward_dispatch_enable"
        )
        self.mailEnableCard = SwitchSettingCard1(
            FIF.MAIL,
            tr('邮件'),
            None,
            "reward_mail_enable"
        )
        self.assistEnableCard = SwitchSettingCard1(
            UiIcon.PEOPLE_LINK,
            tr('支援'),
            None,
            "reward_assist_enable"
        )
        self.questEnableCard = SwitchSettingCard1(
            UiIcon.CLIPBOARD_TASK,
            tr('每日实训'),
            None,
            "reward_quest_enable"
        )
        self.srpassEnableCard = SwitchSettingCard1(
            UiIcon.CROWN,
            tr('无名勋礼'),
            None,
            "reward_srpass_enable"
        )
        self.achievementEnableCard = SwitchSettingCard1(
            UiIcon.TROPHY,
            tr('成就'),
            None,
            "reward_achievement_enable"
        )

        # 兑换码奖励开关
        self.redemptionEnableCard = SwitchSettingCard1(
            UiIcon.TICKET,
            tr('兑换码'),
            None,
            "reward_redemption_code_enable"
        )

        # 短信奖励开关
        self.messageEnableCard = SwitchSettingCard1(
            FIF.CHAT,
            tr('短信'),
            None,
            "reward_message_enable"
        )

        self.assetEnableCard = ExpandableSwitchSettingCard(
            "asset_manager_enable",
            UiIcon.BOX,
            tr("启用资产管理"),
            ""
        )

        self.lc3StarSuperimposeEnableCard = SwitchSettingCard1(
            UiIcon.STACK,
            tr("启用「3星光锥自动叠加」"),
            tr("自动将3星光锥进行叠加以节省背包空间"),
            "asset_lc3_star_superimpose_enable",
        )
        self.selfMoldingResinEnableCard = TimestampSwitchSettingCard(
            FIF.CALENDAR,
            tr("启用「每月自动合成自塑尘脂」"),
            tr("每月自动尝试合成 2 个自塑尘脂，成功后记录时间，并在每月 1 号刷新"),
            "asset_self_molding_resin_enable",
            "asset_self_molding_resin_timestamp",
            tr("上次完成自塑尘脂合成的时间"),
        )
        self.emberSpecialPassEnableCard = TimestampSwitchSettingCard(
            FIF.CALENDAR,
            tr("启用「每月自动购买{item}」").format(item=tr("星轨专票")),
            tr("每月自动尝试在余烬兑换中购买「{item}」，点击最大值并确认后记录时间，并在每月 1 号刷新").format(item=tr("星轨专票")),
            "asset_ember_special_pass_enable",
            "asset_ember_special_pass_timestamp",
            tr("上次完成{item}购买的时间").format(item=tr("星轨专票")),
        )
        self.emberRegularPassEnableCard = TimestampSwitchSettingCard(
            FIF.CALENDAR,
            tr("启用「每月自动购买{item}」").format(item=tr("星轨通票")),
            tr("每月自动尝试在余烬兑换中购买「{item}」，点击最大值并确认后记录时间，并在每月 1 号刷新").format(item=tr("星轨通票")),
            "asset_ember_regular_pass_enable",
            "asset_ember_regular_pass_timestamp",
            tr("上次完成{item}购买的时间").format(item=tr("星轨通票")),
        )
        self.emberTracksOfDestinyEnableCard = TimestampSwitchSettingCard(
            FIF.CALENDAR,
            tr("启用「每月自动购买{item}」").format(item=tr("命运的足迹")),
            tr("每月自动尝试在余烬兑换中购买「{item}」，点击最大值并确认后记录时间，并在每月 1 号刷新").format(item=tr("命运的足迹")),
            "asset_ember_tracks_of_destiny_enable",
            "asset_ember_tracks_of_destiny_timestamp",
            tr("上次完成{item}购买的时间").format(item=tr("命运的足迹")),
        )

        self.CurrencywarsGroup = SettingCardGroup(tr("货币"), self.scrollWidget)
        self.currencywarsEnableCard = TimestampSwitchSettingCard(
            UiIcon.MONEY,
            tr('启用「货币战争」积分奖励'),
            "",
            "currencywars_enable",
            "currencywars_timestamp",
            tr("上次检测到完成货币战争积分奖励的时间")
        )
        self.currencywarsPresetCard = DualPushSettingCard(
            tr('提升晋升等级'),
            tr('提升职级等级'),
            UiIcon.WAND,
            tr('快捷配置')
        )
        self.currencywarsTypeCard = ComboBoxSettingCard2(
            "currencywars_type",
            UiIcon.OPTIONS,
            tr('类别'),
            '',
            texts={tr('标准博弈'): 'normal', tr('超频博弈'): 'overclock'}
        )
        self.currencywarsBonusEnableCard = SwitchSettingCard1(
            UiIcon.DIAMOND,
            tr('自动执行位面饰品快速提取'),
            tr("在领取积分奖励后自动执行位面饰品快速提取消耗深度沉浸器"),
            "currencywars_bonus_enable"
        )
        self.currencywarsRankDifficultyCard = ComboBoxSettingCard2(
            "currencywars_rank_difficulty",
            UiIcon.GAUGE,
            tr('职级难度'),
            '',
            texts={tr('最高职级'): 'highest', tr('当前职级'): 'current', tr('最低职级'): 'lowest'}
        )
        self.currencywarsStrategyCard = ExpandableComboBoxSettingCard(
            "currencywars_strategy",
            UiIcon.LIST,
            tr('货币战争策略'),
            tr('提升晋升等级，推荐在最低职级选择默认策略。提升职级等级，推荐在最高职级选择阿格莱雅或希儿策略。'),
            {tr('默认'): 'default', tr('阿格莱雅'): 'aglaea', tr('希儿') + tr('【测试版】'): 'seele'}
        )
        self.currencywarsRemembranceTrailblazerNameCard = PushSettingCardStr(
            tr('修改'),
            FIF.EDIT,
            tr('「开拓者•记忆」名称'),
            "currencywars_remembrance_trailblazer_name",
            empty_content=tr('未配置时，阿格莱雅/希儿策略将跳过该角色，需要填入自己游戏名称')
        )
        self.currencywarsStrategyRestartOnSpecialTagsCard = SwitchSettingCard1(
            UiIcon.REFRESH,
            tr('遇到特定词条时接受重开'),
            tr('根据所选策略，在遇到特定词条或词条组合时允许重开'),
            "currencywars_strategy_restart_on_special_tags"
        )
        self.currencywarsFastModeCard = SwitchSettingCard1(
            UiIcon.ROCKET,
            tr('启用速通模式'),
            tr("开启后，仅在首领节点尝试装备武器，只推荐在最低职级时开启"),
            "currencywars_fast_mode"
        )

        self.UniverseGroup = SettingCardGroup(tr("差分宇宙"), self.scrollWidget)
        self.weeklyDivergentEnableCard = TimestampSwitchSettingCard(
            UiIcon.PLANET,
            tr('启用「差分宇宙」积分奖励'),
            "",
            "weekly_divergent_enable",
            "weekly_divergent_timestamp",
            tr("上次检测到完成差分宇宙积分奖励的时间")
        )
        self.weeklyDivergentTypeCard = ComboBoxSettingCard2(
            "weekly_divergent_type",
            UiIcon.OPTIONS,
            tr('类别'),
            '',
            texts={tr('常规演算'): 'normal', tr('周期演算'): 'cycle'}
        )
        self.weeklyDivergentLevelCard = ComboBoxSettingCard2(
            "weekly_divergent_level",
            UiIcon.GAUGE,
            tr("难度等级"),
            "",
            texts={f"{tr('难度')} Ⅰ": 1, f"{tr('难度')} Ⅱ": 2, f"{tr('难度')} Ⅲ": 3, f"{tr('难度')} Ⅳ": 4, f"{tr('难度')} Ⅴ": 5, f"{tr('难度')} Ⅹ{tr('（星阶模式）')}": 6}
        )
        self.weeklyDivergentBonusEnableCard = SwitchSettingCard1(
            UiIcon.DIAMOND,
            tr('自动执行饰品提取'),
            tr("在领取积分奖励后自动执行饰品提取消耗沉浸器"),
            "weekly_divergent_bonus_enable"
        )
        self.weeklyDivergentStableModeCard = SwitchSettingCard1(
            FIF.SPEED_OFF,
            tr('启用低性能兼容模式'),
            tr("建议仅在低性能设备开启，可以提高事件和随意门交互的成功率"),
            "weekly_divergent_stable_mode"
        )
        self.divergentAutoSaveCard = SwitchSettingCard1(
            FIF.SAVE_AS,
            tr("自动记录差分宇宙存档"),
            tr("探索成功后保存到第一个空存档位；存档已满时跳过"),
            "divergent_auto_save_enable"
        )

        self.stationPriorityCard = StationPrioritySettingCard(
            UiIcon.LIST,
            tr('站点优先级'),
            tr("自定义差分宇宙「选择下一站」的站点优先级"),
        )

        self.ImmortalGameGroup = SettingCardGroup(tr("逐光捡金"), self.scrollWidget)
        self.forgottenhallEnableCard = ExpandableTimestampSwitchSettingCard(
            "forgottenhall_enable",
            "forgottenhall_timestamp",
            UiIcon.TARGET_ARROW,
            tr('启用混沌回忆'),
            tr("上次运行混沌回忆的时间"),
            ""
        )
        self.forgottenhallLevelCard = PushSettingCardEval(
            tr('修改'),
            UiIcon.FILTER,
            tr("关卡范围"),
            "forgottenhall_level"
        )
        # self.forgottenhallRetriesCard = RangeSettingCard1(
        #     "forgottenhall_retries",
        #     [0, 10],
        #     FIF.REMOVE_FROM,
        #     "重试次数",
        # )
        self.forgottenhallTeamsCard = PushSettingCardTeamWithSwap(
            UiIcon.PEOPLE_TEAM,
            tr("混沌回忆队伍配置"),
            "forgottenhall_team1",
            "forgottenhall_team2"
        )
        self.purefictionEnableCard = ExpandableTimestampSwitchSettingCard(
            "purefiction_enable",
            "purefiction_timestamp",
            UiIcon.TARGET_ARROW,
            tr('启用虚构叙事'),
            tr("上次运行虚构叙事的时间"),
            ""
        )
        self.purefictionConfigCard = ChallengeConfigCard(
            UiIcon.PEOPLE_TEAM,
            tr("虚构叙事配置"), "purefiction", 4
        )
        self.ApocalypticEnableCard = ExpandableTimestampSwitchSettingCard(
            "apocalyptic_enable",
            "apocalyptic_timestamp",
            UiIcon.TARGET_ARROW,
            tr('启用末日幻影'),
            tr("上次运行末日幻影的时间"),
            ""
        )
        self.ApocalypticLevelCard = PushSettingCardEval(
            tr('修改'),
            UiIcon.FILTER,
            tr("关卡范围"),
            "apocalyptic_level"
        )
        self.ApocalypticTeamsCard = PushSettingCardTeamWithSwap(
            UiIcon.PEOPLE_TEAM,
            tr("末日幻影队伍配置"),
            "apocalyptic_team1",
            "apocalyptic_team2"
        )
        self.ProgramGroup = SettingCardGroup(tr('程序设置'), self.scrollWidget)
        self.logLevelCard = ComboBoxSettingCardLog(
            "log_level",
            FIF.TAG,
            tr('日志等级'),
            "",
            texts={tr('简洁'): 'INFO', tr('详细'): 'DEBUG'}
        )
        self.gamePathCard = GamePathSettingCard()
        self.updateViaLauncherEnableCard = ExpandableSwitchSettingCard(
            "update_via_launcher",
            FIF.UPDATE,
            tr('通过启动器更新游戏'),
            ""
        )
        self.launcherPathCard = PushSettingCard(
            tr('修改'),
            FIF.GAME,
            tr("启动器路径"),
            cfg.launcher_path
        )
        self.launcherType = ComboBoxSettingCard2(
            "launcher_title_name",
            FIF.GAME,
            tr('启动器类型'),
            '',
            texts={tr('米哈游启动器'): '米哈游启动器', tr('HoYoPlay'): 'HoYoPlay'}
        )
        self.startGameTimeoutCard = RangeSettingCard1(
            "start_game_timeout",
            [10, 60],
            UiIcon.CLOCK,
            tr("启动游戏超时时间（分）"),
            "",
        )
        self.updateGameTimeoutCard = RangeSettingCard1(
            "update_game_timeout",
            [1, 24],
            UiIcon.CLOCK,
            tr("更新游戏超时时间（时）"),
            "",
        )
        # self.importConfigCard = PushSettingCard(
        #     '导入',
        #     FIF.ADD_TO,
        #     '导入配置',
        #     '选择需要导入的 config.yaml 文件（重启后生效）'
        # )
        self.pauseAfterSuccess = SwitchSettingCard1(
            FIF.SYNC,
            tr('成功后暂停程序'),
            tr("如果勾选，除非循环模式，执行成功后暂停程序。"),
            "pause_after_success"
        )
        self.exitAfterFailure = SwitchSettingCard1(
            FIF.SYNC,
            tr('失败后直接退出'),
            tr("如果勾选，那么失败后直接退出，否则失败后暂停程序。"),
            "exit_after_failure"
        )
        self.afterFinishCard = ExpandableComboBoxSettingCard(
            "after_finish",
            FIF.POWER_BUTTON,
            tr('任务完成后'),
            tr('“退出”指退出游戏，不再建议使用循环模式，请改用日志界面的定时运行功能'),
            texts={tr('无'): 'None', tr('退出'): 'Exit', tr('关机'): 'Shutdown', tr('睡眠'): 'Sleep', tr('休眠'): 'Hibernate', tr('重启'): 'Restart', tr('注销'): 'Logoff', tr('关闭显示器'): 'TurnOffDisplay', tr('运行脚本'): 'RunScript', tr('循环'): 'Loop'}
        )
        self.loopModeCard = ComboBoxSettingCard2(
            "loop_mode",
            UiIcon.REPEAT,
            tr('循环模式（请改用日志界面的定时运行功能）'),
            '',
            texts={tr('定时任务'): 'scheduled', tr('根据开拓力'): 'power'}
        )
        self.scheduledCard = TimePickerSettingCard1(
            "scheduled_time",
            FIF.DATE_TIME,
            tr("定时任务时间"),
        )
        self.powerLimitCard = RangeSettingCard1(
            "power_limit",
            [10, 300],
            UiIcon.FLASH,
            tr("循环运行再次启动所需开拓力"),
            tr("游戏刷新后优先级更高"),
        )
        self.refreshHourEnableCard = RangeSettingCard1(
            "refresh_hour",
            [0, 23],
            FIF.DATE_TIME,
            tr("游戏刷新时间"),
            tr("用于循环运行及判断任务状态，默认凌晨四点"),
        )
        self.ScriptPathCard = PushSettingCard(
            tr('修改'),
            FIF.CODE,
            tr("脚本或程序路径(选择运行脚本时生效)"),
            cfg.script_path
        )
        self.playAudioCard = SwitchSettingCard1(
            UiIcon.SPEAKER,
            tr('声音提示'),
            tr('任务完成后列车长唱歌提示帕！'),
            "play_audio"
        )
        self.closeWindowActionCard = ComboBoxSettingCard2(
            "close_window_action",
            FIF.CLOSE,
            tr('关闭窗口时'),
            tr('选择关闭窗口时的默认行为，也可以在关闭时由对话框询问'),
            texts={tr('询问'): 'ask', tr('最小化到托盘'): 'minimize', tr('关闭程序'): 'close'}
        )
        self.windowMemoryCard = ComboBoxSettingCard2(
            "window_memory",
            FIF.LAYOUT,
            tr('窗口记忆'),
            tr('选择启动时恢复的窗口状态'),
            texts={tr('记忆窗口大小'): 'size', tr('记忆窗口位置'): 'position', tr('记忆窗口大小和位置'): 'size_and_position', tr('都不记忆'): 'none'}
        )

        self.NotifyGroup = SettingCardGroup(tr("消息推送"), self.scrollWidget)
        self.notifyMasterEnableCard = ExpandableSwitchSettingCard(
            "notification_enable",
            FIF.RINGER,
            tr("启用消息推送"),
            tr("消息推送总开关")
        )
        self.testNotifyCard = PrimaryPushSettingCard(
            tr("发送消息"),
            FIF.SEND,
            tr("测试消息推送"),
            ""
        )
        self.notifyLevelCard = ComboBoxSettingCard2(
            "notify_level",
            UiIcon.FILTER,
            tr('通知级别'),
            '',
            texts={tr('推送所有通知'): 'all', tr('仅推送错误通知'): 'error'}
        )
        self.notifyMergeCard = SwitchSettingCard1(
            UiIcon.MERGE,
            tr('通知合并'),
            tr('开启后，完整运行结束时将所有通知合并为一条发送'),
            "notify_merge"
        )
        self.notifyImageEnableCard = SwitchSettingCard1(
            FIF.CAMERA,
            tr('推送图片'),
            tr('关闭后推送消息时不再发送截图'),
            "notify_send_images"
        )
        self.notifyTemplateCard = PushSettingCardNotifyTemplate(
            tr('修改'),
            FIF.FONT_SIZE,
            tr("消息推送格式"),
            "notify_template"
        )

        self.notifyEnableGroup = []
        self.notifyProviderMeta = {
            "winotify": {
                "icon": BrandIcon.WINDOWS,
                "display_name": "Windows",
                "description": tr("Windows 原生通知"),
            },
        }

        self.notifyEnableGroup = []
        provider_names = self.__getNotifyProviderNames()
        for notifier_name in provider_names:
            enable_key = f"notify_{notifier_name}_enable"
            provider_meta = self.notifyProviderMeta.get(notifier_name, {})
            display_name = provider_meta.get("display_name", notifier_name.capitalize())
            support_image = tr("（支持图片）") if provider_meta.get("support_image", False) else ""
            provider_description = provider_meta.get("description", "")
            has_params = bool(provider_meta.get("params"))
            has_tutorial = bool(provider_meta.get("tutorial"))
            if support_image:
                provider_description = f"{provider_description} {support_image}".strip()

            if has_params:
                notifyEnableCard = ExpandableSwitchSettingCard(
                    enable_key,
                    provider_meta.get("icon", FIF.MAIL),
                    tr('启用 {name} 通知').format(name=display_name),
                    provider_description
                )
                notifyEnableCard.switchChanged.connect(self.__refreshNotifiers)

                # 添加教程按钮（在开关左边）
                if has_tutorial:
                    tutorialButton = PushButton(tr("教程"), self)
                    tutorialButton.setFixedWidth(60)
                    # 使用 insertWidgetBeforeSwitch 在开关前插入按钮
                    notifyEnableCard.insertWidgetBeforeSwitch(tutorialButton)
                    # 保存教程内容引用
                    tutorial_content = provider_meta.get("tutorial", "")
                    tutorialButton.clicked.connect(
                        lambda checked=False, name=display_name, content=tutorial_content:
                            self.__showNotifyTutorial(name, content)
                    )

                notifyParamCards = self.__createNotifyParamCards(notifier_name)
                if notifyParamCards:
                    notifyEnableCard.addSettingCards(notifyParamCards)
            else:
                notifyEnableCard = SwitchSettingCard1(
                    provider_meta.get("icon", FIF.MAIL),
                    tr('启用 {name} 通知').format(name=display_name),
                    provider_description,
                    enable_key,
                    self
                )
                notifyEnableCard.switchButton.checkedChanged.connect(self.__refreshNotifiers)

                # 添加教程按钮（winotify 除外，放在开关左边）
                if has_tutorial:
                    tutorialButton = PushButton(tr("教程"), self)
                    tutorialButton.setFixedWidth(60)
                    # 在开关按钮之前插入教程按钮
                    insert_index = max(notifyEnableCard.hBoxLayout.count() - 3, 0)
                    notifyEnableCard.hBoxLayout.insertWidget(insert_index, tutorialButton, 0, Qt.AlignmentFlag.AlignRight)
                    notifyEnableCard.hBoxLayout.insertSpacing(insert_index + 1, 10)
                    # 保存教程内容引用
                    tutorial_content = provider_meta.get("tutorial", "")
                    tutorialButton.clicked.connect(
                        lambda checked=False, name=display_name, content=tutorial_content:
                            self.__showNotifyTutorial(name, content)
                    )

            self.notifyEnableGroup.append(notifyEnableCard)

        self.MiscGroup = SettingCardGroup(tr("杂项"), self.scrollWidget)
        self.autoBattleDetectEnableCard = SwitchSettingCard1(
            FIF.ROBOT,
            tr('启用自动战斗和二倍速检测'),
            tr("游戏启动前通过修改注册表或本地存储开启自动战斗和二倍速，并在清体力、货币战争和逐光捡金场景中检测并保持自动战斗状态"),
            "auto_battle_detect_enable"
        )
        self.ocrGpuAccelerationCard = ComboBoxSettingCard2(
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
            }
        )
        self.autoSetResolutionEnableCard = SwitchSettingCard1(
            FIF.FULL_SCREEN,
            tr('启用自动修改分辨率并关闭自动 HDR'),
            tr("通过软件启动游戏会自动修改 1920x1080 分辨率并关闭自动 HDR，不影响手动启动游戏（支持国服和国际服）"),
            "auto_set_resolution_enable"
        )
        self.autoSetGamePathEnableCard = SwitchSettingCard1(
            FIF.GAME,
            tr('启用自动配置游戏路径'),
            tr("通过快捷方式、官方启动器、运行中的游戏进程等方式尝试自动配置游戏路径（支持国服和国际服）"),
            "auto_set_game_path_enable"
        )
        self.useBackgroundScreenshotCard = SwitchSettingCard1(
            FIF.CAMERA,
            tr('优先使用后台截图'),
            tr("默认开启，可以避免悬浮窗等干扰"),
            "use_background_screenshot"
        )
        self.localControlModeCard = ExpandableComboBoxSettingCard(
            'local_control_mode', FIF.GAME, tr('本地操作模式'),
            tr('后台操作遇到鼠标干扰时会等待并重试；滚轮临时切前台，下次启动任务生效。'),
            texts={tr('前台'): 'foreground', tr('后台'): 'background'},
            confirm=self.__confirmLocalControlMode,
        )
        self.backgroundMouseProtectionCard = SwitchSettingCard1(
            FIF.GAME, tr('重试失败时短暂锁定鼠标'),
            tr('仅保护必要的鼠标操作，保留键盘和暂停热键。'),
            'background_mouse_protection',
        )
        self.localControlModeCard.addSettingCard(self.backgroundMouseProtectionCard)
        def refresh_mouse_protection_option(*_args):
            self.backgroundMouseProtectionCard.setEnabled(cfg.get_value('local_control_mode') == 'background')
        self.localControlModeCard.currentIndexChanged.connect(refresh_mouse_protection_option)
        refresh_mouse_protection_option()
        if sys.platform == 'win32':
            self.autostartCard = AutostartSettingCard(
                FIF.GAME,
                tr('在用户登录时启动'),
                tr("登录后自动启动，点击「配置」进行详细设置；无人值守可能需要自行配置 Windows 自动登录")
            )
        if sys.platform == 'win32':
            self.debugModeEnableCard = SwitchSettingCard1(
                FIF.DEVELOPER_TOOLS,
                tr('启用调试模式'),
                tr("开启后会在屏幕上实时绘制检测范围框（透明悬浮窗），用于调试自动化识别效果。仅 Windows 生效。"),
                "debug_mode_enable"
            )
        self.hotkeyCard = SwitchSettingCardHotkey(
            UiIcon.KEYBOARD,
            tr('修改按键'),
            tr("配置秘技、地图、跃迁、停止任务等按键设置")
        )

        self.AboutGroup = SettingCardGroup(tr('关于'), self.scrollWidget)
        self.githubCard = PrimaryPushSettingCard(
            tr('项目主页'),
            FIF.GITHUB,
            tr('项目主页'),
            "https://github.com/moesnow/March7thAssistant"
        )
        self.agentPromptCard = PrimaryPushSettingCard(
            tr('复制提示词'),
            FIF.ROBOT,
            tr('AI 助手'),
            tr('复制一段提示词发给 DeepSeek Harness、Codex、Claude Code 等 AI 助手，让它学会操作三月七小助手')
        )
        self.bilibiliCard = PrimaryPushSettingCard(
            tr('立即前往'),
            BrandIcon.BILIBILI,
            tr('哔哩哔哩'),
            tr('欢迎关注我们的B站账号，获取最新动态和教程')
        )
        self.qqGroupCard = PrimaryPushSettingCard(
            tr('加入群聊'),
            BrandIcon.QQ,
            tr('QQ群'),
            ""
        )
        # self.feedbackCard = PrimaryPushSettingCard(
        #     tr('提供反馈'),
        #     FIF.FEEDBACK,
        #     tr('提供反馈'),
        #     tr('帮助我们改进 March7thAssistant')
        # )
        self.aboutCard = PrimaryPushSettingCard(
            tr('打开发布页'),
            FIF.INFO,
            tr('关于'),
            tr('当前版本：') + " " + cfg.version + " | Python " + sys.version.split()[0] + " | " + platform.system() + " " + platform.machine()
        )
        self.languageCard = ComboBoxSettingCardLanguage(
            "ui_language",
            FIF.LANGUAGE,
            '界面语言 / 界面語言 / 日本語 / 인터페이스 언어 / UI Language',
            '切换后即时生效 / 切換後即時生效 / 切り替え後すぐ適用 / 변경 즉시 적용 / Takes effect immediately',
            texts={'自动': AUTO_LANGUAGE, **available_languages()}
        )
    def __initLayout(self):
        self.settingLabel.move(36, 30)
        # pivot 位于 pivotScrollArea 内；x=40 与标题对齐，y=80 与原位置一致
        # height=54：pivot ~46px + 8px 供 AsNeeded 滚动条偶尔占用，底边 y=134
        # setViewportMargins(0, 140, ...) 保留 6px 间距，不影响内容区域
        self.pivotScrollArea.move(40, 80)
        self.pivotScrollArea.setFixedHeight(46)  # pivot 本身高度，无需为滚动条留空
        # ── 关键修复：构造时必须给 scroll area 设置初始宽度 ──────────────
        # self.width() 在 __init__ 期间为 0（QWidget 尚未布局），
        # 但 self.parent 是已显示的 MainWindow，其宽度有效（≥960）。
        # 若无法取到父宽度则回退到最小窗口宽度 960。
        # resizeEvent 会在窗口缩放时持续更新该值。
        try:
            initial_w = self.parent.width() if self.parent and self.parent.width() > 0 else 960
        except Exception:
            initial_w = 960
        self.pivotScrollArea.setFixedWidth(max(initial_w - 40, 400))
        # self.title_area.move(36, 80)
        # self.vBoxLayout.addWidget(self.pivot, 0, Qt.AlignTop)
        self.vBoxLayout.addWidget(self.stackedWidget, 0, Qt.AlignmentFlag.AlignTop)
        self.vBoxLayout.setContentsMargins(36, 0, 36, 0)

        self.PowerGroup.addSettingCard(self.powerEnableCard)
        self.PowerGroup.addSettingCard(self.powerPlanCard)
        self.PowerGroup.addSettingCard(self.instanceTypeCard)
        # self.PowerGroup.addSettingCard(self.calyxGoldenPreferenceCard)
        self.instanceTypeCard.addSettingCards([
            self.instanceTeamEnableCard,
            self.tpBeforeInstanceEnableCard,
            self.useReservedTrailblazePowerEnableCard,
            self.useFuelEnableCard,
            self.weeklyRelicCleanupEnableCard,
            self.mergeImmersifierEnableCard,
            self.instanceNameChallengeCountCard
        ])
        self.weeklyRelicCleanupEnableCard.addSettingCard(self.smartRelicDiscardEnableCard)
        self.weeklyRelicCleanupEnableCard.expandAni.valueChanged.connect(self.instanceTypeCard._adjustViewSize)
        self.PowerGroup.addSettingCard(self.instanceNameCard)
        self.PowerGroup.addSettingCard(self.borrowEnableCard)
        # 将子卡片添加到 borrowEnableCard 的可展开区域
        self.borrowEnableCard.addSettingCards([
            self.borrowCharacterEnableCard,
            self.borrowFriendsCard,
            self.borrowScrollTimesCard
        ])
        # self.PowerGroup.addSettingCard(self.maxCalyxPerRoundNumOfAttempts)
        self.PowerGroup.addSettingCard(self.buildTargetEnableCard)
        self.buildTargetEnableCard.addSettingCards([
            self.buildTargetSchemeCard,
            self.buildTargetPlanarOrnamentWeeklyCountCard,
            self.buildTargetUseUserInstanceWhenOnlyErosionAndOrnamentCard
        ])
        self.PowerGroup.addSettingCard(self.echoofwarEnableCard)
        self.echoofwarEnableCard.addSettingCards([
            self.echoofwarRunTimeCard
        ])
        # self.PowerGroup.addSettingCard(self.echoofwarStartDayOfWeekCard)
        # self.BorrowGroup.addSettingCard(self.borrowCharacterFromCard)
        # self.BorrowGroup.addSettingCard(self.borrowCharacterInfoCard)
        # self.BorrowGroup.addSettingCard(self.borrowCharacterCard)

        self.DailyGroup.addSettingCard(self.dailyEnableCard)
        self.dailyEnableCard.addSettingCards([
            self.dailyMaterialEnableCard,
            # self.dailyHimekoTryEnableCard,
            self.dailyMemoryOneEnableCard,
            self.dailyMemoryOneTeamCard
        ])
        self.DailyGroup.addSettingCard(self.activityEnableCard)
        self.activityEnableCard.addSettingCards([
            self.activityDailyCheckInEnableCard,
            self.activityGardenOfPlentyEnableCard,
            self.activityRealmOfTheStrangeEnableCard,
            self.activityPlanarFissureEnableCard,
            self.activityJourneyHighlightsNotificationEnableCard
        ])
        self.DailyGroup.addSettingCard(self.rewardEnableCard)
        self.rewardEnableCard.addSettingCards([
            self.dispatchEnableCard,
            self.mailEnableCard,
            self.assistEnableCard,
            self.questEnableCard,
            self.srpassEnableCard,
            self.redemptionEnableCard,
            self.achievementEnableCard,
            self.messageEnableCard
        ])
        self.DailyGroup.addSettingCard(self.assetEnableCard)
        self.assetEnableCard.addSettingCards(
            [
                self.selfMoldingResinEnableCard,
                self.emberSpecialPassEnableCard,
                self.emberRegularPassEnableCard,
                self.emberTracksOfDestinyEnableCard,
                self.lc3StarSuperimposeEnableCard,
            ]
        )

        self.CurrencywarsGroup.addSettingCard(self.currencywarsEnableCard)
        self.CurrencywarsGroup.addSettingCard(self.currencywarsPresetCard)
        self.CurrencywarsGroup.addSettingCard(self.currencywarsTypeCard)
        self.CurrencywarsGroup.addSettingCard(self.currencywarsBonusEnableCard)
        self.CurrencywarsGroup.addSettingCard(self.currencywarsRankDifficultyCard)
        self.CurrencywarsGroup.addSettingCard(self.currencywarsStrategyCard)
        self.currencywarsStrategyCard.addSettingCards([
            self.currencywarsRemembranceTrailblazerNameCard,
            self.currencywarsStrategyRestartOnSpecialTagsCard,
            self.currencywarsFastModeCard
        ])

        self.UniverseGroup.addSettingCard(self.weeklyDivergentEnableCard)
        self.UniverseGroup.addSettingCard(self.weeklyDivergentTypeCard)
        self.UniverseGroup.addSettingCard(self.weeklyDivergentBonusEnableCard)
        self.UniverseGroup.addSettingCard(self.weeklyDivergentLevelCard)
        self.UniverseGroup.addSettingCard(self.stationPriorityCard)
        self.UniverseGroup.addSettingCard(self.weeklyDivergentStableModeCard)
        self.UniverseGroup.addSettingCard(self.divergentAutoSaveCard)

        self.ImmortalGameGroup.addSettingCard(self.forgottenhallEnableCard)
        self.forgottenhallEnableCard.addSettingCards([
            self.forgottenhallLevelCard,
            self.forgottenhallTeamsCard
        ])

        self.ImmortalGameGroup.addSettingCard(self.purefictionEnableCard)
        self.purefictionEnableCard.addSettingCards([
            self.purefictionConfigCard
        ])

        self.ImmortalGameGroup.addSettingCard(self.ApocalypticEnableCard)
        self.ApocalypticEnableCard.addSettingCards([
            self.ApocalypticLevelCard,
            self.ApocalypticTeamsCard
        ])

        self.ProgramGroup.addSettingCard(self.logLevelCard)
        self.ProgramGroup.addSettingCard(self.gamePathCard)
        self.ProgramGroup.addSettingCard(self.updateViaLauncherEnableCard)
        self.updateViaLauncherEnableCard.addSettingCards([
            self.launcherPathCard,
            self.launcherType,
            self.updateGameTimeoutCard
        ])
        self.ProgramGroup.addSettingCard(self.startGameTimeoutCard)
        # self.ProgramGroup.addSettingCard(self.importConfigCard)
        self.ProgramGroup.addSettingCard(self.pauseAfterSuccess)
        self.ProgramGroup.addSettingCard(self.exitAfterFailure)
        self.ProgramGroup.addSettingCard(self.afterFinishCard)
        self.afterFinishCard.addSettingCards([
            self.loopModeCard,
            self.scheduledCard,
            self.powerLimitCard,
            self.refreshHourEnableCard,
            self.ScriptPathCard
        ])
        self.ProgramGroup.addSettingCard(self.playAudioCard)
        self.ProgramGroup.addSettingCard(self.closeWindowActionCard)
        self.ProgramGroup.addSettingCard(self.windowMemoryCard)

        self.NotifyGroup.addSettingCard(self.notifyMasterEnableCard)
        self.notifyMasterEnableCard.addSettingCards([
            self.testNotifyCard,
            self.notifyLevelCard,
            self.notifyMergeCard,
            self.notifyImageEnableCard,
            self.notifyTemplateCard
        ])
        for value in self.notifyEnableGroup:
            self.NotifyGroup.addSettingCard(value)

        self.MiscGroup.addSettingCard(self.autoBattleDetectEnableCard)
        self.MiscGroup.addSettingCard(self.ocrGpuAccelerationCard)
        self.MiscGroup.addSettingCard(self.autoSetResolutionEnableCard)
        self.MiscGroup.addSettingCard(self.autoSetGamePathEnableCard)
        self.MiscGroup.addSettingCard(self.useBackgroundScreenshotCard)
        self.MiscGroup.addSettingCard(self.localControlModeCard)
        if sys.platform == 'win32':
            self.MiscGroup.addSettingCard(self.autostartCard)
            self.MiscGroup.addSettingCard(self.debugModeEnableCard)
        self.MiscGroup.addSettingCard(self.hotkeyCard)

        self.AboutGroup.addSettingCard(self.githubCard)
        self.AboutGroup.addSettingCard(self.agentPromptCard)
        self.AboutGroup.addSettingCard(self.bilibiliCard)
        self.AboutGroup.addSettingCard(self.qqGroupCard)
        # self.AboutGroup.addSettingCard(self.feedbackCard)
        self.AboutGroup.addSettingCard(self.aboutCard)
        self.AboutGroup.addSettingCard(self.languageCard)

        if sys.platform != 'win32':
            self.gamePathCard.setHidden(True)
            self.updateViaLauncherEnableCard.setHidden(True)
            self.autoSetResolutionEnableCard.setHidden(True)
            self.autoSetGamePathEnableCard.setHidden(True)
            self.useBackgroundScreenshotCard.setHidden(True)
            self.localControlModeCard.setHidden(True)

        self.addSubInterface(self.PowerGroup, 'PowerInterface', tr('体力'))
        # self.addSubInterface(self.BorrowGroup, 'BorrowInterface', '支援')
        self.addSubInterface(self.DailyGroup, 'DailyInterface', tr('日常'))
        self.addSubInterface(self.CurrencywarsGroup, 'CurrencywarsInterface', tr('货币战争'))
        self.addSubInterface(self.UniverseGroup, 'UniverseInterface', tr('差分宇宙'))
        self.addSubInterface(self.ImmortalGameGroup, 'ImmortalGameInterface', tr('逐光捡金'))

        self.pivot.addItem(
            routeKey='verticalBar',
            text="|",
            onClick=lambda: self.pivot.setCurrentItem(self.stackedWidget.currentWidget().objectName()),
        )

        self.addSubInterface(self.ProgramGroup, 'programInterface', tr('程序'))
        self.addSubInterface(self.NotifyGroup, 'NotifyInterface', tr('推送'))
        self.addSubInterface(self.MiscGroup, 'KeybindingInterface', tr('杂项'))
        if sys.platform == 'win32':
            self.addSubInterface(
                accounts_interface(self.tr, self.scrollWidget),
                'AccountsInterface',
                tr('账号')
            )
        self.addSubInterface(self.AboutGroup, 'AboutInterface', tr('关于'))

        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.pivot.setCurrentItem(self.stackedWidget.currentWidget().objectName())
        self.stackedWidget.setFixedHeight(self.stackedWidget.currentWidget().sizeHint().height())

        # ── pivot 尺寸与滚动过滤器 ────────────────────────────────────
        # 所有 addItem 调用完成后 pivot 才能计算正确宽度
        self.pivot.adjustSize()
        # 将滚动/拖拽过滤器安装到 pivot 本身及其所有子控件（tab 按钮）
        # 只在 viewport 上安装不够：tab 子控件直接收到鼠标事件，不经过 viewport
        self._pivot_scroll_filter = _PivotScrollFilter(self.pivotScrollArea, self.pivot)
        self.pivot.installEventFilter(self._pivot_scroll_filter)
        for child in self.pivot.findChildren(QWidget):
            child.installEventFilter(self._pivot_scroll_filter)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 随窗口宽度同步 pivot 滚动容器宽度（right margin = 40px 与布局对齐）
        if self.width() > 0:
            self.pivotScrollArea.setFixedWidth(max(self.width() - 40, 400))

    def __connectSignalToSlot(self):
        def connect_expand_state(card):
            if hasattr(card, "expandStateChanged"):
                card.expandStateChanged.connect(self.__onExpandableCardStateChanged)

        # self.importConfigCard.clicked.connect(self.__onImportConfigCardClicked)
        self.gamePathCard.clicked.connect(self.__onGamePathCardClicked)
        self.launcherPathCard.clicked.connect(self.__onLauncherPathCardClicked)
        self.ScriptPathCard.clicked.connect(self.__onScriptPathCardClicked)
        self.currencywarsPresetCard.leftClicked.connect(self.__applyCurrencywarsPromotionPreset)
        self.currencywarsPresetCard.rightClicked.connect(self.__applyCurrencywarsRankPreset)
        # self.borrowCharacterInfoCard.clicked.connect(self.__openCharacterFolder())

        self.testNotifyCard.clicked.connect(self.__sendTestNotification)
        self.notifyMasterEnableCard.switchChanged.connect(self.__refreshNotifiers)

        connect_expand_state(self.afterFinishCard)
        connect_expand_state(self.localControlModeCard)

        self.githubCard.clicked.connect(self.__openUrl("https://github.com/moesnow/March7thAssistant"))
        self.agentPromptCard.clicked.connect(self.__copyAgentPrompt)
        self.qqGroupCard.clicked.connect(self.__openUrl("https://qm.qq.com/q/C3IryUWCQw"))
        # self.feedbackCard.clicked.connect(self.__openUrl("https://github.com/moesnow/March7thAssistant/issues"))
        self.bilibiliCard.clicked.connect(self.__openUrl("https://space.bilibili.com/3706960664857075"))

        self.aboutCard.clicked.connect(self.__openUrl("https://github.com/moesnow/March7thAssistant/releases"))

        # 连接可展开卡片的展开状态改变信号，在动画前调整 stackedWidget 高度
        connect_expand_state(self.borrowEnableCard)
        connect_expand_state(self.buildTargetEnableCard)
        connect_expand_state(self.dailyEnableCard)
        connect_expand_state(self.activityEnableCard)
        connect_expand_state(self.rewardEnableCard)
        connect_expand_state(self.assetEnableCard)
        connect_expand_state(self.currencywarsEnableCard)
        connect_expand_state(self.currencywarsStrategyCard)
        connect_expand_state(self.weeklyDivergentEnableCard)
        connect_expand_state(self.forgottenhallEnableCard)
        connect_expand_state(self.purefictionEnableCard)
        connect_expand_state(self.ApocalypticEnableCard)
        connect_expand_state(self.gamePathCard)
        connect_expand_state(self.updateViaLauncherEnableCard)
        connect_expand_state(self.notifyMasterEnableCard)
        for notify_card in self.notifyEnableGroup:
            connect_expand_state(notify_card)
        connect_expand_state(self.instanceTypeCard)
        connect_expand_state(self.weeklyRelicCleanupEnableCard)
        connect_expand_state(self.echoofwarEnableCard)

    def __confirmLocalControlMode(self, value):
        """切换到后台模式前说明限制；确认后才写入配置，取消则保留原模式。"""
        if value != 'background':
            return True
        confirm = MessageBox(
            tr("启用后台模式前请确认"),
            tr("后台模式下，任务运行时你可以继续使用电脑，但仍有以下限制：\n\n"
               "• 点击和拖动会短暂借用鼠标，完成后归还；你正在移动鼠标时，任务会等鼠标停下再操作。\n"
               "• 在大世界中按键时，光标会被短暂锁定在游戏窗口中央。\n"
               "• 需要滚轮时会临时把游戏切到前台，完成后恢复原来的窗口。\n"
               "• 游戏窗口可以放在其他窗口后面，但不能最小化；运行期间请保持系统解锁。\n\n"
               "设置在下次启动任务时生效，自动对话需重新开启。完整说明见使用文档“后台运行”。"),
            self.window()
        )
        confirm.yesButton.setText(tr("我已了解，启用后台模式"))
        confirm.cancelButton.setText(tr("取消"))
        return bool(confirm.exec())

    def __getNotifyProviderNames(self):
        provider_names = []
        for key in cfg.config.keys():
            if key.startswith("notify_") and key.endswith("_enable"):
                notifier_name = key[len("notify_"):-len("_enable")]
                if sys.platform != 'win32' and notifier_name == 'winotify':
                    continue
                provider_names.append(notifier_name)

        # 自定义排序顺序
        custom_order = [
            "winotify",        # Windows 原生通知
            "wechatworkbot",   # 企业微信机器人
            "qqbot",           # QQ 官方机器人
            "smtp",            # SMTP
            "lark",            # 飞书
            "telegram",        # Telegram
            "dingtalk",        # 钉钉
            "serverchan3",     # Server酱³
            "onebot",          # OneBot
            "serverchanturbo", # Server酱 Turbo
            "bark",            # Bark
            "wechatworkapp",   # 企业微信应用
            "pushplus",        # Pushplus
            "discord",         # Discord
            "meow",            # MeoW
            "gotify",          # Gotify
            "kook",            # KOOK
            "qmsg",            # Qmsg
            "matrix",          # Matrix
            "pushdeer",        # Pushdeer
            "gocqhttp",        # Go-cqhttp
        ]

        # 先按自定义顺序排列指定的 provider，其余保持原有顺序，webhook/自定义通知置底
        custom_set = set(custom_order) | {"webhook", "custom"}
        ordered = [name for name in custom_order if name in provider_names]
        remaining = [name for name in provider_names if name not in custom_set]
        tail = [name for name in ("webhook", "custom") if name in provider_names]
        return ordered + remaining + tail

    def __createNotifyParamCards(self, notifier_name):
        param_cards = []
        prefix = f"notify_{notifier_name}_"
        enable_key = f"notify_{notifier_name}_enable"

        for key in cfg.config.keys():
            if not key.startswith(prefix) or key == enable_key:
                continue

            param_name = key[len(prefix):]
            param_meta = self.notifyProviderMeta.get(notifier_name, {}).get("params", {}).get(param_name, {})
            if "description" in param_meta:
                param_description = param_meta.get("description", "")
            elif param_meta:
                param_description = ""
            else:
                param_description = tr("该参数用于配置该通知方式的请求字段")
            param_title = param_meta.get("title", param_name)
            param_type = param_meta.get("type", "text")

            if param_type == "bool":
                # self.__normalizeNotifyBoolConfigValue(key)
                notify_param_card = SwitchSettingCard1(
                    FIF.CHECKBOX,
                    param_title,
                    param_description,
                    key,
                    self
                )
                notify_param_card.switchButton.checkedChanged.connect(self.__refreshNotifiers)
            else:
                notify_param_card = CustomPushSettingCard(
                    tr('修改'),
                    FIF.EDIT,
                    param_title,
                    key,
                    param_description,
                    self
                )
                notify_param_card.button.clicked.connect(
                    lambda _, card=notify_param_card: self.__onNotifyParamCardClicked(card)
                )
            param_cards.append(notify_param_card)

        return param_cards

    def __createQqBotBindCard(self):
        """QQ 官方机器人：自动绑定 openid / group_openid 的卡片。"""
        self._qqbotBindThread = None
        self.qqbotStateTooltip = None
        bind_card = DualPushSettingCard(
            tr("绑定单聊"), tr("绑定群聊"),
            FIF.LINK,
            tr("自动绑定收件标识"),
        )
        bind_card.leftClicked.connect(lambda: self.__onQqBotBindClicked("user"))
        bind_card.rightClicked.connect(lambda: self.__onQqBotBindClicked("group"))
        return bind_card

    def __onQqBotBindClicked(self, mode: str):
        if self._qqbotBindThread is not None and self._qqbotBindThread.isRunning():
            InfoBar.warning(
                title=tr("正在绑定中"),
                content=tr("请等待当前绑定完成后再试"),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.window()
            )
            return

        appid = cfg.get_value("notify_qqbot_appid") or ""
        client_secret = cfg.get_value("notify_qqbot_client_secret") or ""
        if not appid or not client_secret:
            InfoBar.warning(
                title=tr("无法绑定"),
                content=tr("请先填写机器人 AppID 与 AppSecret"),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.window()
            )
            return

        from module.notification.qqbot import QqBotOpenIdBinder
        verify_code = f"{random.randint(0, 9999):04d}"
        seconds = QqBotOpenIdBinder.BIND_TIMEOUT
        if mode == "user":
            tip = tr("点击「开始监听」后，请在 {seconds} 秒内用 QQ 私聊机器人并发送验证码 {code}")
        else:
            tip = tr("点击「开始监听」后，请在 {seconds} 秒内在群聊中 @ 机器人并发送验证码 {code}，或将机器人拉进目标群")
        tip = tip.format(seconds=seconds, code=verify_code)

        confirm = MessageBox(tr("自动绑定收件标识"), tip, self.window())
        confirm.yesButton.setText(tr("开始监听"))
        confirm.cancelButton.setText(tr("取消"))
        if not confirm.exec():
            return

        thread = QqBotBindThread(appid, client_secret, mode, verify_code, self)
        thread.resultSignal.connect(self.__onQqBotBindFinished)
        self._qqbotBindThread = thread
        thread.start()

        # 监听期间常驻显示（同「抽卡记录-更新数据」的 StateToolTip），避免用户忘记验证码
        if mode == "user":
            listen_tip = tr("监听中，请私聊机器人发送验证码 {code}（{seconds} 秒内）")
        else:
            listen_tip = tr("监听中，请在群聊中 @ 机器人发送验证码 {code}（{seconds} 秒内）")
        listen_tip = listen_tip.format(code=verify_code, seconds=seconds)
        try:
            self.qqbotStateTooltip = StateToolTip(tr("自动绑定收件标识"), listen_tip, self.window())
            self.qqbotStateTooltip.closeButton.setVisible(False)
            self.qqbotStateTooltip.move(self.qqbotStateTooltip.getSuitablePos())
            self.qqbotStateTooltip.show()
        except Exception:
            self.qqbotStateTooltip = None

    def __onQqBotBindFinished(self, success: bool, mode: str, value: str):
        # 收起常驻提示（setState(True) 后自动淡出）
        tooltip = getattr(self, "qqbotStateTooltip", None)
        self.qqbotStateTooltip = None
        if tooltip is not None:
            try:
                tooltip.setContent(tr("绑定成功") if success else tr("绑定失败"))
                tooltip.setState(True)
            except Exception:
                pass

        if success:
            configname = "notify_qqbot_openid" if mode == "user" else "notify_qqbot_group_openid"
            cfg.set_value(configname, value)
            self.__refreshNotifiers()
            InfoBar.success(
                title=tr("绑定成功"),
                content=value,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self.window()
            )
        else:
            InfoBar.error(
                title=tr("绑定失败"),
                content=value,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=8000,
                parent=self.window()
            )

    def __onNotifyParamCardClicked(self, card):
        current_value = cfg.get_value(card.configname)
        message_box = MessageBoxEdit(card.title, str(current_value), self.window())
        if message_box.exec():
            cfg.set_value(card.configname, self.__parseNotifyValue(message_box.getText()))
            self.__refreshNotifiers()

    def __parseNotifyValue(self, input_text):
        try:
            return eval(input_text)
        except (SyntaxError, NameError, ValueError):
            return input_text

    def __normalizeNotifyBoolConfigValue(self, configname):
        value = cfg.get_value(configname)
        if isinstance(value, bool):
            return

        normalized = False
        if isinstance(value, str):
            text = value.strip().lower()
            if text in {"1", "true", "yes", "on"}:
                normalized = True
            elif text in {"0", "false", "no", "off", "", "none", "null"}:
                normalized = False
            else:
                normalized = bool(text)
        else:
            normalized = bool(value)

        cfg.set_value(configname, normalized)

    def __refreshNotifiers(self, *_):
        try:
            init_notifiers()
        except Exception:
            pass

    def __showNotifyTutorial(self, provider_name: str, tutorial_html: str):
        """显示通知方式配置教程对话框"""
        from .card.messagebox_custom import MessageBoxTutorial
        dialog = MessageBoxTutorial(
            tr("{name} 配置教程").format(name=provider_name),
            tutorial_html,
            self.window()
        )
        dialog.exec()

    def __sendTestNotification(self):
        from module.notification import notif
        from module.notification.notification import NotificationLevel
        notif.notify(
            content=cfg.notify_template['TestMessage'],
            image="./assets/app/images/March7th.jpg",
            level=NotificationLevel.ALL,
        )

    def addSubInterface(self, widget: QLabel, objectName, text):
        def remove_spacing(layout):
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if isinstance(item, QSpacerItem):
                    layout.removeItem(item)
                    break

        remove_spacing(widget.vBoxLayout)
        widget.titleLabel.setHidden(True)

        widget.setObjectName(objectName)
        self.stackedWidget.addWidget(widget)
        self.pivot.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget)
        )

    def onCurrentIndexChanged(self, index):
        widget = self.stackedWidget.widget(index)
        self.pivot.setCurrentItem(widget.objectName())

        self.verticalScrollBar().setValue(0)
        self.stackedWidget.setFixedHeight(self.stackedWidget.currentWidget().sizeHint().height())

    # def __onImportConfigCardClicked(self):
    #     configdir, _ = QFileDialog.getOpenFileName(self, "选取配置文件", "./", "Config Files (*.yaml)")
    #     if (configdir != ""):
    #         cfg._load_config(configdir)
    #         cfg.save_config()
    #         self.__showRestartTooltip()

    def __onGamePathCardClicked(self):
        game_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("选择游戏路径"),
            "",
            tr("脚本或可执行文件 (*.exe *.bat *.cmd *.ps1)")
        )
        if not game_path or cfg.game_path == game_path:
            return
        cfg.set_value("game_path", game_path)
        self.gamePathCard.setContent(game_path)

    def __onLauncherPathCardClicked(self):
        launcher_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("选择启动器路径"),
            "",
            tr("脚本或可执行文件 (*.exe *.bat *.cmd *.ps1)")
        )
        if not launcher_path or cfg.launcher_path == launcher_path:
            return
        cfg.set_value("launcher_path", launcher_path)
        self.launcherPathCard.setContent(launcher_path)

    # def __openCharacterFolder(self):
    #     return lambda: os.startfile(os.path.abspath("./assets/images/share/character"))

    def __openUrl(self, url):
        return lambda: QDesktopServices.openUrl(QUrl(url))

    def __copyAgentPrompt(self):
        try:
            clipboard.copy(build_agent_prompt())
            InfoBar.success(
                title=tr('复制成功(＾∀＾●)'),
                content=tr("粘贴给你的 AI 助手即可"),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
        except Exception:
            InfoBar.warning(
                title=tr('复制失败(╥╯﹏╰╥)'),
                content="",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    # def __showRestartTooltip(self):
    #     InfoBar.success(
    #         '更新成功',
    #         '配置在重启软件后生效',
    #         duration=1500,
    #         parent=self
    #     )
    def __onScriptPathCardClicked(self):
        script_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("脚本或程序路径"),
            "",
            tr("脚本或可执行文件 (*.exe *.bat *.cmd *.ps1)")
        )
        if not script_path or cfg.script_path == script_path:
            return
        cfg.set_value("script_path", script_path)
        self.ScriptPathCard.setContent(script_path)

    def __setComboBoxCardValue(self, card, value):
        for index in range(card.comboBox.count()):
            if card.comboBox.itemData(index) != value:
                continue

            if card.comboBox.currentIndex() != index:
                card.comboBox.setCurrentIndex(index)
            else:
                cfg.set_value(card.configname, value)
            return

        cfg.set_value(card.configname, value)

    def __setSwitchCardValue(self, card, value):
        if card.switchButton.isChecked() != value:
            card.switchButton.setChecked(value)
            return

        card.setValue(value)
        cfg.set_value(card.configname, value)

    def __applyFightPreset(self, map_version, label):
        """三个快捷配置共用：切地图版本，并打开「特殊物品领取」总开关与三项购买"""
        self.__setComboBoxCardValue(self.fightMapVersionCard, map_version)
        self.__setSwitchCardValue(self.fightRewardEnableCard, True)
        for card in (self.fightAllowSnackBuyCard, self.fightAllowMapBuyCard, self.fightAllowMemoryTokenCard):
            self.__setComboBoxCardValue(card, True)
        InfoBar.success(
            title=tr('已应用快捷配置'),
            content=tr('当前为“{name}”模式').format(name=label),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def __applyFightRangedPreset(self):
        self.__applyFightPreset('default', tr('远程一号位锄地'))

    def __applyFightAcheronPreset(self):
        self.__applyFightPreset('HuangQuan', tr('黄泉一号位锄地'))

    def __applyFightRewardOnlyPreset(self):
        self.__applyFightPreset('reward', tr('仅获取特殊物品'))

    def __applyCurrencywarsPromotionPreset(self):
        self.__setComboBoxCardValue(self.currencywarsTypeCard, 'overclock')
        self.__setComboBoxCardValue(self.currencywarsRankDifficultyCard, 'lowest')
        self.__setComboBoxCardValue(self.currencywarsStrategyCard, 'default')
        self.__setSwitchCardValue(self.currencywarsFastModeCard, True)
        InfoBar.success(
            title=tr('已应用快捷配置'),
            content=tr('当前为“提升晋升等级”模式'),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def __applyCurrencywarsRankPreset(self):
        self.__setComboBoxCardValue(self.currencywarsTypeCard, 'normal')
        self.__setComboBoxCardValue(self.currencywarsRankDifficultyCard, 'highest')
        self.__setComboBoxCardValue(self.currencywarsStrategyCard, 'aglaea')
        self.__setSwitchCardValue(self.currencywarsFastModeCard, False)
        InfoBar.success(
            title=tr('已应用快捷配置'),
            content=tr('当前为“提升职级等级”模式'),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def __onExpandableCardStateChanged(self, is_expanding: bool):
        """可展开卡片状态改变时，调整 stackedWidget 高度以包含子卡片"""
        # 获取发送信号的卡片对象
        sender_card = self.sender()

        # 根据展开的卡片获取其 viewLayout 的高度
        if sender_card:
            card_weight = sender_card.viewLayout.sizeHint().height()
        else:
            # 如果无法获取发送者，使用默认高度（向后兼容）
            card_weight = 0

        # 在动画执行前调整 stackedWidget 高度
        if is_expanding:
            self.stackedWidget.setFixedHeight(self.stackedWidget.currentWidget().sizeHint().height() + card_weight)
        else:
            self.stackedWidget.setFixedHeight(self.stackedWidget.currentWidget().sizeHint().height())
