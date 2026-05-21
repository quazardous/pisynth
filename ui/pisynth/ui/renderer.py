"""Renderer — the portable display/view layer (#308 step 5).

Turns a screen model (ui.menu.MenuScreen) + a small `Status` snapshot into pixels on a
`Display` (io.display.Framebuffer or any blittable surface), and owns the matching
*geometry* + *hit-testing* helpers the controller uses to map taps back to widgets. It
holds NO application state — only the display, fonts, theme and layout — so "porting the
display" is: swap the Display, reuse this Renderer + the ui/ toolkit. The controller
(app.App) passes a `Status` each frame instead of `self`.
"""
from collections import namedtuple

from PIL import Image, ImageDraw

from .menu import MenuScreen
from .theme import (ACCENT, AMBER, BARBG, BG, BT_BLUE, BTN, ERR, FG, ICON, MUTED, OK,
                    PINK, SEL_BORDER, SEL_SUB, SELBG, TILE_PALETTE, load_font, load_icon_font)

# Dynamic bits the view needs each frame — a snapshot, so the renderer never reaches
# back into the controller (#308). depth = len(nav stack); toast = active toast text/None;
# health = 'good'|'warn'|'crit' for the Home health smiley (#325); kbd = MidiState|None for
# the MIDI Test-keyboard screen (#331).
Status = namedtuple("Status", "depth wifi bt bt_conn midi synth audio "
                              "metro_running metro_beat metro_beats toast health kbd loading")

# Snapshot of the live MIDI monitor for the Test-keyboard screen (#331).
MidiState = namedtuple("MidiState", "active lo hi last count")

_HEALTH_GLYPH = {"good": "health_good", "warn": "health_warn", "crit": "health_crit"}
_HEALTH_COLOR = {"good": OK, "warn": AMBER, "crit": ERR}
_WHITE_PCS = (0, 2, 4, 5, 7, 9, 11)          # pitch classes of white keys
_NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def note_name(n):
    """MIDI note number → name like 'C4' (#331; MIDI C4 = 60)."""
    return f"{_NOTE_NAMES[n % 12]}{n // 12 - 1}"


