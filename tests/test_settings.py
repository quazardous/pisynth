import json

import pytest

from pisynth.core import settings as S


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "SETTINGS_PATH", str(tmp_path / "cfg" / "settings.yaml"))
    monkeypatch.setattr(S, "CAL_PATH", str(tmp_path / "cfg" / "touch_cal.json"))
    return tmp_path / "cfg"


def test_settings_round_trip_keeps_documented_header(paths):
    d = {"sleep_after": 60, "preset": {"font": "01-A.sf3", "bank": 0, "prog": 4, "name": "EP"}}
    S.save_settings(d)
    assert S.load_settings() == d
    text = (paths / "settings.yaml").read_text()
    assert text.startswith("# pisynth local preferences")
    assert not (paths / "settings.yaml.tmp").exists()          # atomic write leaves no tmp


def test_missing_or_garbage_settings_give_empty_dict(paths):
    assert S.load_settings() == {}
    paths.mkdir(parents=True, exist_ok=True)
    (paths / "settings.yaml").write_text("- just\n- a list\n")
    assert S.load_settings() == {}


def test_legacy_json_is_imported_once_as_yaml(paths):
    paths.mkdir(parents=True)
    (paths / "settings.json").write_text(json.dumps({"soundcard": "Hub"}))
    assert S.load_settings() == {"soundcard": "Hub"}
    assert (paths / "settings.yaml").exists()


def test_calibration_round_trip(paths):
    assert S.load_cal() is None
    S.save_cal([1.0, 0.0, 2.0, 0.0, 1.0, 3.0])
    assert S.load_cal() == [1.0, 0.0, 2.0, 0.0, 1.0, 3.0]
