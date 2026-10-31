# coding:utf-8
"""GUI 暂停功能测试：按钮切换、状态同步、悬浮窗徽章与快捷键提示。"""
import json
import sys
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or not hasattr(sys, 'getwindowsversion'),
    reason="GUI 测试仅在 Windows 平台运行"
)


def test_cooperative_stop_waits_for_cleanup_and_keeps_old_process_identity(monkeypatch,tmp_path):
    import app.log_interface as module
    from utils.pause import STATE_STOPPING
    callbacks=[]
    monkeypatch.setattr(module.QTimer,'singleShot',lambda _delay,callback:callbacks.append(callback))
    process=SimpleNamespace(state=lambda:module.QProcess.Running,processId=lambda:123)
    killed=[]
    host=SimpleNamespace(process=process,_pauseControlPath=lambda:str(tmp_path/'control.json'),
                         _killProcessTree=lambda pid:killed.append(pid),appendLog=lambda _:None)
    host._finishCooperativeStop=lambda p,pid,d:module.LogInterface._finishCooperativeStop(host,p,pid,d)
    module.LogInterface._finishCooperativeStop(host,process,123,module.time.monotonic()+10)
    assert killed==[] and callbacks
    (tmp_path/'control.json.state').write_text(json.dumps({'state':STATE_STOPPING}),encoding='utf-8')
    callbacks.pop()()
    assert killed==[123]
    host.process=SimpleNamespace(state=lambda:module.QProcess.Running,processId=lambda:456)
    module.LogInterface._finishCooperativeStop(host,process,123,0)
    assert killed==[123]


def test_stop_sends_stop_and_prevents_hotkey_overwriting_it(monkeypatch,tmp_path):
    import app.log_interface as module
    callbacks=[]
    monkeypatch.setattr(module.QTimer,'singleShot',lambda _delay,callback:callbacks.append(callback))
    process=SimpleNamespace(state=lambda:module.QProcess.Running,processId=lambda:123)
    killed=[]
    path=tmp_path/'control.json'
    host=SimpleNamespace(process=process,_clearTaskTimeout=lambda:None,_pause_supported=True,
                         _pauseControlPath=lambda:str(path),_killProcessTree=lambda pid:killed.append(pid),
                         appendLog=lambda _:None,pauseButton=SimpleNamespace(setEnabled=lambda _:None))
    host._finishCooperativeStop=lambda p,pid,d:module.LogInterface._finishCooperativeStop(host,p,pid,d)
    module.LogInterface.stopTask(host)
    assert json.loads(path.read_text(encoding='utf-8'))['command']=='stop'
    assert killed==[] and len(callbacks)==1
    module.LogInterface._sendPauseCommand(host,'resume')
    assert json.loads(path.read_text(encoding='utf-8'))['command']=='stop'
    module.LogInterface.stopTask(host)
    assert len(callbacks)==1
    (tmp_path/'control.json.state').write_text(json.dumps({'state':'stopping'}),encoding='utf-8')
    callbacks.pop()()
    assert killed==[123]


@pytest.fixture(scope="session")
def qapp():
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        return app
    except ImportError:
        pytest.skip("PySide6 未安装")


class _FakeButton:
    def __init__(self):
        self.enabled = None
        self.text = None

    def setEnabled(self, enabled):
        self.enabled = bool(enabled)

    def setText(self, text):
        self.text = text


class _FakeLabel:
    def __init__(self, value=''):
        self.value = value

    def text(self):
        return self.value

    def setText(self, value):
        self.value = value


class _FakeTimer:
    def __init__(self):
        self.stopped = False
        self.started_with = None
        self.remaining = 5000

    def remainingTime(self):
        return self.remaining

    def stop(self):
        self.stopped = True

    def start(self, msec):
        self.started_with = msec


class TestPausableTasksWhitelist:
    """仅内置自动化任务支持暂停。"""

    def test_builtin_tasks_in_whitelist(self):
        from utils.tasks import PAUSABLE_TASKS
        for task_id in ("main", "daily", "power", "currencywars", "divergent", "screen_test"):
            assert task_id in PAUSABLE_TASKS

    def test_non_automation_tasks_not_in_whitelist(self):
        from utils.tasks import PAUSABLE_TASKS
        for task_id in ("game_update", "game_pre_download", "mobileui_update", "game"):
            assert task_id not in PAUSABLE_TASKS


class TestResolvePauseSupport:
    """启动目标的暂停支持判定：内置任务按白名单，外部程序不支持。"""

    def test_builtin_pausable_tasks(self):
        from app.log_interface import LogInterface
        for task_id in ("main", "daily", "currencywars", "divergentloop", "screen_test"):
            assert LogInterface._resolvePauseSupport(task_id) is True

    def test_builtin_non_pausable_tasks(self):
        from app.log_interface import LogInterface
        for task_id in ("game_update", "game", "mobileui_update"):
            assert LogInterface._resolvePauseSupport(task_id) is False

    def test_external_program_is_not_pausable(self):
        from app.log_interface import LogInterface
        task = {"program": "BetterGI.exe", "args": "--foo"}
        assert LogInterface._resolvePauseSupport(task) is False

    def test_self_program_uses_task_id(self):
        from app.log_interface import LogInterface
        assert LogInterface._resolvePauseSupport({"program": "self", "args": "daily"}) is True
        assert LogInterface._resolvePauseSupport({"program": "self", "args": "game"}) is False


