"""Browse draws progressively; it must still show each day heading once and every matching session."""

import re
from pathlib import Path

PAGE = (Path(__file__).resolve().parent.parent / "src" / "planner.html").read_text(encoding="utf-8")


def test_day_heading_decided_when_grouping_not_when_drawing():
    body = re.search(r"\nfunction renderBrowse\(\)\{(.*?)\n\}", PAGE, re.S).group(1)
    assert "const head=d!==lastDay" in body, "the day heading must be decided before lastDay moves on"
    assert "${head?" in body and "d!==lastDay?" not in body


def test_patch_path_only_when_the_list_cannot_change():
    patch = re.search(r"\nfunction browsePatch\(x,gl\)\{(.*?)\n\}", PAGE, re.S).group(1)
    for guard in ("F.fits", "F.mine", "locked.size", "matches(x,gl)", "backups"):
        assert guard in patch, f"browsePatch must fall back to a full render when {guard} is involved"


def test_print_draws_the_whole_list():
    assert 'addEventListener("beforeprint"' in PAGE