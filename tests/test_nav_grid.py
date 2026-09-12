"""D-pad grid navigation (screens/nav.py `_nav_dispatch`): 3-column tile grids with paging,
plain lists stepping ±1, wrap-around at every edge (#373/#376)."""
import pytest

from pisynth.screens.nav import NavMixin
from pisynth.ui.menu import Item, MenuScreen


class Host(NavMixin):
    """Just enough of App for the dispatcher: a current screen + nav_move like App's."""

    def __init__(self, n, tiles=True, idx=0):
        self.cur = MenuScreen("t", [Item(str(i)) for i in range(n)], idx=idx, tiles=tiles)
        self.selected = self.backs = 0

    def nav_move(self, delta):
        self.cur.move(delta)
        self.cur.page = self.cur.idx // self.cur._per_page()

    def nav_select(self):
        self.selected += 1

    def nav_back(self):
        self.backs += 1


@pytest.fixture(autouse=True)
def six_per_page(monkeypatch):
    monkeypatch.setattr(MenuScreen, "per_page_tiles", 6)
    monkeypatch.setattr(MenuScreen, "per_page_rows", 6)


def walk(host, *actions):
    for a in actions:
        host._nav_dispatch(a)
    return host.cur.idx


# 8 tiles, 6 per page, 3 columns → page 0: [0 1 2] [3 4 5]   page 1: [6 7]
def test_down_keeps_column_across_pages_and_wraps():
    assert walk(Host(8), "down") == 3
    assert walk(Host(8), "down", "down") == 6
    assert walk(Host(8), "down", "down", "down") == 0


def test_down_skips_rows_missing_that_column():
    assert walk(Host(8, idx=2), "down", "down") == 2          # row 2 has no column 2


def test_right_at_row_end_flips_to_next_page():
    h = Host(8, idx=2)
    assert walk(h, "right") == 6 and h.cur.page == 1
    assert walk(Host(8, idx=5), "right") == 6                  # row absent on the partial page


def test_left_at_row_start_flips_to_previous_page_end_of_row():
    assert walk(Host(8), "left") == 7


def test_single_page_right_wraps_within_row():
    assert walk(Host(3, idx=2), "right") == 0


def test_list_steps_and_wraps():
    assert walk(Host(4, tiles=False), "up") == 3
    assert walk(Host(4, tiles=False), "right", "down") == 2


def test_select_and_back_are_forwarded():
    h = Host(4)
    walk(h, "select", "back")
    assert (h.selected, h.backs) == (1, 1)
