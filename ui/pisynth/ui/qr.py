"""QR code bitmap for the touch screen (#659), via `segno` (python3-segno, pure Python)."""
from PIL import Image


def qr_image(data, size):
    """A square black-on-white QR image of `data`, at most `size` px (whole modules, 2-module
    quiet zone). None when segno isn't installed."""
    try:
        import segno
    except ImportError:
        return None
    matrix = [list(row) for row in segno.make(data, error="m").matrix]
    n = len(matrix) + 4                                   # + quiet zone
    scale = max(1, size // n)
    img = Image.new("L", (n, n), 255)
    px = img.load()
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                px[x + 2, y + 2] = 0
    return img.resize((n * scale, n * scale), Image.NEAREST)
