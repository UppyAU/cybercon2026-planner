"""Build the unofficial CyberCon 2026 Planner.

    python tools/build.py                   public edition only          -> dist/public/
    python tools/build.py --private DIR     plus the full editions       -> dist/private/, dist/cybercon2026-planner.html
    python tools/build.py --check           fail if private content has crept into this public repo

public    Anyone, no sign-in. No abstracts (search keywords + links to the official session pages instead);
          MCEC floor plans load from MCEC's published guide rather than being re-hosted.
private   Full planner for invited users with the "planner" role (Azure Static Web Apps auth).
offline   cybercon2026-planner.html: the full planner as one file to open straight from disk.

DIR (or the CYBERCON_PRIVATE environment variable) holds content that is not ours to publish:
    abstracts.json          {"<session slug>": "<abstract>"}
    floorplans/P.jpg, L1.jpg, L2.jpg
Needs Pillow for the app icons.
"""
import argparse, base64, hashlib, json, os, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "src" / "planner.html"
DATA = ROOT / "data"
ROLE = "planner"
REPO_URL = "https://github.com/UppyAU/cybercon2026-planner"

# MCEC "Floor Plans and Space Capacities" guide on Issuu (pages 3, 6, 7). Each entry places the
# full page image so the crop the map was traced on lines up with the stage (stage px).
ISSUU = "https://svg.issuu.com/260820021006-6a110cdf75a8bb0877f5b16a09c4eaeb/page_{}.svg"
REMOTE_FLOORS = {
    "P":  {"url": ISSUU.format(3), "pw": 1772.85, "ph": 1253.1, "x": 88.64, "y": 84.21},
    "L1": {"url": ISSUU.format(6), "pw": 2382, "ph": 1684, "x": 1191, "y": 1078},
    "L2": {"url": ISSUU.format(7), "pw": 2382, "ph": 1684, "x": 119, "y": 1020},
}
PLACEHOLDER = re.compile(r'/\*@([A-Z0-9_]+)@\*/(\[\]|""|null|"dev")')


