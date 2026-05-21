"""UI theme (#308): colour palette, fonts, and the bundled icon font.

App-independent — the renderer/screens read their colours and fonts from here, so
a different skin/panel is a different theme.
"""
import os

from PIL import ImageFont

BG     = (18, 18, 24)
FG     = (235, 235, 240)
MUTED  = (120, 124, 140)
ACCENT = (90, 160, 255)
BARBG  = (34, 36, 48)
SELBG  = (44, 48, 66)
BTN    = (52, 56, 74)
OK     = (90, 200, 120)
ERR    = (220, 90, 90)
BT_BLUE = (0, 130, 252)                          # Bluetooth brand blue — lit BT icon (#306)
PINK    = (255, 92, 170)                          # metronome icon when running (#287)
AMBER   = (245, 175, 45)                          # health warning smiley (#325)
TILE_PALETTE = [
    (41, 128, 185), (142, 68, 173), (22, 160, 133), (211, 84, 0),
    (39, 174, 96), (192, 57, 43), (52, 73, 94), (199, 77, 135),
]
TILE_SETTINGS = (90, 98, 120)
TILE_MUTED    = (48, 50, 62)
SEL_BORDER = (245, 205, 50)     # yellow frame on the current font/preset tile (#276)
SEL_SUB    = (248, 232, 150)    # selected preset name shown under the font tile (#276)


def load_font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


# Bundled icon font (#306): an 11-glyph subset of Material Symbols Rounded (filled,
# Apache-2.0). Lives in the package's assets/ dir (one level up from this ui/ module).
ICON_FONT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "assets", "pisynth-icons.ttf")
ICON = {"settings": "\ue8b8", "wifi": "\ue63e", "bluetooth": "\ue1a7",
        "bluetooth_connected": "\ue1a8", "piano": "\ue521",
        "volume_up": "\ue050", "metronome": "\uf4ba", "synth": "\U000fffd8",
        "health_good": "\ue815", "health_warn": "\ue811", "health_crit": "\ue814",
        "pending": "\uef64"}                       # loading badge on a font tile (#334)


def load_icon_font(size):
    try:
        return ImageFont.truetype(ICON_FONT, size)
    except OSError:
        return None
