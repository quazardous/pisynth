"""Menu SDK (#308): Item + MenuScreen — the app-independent screen model.

Paging is configured by the controller via the MenuScreen class attributes
per_page_tiles / per_page_rows (no module globals).
"""
PAGE_TILES_OPTIONS = [4, 6, 9, 12]   # Settings -> Tiles per page (#276)


class Item:
    """One menu cell/row. on_select = enter; on_adjust(±1) = left/right change."""

    def __init__(self, label, on_select=None, on_adjust=None,
                 value=None, marker=None, bar=None, submenu=False, color=None,
                 sublabel=None):
        self.label = label
        self.on_select = on_select
        self.on_adjust = on_adjust
        self.value = value        # callable -> str (right-aligned)
        self.marker = marker      # callable -> bool (current → yellow tile frame)
        self.bar = bar            # callable -> 0..1 (inline VU bar)
        self.submenu = submenu
        self.color = color        # tile color override (else palette by index)
        self.sublabel = sublabel  # callable -> str|None (2nd line on a tile, e.g. preset name)


class MenuScreen:
    """A screen: title + items, rendered as a Metro tile grid (paged) or a
    tabular list. Navigation/render/input treat every screen uniformly."""

    per_page_tiles = 6      # tiles/page (Tiles-per-page setting); set by App (#276)
    per_page_rows = 6       # list rows/page; recomputed from screen height by App (#276)

    def __init__(self, title, items, idx=0, tiles=False, footer=None, keyboard=False):
        self.title = title
        self.items = items
        self.idx = idx
        self.tiles = tiles
        self.keyboard = keyboard      # MIDI test screen: body is a live mini-keyboard (#331)
        self.page = 0
        self.footer = footer          # optional one-line status under the list

    @property
    def selected(self):
        return self.items[self.idx]

    def move(self, delta):
        # Wrap-around (#373): stepping past an edge loops to the other side, so MIDI/D-pad
        # nav never dead-ends (david: « ça devrait revenir de l'autre côté »).
        n = len(self.items)
        if n:
            self.idx = (self.idx + delta) % n

    # ---- pagination (tiles: PAGE_TILES per page; lists: LIST_ROWS per page, #276) ----
    def _per_page(self):
        return MenuScreen.per_page_tiles if self.tiles else MenuScreen.per_page_rows

    def npages(self):
        if not self.items:
            return 1
        per = self._per_page()
        return max(1, (len(self.items) + per - 1) // per)

    def page_slice(self):
        """[(global_index, item), ...] for the current page."""
        per = self._per_page()
        self.page %= self.npages()
        start = self.page * per
        return [(start + i, it) for i, it in enumerate(self.items[start:start + per])]

    def page_flip(self, delta=1):
        n = self.npages()
        self.page = (self.page + delta) % n