def js(v):
    return json.dumps(v, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def fill(tpl, values):
    found = {m.group(1) for m in PLACEHOLDER.finditer(tpl)}
    assert found == set(values), f"placeholders {sorted(found)} != {sorted(values)}"
    return PLACEHOLDER.sub(lambda m: values[m.group(1)], tpl)


def replace_once(s, old, new):
    assert s.count(old) == 1, f"expected one match for {old[:60]!r}, found {s.count(old)}"
    return s.replace(old, new)


def slug(r):
    return r["url"].rstrip("/").rsplit("/", 1)[-1] if r.get("url") else None


def build_id():
    if os.environ.get("BUILD_ID"):
        return os.environ["BUILD_ID"][:12]
    try:
        sha = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", "src", "data", "tools"], capture_output=True, text=True).stdout.strip()
        return sha + ("+dev" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "local"


def check_public():
    """Guard against committing content that only the private repo may hold."""
    problems = []
    for r in json.loads((DATA / "program.json").read_text(encoding="utf-8")):
        if r.get("summary"):
            problems.append(f"data/program.json has an abstract for {slug(r) or r['title']!r}")
            break
    for p in ROOT.rglob("*"):
        rel = p.relative_to(ROOT).as_posix()
        if not p.is_file() or rel.split("/")[0] in {".git", "dist", ".venv", "private"} or "__pycache__" in rel:
            continue
        # mobile/: installed packages and generated native projects/icons (all gitignored there).
        if (rel.split("/")[:2] in (["mobile", "node_modules"], ["mobile", "android"], ["mobile", "ios"], ["mobile", ".expo"])
                or rel.startswith("mobile/assets/generated/") or re.match(r"mobile/modules/[^/]+/android/build/", rel)):
            continue
        if p.name == "abstracts.json" or p.suffix.lower() in {".jpg", ".jpeg", ".png", ".pdf"}:
            problems.append(f"{rel}: private or binary content does not belong in this repo")
        elif p.suffix.lower() in {".html", ".js", ".json", ".py", ".md", ".css", ".yml", ".yaml", ".txt"}:
            if re.search(r"data:image/(jpeg|png);base64,[A-Za-z0-9+/]{200}", p.read_text(encoding="utf-8", errors="ignore")):
                problems.append(f"{rel}: contains an embedded image")
    for msg in problems:
        print("CHECK FAILED:", msg)
    return not problems


def load():
    tpl = TEMPLATE.read_text(encoding="utf-8")
    sessions = json.loads((DATA / "program.json").read_text(encoding="utf-8"))
    changes = json.loads((DATA / "program-changes.json").read_text(encoding="utf-8"))
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
    return tpl, sessions, changes, meta


def render(tpl, sessions, changes, meta, bid, images=None):
    vals = {"RAW": js(sessions), "SCRAPED": js(meta["scraped"]), "CHANGES": js(changes), "BUILD": js(bid)}
    if images:
        vals.update({f"IMG_{k}": js(v) for k, v in images.items()}, REMOTE_FLOORS="null")
    else:
        vals.update({"IMG_P": '""', "IMG_L1": '""', "IMG_L2": '""', "REMOTE_FLOORS": js(REMOTE_FLOORS)})
    return fill(tpl, vals)


def private_inputs(pdir, sessions):
    pdir = Path(pdir)
    ab = json.loads((pdir / "abstracts.json").read_text(encoding="utf-8"))
    full = [dict(r, summary=ab.get(slug(r) or "", r.get("summary", ""))) for r in sessions]
    images = {k: "data:image/jpeg;base64," + base64.b64encode((pdir / "floorplans" / f"{k}.jpg").read_bytes()).decode() for k in ("P", "L1", "L2")}
    return full, images, sum(1 for r in full if r["summary"])


def add_shell(html, edition):
    cred = ' crossorigin="use-credentials"' if edition == "private" else ""
    head = (f'<link rel="manifest" href="/manifest.webmanifest"{cred}>\n'
            '<link rel="icon" type="image/png" href="/icons/icon-192.png">\n'
            '<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">\n'
            '<meta name="description" content="Unofficial attendee planner for CyberCon 2026 (Melbourne, 14-16 Oct 2026). Not affiliated with AISA.">\n')
    if edition == "private":
        head += '<meta name="robots" content="noindex,nofollow">\n'
    html = replace_once(html, "</title>\n", "</title>\n" + head)
    me = 'Built by <a href="https://github.com/UppyAU" target="_blank" rel="noopener">@UppyAU</a>'
    src = f'<a href="{REPO_URL}" target="_blank" rel="noopener">Source &amp; feedback on GitHub</a>'
    if edition == "public":
        credit = ("Unofficial attendee planner, not affiliated with or endorsed by AISA, CyberCon or MCEC. Session times, rooms and speakers come from the "
                  '<a href="https://melbourne2026.cyberconference.com.au/program" target="_blank" rel="noopener">official program</a> (&copy; AISA), '
                  "where the full abstracts are. Floor plans &copy; MCEC, shown from MCEC's published "
                  '<a href="https://www.mcec.com.au/event-planning-resources/floor-plans-and-space-capacities" target="_blank" rel="noopener">Floor Plans and Space Capacities guide</a>. '
                  f"Your plan is stored only in this browser. {me} · {src}.")
    else:
        credit = f"Private copy for personal use. Program content &copy; AISA; floor plans &copy; MCEC. Your plan is stored only in this browser. {me} · {src}."
    html = replace_once(html, "</main>\n", f'</main>\n<footer class="credits noprint">{credit}</footer>\n')
    reg = '\nif("serviceWorker" in navigator&&/^https?:$/.test(location.protocol))navigator.serviceWorker.register("/sw.js").catch(()=>{});\n</script>'
    return replace_once(html, "loadShared();buildFilters();render();\n</script>", "loadShared();buildFilters();render();" + reg)


def script_hash(html):
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    assert len(scripts) == 1, len(scripts)
    return "'sha256-" + base64.b64encode(hashlib.sha256(scripts[0].encode("utf-8")).digest()).decode() + "'"


def csp(html, edition):
    img = "'self' data: blob:" + (" https://svg.issuu.com" if edition == "public" else "")
    connect = "'self'" + (" https://svg.issuu.com" if edition == "public" else "")
    return "; ".join([
        "default-src 'none'", f"script-src 'self' {script_hash(html)}", "style-src 'unsafe-inline'",
        f"img-src {img}", f"connect-src {connect}", "manifest-src 'self'", "worker-src 'self'",
        "base-uri 'none'", "form-action 'none'", "frame-ancestors 'none'", "object-src 'none'"])


def swa_config(html, edition):
    nocache = {"Cache-Control": "no-cache"}
    icons = {"Cache-Control": "public, max-age=604800"}
    headers = {
        "Content-Security-Policy": csp(html, edition),
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        "Strict-Transport-Security": "max-age=31536000",
        "Cross-Origin-Opener-Policy": "same-origin",
    }
    cfg = {
        "navigationFallback": {"rewrite": "/index.html", "exclude": ["/icons/*", "/*.{webmanifest,js,json,png,svg,ico,html}"]},
        "mimeTypes": {".webmanifest": "application/manifest+json"},
        "globalHeaders": headers,
    }
    if edition == "public":
        cfg["routes"] = [
            {"route": "/.auth/login/aad", "statusCode": 404},
            {"route": "/.auth/login/github", "statusCode": 404},
            {"route": "/.auth/login/twitter", "statusCode": 404},
            {"route": "/sw.js", "headers": nocache},
            {"route": "/icons/*", "headers": icons},
            {"route": "/*", "headers": nocache},
        ]
    else:
        headers["X-Robots-Tag"] = "noindex, nofollow"
        cfg["routes"] = [
            {"route": "/.auth/login/github", "statusCode": 404},
            {"route": "/.auth/login/twitter", "statusCode": 404},
            {"route": "/forbidden.html", "allowedRoles": ["anonymous"], "headers": nocache},
            {"route": "/manifest.webmanifest", "allowedRoles": ["anonymous"]},
            {"route": "/icons/*", "allowedRoles": ["anonymous"], "headers": icons},
            {"route": "/sw.js", "allowedRoles": [ROLE], "headers": nocache},
            {"route": "/*", "allowedRoles": [ROLE], "headers": nocache},
        ]
        cfg["responseOverrides"] = {
            "401": {"redirect": "/.auth/login/aad?post_login_redirect_uri=.referrer", "statusCode": 302},
            "403": {"rewrite": "/forbidden.html"},
        }
    return cfg


SW = r"""// CyberCon planner offline cache. Version changes with every build so stale copies are dropped.
const V = "cc26-__VER__";
const SHELL = ["/", "/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png", "/icons/apple-touch-icon.png"];
const REMOTE = __REMOTE__;
self.addEventListener("install", e => e.waitUntil((async () => {
  const c = await caches.open(V);
  await c.addAll(SHELL);
  await Promise.all(REMOTE.map(u => fetch(u, {mode: "cors", credentials: "omit"}).then(r => r.ok && c.put(u, r)).catch(() => {})));
  await self.skipWaiting();
})()));
self.addEventListener("activate", e => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k !== V) await caches.delete(k);
  await self.clients.claim();
})()));
self.addEventListener("fetch", e => {
  const req = e.request, u = new URL(req.url);
  if (req.method !== "GET" || u.pathname.startsWith("/.auth/")) return;
  if (req.mode === "navigate") {
    // Network first so updates and sign-in redirects win; the cached app is the offline fallback.
    e.respondWith(fetch(req).then(r => {
      if (r.ok && r.type === "basic") { const cp = r.clone(); caches.open(V).then(c => c.put("/", cp)); }
      return r;
    }).catch(() => caches.match("/")));
    return;
  }
  if (u.origin === location.origin || REMOTE.includes(u.href)) {
    e.respondWith(caches.match(req, {ignoreVary: true}).then(hit => hit || fetch(req).then(r => {
      if (r.ok && (r.type === "basic" || r.type === "cors")) { const cp = r.clone(); caches.open(V).then(c => c.put(req, cp)); }
      return r;
    })));
  }
});
"""

FORBIDDEN = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Not invited</title><style>body{font:16px/1.5 system-ui,sans-serif;max-width:560px;margin:15vh auto;padding:0 20px;color:#1b1f3a}a{color:#3355dd}</style></head>
<body><h1>This planner is private</h1><p>You're signed in, but this account hasn't been invited. Ask the owner for an invitation link, or
<a href="/.auth/logout">sign out</a> and use the invited account.</p></body></html>
"""


def manifest():
    return {
        "name": "CyberCon 2026 Planner (unofficial)", "short_name": "CyberCon", "start_url": "/", "scope": "/",
        "display": "standalone", "background_color": "#0f1220", "theme_color": "#3355dd",
        "description": "Unofficial planner for CyberCon 2026 sessions, clashes and routes around MCEC.",
        "icons": [
            {"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }


def make_icons(out):
    from PIL import Image, ImageDraw, ImageFont
    out.mkdir(parents=True, exist_ok=True)

    def draw(size, pad_frac, rounded):
        im = Image.new("RGBA", (size, size), (0, 0, 0, 0) if rounded else (51, 85, 221, 255))
        d = ImageDraw.Draw(im)
        if rounded:
            d.rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 5, fill=(51, 85, 221, 255))
        p = size * pad_frac
        w = size - 2 * p
        x0, y0, x1, y1 = p, p + w * 0.08, size - p, size - p
        lw = max(2, round(size * 0.035))
        d.rounded_rectangle([x0, y0, x1, y1], radius=w * 0.12, outline="white", width=lw)
        d.line([x0, y0 + w * 0.26, x1, y0 + w * 0.26], fill="white", width=lw)
        for fx in (0.3, 0.7):
            d.line([x0 + w * fx, p - w * 0.02, x0 + w * fx, y0 + w * 0.12], fill="white", width=lw)
        try:
            f = ImageFont.truetype("segoeuib.ttf", round(w * 0.42))
        except OSError:
            f = ImageFont.load_default()
        d.text(((x0 + x1) / 2, y0 + w * 0.6), "26", fill="white", font=f, anchor="mm")
        return im

    draw(192, 0.2, True).save(out / "icon-192.png")
    draw(512, 0.2, True).save(out / "icon-512.png")
    draw(512, 0.28, False).save(out / "icon-maskable-512.png")
    draw(180, 0.2, False).convert("RGB").save(out / "apple-touch-icon.png")


def write_site(out, html, edition):
    html = add_shell(html, edition)
    out.mkdir(parents=True)
    (out / "index.html").write_text(html, encoding="utf-8")
    remote = [v["url"] for v in REMOTE_FLOORS.values()] if edition == "public" else []
    ver = hashlib.sha256((html + json.dumps(remote)).encode()).hexdigest()[:12]
    (out / "sw.js").write_text(SW.replace("__VER__", ver).replace("__REMOTE__", json.dumps(remote)), encoding="utf-8")
    (out / "manifest.webmanifest").write_text(json.dumps(manifest(), indent=2), encoding="utf-8")
    (out / "staticwebapp.config.json").write_text(json.dumps(swa_config(html, edition), indent=2), encoding="utf-8")
    if edition == "private":
        (out / "forbidden.html").write_text(FORBIDDEN, encoding="utf-8")
    make_icons(out / "icons")
    print(f"{edition:8} {(out / 'index.html').stat().st_size / 1024:,.0f} KB  sw {ver}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--private", default=os.environ.get("CYBERCON_PRIVATE"), help="private data directory (abstracts + floor plans)")
    ap.add_argument("--out", default=str(ROOT / "dist"), help="output directory (default: dist/)")
    ap.add_argument("--check", action="store_true", help="only run the public-repo content check")
    a = ap.parse_args()
    if not check_public():
        sys.exit(1)
    if a.check:
        print("check: no private content in the public repo")
        return
    tpl, sessions, changes, meta = load()
    bid = build_id()
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    print(f"build {bid} · {len(sessions)} sessions · snapshot {meta['scraped']}")
    write_site(out / "public", render(tpl, sessions, changes, meta, bid), "public")
    if a.private:
        full, images, n = private_inputs(a.private, sessions)
        html = render(tpl, full, changes, meta, bid, images)
        write_site(out / "private", html, "private")
        (out / "cybercon2026-planner.html").write_text(html, encoding="utf-8")
        print(f"offline  {(out / 'cybercon2026-planner.html').stat().st_size / 1024:,.0f} KB  ({n} abstracts)")


if __name__ == "__main__":
    main()
