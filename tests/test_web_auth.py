"""web/auth.py — one-time QR tokens and persisted, hashed sessions (#659)."""
import json

from web.auth import TOKEN_TTL_S, Auth, cookie_value


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_token_is_single_use():
    a = Auth()
    token, ttl = a.new_token()
    assert ttl == TOKEN_TTL_S
    sid = a.redeem(token)
    assert sid and a.valid(sid)
    assert a.redeem(token) is None                      # replay refused


def test_token_expires():
    clock = Clock()
    a = Auth(clock=clock)
    token, _ = a.new_token()
    clock.t += TOKEN_TTL_S + 1
    assert a.redeem(token) is None


def test_garbage_tokens_and_sessions_are_refused():
    a = Auth()
    assert a.redeem("nope") is None and a.redeem(None) is None and a.redeem({"x": 1}) is None
    assert not a.valid("") and not a.valid("made-up")


def test_sessions_persist_hashed_and_forget_all(tmp_path):
    path = tmp_path / "cfg" / "web_sessions.json"
    saved = []
    a = Auth(str(path), on_saved=saved.append)
    sid = a.redeem(a.new_token()[0])
    stored = json.loads(path.read_text())
    assert sid not in path.read_text() and len(stored) == 1     # only the hash is on disk
    assert saved == [str(path)]
    assert (path.stat().st_mode & 0o777) == 0o600
    b = Auth(str(path))                                          # survives a restart
    assert b.valid(sid) and b.session_count == 1
    b.forget_all()
    assert not Auth(str(path)).valid(sid)


def test_cookie_value():
    h = {"cookie": "a=1; pisynth_session=abc_-9; b=2"}
    assert cookie_value(h) == "abc_-9"
    assert cookie_value({}) == "" and cookie_value({"cookie": "pisynth_sessionx=1"}) == ""


def test_pairing_a_new_browser_revokes_the_previous_one():
    a = Auth()
    first = a.redeem(a.new_token()[0])
    second = a.redeem(a.new_token()[0])
    assert a.valid(second) and not a.valid(first) and a.session_count == 1
