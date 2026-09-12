"""Pairing + sessions for the web companion (#659).

Physical presence is the key: the touch screen shows a QR code carrying a one-time token;
only someone who can see the Pi's screen can pair a phone. The phone trades the token for
a long-lived session cookie. Tokens live in RAM only; sessions are persisted (hashed — the
file alone can't be replayed as a cookie) so paired phones survive a restart.
"""
import hashlib
import json
import os
import secrets
import time

TOKEN_TTL_S = 120


def _digest(session_id):
    return hashlib.sha256(session_id.encode()).hexdigest()


class Auth:
    def __init__(self, sessions_path=None, clock=time.monotonic, wall=time.time, on_saved=None):
        self.sessions_path = sessions_path
        self._clock, self._wall = clock, wall
        self._on_saved = on_saved                  # e.g. read-only root write-through
        self._tokens = {}                          # token -> expiry (monotonic)
        self._sessions = {}                        # sha256(session id) -> {"created": epoch}
        self._load()

    # ---- one-time pairing tokens (shown as a QR on the box) ----
    def new_token(self):
        self._prune()
        token = secrets.token_urlsafe(16)
        self._tokens[token] = self._clock() + TOKEN_TTL_S
        return token, TOKEN_TTL_S

    def redeem(self, token):
        """Single use: a valid, unexpired token → a new session id; anything else → None."""
        self._prune()
        if not isinstance(token, str) or token not in self._tokens:
            return None
        del self._tokens[token]
        session_id = secrets.token_urlsafe(32)
        self._sessions[_digest(session_id)] = {"created": int(self._wall())}
        self._save()
        return session_id

    def _prune(self):
        now = self._clock()
        for t in [t for t, exp in self._tokens.items() if exp <= now]:
            del self._tokens[t]

    # ---- sessions ----
    def valid(self, session_id):
        return bool(session_id) and _digest(session_id) in self._sessions

    def forget_all(self):
        self._sessions.clear()
        self._tokens.clear()
        self._save()

    @property
    def session_count(self):
        return len(self._sessions)

    def _load(self):
        if not self.sessions_path:
            return
        try:
            with open(self.sessions_path) as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._sessions = {k: v for k, v in data.items() if isinstance(v, dict)}
        except (OSError, ValueError):
            self._sessions = {}

    def _save(self):
        if not self.sessions_path:
            return
        d = os.path.dirname(self.sessions_path)
        os.makedirs(d, exist_ok=True)
        tmp = self.sessions_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self._sessions, f)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.sessions_path)
        if self._on_saved:
            self._on_saved(self.sessions_path)


def cookie_value(headers, name="pisynth_session"):
    """The value of cookie `name` from a {lower-name: value} header dict, or ''."""
    for part in headers.get("cookie", "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == name:
            return v
    return ""