class TestPauseToggle:
    """按钮/热键共用的暂停切换逻辑。"""

    def _make_iface(self, tmp_path):
        from app.log_interface import LogInterface
        from utils.pause import STATE_RUNNING
        iface = LogInterface.__new__(LogInterface)
        iface._pause_supported = True
        iface._pause_state = STATE_RUNNING
        iface._status_text_before_pause = None
        iface._paused_timeout_remaining = None
        iface._timeout_timer = None
        iface.log_lines = []
        iface.appendLog = iface.log_lines.append
        iface.isTaskRunning = lambda: True
        iface._pauseControlPath = lambda: str(tmp_path / "pause.json")
        iface.pauseButton = _FakeButton()
        iface.statusLabel = _FakeLabel('正在运行：货币战争')
        iface._log_overlay = SimpleNamespace(set_paused=lambda p: iface.paused_flags.append(p))
        iface.paused_flags = []
        return iface

    def test_toggle_writes_pause_then_resume(self, tmp_path):
        from utils.pause import STATE_PAUSED
        iface = self._make_iface(tmp_path)
        control = tmp_path / "pause.json"

        iface._onPauseToggle()
        assert json.loads(control.read_text(encoding="utf-8"))["command"] == "pause"
        assert iface._pause_state == "pausing"
        assert any("暂停指令已发送" in line for line in iface.log_lines)

        # 任务真正停下（CLI 回执 paused）后按键才发送继续指令
        (tmp_path / "pause.json.state").write_text(
            json.dumps({"state": STATE_PAUSED}), encoding="utf-8"
        )
        iface._onPauseToggle()
        assert json.loads(control.read_text(encoding="utf-8"))["command"] == "resume"
        assert iface._pause_state == "running"
        assert any("继续指令已发送" in line for line in iface.log_lines)

    def test_toggle_never_resumes_before_fully_paused(self, tmp_path):
        """任务未真正停下前连按暂停热键/按钮，始终是暂停语义，不会切成继续。"""
        from utils.pause import STATE_PAUSING
        iface = self._make_iface(tmp_path)
        control = tmp_path / "pause.json"

        iface._onPauseToggle()
        assert json.loads(control.read_text(encoding="utf-8"))["command"] == "pause"
        # 模拟 CLI 回执「暂停中」（已发暂停指令、尚未停到卡点）
        (tmp_path / "pause.json.state").write_text(
            json.dumps({"state": STATE_PAUSING}), encoding="utf-8"
        )
        for _ in range(3):
            iface._onPauseToggle()
            assert json.loads(control.read_text(encoding="utf-8"))["command"] == "pause"
        assert iface._pause_state == "pausing"
        assert not any("继续指令已发送" in line for line in iface.log_lines)

    def test_toggle_ignored_when_task_not_supported(self, tmp_path):
        iface = self._make_iface(tmp_path)
        iface._pause_supported = False
        iface._onPauseToggle()
        assert not (tmp_path / "pause.json").exists()
        assert iface.log_lines == []

    def test_sync_state_updates_ui_on_paused(self, tmp_path):
        from utils.pause import STATE_PAUSED, write_command
        from module.localization import tr
        iface = self._make_iface(tmp_path)
        control = tmp_path / "pause.json"
        write_command(str(control), "resume")
        # 模拟 CLI 回执 paused
        (tmp_path / "pause.json.state").write_text(
            json.dumps({"state": STATE_PAUSED}), encoding="utf-8"
        )

        iface._syncPauseState()

        assert iface._pause_state == STATE_PAUSED
        assert iface.statusLabel.value == tr('已暂停')
        assert iface.paused_flags == [True]
        assert iface.pauseButton.enabled is True
        assert tr('继续任务') in iface.pauseButton.text

    def test_reset_pause_runtime(self, tmp_path):
        from utils.pause import STATE_PAUSED, read_state, write_command
        iface = self._make_iface(tmp_path)
        control = tmp_path / "pause.json"
        write_command(str(control), "pause")
        (tmp_path / "pause.json.state").write_text(
            json.dumps({"state": STATE_PAUSED}), encoding="utf-8"
        )
        iface._pause_state = STATE_PAUSED
        iface._status_text_before_pause = '正在运行：货币战争'

        iface._resetPauseRuntime()

        assert iface._pause_supported is False
        assert iface._pause_state == "running"
        assert iface.pauseButton.enabled is False
        assert read_state(str(control)) is None

    def test_timeout_timer_frozen_while_paused(self, tmp_path):
        iface = self._make_iface(tmp_path)
        timer = _FakeTimer()
        iface._timeout_timer = timer

        iface._freezeTimeoutTimer()
        assert timer.stopped is True
        assert iface._paused_timeout_remaining == 5000

        # 重复暂停请求不覆盖已冻结的剩余时间（定时器已停止时 remainingTime 无意义）
        timer.remaining = -1
        iface._freezeTimeoutTimer()
        assert iface._paused_timeout_remaining == 5000

        iface._resumeTimeoutTimer()
        assert timer.started_with == 5000
        assert iface._paused_timeout_remaining is None

    def test_schedule_check_skipped_while_paused(self, tmp_path):
        iface = self._make_iface(tmp_path)
        from utils.pause import STATE_PAUSED
        iface._pause_state = STATE_PAUSED
        iface._updateScheduleStatusLabel = lambda: None
        # 暂停期间直接返回，不读取定时任务配置（配置对象若被访问会失败）
        iface._checkScheduledTime()


