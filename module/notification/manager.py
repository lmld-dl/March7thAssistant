import sys
from module.config import cfg
from module.logger import log
from module.notification.notification import Notification, NotificationLevel
if sys.platform == 'win32':
    from module.notification.winotify import WinotifyNotifier


class _UnconfiguredChannel:
    """Keep an enabled but invalid legacy channel visible in actual delivery results."""
    supports_image = False

    def send(self, title, content):
        raise ValueError("invalid notification configuration")


class NotifierFactory:
    # 精简客户端只保留 Windows 本地 Toast。旧配置里的其他渠道会被跳过，不导致启动失败。
    notifier_classes = {}
    if sys.platform == 'win32':
        notifier_classes["winotify"] = WinotifyNotifier

    @staticmethod
    def create_notifier(notifier_name, params, logger):
        """
        根据提供的notifier_name，从映射字典中找到对应的类并实例化。
        未内置支持的通知方式返回None，并记录警告。
        """
        notifier_class = NotifierFactory.notifier_classes.get(notifier_name)
        if notifier_class is None:
            logger.warning(f"暂不支持的通知方式: {notifier_name}，已跳过")
            return None
        return notifier_class(params, logger)


notif = Notification(cfg.notify_template['Title'], log)


def init_notifiers():
    """(Re)initialize notifiers from current configuration.

    This updates the existing global `notif` instance in-place: clears previous notifiers,
    sets the level filter, and (re)creates notifier instances based on `cfg`.
    """
    # 清理已有的notifiers
    channels = {}

    # 检查消息推送总开关
    if not cfg.get_value('notification_enable', True):
        notif.notifiers = {}
        return

    # 设置通知级别过滤器
    try:
        notify_level = cfg.get_value('notify_level', NotificationLevel.ALL)
        notif.set_level_filter(notify_level)
    except Exception:
        pass

    # 设置是否发送图片
    try:
        notify_send_images = cfg.get_value('notify_send_images', True)
        notif.set_image_enable(notify_send_images)
    except Exception:
        pass

    # 创建并注册Notifier实例
    try:
        for key, value in cfg.config.items():
            if key.startswith("notify_") and key.endswith("_enable") and value:
                notifier_name = key[len("notify_"):-len("_enable")]
                params = {param_key[len("notify_" + notifier_name + "_"):]: param_value
                          for param_key, param_value in cfg.config.items()
                          if param_key.startswith(f"notify_{notifier_name}_") and param_key != f"notify_{notifier_name}_enable" and param_value != ""}
                if sys.platform != 'win32' and notifier_name == 'winotify':
                    continue  # 跳过 Windows 专用的通知器
                try:
                    notifier = NotifierFactory.create_notifier(notifier_name, params, log)
                except Exception as e:
                    channels[notifier_name] = _UnconfiguredChannel()
                    log.error(f"{notifier_name} 通知初始化失败: {type(e).__name__}")
                    continue
                if notifier is not None:
                    channels[notifier_name] = notifier
    except Exception as exc:
        log.warning(f"刷新通知渠道失败：{type(exc).__name__}")
        return
    notif.notifiers = channels


# 首次初始化
init_notifiers()
