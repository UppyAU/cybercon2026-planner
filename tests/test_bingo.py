"""Buzzword bingo: only on keynotes and featured talks, a real 5x5 card, every winning line counted, cards saved per talk."""

import re
from pathlib import Path

PAGE = (Path(__file__).resolve().parent.parent / "src" / "planner.html").read_text(encoding="utf-8")


def test_enough_unique_words_for_a_card():
    words = re.findall(r'"([^"]+)"', re.search(r"const BINGO_WORDS=\[(.*?)\];", PAGE, re.S).group(1))
    assert len(words) >= 40, "need plenty of words so cards differ between talks"
    assert len(set(w.replace("\\u00AD", "").lower() for w in words)) == len(words), "no duplicate words"


def test_twelve_winning_lines():
    lines = [[r * 5 + c for c in range(5)] for r in range(5)] + [[c * 5 + r for c in range(5)] for r in range(5)]
    lines += [[0, 6, 12, 18, 24], [4, 8, 12, 16, 20]]
    assert len(lines) == 12 and all(12 in l for l in (lines[2], lines[7], lines[10], lines[11]))
    assert "BG_LINES=[0,1,2,3,4].flatMap" in PAGE and "[[0,6,12,18,24],[4,8,12,16,20]]" in PAGE


def test_only_on_keynotes_and_featured_talks():
    assert 'const bingoFor=x=>!!x&&(x.format==="Keynote"||x.format==="Featured");' in PAGE


def test_card_saved_per_talk_and_free_centre():
    assert 'const KEY_BG="cybercon2026-bingo-v1";' in PAGE
    assert "c.splice(12,0,null)" in PAGE, "centre square is free"


def test_words_never_break_mid_word():
    assert "overflow-wrap:normal;hyphens:manual;" in PAGE