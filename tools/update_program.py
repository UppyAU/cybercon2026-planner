"""Re-download the official CyberCon 2026 program and record what changed since the last snapshot.

    python tools/update_program.py                    fetch, compare, then update data/
    python tools/update_program.py --check            fetch and compare only (writes nothing)
    python tools/update_program.py --private DIR      also refresh DIR/abstracts.json (private repo)

Writes session facts (titles, times, rooms, speakers, themes, links) plus search keywords to data/program.json.
Abstracts are AISA's text, so they are never written to this repo; pass --private to store them in the private repo.
Sessions are matched by their official page slug. Moved rooms, new times, renamed, new and cancelled sessions go
to data/program-changes.json, which the planner flags in Browse, My plan and Now. Cancelled sessions stay in the
data (marked cancelled) so plans that include them can show what happened.
"""
import argparse, datetime, html, json, os, re, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROGRAM = ROOT / "data" / "program.json"
HISTORY = ROOT / "data" / "program-changes.json"
META = ROOT / "data" / "meta.json"
BASE = "https://melbourne2026.cyberconference.com.au/program"
ITEM = 'role="listitem" class="sessions_card-item w-dyn-item"'
UA = "CyberCon2026-unofficial-planner/1.0 (https://github.com/UppyAU/cybercon2026-planner)"

STOP = set("""a about above across after again against all almost along also although always am among an and
another any anyone anything are around as at away back be became because become becomes been before being
below between both but by can cannot could did do does doing done down during each either else enough even
ever every few for from further get gets getting give given go going got had has have having he her here hers
him his how however i if in into is it its itself just keep last least less let like made make makes making
many may me might more most much must my need needs never new next no not now of off often on once one only
onto or other others our ours out over own part per put rather really same see seen several she should show
shows since so some something still such take takes than that the their theirs them themselves then there
these they thing things this those though through throughout thus to today together too toward towards under
until up upon us use used uses using very via was way ways we well were what when where whether which while
who whom whose why will with within without would yet you your yours session talk explore explores explored
discuss discusses learn look looks share shares sharing set sets put puts real""".split())
SHORT_KEEP = {"ai", "ot", "ir", "ics", "iam", "pam", "soc", "edr", "xdr", "llm", "5g", "iot", "api", "sbom", "cve", "dns", "mfa", "ciso"}


def keywords(text):
    words = set()
    for w in re.findall(r"[a-z0-9][a-z0-9'+\-]*", text.lower()):
        w = w.strip("'-").replace("'s", "")
        if not w or w in STOP or w.isdigit():
            continue
        if len(w) < 3 and w not in SHORT_KEEP:
            continue
        words.add(w)
    return " ".join(sorted(words))


