"""The native app (mobile/) reaches into src/planner.html: it calls page functions, reads page variables,
clicks page elements and exchanges messages. Renaming any of those in the page would break the app without
breaking the website, so this test pins the contract.

Each entry says what mobile/ relies on and what the page must provide. A failure means one of:
  * the page renamed or removed something the app uses: put it back, or update mobile/ in the same PR;
  * mobile/ stopped using something: delete that entry from CONTRACT.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "src" / "planner.html").read_text(encoding="utf-8")
MOBILE = {
    p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8")
    for p in sorted((ROOT / "mobile").rglob("*.js"))
    if "node_modules" not in p.parts
}

# (what, regex that finds the use in mobile/, regex the page must match)
CONTRACT = [
    # Page globals the injected bridge script calls or reads (mobile/src/bridge.js).
    ("function nativeSync", r"\bnativeSync\b", r"\bfunction nativeSync\("),
    ("function goList", r"\bgoList\(", r"\bconst goList="),
    ("function walkMin", r"\bwalkMin\(", r"\bfunction walkMin\("),
    ("function download", r"\bwindow\.download\b", r"\bfunction download\(name,type,text\)"),
    ("function xferReceive", r"\bxferReceive\(", r"\bfunction xferReceive\("),
    ("variable DAYS", r"\bDAYS\[", r"\bconst DAYS="),
    ("variable PV", r"\bPV\b", r"\blet PV="),
    ("variable remindMin", r"\bremindMin\b", r"\blet remindMin="),
    # Page elements the app clicks, restyles or hides.
    ('element [data-act="xrecv"]', r'data-act="xrecv"', r'data-act="xrecv"'),
    ('element [data-act="print"]', r'data-act="print"', r'data-act="print"'),
    ("element #tabNow", r'getElementById\("tabNow"\)', r'id="tabNow"'),
    ("element #mbar", r"#mbar\b", r'id="mbar"'),
    ("element details.more", r"details\.more", r'<details class="more'),
    ("CSS variable --bg", r"var\(--bg\)", r"--bg:"),
    # Messages the page posts to the app (mobile/App.js onMessage).
    ("message cc26-plan", r"'cc26-plan'", r'type:"cc26-plan",v:1'),
    ("message cc26-file", r"'cc26-file'", r'type:"cc26-file"'),
    # Transfer links the app scans or pastes (mobile/App.js, page xferCodeIn).
    ("transfer link #x=", r"#x=", r'"#x="'),
]


def _uses(pattern):
    return [name for name, src in MOBILE.items() if re.search(pattern, src)]


@pytest.mark.parametrize(("what", "in_mobile", "in_page"), CONTRACT, ids=[c[0] for c in CONTRACT])
def test_page_provides_what_the_app_uses(what, in_mobile, in_page):
    assert _uses(in_mobile), f"mobile/ no longer uses {what}; remove it from CONTRACT"
    assert re.search(in_page, PAGE), f"src/planner.html no longer provides {what}, which {', '.join(_uses(in_mobile))} relies on"


def test_page_globals_stay_reachable():
    # The bridge reaches page names as globals, which a module script or a wrapper function would hide.
    scripts = re.findall(r"<script\b[^>]*>", PAGE)
    assert scripts == ["<script>"], f"expected one classic <script>, found {scripts}"


def test_user_agent_tag_matches():
    tag = re.search(r"USER_AGENT_TAG\s*=\s*'([^']+)'", MOBILE["mobile/App.js"]).group(1)
    page_rx = re.search(r"function nativeApp\(\)\{return /(.+?)/\.test\(navigator\.userAgent\)", PAGE).group(1)
    ua = f"Mozilla/5.0 (Linux; Android 17) AppleWebKit/537.36 Chrome/150.0 Mobile Safari/537.36 {tag}"
    assert re.search(page_rx.replace("\\/", "/"), ua), f"the page's nativeApp() pattern /{page_rx}/ doesn't match the app's user agent tag {tag!r}"
    assert not re.search(page_rx.replace("\\/", "/"), ua.replace(tag, "SomeOtherApp/1")), "nativeApp() must not match other in-app browsers"


def test_plan_message_has_the_fields_the_app_reads():
    body = re.search(r"function nativeSync\(\)\{(.*?)\n\}", PAGE, re.S).group(1)
    for field in ("remind:", "sessions", "id:", "title:", "loc:", "start:", "end:", "from", "walk:"):
        assert field in body, f"nativeSync() no longer sends {field.rstrip(':')}, which mobile/src/reminders.js reads"