class TestGameLogOverlayPauseDisplay:
    """悬浮窗：双快捷键提示 + 暂停徽章。"""

    def _make_overlay(self):
        from app.log_interface import GameLogOverlay
        overlay = GameLogOverlay.__new__(GameLogOverlay)
        overlay.hotkeyLabel = _FakeLabel()
        overlay.pauseBadge = SimpleNamespace(
            visible=None,
            setVisible=lambda v: setattr(overlay.pauseBadge, 'visible', bool(v)),
        )
        return overlay

    def test_hotkey_hint_shows_both_hotkeys(self, qapp):
        from module.localization import tr
        overlay = self._make_overlay()
        overlay.update_hotkey_hint('F10', 'F8')
        assert 'F10' in overlay.hotkeyLabel.value
        assert 'F8' in overlay.hotkeyLabel.value
        assert tr('按下 {stop} 停止 · {pause} 暂停').format(stop='F10', pause='F8') == overlay.hotkeyLabel.value

    def test_hotkey_hint_switches_to_resume_when_paused(self, qapp):
        from module.localization import tr
        overlay = self._make_overlay()
        overlay.update_hotkey_hint('F10', 'F8', paused=True)
        assert overlay.hotkeyLabel.value == tr('按下 {stop} 停止 · {pause} 继续').format(stop='F10', pause='F8')

    def test_hotkey_hint_hides_pause_hotkey_when_not_pausable(self, qapp):
        from module.localization import tr
        overlay = self._make_overlay()
        overlay.update_hotkey_hint('F10', None)
        assert overlay.hotkeyLabel.value == tr('按下 {stop} 停止任务').format(stop='F10')
        # 不支持暂停的任务即使处于暂停态（不会发生）也只显示停止提示
        overlay.update_hotkey_hint('F10', None, paused=True)
        assert overlay.hotkeyLabel.value == tr('按下 {stop} 停止任务').format(stop='F10')

    def test_set_paused_toggles_badge(self, qapp):
        overlay = self._make_overlay()
        overlay.set_paused(True)
        assert overlay.pauseBadge.visible is True
        overlay.set_paused(False)
        assert overlay.pauseBadge.visible is False

    def test_overlay_hint_reflects_task_pausability(self, tmp_path):
        from app.log_interface import LogInterface
        from utils.pause import STATE_RUNNING
        iface = LogInterface.__new__(LogInterface)
        iface._pause_supported = False
        iface._pause_state = STATE_RUNNING
        calls = []
        iface._log_overlay = SimpleNamespace(
            update_hotkey_hint=lambda stop, pause, paused=False: calls.append((stop, pause, paused)),
        )

        iface._updateOverlayHotkeyHint()
        assert calls[-1][1] is None  # 不可暂停：不显示暂停快捷键

        iface._pause_supported = True
        iface._updateOverlayHotkeyHint()
        assert calls[-1][1] is not None  # 可暂停：显示暂停快捷键
        assert calls[-1][2] is False  # 未暂停：提示仍是「暂停」

    def test_overlay_hint_reflects_paused_state(self, tmp_path):
        from app.log_interface import LogInterface
        from utils.pause import STATE_PAUSED, STATE_PAUSING, STATE_RUNNING
        iface = LogInterface.__new__(LogInterface)
        iface._pause_supported = True
        calls = []
        iface._log_overlay = SimpleNamespace(
            update_hotkey_hint=lambda stop, pause, paused=False: calls.append(paused),
        )

        iface._pause_state = STATE_RUNNING
        iface._updateOverlayHotkeyHint()
        assert calls[-1] is False

        # 「暂停中」过渡态不切换文案（与暂停徽章/按钮文本一致）
        iface._pause_state = STATE_PAUSING
        iface._updateOverlayHotkeyHint()
        assert calls[-1] is False

        iface._pause_state = STATE_PAUSED
        iface._updateOverlayHotkeyHint()
        assert calls[-1] is True  # 已暂停：提示改为「继续」
