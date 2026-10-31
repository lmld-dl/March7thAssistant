from module.config import cfg
from module.logger import log
from module.game.base import GameControllerBase
from module.game.local import LocalGameController

local_game: LocalGameController = LocalGameController(cfg=cfg, logger=log)


def get_game_controller() -> GameControllerBase:
    local_game.reload_config(cfg)
    return local_game