def fetch(page):
    url = BASE + (f"?f42ef429_page={page}" if page > 1 else "")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def clean(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def values(block, name):
    pat = r'<(\w+)\b[^>]*\bfs-list-field="%s"[^>]*>(.*?)</\1>' % re.escape(name)
    return [v for v in (clean(m.group(2)) for m in re.finditer(pat, block, re.S)) if v]


def parse(page_html):
    out = []
    for block in page_html.split(ITEM)[1:]:
        one = lambda n: (values(block, n) or [""])[0]
        href = re.search(r'href="(/sessions/[^"]+)"', block)
        spk = one("speakers")
        out.append({
            "title": one("title"), "format": one("format"), "day": one("day"), "start": one("start"),
            "finish": one("finish"), "location": one("location"),
            "speakers": [spk] if spk else [],
            "summary": one("summary"), "theme": sorted(set(values(block, "theme"))), "topic": sorted(set(values(block, "topic"))),
            "audience": one("audience"), "sponsor": one("sponsor"), "sortkey": one("date"),
            "url": "https://melbourne2026.cyberconference.com.au" + href.group(1) if href else "",
        })
    return out


def scrape():
    sessions, page = [], 1
    while page <= 40:
        items = parse(fetch(page))
        if not items:
            break
        sessions += items
        print(f"  page {page}: {len(items)} sessions", flush=True)
        page += 1
        time.sleep(0.6)
    return sessions


def key(r):
    return r["url"].rstrip("/").rsplit("/", 1)[-1] if r.get("url") else None


def same_words(a, b):
    """True when two titles differ only in capitalisation, spacing or punctuation."""
    norm = lambda t: re.sub(r"[\W_]+", "", t.casefold())
    return norm(a) == norm(b)


def diff(old, new, stamp):
    oldk = {key(r): r for r in old if key(r)}
    newk = {key(r): r for r in new if key(r)}
    changes = []
    when = lambda r: f'{r["day"]} {r["start"]}–{r["finish"]}'
    for k, r in newk.items():
        o = oldk.get(k)
        if o is None or o.get("cancelled"):
            changes.append({"id": k, "kind": "new", "was": "", "now": r["title"]})
            continue
        if o["location"] != r["location"]:
            changes.append({"id": k, "kind": "moved", "was": o["location"], "now": r["location"]})
        if (o["day"], o["start"], o["finish"]) != (r["day"], r["start"], r["finish"]):
            changes.append({"id": k, "kind": "time", "was": when(o), "now": when(r)})
        if o["title"] != r["title"] and not same_words(o["title"], r["title"]):
            changes.append({"id": k, "kind": "retitled", "was": o["title"], "now": r["title"]})
    gone = [o for k, o in oldk.items() if k not in newk]
    for o in gone:
        if not o.get("cancelled"):
            changes.append({"id": key(o), "kind": "cancelled", "was": when(o), "now": ""})
    for c in changes:
        c["date"] = stamp
    return changes, [dict(o, cancelled=True) for o in gone]


def main():
    ap = argparse.ArgumentParser(description="Refresh the CyberCon 2026 program data.")
    ap.add_argument("--check", action="store_true", help="compare only, write nothing")
    ap.add_argument("--private", default=os.environ.get("CYBERCON_PRIVATE"), help="private data directory for abstracts.json")
    a = ap.parse_args()
    stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=11))).strftime("%-d %b %Y" if sys.platform != "win32" else "%#d %b %Y")
    old = json.loads(PROGRAM.read_text(encoding="utf-8"))
    print("Fetching the official program…")
    new = scrape()
    if len(new) < 0.8 * len([r for r in old if not r.get("cancelled")]):
        sys.exit(f"Only {len(new)} sessions found (had {len(old)}). The site layout may have changed; nothing written.")
    changes, cancelled = diff(old, new, stamp)
    print(f"\n{len(new)} sessions online, {len(changes)} change(s) since the last snapshot:")
    for c in changes:
        print(f"  {c['kind']:9} {c['id']}  {c['was']!s:30} -> {c['now']}")
    if a.check:
        return
    abstracts = {key(r): r["summary"] for r in new if key(r) and r.get("summary")}
    for r in new:
        r["kw"] = keywords(r.get("summary") or "")
        r["summary"] = ""
    merged = new + cancelled
    PROGRAM.write_text(json.dumps(merged, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    # Keep the latest record per session and kind; a reinstated session clears its "cancelled" flag.
    for c in changes:
        history = [h for h in history if not (h["id"] == c["id"] and (h["kind"] == c["kind"] or (c["kind"] == "new" and h["kind"] == "cancelled")))]
        history.append(c)
    HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    META.write_text(json.dumps({"scraped": stamp}, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"\nUpdated data/ (snapshot {stamp}).")
    if a.private:
        p = Path(a.private) / "abstracts.json"
        prev = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        prev.update(abstracts)  # keep abstracts of cancelled sessions
        p.write_text(json.dumps(prev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"Updated {p} ({len(abstracts)} abstracts).")
    else:
        print("Abstracts not saved (no --private directory); the full editions keep their previous abstracts.")
    print("Next: commit data/ here (and abstracts.json in the private repo), then run tools/build.py.")


if __name__ == "__main__":
    main()
