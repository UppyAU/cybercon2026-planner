"""Keyword hiding (#7) must stay safe: whole words only, and never hide what you've planned."""

import re
from pathlib import Path

PAGE = (Path(__file__).resolve().parent.parent / "src" / "planner.html").read_text(encoding="utf-8")


def _fn(name):
    # A declaration runs until the next top-level const/let/function (some span several lines).
    m = re.search(rf"\nconst {name}=(.*?)\n(?=const |let |function )", PAGE, re.S)
    assert m, f"{name} not found in src/planner.html"
    return m.group(1)


def test_matching_is_whole_word_and_unicode_aware():
    rx = _fn("muteRx")
    assert "(?<![\\\\p{L}\\\\p{N}])" in rx, "keywords must not match inside words (e.g. 'ai' in 'maintain')"
    assert '"iu"' in rx, "keyword matching must be case-insensitive and Unicode-aware"
    assert "replace(/[.*+?^${}()|[\\]\\\\]/g" in rx, "keywords must be regex-escaped before matching"


def test_planned_sessions_and_breaks_are_never_hidden():
    hit = _fn("muteHit")
    for guard in ("x.logi", "isBrk(x)", "plan[x.id]", "backupOf(x.id)"):
        assert guard in hit, f"muteHit() must keep {guard} sessions visible"


def test_keywords_travel_with_backups_and_transfers():
    assert "KEY_M," in re.search(r"const XFER_KEYS=\(\)=>\[(.*?)\]", PAGE).group(1) + ","
    assert re.search(r"JSON\.stringify\(\{version:\d+,[^}]*\bmute\b", PAGE), "backups must include mute keywords"
