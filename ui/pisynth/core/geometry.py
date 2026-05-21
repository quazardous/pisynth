"""Calibration geometry: least-squares affine raw->screen (#308)."""
import numpy as np

def solve_affine(raws, screens):
    """Least-squares affine raw (rx,ry) -> screen (sx,sy)."""
    m = np.array([[rx, ry, 1.0] for rx, ry in raws])
    a = np.linalg.lstsq(m, np.array([s[0] for s in screens], float), rcond=None)[0]
    b = np.linalg.lstsq(m, np.array([s[1] for s in screens], float), rcond=None)[0]
    return [float(v) for v in (*a, *b)]
