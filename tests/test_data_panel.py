"""The plan menu stays short: data actions live in the Save & move your plan panel, and none get lost."""

import re
from pathlib import Path

PAGE = (Path(__file__).resolve().parent.parent / "src" / "planner.html").read_text(encoding="utf-8")
PANEL_ACTS = ("xsend", "xrecv", "backup", "restore", "csv", "clear")


def _plan_menu():
    m = re.search(r'<details class="more"><summary class="btn" title="More actions">.*?</details>', PAGE, re.S)
    assert m, "My plan's More menu not found"
    return m.group(0)


def _panel():
    m = re.search(r"\nfunction xferData\(\)\{(.*?)\n\}", PAGE, re.S)
    assert m, "xferData() not found in src/planner.html"
    return m.group(1)


def test_menu_opens_the_panel_and_keeps_only_everyday_actions():
    menu = _plan_menu()
    assert 'data-act="xdata"' in menu
    for act in ("pcollapse", "lockall", "unlockall", "print"):
        assert f'data-act="{act}"' in menu, f"{act} should stay in the More menu"
    for act in PANEL_ACTS + ("fb",):
        assert f'data-act="{act}"' not in menu, f"{act} belongs in the panel (or the header), not the More menu"


def test_every_data_action_is_in_the_panel_and_handled():
    panel = _panel()
    assert 'el.id="xfer"' in panel, "the panel must reuse #xfer so Esc, backdrop and xferClose() apply"
    for act in PANEL_ACTS:
        assert f'data-act="{act}"' in panel, f"{act} is missing from the Save & move panel"
        assert f'a==="{act}"' in PAGE, f"no click handler for {act}"
    assert 'a==="xdata"' in PAGE


def test_feedback_is_still_reachable():
    assert PAGE.count('data-act="fb" data-t="bug"') >= 2 and 'data-act="fb" data-t="idea"' in PAGE