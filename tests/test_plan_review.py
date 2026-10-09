"""Plan review fixes: cosmetic retitles aren't changes, unmapped rooms warn, stair labels fit phones, walks can be stepped through."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "src" / "planner.html").read_text(encoding="utf-8")
sys.path.insert(0, str(ROOT / "tools"))
import update_program  # noqa: E402


def test_capitalisation_only_retitles_are_not_changes():
    assert update_program.same_words("Terraforming the blast radius: building", "Terraforming the blast radius: Building")
    assert update_program.same_words("roadmap to 2030 : The", "roadmap to 2030: The")
    assert not update_program.same_words("Keynote with Sir Tim Berners-Lee", "In conversation with Sir Tim Berners-Lee")
    assert "c.kind===\"retitled\"&&sameWords(c.was,c.now)" in PAGE, "older cosmetic retitles in the data must be ignored too"


def test_unmapped_rooms_still_get_a_leave_by_time():
    assert re.search(r"const UNK_WALK=\d+;", PAGE)
    assert "isn't on MCEC's floor plans, so check signage" in PAGE
    assert "No walk estimate" not in PAGE


def test_stair_labels_have_a_short_phone_form():
    assert 'class="ps"' in PAGE and ".mx-stage .portal .pl{display:none}" in PAGE


def test_walks_can_be_stepped_through():
    for hook in ('data-act="mleg"', 't.dataset.act==="mleg"', 't.dataset.act==="mlegx"', "function walkLegs(", "function legBar("):
        assert hook in PAGE, hook