class Renderer:
    BAR_H = 45      # top bar = same height as a settings row (ROW_H)
    ROW_H = 45      # tabular rows

    def __init__(self, display):
        self.display = display
        self.f_big = load_font(24)
        self.f_med = load_font(18)
        self.f_small = load_font(13)
        self.f_icon = load_icon_font(26)          # bundled Material Symbols subset (#306)
        self.f_icon_sm = load_icon_font(20)       # smaller variant: tile 'pending' badge (#334)

    # ---- geometry (shared by render + the controller's hit-testing) ----
    def _back_rect(self, depth):
        """Standardized back button (top-left of the bar) on every sub-screen."""
        return (0, 0, 56, self.BAR_H) if depth > 1 else None

    def _page_rect(self, screen):
        """Pagination hit zone (top-right of the bar) when the screen is paged.
        Left half = previous page, right half = next (matches the ‹ › arrows)."""
        return (self.display.w - 110, 0, self.display.w, self.BAR_H) if screen.npages() > 1 else None

    def _row_y(self, i):
        return self.BAR_H + 4 + i * self.ROW_H

    def _stepper_rects(self, ry):
        """(minus, plus, value_center_x) for an adjustable row (e.g. Gain)."""
        cy = ry + self.ROW_H // 2
        b = self.ROW_H - 12
        plus = (self.display.w - 10 - b, cy - b // 2, self.display.w - 10, cy + b // 2)
        vcx = plus[0] - 26
        mx1 = plus[0] - 52
        minus = (mx1 - b, cy - b // 2, mx1, cy + b // 2)
        return minus, plus, vcx

    def _tile_grid(self, n, cols=3, rows=None):
        gap = 6
        w, h = self.display.w, self.display.h
        top = self.BAR_H + gap
        if rows is None:
            rows = max(1, (n + cols - 1) // cols)
        tw = (w - gap * (cols + 1)) / cols
        th = (h - top - gap * rows) / rows
        rects = []
        for idx in range(n):
            r, c = divmod(idx, cols)
            x0 = gap + c * (tw + gap)
            y0 = top + r * (th + gap)
            rects.append((x0, y0, x0 + tw, y0 + th))
        return rects

    def _fixed_rows(self, m):
        """Keep a uniform tile size across pages: 3 rows once a screen is paged."""
        return ((MenuScreen.per_page_tiles + 2) // 3) if m.npages() > 1 else None

    # ---- primitives ----
    @staticmethod
    def _ic_color(on, lit=OK):
        return lit if on else (66, 70, 88)           # lit colour when on, idle = dim slate

    def _center_text(self, d, y, text, font, fill=FG):
        tw = d.textlength(text, font=font)
        d.text((self.display.w / 2 - tw / 2, y), text, font=font, fill=fill)

    def _tri(self, d, cx, cy, h, direction, fill):
        """Filled triangle drawn as horizontal scanlines so the diagonal steps evenly —
        a constant 1 px change per row (regular slope), pointing left/right. Deliberately
        not mathematically equilateral: equilateral gave uneven pixel steps (#289)."""
        cx, cy, hh = int(cx), int(cy), int(h) // 2
        xL = cx - hh // 2
        for i in range(-hh, hh + 1):
            depth = hh - abs(i)                  # constant 1 px/row → even slope
            y = cy + i
            if direction == "right":
                d.line((xL, y, xL + depth, y), fill=fill)
            else:
                d.line((xL + hh - depth, y, xL + hh, y), fill=fill)

    def _glyph(self, d, name, cx, cy, fill, font=None):
        """Draw a bundled icon-font glyph centred on (cx, cy) (#306). No-op if the icon
        font failed to load — the bar then shows no icon rather than a broken box."""
        font = font or self.f_icon
        if not font:
            return
        ch = ICON[name]
        x0, y0, x1, y1 = d.textbbox((0, 0), ch, font=font)
        d.text((cx - (x1 + x0) / 2, cy - (y1 + y0) / 2), ch, font=font, fill=fill)

    def _hbar(self, d, x0, y0, x1, y1, frac):
        n, gap = 12, 2
        seg = (x1 - x0 - (n - 1) * gap) / n
        for k in range(n):
            f = (k + 0.5) / n
            base = (60, 200, 90) if f < 0.6 else (235, 200, 60) if f < 0.85 else (225, 80, 80)
            col = base if f <= frac else tuple(c // 6 for c in base)
            sx = x0 + k * (seg + gap)
            d.rectangle((sx, y0, sx + seg, y1), fill=col)

    def _ellipsize(self, d, text, font, maxw):
        if d.textlength(text, font=font) <= maxw:
            return text
        while text and d.textlength(text + "…", font=font) > maxw:
            text = text[:-1]
        return (text + "…") if text else ""

    # ---- Home status indicators (#306) ----
    def _draw_status_icons(self, d, x, cy, status):
        """Render the Home indicators left-to-right from x: Wi-Fi · Bluetooth · keyboard
        (MIDI in) · synth (fluidsynth stack) · audio (sound card) · metronome · health.
        Lit when on/present/running (Bluetooth brand blue, metronome pink, the rest
        green), dim slate when off/absent (#306/#326/#327)."""
        step = 32
        self._glyph(d, "wifi", x, cy, self._ic_color(status.wifi))
        # Bluetooth: dim (off) → blue `bluetooth` (radio on) → blue `bluetooth_connected`
        # (a device is connected), so you see at a glance if something's paired+live (#306).
        bt_glyph = "bluetooth_connected" if status.bt_conn else "bluetooth"
        self._glyph(d, bt_glyph, x + step, cy, self._ic_color(status.bt, BT_BLUE))
        self._glyph(d, "piano", x + 2 * step, cy, self._ic_color(status.midi, FG))  # white = keys active (#326)
        self._glyph(d, "synth", x + 3 * step, cy, self._ic_color(status.synth))     # fluidsynth stack up (#327)
        self._glyph(d, "volume_up", x + 4 * step, cy, self._ic_color(status.audio)) # sound card OK (#327)
        self._glyph(d, "metronome", x + 5 * step, cy,
                    self._ic_color(status.metro_running, PINK))   # pink when running (#287)
        # health smiley (#325): face + colour both convey severity (good/warn/crit)
        self._glyph(d, _HEALTH_GLYPH[status.health], x + 6 * step, cy,
                    _HEALTH_COLOR[status.health])

    def _draw_beats(self, d, status):
        """Beat indicator on the Metronome screen: a dot per beat, the current one filled
        (accent beat 1 in yellow), the rest outlined (#287)."""
        n = max(1, status.metro_beats)
        r, gap = 13, 16
        total = n * 2 * r + (n - 1) * gap
        x0, y = (self.display.w - total) / 2, self.display.h - 56
        for i in range(n):
            cx = x0 + r + i * (2 * r + gap)
            box = (cx - r, y - r, cx + r, y + r)
            if status.metro_running and status.metro_beat == i + 1:
                d.ellipse(box, fill=(SEL_BORDER if i == 0 else ACCENT))
            else:
                d.ellipse(box, outline=MUTED, width=2)

    # ---- list / tile bodies ----
    def _draw_rows(self, d, m):
        w = self.display.w
        for pos, (gi, it) in enumerate(m.page_slice()):   # paged (#276)
            ry = self._row_y(pos)
            cy = ry + self.ROW_H // 2
            if gi == m.idx:
                d.rectangle((0, ry, w, ry + self.ROW_H - 2), fill=SELBG)
                d.rectangle((0, ry, 3, ry + self.ROW_H - 2), fill=ACCENT)
            if it.marker and it.marker():
                d.ellipse((14, cy - 4, 22, cy + 4), fill=OK)
            d.text((30, cy - 10), it.label, font=self.f_med, fill=FG)
            if it.on_adjust:                       # − value + stepper
                minus, plus, vcx = self._stepper_rects(ry)
                for rect, sym in ((minus, "−"), (plus, "+")):
                    d.rounded_rectangle(rect, radius=6, fill=BTN, outline=ACCENT)
                    sw = d.textlength(sym, font=self.f_med)
                    d.text(((rect[0] + rect[2]) / 2 - sw / 2, (rect[1] + rect[3]) / 2 - 11),
                           sym, font=self.f_med, fill=FG)
                if it.value:
                    v = it.value() or ""
                    vw = d.textlength(v, font=self.f_med)
                    d.text((vcx - vw / 2, cy - 10), v, font=self.f_med, fill=ACCENT)
                if it.bar:
                    self._hbar(d, 130, cy - 5, minus[0] - 12, cy + 5, it.bar())
            else:
                rx = w - 14
                if it.submenu:
                    d.text((rx - 10, cy - 11), "›", font=self.f_med, fill=MUTED)
                    rx -= 22
                if it.value:
                    v = it.value() or ""
                    lab_end = 30 + d.textlength(it.label, font=self.f_med) + 12
                    v = self._ellipsize(d, v, self.f_med, rx - lab_end)   # never overflow the label (#316)
                    vw = d.textlength(v, font=self.f_med)
                    d.text((rx - vw, cy - 10), v, font=self.f_med, fill=ACCENT)

    def _draw_tiles(self, d, m, loading=False):
        slice_ = m.page_slice()
        rects = self._tile_grid(len(slice_), rows=self._fixed_rows(m))
        for (gi, it), rect in zip(slice_, rects):
            col = it.color or TILE_PALETTE[gi % len(TILE_PALETTE)]
            d.rectangle(rect, fill=col)            # flat tile
            sub = it.sublabel() if it.sublabel else None
            self._tile_label(d, rect, it.label, sub)
            if it.marker and it.marker():          # current selection: amber frame + 'pending' glyph
                b = 3                              # while loading, green frame once resident (#290/#334)
                d.rectangle((rect[0] - b, rect[1] - b, rect[2] + b, rect[3] + b),
                            outline=(SEL_BORDER if loading else OK), width=b)
                if loading:                        # small 'sync' (Material) top-right, label colour (#334)
                    self._glyph(d, "sync", rect[2] - 16, rect[1] + 16, (255, 255, 255), self.f_icon_sm)

    def _tile_label(self, d, rect, label, sub=None):
        x0, y0, x1, y1 = rect
        maxw = (x1 - x0) - 12
        words, lines, cur = label.split(), [], ""
        for wd in words:
            t = (cur + " " + wd).strip()
            if d.textlength(t, font=self.f_med) <= maxw:
                cur = t
            else:
                if cur:
                    lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
        lh = 21
        sub_h = 17 if sub else 0
        ty = (y0 + y1) / 2 - (lh * len(lines) + sub_h) / 2
        for ln in lines:
            tw = d.textlength(ln, font=self.f_med)
            d.text(((x0 + x1) / 2 - tw / 2, ty), ln, font=self.f_med, fill=(255, 255, 255))
            ty += lh
        if sub:                                    # 2nd line: selected preset name (#276)
            s = self._ellipsize(d, sub, self.f_small, maxw)
            tw = d.textlength(s, font=self.f_small)
            d.text(((x0 + x1) / 2 - tw / 2, ty + 1), s, font=self.f_small, fill=SEL_SUB)

    # ---- MIDI test keyboard (#331) ----
    def _draw_keyboard(self, d, kbd):
        """Mini piano: white+black keys, active notes filled accent. Full 88-key range
        (A0-C8) by default so it fits any keyboard (#331); widens further only if a device
        sends outside that. Keys keep a realistic ~1:6 proportion (a horizontal strip).
        kbd = MidiState | None."""
        active = kbd.active if kbd else frozenset()
        lo, hi = 21, 108                               # full 88-key piano A0..C8 (#331)
        if kbd and kbd.lo is not None:                 # exotic controller outside 88 → widen
            lo = min(lo, kbd.lo - kbd.lo % 12)
            hi = max(hi, kbd.hi + (11 - kbd.hi % 12))
        w, h = self.display.w, self.display.h
        whites = [n for n in range(lo, hi + 1) if n % 12 in _WHITE_PCS]
        if not whites:
            return
        kw = w / len(whites)
        kb_h = min(h - self.BAR_H - 60, kw * 6)        # realistic key proportion (white ~1:6)
        top = self.BAR_H + 8 + (h - self.BAR_H - 8 - kb_h - 26) / 2   # centre the strip
        wx = {}
        for i, n in enumerate(whites):
            x0 = i * kw
            d.rectangle((x0, top, x0 + kw - 1, top + kb_h),
                        fill=(ACCENT if n in active else (240, 240, 245)), outline=(40, 42, 52))
            wx[n] = i
        bw, bh = kw * 0.58, kb_h * 0.62                # black keys on top (realistic ~0.58 width)
        for n in range(lo, hi + 1):
            if n % 12 not in _WHITE_PCS and (n - 1) in wx:
                x0 = (wx[n - 1] + 1) * kw - bw / 2
                d.rectangle((x0, top, x0 + bw, top + bh),
                            fill=(ACCENT if n in active else (24, 24, 32)), outline=(40, 42, 52))
        if kbd and kbd.count:                          # readout under the strip: last note + total
            msg, col = f"{note_name(kbd.last)}   ·   {kbd.count} notes", FG
        else:
            msg, col = "press a key on your MIDI keyboard…", MUTED
        tw = d.textlength(msg, font=self.f_small)
        d.text((w / 2 - tw / 2, top + kb_h + 10), msg, font=self.f_small, fill=col)

    # ---- frame ----
    def render(self, screen, status):
        w, h = self.display.w, self.display.h
        img = Image.new("RGB", (w, h), BG)
        d = ImageDraw.Draw(img)
        m = screen
        # status / menu bar: back button (left) · title · pagination (right)
        d.rectangle((0, 0, w, self.BAR_H), fill=BARBG)
        cy = self.BAR_H // 2
        tx = 10
        back = self._back_rect(status.depth)
        if back:
            self._tri(d, 22, cy, 20, "left", ACCENT)   # back arrow = pager-triangle design, own colour (#289)
            d.line((back[2], 6, back[2], self.BAR_H - 6), fill=(64, 68, 86), width=1)
            tx = back[2] + 8
        elif status.depth == 1:                        # Home: settings cog in the left slot (#289)
            self._glyph(d, "settings", 24, cy, ACCENT)
            d.line((56, 6, 56, self.BAR_H - 6), fill=(64, 68, 86), width=1)
            tx = 56 + 8
        if status.depth == 1:                          # Home: status icons replace the "pisynth" title (#306)
            self._draw_status_icons(d, tx + 18, cy, status)
        else:
            d.text((tx, cy - 10), m.title, font=self.f_med, fill=FG)
        npages = m.npages()
        if npages > 1:                              # ◀ p/N ▶ — yellow triangles around the number (#276)
            num = f"{m.page + 1}/{npages}"
            nw = d.textlength(num, font=self.f_med)
            tw, gap, right = 16, 10, w - 12
            self._tri(d, right - tw / 2, cy, 20, "right", SEL_BORDER)
            d.text((right - tw - gap - nw, cy - 10), num, font=self.f_med, fill=FG)
            self._tri(d, right - tw - gap - nw - gap - tw / 2, cy, 20, "left", SEL_BORDER)
        if m.keyboard:
            self._draw_keyboard(d, status.kbd)
        elif m.tiles:
            self._draw_tiles(d, m, status.loading)
        else:
            self._draw_rows(d, m)
        if m.title == "Metronome":
            self._draw_beats(d, status)
        # toast (transient, #320) takes the bottom slot over the per-screen footer (e.g. BT);
        # plain centred text, no box (#320: david preferred 'juste le texte').
        label = status.toast or m.footer
        if label:
            fw = d.textlength(label, font=self.f_small)
            d.text((w / 2 - fw / 2, h - 18), label, font=self.f_small, fill=MUTED)
        self.display.blit(img)

    # ---- calibration screens (driven by app.calibrate / _verify_loop) ----
    def _draw_target(self, tx, ty, n, total):
        img = Image.new("RGB", (self.display.w, self.display.h), BG)
        d = ImageDraw.Draw(img)
        self._center_text(d, 20, "Touch calibration", self.f_big, ACCENT)
        self._center_text(d, 54, f"Tap the target  {n}/{total}", self.f_med)
        tx, ty, r = int(tx), int(ty), 16
        d.line((tx - r, ty, tx + r, ty), fill=ACCENT, width=2)
        d.line((tx, ty - r, tx, ty + r), fill=ACCENT, width=2)
        d.ellipse((tx - r, ty - r, tx + r, ty + r), outline=ACCENT, width=2)
        d.ellipse((tx - 3, ty - 3, tx + 3, ty + 3), fill=OK)
        self.display.blit(img)

    def _draw_verify(self, done, dot):
        img = Image.new("RGB", (self.display.w, self.display.h), BG)
        d = ImageDraw.Draw(img)
        self._center_text(d, 14, "Calibration check", self.f_med, ACCENT)
        self._center_text(d, 38, "Touch to test, then Done", self.f_small)
        d.rounded_rectangle(done, radius=8, fill=(50, 110, 70), outline=ACCENT)
        lab = "Done"
        tw = d.textlength(lab, font=self.f_med)
        d.text(((done[0] + done[2]) / 2 - tw / 2, (done[1] + done[3]) / 2 - 12), lab, font=self.f_med, fill=FG)
        if dot:
            x, y = dot
            d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(255, 80, 80), outline=FG)
            d.text((6, self.display.h - 20), f"({x}, {y})", font=self.f_small, fill=FG)
        self.display.blit(img)
