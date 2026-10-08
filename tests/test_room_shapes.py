"""Room outlines on the venue map: every mapped room has a sane outline and its number lands inside it."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "src" / "planner.html").read_text(encoding="utf-8")
SHAPES = json.loads(re.search(r"const SHAPES=(\{.*?\n\});", PAGE, re.S).group(1))
ROOMS_WITH_SPOT = set(re.findall(r'"([^"]+)":\{lv:"L[12]",cap:\d+,p:\[', PAGE))
LOCATIONS = {x["location"] for x in json.loads((ROOT / "data" / "program.json").read_text(encoding="utf-8"))}


def _centroid(pts):
    a = x = y = 0.0
    for i, (x0, y0) in enumerate(pts):
        x1, y1 = pts[(i + 1) % len(pts)]
        c = x0 * y1 - x1 * y0
        a, x, y = a + c, x + (x0 + x1) * c, y + (y0 + y1) * c
    return x / (3 * a), y / (3 * a)


def _inside(pt, pts):
    px, py, hit = pt[0], pt[1], False
    for i, (x0, y0) in enumerate(pts):
        x1, y1 = pts[i - 1]
        if (y0 > py) != (y1 > py) and px < (x1 - x0) * (py - y0) / (y1 - y0) + x0:
            hit = not hit
    return hit


def test_every_level_room_in_the_program_has_an_outline():
    missing = sorted(r for r in ROOMS_WITH_SPOT if r in LOCATIONS and r not in SHAPES)
    assert not missing, f"rooms with sessions but no outline: {missing}"
    for loc in ("Plenary Theatre", "Exhibition Hall"):
        assert loc in SHAPES


def test_outlines_are_valid_and_numbers_land_inside():
    for loc, (floor, pts) in SHAPES.items():
        assert floor in ("P", "L1", "L2"), loc
        assert len(pts) >= 3 and all(0 <= v <= 100 for q in pts for v in q), loc
        assert _inside(_centroid(pts), pts), f"{loc}: its number would sit outside the room"


def test_exhibition_hall_is_marked_approximate():
    assert re.search(r'const APPROX=new Set\(\["Exhibition Hall"\]\)', PAGE)
    assert "doesn't say which bays" in PAGE