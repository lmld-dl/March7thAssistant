import sys
from module.config import cfg
from module.logger import log
from module.notification.notification import Notification, NotificationLevel

if sys.platform == 'win32':
    from module.notification.winotify import WinotifyNotifier


class NotifierFactory:
    notifier_classes = {}
    if sys.platform == 'win32':
        notifier_classes["winotify"] = WinotifyNotifier

    @staticmethod
    def create_notifier(notifier_name, params, logger):
        """
        根据提供的notifier_name，从映射字典中找到对应的类并实例化。
        精简客户端只保留 Windows 原生通知（winotify）。
        """
        notifier_class = NotifierFactory.notifier_classes.get(notifier_name)
        if notifier_class is None:
            logger.warning(f"精简客户端不支持的通知方式: {notifier_name}，已跳过")
            return None
        return notifier_class(params, logger)


notif = Notification(cfg.notify_template['Title'], log)


def init_notifiers():
    """按当前配置重建通知器。精简客户端只注册 winotify。"""
    try:
        notif.notifiers.clear()
    except Exception:
        pass

    if not cfg.get_value('notification_enable', True):
        return

    try:
        notify_level = cfg.get_value('notify_level', NotificationLevel.ALL)
        notif.set_level_filter(notify_level)
    except Exception:
        pass

    try:
        notify_send_images = cfg.get_value('notify_send_images', True)
        notif.set_image_enable(notify_send_images)
    except Exception:
        pass

    if sys.platform != 'win32':
        return

    if not cfg.get_value('notify_winotify_enable', True):
        return

    try:
        notifier = NotifierFactory.create_notifier('winotify', {}, log)
    except Exception as e:
        log.error(f"winotify 通知初始化失败: {e}")
        return
    if notifier is not None:
        notif.set_notifier('winotify', notifier)


init_notifiers()
