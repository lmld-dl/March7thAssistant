# coding:utf-8
"""workflow 执行前置的游戏窗口校验测试。

覆盖语义：游戏未启动或切换失败时报错并终止，与流程编排启动行为一致。
"""
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_game_module():
    try:
        import tasks.game as game
        return game
    except Exception as e:  # 任务模块依赖较重，环境不可用时跳过
        pytest.skip(f"tasks.game 依赖不可用: {e}")


class _LogStub:
    def __init__(self):
        self.errors = []

    def error(self, message, *args, **kwargs):
        self.errors.append(message)

    def hr(self, *args, **kwargs):
        pass

    def info(self, message, *args, **kwargs):
        pass


def _prepare(monkeypatch, running, switch_ok):
    game = _load_game_module()
    calls = []
    controller = SimpleNamespace(
        is_game_running=lambda: calls.append('is_game_running') or running,
        switch_to_game=lambda: calls.append('switch_to_game') or switch_ok,
    )
    monkeypatch.setattr(game, 'get_game_controller', lambda: controller)
    # 本组用例覆盖前台模式的切换语义，不随本机配置的本地操作模式变化（后台模式见 test_background_integration）
    monkeypatch.setattr(game, 'auto', SimpleNamespace(input_handler=SimpleNamespace(is_background=False)))
    log_stub = _LogStub()
    monkeypatch.setattr(game, 'log', log_stub)
    return game, calls, log_stub


class TestEnsureGameReady:
    def test_game_not_running_reports_error_and_skips_switch(self, monkeypatch):
        game, calls, log_stub = _prepare(monkeypatch, running=False, switch_ok=True)
        assert game.ensure_game_ready() is False
        assert calls == ['is_game_running']  # 未切换
        assert any('未检测到游戏窗口' in message for message in log_stub.errors)

    def test_switch_failure_reports_error(self, monkeypatch):
        game, calls, log_stub = _prepare(monkeypatch, running=True, switch_ok=False)
        assert game.ensure_game_ready() is False
        assert calls == ['is_game_running', 'switch_to_game']
        assert any('切换到游戏窗口失败' in message for message in log_stub.errors)

    def test_ready_when_running_and_switched(self, monkeypatch):
        game, calls, log_stub = _prepare(monkeypatch, running=True, switch_ok=True)
        assert game.ensure_game_ready() is True
        assert calls == ['is_game_running', 'switch_to_game']
        assert log_stub.errors == []
