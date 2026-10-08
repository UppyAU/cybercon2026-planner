"""Map route legs that share a corridor must be drawn side by side, never on top of each other."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PAGE = (Path(__file__).resolve().parent.parent / "src" / "planner.html").read_text(encoding="utf-8")


def _fn(name):
    m = re.search(rf"\nfunction {name}\(.*?\n\}}\n", PAGE, re.S)
    assert m, f"{name}() not found in src/planner.html"
    return m.group(0)


def _run(js):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    src = "const dist=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);\n" + _fn("laneOffsets") + _fn("laneLine") + js
    return json.loads(subprocess.run([node, "-e", src], capture_output=True, text=True, check=True).stdout)


def test_shared_corridor_legs_get_opposite_sides():
    # Leg A walks east along y=0; leg B walks back west over the same stretch, then turns north.
    out = _run("""
      const A=[[0,0],[100,0],[200,0]],B=[[200,0],[100,0],[100,-80]];
      const L=laneOffsets([A,B]),g=8,a=laneLine(A,L[0],g),b=laneLine(B,L[1],g);
      console.log(JSON.stringify({L,ay:a[a.length-1][1],by:b[0][1],solo:laneOffsets([A])}));""")
    assert out["L"][0][1] != 0 and out["L"][1][0] != 0, "the shared stretch must be split into lanes"
    assert out["ay"] * out["by"] < 0, "the two legs must sit on opposite sides of the corridor"
    assert abs(out["ay"] - out["by"]) >= 7, "lanes must be at least a line-width apart"
    assert out["solo"] == [[0, 0]], "a leg on its own stays on the corridor centre line"


def test_outlines_are_drawn_under_every_line():
    m = re.search(r"const segs=(.*?);\n", PAGE, re.S)
    assert m, "segs not found in src/planner.html"
    e = m.group(1)
    assert e.rindex('class="rt-bg') < e.index('class="rt '), "every outline must be drawn before any line"