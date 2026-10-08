"""Walking routes must follow corridors: no leg cuts through a room, and every door sits on its room's wall."""

import json
import math
import re
from pathlib import Path

PAGE = (Path(__file__).resolve().parent.parent / "src" / "planner.html").read_text(encoding="utf-8")
SHAPES = {k: v for k, v in json.loads(re.search(r"const SHAPES=(\{.*?\n\});", PAGE, re.S).group(1)).items()
          if k != "Melbourne Room"}
DOORS = {k: (float(a), float(b)) for k, a, b in
         re.findall(r'"([^"]+)":\[([\d.]+),([\d.]+)\]', re.search(r"const DOORS=\{(.*?)\};", PAGE, re.S).group(1))}
NAV_SRC = re.search(r"const NAV=\{(.*?)\n\};", PAGE, re.S).group(1)


def _nav(floor):
    m = re.search(floor + r':\{n:\{(.*?)\},\s*e:"(.*?)"', NAV_SRC, re.S)
    nodes = {k: (float(a), float(b)) for k, a, b in re.findall(r"(\w+):\[([\d.]+),([\d.]+)\]", m.group(1))}
    return nodes, [e.split("-") for e in m.group(2).split()]


def _inside(p, poly):
    hit = False
    for i, (x0, y0) in enumerate(poly):
        x1, y1 = poly[i - 1]
        if (y0 > p[1]) != (y1 > p[1]) and p[0] < (x1 - x0) * (p[1] - y0) / (y1 - y0) + x0:
            hit = not hit
    return hit


def _edge_dist(p, poly):
    best = math.inf
    for i in range(len(poly)):
        (ax, ay), (bx, by) = poly[i - 1], poly[i]
        dx, dy = bx - ax, by - ay
        t = max(0, min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy or 1)))
        best = min(best, math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy))
    return best


def test_every_door_is_on_its_room_wall():
    for room, door in DOORS.items():
        if room in SHAPES:
            assert _edge_dist(door, SHAPES[room][1]) < 0.15, f"{room}: door is off the room's wall"


def test_no_corridor_cuts_through_a_room():
    for floor in ("P", "L1", "L2"):
        nodes, edges = _nav(floor)
        for a, b in edges:
            assert a in nodes and b in nodes, f"{floor}: edge {a}-{b} uses an unknown point"
            (ax, ay), (bx, by) = nodes[a], nodes[b]
            for i in range(1, 60):
                q = (ax + (bx - ax) * i / 60, ay + (by - ay) * i / 60)
                for room, (f, poly) in SHAPES.items():
                    near_door = room in DOORS and math.dist(q, DOORS[room]) < 1.2
                    assert f != floor or near_door or not _inside(q, poly), f"{floor} {a}-{b} cuts through {room}"


def test_stairs_exist_on_every_floor():
    for floor in ("P", "L1", "L2"):
        nodes, _ = _nav(floor)
        assert {"s1", "s2", "s3"} <= nodes.keys()