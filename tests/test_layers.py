"""The #308 layering, enforced: lower layers never import upper ones.
core ← io ← ui ← screens ← app   (core is pure logic, io wraps devices, ui draws)."""
import ast
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[1] / "ui" / "pisynth"

FORBIDDEN = {
    "core": {"io", "ui", "screens", "app"},
    "io": {"ui", "screens", "app"},
    "ui": {"io", "screens", "app"},
}


def _imported_layers(path, layer):
    """Top-level pisynth sub-packages imported by `path` (absolute or relative)."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.ImportFrom):
            if node.level == 0:
                parts = (node.module or "").split(".")
                if parts[0] == "pisynth" and len(parts) > 1:
                    found.add(parts[1])
            elif node.level == 1:            # from .x  → same layer
                continue
            else:                            # from ..x → pisynth.x
                if node.module:
                    found.add(node.module.split(".")[0])
                else:                        # from .. import x
                    found.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            for a in node.names:
                parts = a.name.split(".")
                if parts[0] == "pisynth" and len(parts) > 1:
                    found.add(parts[1])
    return found


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_no_upward_imports(layer):
    bad = []
    for path in sorted((PKG / layer).glob("*.py")):
        hits = _imported_layers(path, layer) & FORBIDDEN[layer]
        if hits:
            bad.append(f"{path.relative_to(PKG)} imports {sorted(hits)}")
    assert not bad, "layering violation:\n" + "\n".join(bad)
