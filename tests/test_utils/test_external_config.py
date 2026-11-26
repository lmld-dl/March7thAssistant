from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from utils import external_config as sync, paths


@pytest.mark.parametrize("kind", paths.EXTERNAL)
def test_round_trip_user_edits_restore_and_reset(tmp_path, monkeypatch, kind):
    monkeypatch.setattr(paths, "_layout", paths.select(tmp_path))
    tool = tmp_path / "custom tool"
    tool.mkdir()
    central = paths.layout().root / "external" / kind
    log = Mock()
    for name in paths.EXTERNAL[kind]:
        (tool / name).write_bytes(b"initial")
    with sync.tool_settings(kind, tool, log):
        assert all((central / n).read_bytes() == b"initial" for n in paths.EXTERNAL[kind])
    for name in paths.EXTERNAL[kind]:
        (tool / name).write_bytes(b"changed in tool")
        (central / name).write_bytes(b"user data")
    with pytest.raises(RuntimeError):
        with sync.tool_settings(kind, tool, log):
            for name in paths.EXTERNAL[kind]:
                assert (central / name).read_bytes() == b"changed in tool"
                (tool / name).write_bytes(b"updated before failure")
            raise RuntimeError("external process failed")
    for name in paths.EXTERNAL[kind]:
        assert (central / name).read_bytes() == b"updated before failure"
        (central / name).write_bytes(b"restored settings")
    with sync.tool_settings(kind, tool, log):
        assert all((tool / name).read_bytes() == b"restored settings" for name in paths.EXTERNAL[kind])
    sync.reset(kind, tool)
    assert not list(tool.iterdir()) and not list(central.iterdir())
    log.warning.assert_not_called()







def test_reset_reports_locked_file_and_clears_other_copies(tmp_path, monkeypatch):
    from pathlib import Path
    current = paths.select(tmp_path)
    monkeypatch.setattr(paths, "_layout", current)
    tool = tmp_path / "tool"
    tool.mkdir()
    name, other = paths.EXTERNAL["universe"]
    for n in (name, other):
        (tool / n).write_bytes(b"settings")
    with sync.tool_settings("universe", tool, Mock()):
        pass
    original = Path.unlink
    def locked(path, *args, **kwargs):
        if path == tool / name:
            raise PermissionError("file in use")
        original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", locked)
    assert sync.reset("universe", tool) == ["file in use"]
    assert (tool / name).is_file() and not (tool / other).exists()
    assert not list((current.root / "external/universe").iterdir())
