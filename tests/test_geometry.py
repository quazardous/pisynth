from pisynth.core.geometry import solve_affine


def _apply(c, x, y):
    a, b, cc, d, e, f = c
    return a * x + b * y + cc, d * x + e * y + f


def test_recovers_exact_affine():
    true = [0.12, -0.01, -20.0, 0.005, 0.09, -15.0]      # rotated/scaled raw ADS7846 → 480×320
    raws = [(400, 350), (3700, 380), (3650, 3600), (420, 3580)]
    screens = [_apply(true, *r) for r in raws]
    got = solve_affine(raws, screens)
    for raw, (sx, sy) in zip(raws, screens):
        gx, gy = _apply(got, *raw)
        assert abs(gx - sx) < 1e-6 and abs(gy - sy) < 1e-6
