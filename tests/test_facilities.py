"""Venue facilities (quiet room, prayer room) stay on the map, in the right place, with their guidance."""

import json
import re
from pathlib import Path

PAGE = (Path(__file__).resolve().parent.parent / "src" / "planner.html").read_text(encoding="utf-8")
FAC = re.search(r"const FACILITIES=\[(.*?)\n\];", PAGE, re.S).group(1)


def _inside(p, poly):
    hit = False
    for i, (x0, y0) in enumerate(poly):
        x1, y1 = poly[i - 1]
        if (y0 > p[1]) != (y1 > p[1]) and p[0] < (x1 - x0) * (p[1] - y0) / (y1 - y0) + x0:
            hit = not hit
    return hit


def test_quiet_room_is_room_215_on_level_2_with_its_rules():
    m = re.search(r'k:"quiet".*?m:"L2".*?pts:(\[\[.*?\]\]).*?txt:"(.*?)"', FAC, re.S)
    assert m, "quiet room must be on Level 2 with an outline"
    assert "Room 215" in FAC and "phone calls" in m.group(2) and "work" in m.group(2)
    pts = json.loads(m.group(1))
    centre = (sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts))
    assert _inside(centre, pts)


def test_prayer_room_is_on_the_ground_floor_near_goldfields():
    m = re.search(r'k:"prayer".*?m:"P".*?p:\[([\d.]+),([\d.]+)\].*?txt:"(.*?)"', FAC, re.S)
    assert m, "prayer room must be a ground-floor point"
    assert "Goldfields" in m.group(3) and "customer service" in m.group(3)
    plenary = json.loads(re.search(r'"Plenary Theatre":\["P",(\[\[.*?\]\])\]', PAGE).group(1))
    assert not _inside((float(m.group(1)), float(m.group(2))), plenary), "prayer room is behind the stage, not in the theatre"


def test_facilities_reachable_from_map_header_and_now_page():
    assert 'data-act="facgo"' in PAGE and 'a==="facgo"' not in PAGE  # handled via t.dataset.act
    assert 't.dataset.act==="facgo"' in PAGE and 't.dataset.act==="mfac"' in PAGE
    assert "Need a break?" in PAGE