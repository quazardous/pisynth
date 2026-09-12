"""App._cycle_font — D-pad ←/→/● via midi-bridge.sh → UI socket (next/prev/first soundfont)."""
from pisynth.app import App


class Host:
    _cycle_font = App._cycle_font

    def __init__(self, cur=None):
        self.fonts = [(None, "/sf/01-A.sf3"), (None, "/sf/02-B.sf2"), (None, "/sf/03-C.sf2")]
        self.cur_font_path = cur
        self.chosen = []

    def _default_preset(self, sfid, path):
        return (0, 0, "default of " + path.rsplit("/", 1)[-1])

    def _choose_preset(self, path, bank, prog, name):
        self.cur_font_path = path
        self.chosen.append(path.rsplit("/", 1)[-1])


def test_next_prev_wrap_and_first():
    h = Host("/sf/02-B.sf2")
    h._cycle_font(1); h._cycle_font(1); h._cycle_font(-1); h._cycle_font(0, first=True)
    assert h.chosen == ["03-C.sf2", "01-A.sf3", "03-C.sf2", "01-A.sf3"]


def test_no_current_font_starts_at_first():
    h = Host(None)
    h._cycle_font(1)
    assert h.chosen == ["01-A.sf3"]


def test_empty_catalog_is_a_no_op():
    h = Host()
    h.fonts = []
    h._cycle_font(1)
    assert h.chosen == []
