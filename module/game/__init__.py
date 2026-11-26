import sys

from module.config import cfg
from module.config.platform import ControlBackend, get_control_backend
from module.logger import log
from module.game.adb import AdbGameController
from module.game.adb_transport import AdbError
from module.game.base import GameControllerBase
from module.localization import tr

if sys.platform != "android":
    from module.game.local import LocalGameController

    local_game = LocalGameController(cfg=cfg, logger=log)

adb_game = AdbGameController(cfg=cfg, logger=log)


def require_desktop_task(config, task: str) -> None:
    if get_control_backend(config) == "adb":
        raise AdbError("desktop_task_unsupported", tr(
            "ADB 模式不支持「{task}」，请使用本地或云游戏后端"
        ).format(task=task))


def _get_local_controller() -> GameControllerBase:
    local_game.reload_config(cfg)
    return local_game


class _CloudRemoved:
    def __getattr__(self, name):
        raise ValueError(tr("精简版不包含云·星穹铁道，请改用本地客户端或安卓设备"))


cloud_game = _CloudRemoved()


def _cloud_removed() -> GameControllerBase:
    raise ValueError(tr("精简版不包含云·星穹铁道，请改用本地客户端或安卓设备"))


_CONTROLLER_FACTORIES = {
    "local": _get_local_controller,
    "cloud": _cloud_removed,
    "adb": lambda: adb_game,
}


def get_game_controller(backend: ControlBackend | None = None) -> GameControllerBase:
    if backend is None:
        backend = get_control_backend(cfg)
    if sys.platform == "android" and backend != "adb":
        raise ValueError(backend)
    return _CONTROLLER_FACTORIES[backend]()
