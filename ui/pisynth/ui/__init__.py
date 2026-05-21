"""ui — presentation toolkit (#308): theme (palette/fonts) + menu SDK + renderer.

App-independent presentation layer. `theme` (palette/fonts), the `menu` model
(MenuScreen/Item), and the `Renderer` (draw + geometry + the matching hit-testing
helpers) together form the portable "display SDK": the App controller passes a screen
model + a `Status` snapshot and the Renderer turns it into pixels on any Display.
"""
from .menu import Item, MenuScreen, PAGE_TILES_OPTIONS
from .renderer import Renderer, Status

__all__ = ["Item", "MenuScreen", "PAGE_TILES_OPTIONS", "Renderer", "Status"]
