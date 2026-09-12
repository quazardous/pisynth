"""Hot-plug detection (#2410): notice a device coming (back), from periodic presence polls.

Pure logic, no I/O: the caller polls what is present (sound cards, MIDI clients) and feeds
the set of keys; `update()` returns the keys that just (re)appeared and stayed put for
`settle` polls — so a flaky connector or a USB re-enumeration doesn't fire twice.
"""


class PresenceWatch:
    """Edge detector over polled key sets.

    - The first `update()` only learns the initial state (nothing fires at startup).
    - `require_seen=True`: only a key that was present before, went away and came back
      fires (a sound card replugged). `False`: any key appearing after startup fires
      (a keyboard plugged in for the first time needs the same re-wiring as a replug).
    - A key fires once per appearance, after `settle` consecutive present polls.
    """

    def __init__(self, settle=2, require_seen=True):
        self.settle = max(1, int(settle))
        self.require_seen = require_seen
        self._streak = {}          # key -> consecutive polls present (0 = absent last poll)
        self._seen = set()         # keys that have been stably present at some point
        self._armed = set()        # keys that appeared and will fire once settled
        self._started = False

    def update(self, present):
        present = set(present)
        fired = set()
        for key in present:
            streak = self._streak.get(key, 0) + 1
            if not self._started:                       # initial state: learn, don't fire
                self._streak[key] = self.settle
                self._seen.add(key)
                continue
            self._streak[key] = streak
            if streak == 1 and (key in self._seen or not self.require_seen):
                self._armed.add(key)
            if streak == self.settle:
                self._seen.add(key)
                if key in self._armed:
                    self._armed.discard(key)
                    fired.add(key)
        for key in list(self._streak):
            if key not in present:
                self._streak[key] = 0
                self._armed.discard(key)                # flapped away before settling
        self._started = True
        return fired
