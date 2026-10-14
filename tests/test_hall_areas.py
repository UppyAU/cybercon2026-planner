"""CyberCon areas in the Exhibition Hall sit inside the hall, in order along the Bay 18/19 wall, and don't overlap when named."""

import json
import re
from pathlib import Path

PAGE = (Path(__file__).resolve().parent.parent / "src" / "planner.html").read_text(encoding="utf-8")
AREAS = re.findall(r'\{k:"(\w+)",ic:"\w+",t:"([^"]+)",m:"P",p:\[([\d.]+),([\d.]+)\]', re.search(r"const AREAS=\[(.*?)\n\];", PAGE, re.S).group(1))
HALL_AREAS = [a for a in AREAS if not re.fullmatch(r"tt\d", a[0])]
THINK_TANKS = [a for a in AREAS if re.fullmatch(r"tt\d", a[0])]
HALL = json.loads(re.search(r'"Exhibition Hall":\["P",(\[\[.*?\]\])\]', PAGE).group(1))
THEATRE = json.loads(re.search(r'"Plenary Theatre":\["P",(\[\[.*?\]\])\]', PAGE).group(1))


def _inside(p, poly):
    hit = False
    for i, (x0, y0) in enumerate(poly):
        x1, y1 = poly[i - 1]
        if (y0 > p[1]) != (y1 > p[1]) and p[0] < (x1 - x0) * (p[1] - y0) / (y1 - y0) + x0:
            hit = not hit
    return hit


def test_four_areas_inside_the_hall_in_order():
    assert [a[0] for a in HALL_AREAS] == ["careers", "lego", "khub", "podcast"]
    pts = [(float(x), float(y)) for _, _, x, y in HALL_AREAS]
    assert all(_inside(p, HALL) for p in pts)
    assert all(a[1] < b[1] for a, b in zip(pts, pts[1:])), "from the concourse end towards Kiosk 5"


def test_think_tanks_in_the_plenary_foyer_from_the_cafe_end():
    assert [a[1] for a in THINK_TANKS] == ["Think Tank 1", "Think Tank 2", "Think Tank 3", "Think Tank 4"]
    pts = [(float(x), float(y)) for _, _, x, y in THINK_TANKS]
    assert not any(_inside(p, THEATRE) or _inside(p, HALL) for p in pts), "they're in the foyer, not the theatre or hall"
    assert all(a[0] > b[0] for a, b in zip(pts, pts[1:])), "Think Tank 1 is nearest the Plenary Cafe (east), 4 by Stair 1 (west)"
    for n in range(1, 5):
        assert f"t{n}:[" in PAGE, f"Think Tank {n} needs a walkway point"


def test_names_only_when_spread_out():
    assert 'st.classList.toggle("zin",areaGap()*MX.k>=28)' in PAGE
    assert ".mx-stage:not(.zin) .mk2.area span{display:none}" in PAGE