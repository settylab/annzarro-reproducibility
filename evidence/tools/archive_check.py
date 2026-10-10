"""Build evidence/matrix/archive.yaml: live status + closest Wayback snapshot (read-only API)."""
import re, glob, json, subprocess, sys, time, urllib.parse, datetime, os
import yaml
REPO = os.path.expanduser("~/gits/annzarro-reproducibility")
OUT = f"{REPO}/evidence/matrix/archive.yaml"
TODAY = datetime.date.today().isoformat()
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"

def sources():
    files = sorted(glob.glob(f"{REPO}/notes/comparison/*.md")) + sorted(glob.glob(f"{REPO}/evidence/matrix/tools/*.yaml")) + [f"{REPO}/figures/COMPARISON_NOTES.md"]
    urls = {}
    for f in files:
        for u in re.findall(r'https?://[^\s\)\]>"\'`|,]+', open(f).read()):
            u = u.rstrip('.;:*')
            if re.match(r'https?://github\.com/[^/]+/[^/]+/blob/', u) or 'web.archive.org' in u:
                continue
            urls.setdefault(u, set()).add(os.path.relpath(f, REPO))
    return urls

def skip_reason(u):
    if re.match(r'https?://(127\.0\.0\.1|localhost)', u): return "local demo server"
    if '…' in u or '<' in u or 'example.org' in u: return "placeholder in prose"
    if u.rstrip('/').endswith('?url='): return "URL template"
    return None

LAST = [0.0]
def throttle():
    d = time.time() - LAST[0]
    if d < 1.0: time.sleep(1.0 - d)
    LAST[0] = time.time()

def curl(u, proxy=False):
    throttle()
    cmd = ["curl", "-s", "-L", "-o", "/dev/null", "-m", "30", "-A", UA, "-w", "%{http_code} %{url_effective}", "--max-redirs", "10", "-H", "Accept: text/html,*/*"]
    if proxy: cmd += ["--socks5-hostname", "localhost:1080"]
    r = subprocess.run(cmd + [u], capture_output=True, text=True)
    out = r.stdout.strip().split(" ", 1)
    code = int(out[0]) if out and out[0].isdigit() else 0
    return code, (out[1] if len(out) > 1 else u)

def wayback(u):
    q = "https://archive.org/wayback/available?" + urllib.parse.urlencode({"url": u, "timestamp": "20261004"})
    for attempt in range(6):
        time.sleep(10); throttle()
        cmd = ["curl", "-s", "-m", "40", "-A", "annzarro-reproducibility evidence refs (read-only lookup)"]
        if attempt % 2 == 1: cmd += ["--socks5-hostname", "localhost:1080"]
        r = subprocess.run(cmd + [q], capture_output=True, text=True)
        try:
            s = json.loads(r.stdout)["archived_snapshots"].get("closest"); break
        except Exception:
            print("  wayback retry", attempt, r.stdout[:60].replace("\n", " "), flush=True)
            time.sleep(90 * (attempt + 1))
    else:
        return "error"
    if s and s.get("available"):
        return s["url"].replace("http://web.archive.org", "https://web.archive.org"), s["timestamp"], s.get("status")
    return None

def main(extra=()):
    db = yaml.safe_load(open(OUT)) if os.path.exists(OUT) else None
    db = db or {}
    entries = db.get("urls") or {}
    src = sources()
    for u in extra: src.setdefault(u, set()).add("evidence/matrix/papers.yaml")
    phase = os.environ.get("PHASE", "live")
    for u in sorted(src):
        old = entries.get(u)
        if old and phase == "archive" and not old.get("skipped") and old.get("archive") in ("error", "pending"):
            cands = [u.split('#')[0]]
            if old.get("final_url") and old["final_url"].split('#')[0] != cands[0]:
                f = old["final_url"].split('#')[0]
                cands = [f, cands[0]] if u.startswith("https://doi.org/") else cands + [f]
            wb = None
            for c in cands:
                wb = wayback(c)
                if wb and wb != "error": break
            if wb == "error": old.update(archive="error", archive_timestamp=None)
            elif wb: old.update(archive=wb[0], archive_timestamp=wb[1], archive_status=wb[2])
            else: old.update(archive=None, archive_timestamp=None)
            print(u, "wb", old.get("archive_timestamp"), flush=True); write(entries); continue
        if old and old.get("status") != "error":
            old["cited_in"] = sorted(src[u]); continue
        e = {"cited_in": sorted(src[u])}
        sr = skip_reason(u)
        if sr:
            e.update(checked=TODAY, status=None, skipped=sr, archive=None, archive_timestamp=None)
        else:
            base = u.split('#')[0] if '#?' not in u else u
            code, final = curl(base)
            via = "direct"
            if code in (0, 403, 401, 429, 503):
                c2, f2 = curl(base, proxy=True)
                if c2 and (code == 0 or c2 < 400):
                    code, final, via = c2, f2, "proxy"
            e.update(checked=TODAY, status=code or "error", final_url=final if final != base else None, via=via,
                     archive="pending", archive_timestamp=None)
            classify(e)
        entries[u] = e
        print(u, e.get("status"), e.get("archive_timestamp"), flush=True)
        write(entries)
    write(entries)

def classify(e):
    e.pop("dead", None); e.pop("blocked", None)
    c = e.get("status")
    if e.get("skipped"): return
    if c in (401, 403, 429): e["blocked"] = True      # bot wall / rate limit / no listing: not proven dead
    elif c == "error" or (isinstance(c, int) and c >= 400): e["dead"] = True

def write(entries):
    for e in entries.values(): classify(e)
    def needs(e):
        if e.get("skipped"): return False
        ts = e.get("archive_timestamp")
        return not ts or str(ts) < "20260101"
    out = {
        "generated_by": "archive lookup (read-only: archive.org/wayback/available; no snapshot was created)",
        "checked": TODAY,
        "summary": {
            "urls": len(entries),
            "skipped": sum(1 for e in entries.values() if e.get("skipped")),
            "archived": sum(1 for e in entries.values() if str(e.get("archive") or "").startswith("http")),
            "dead": sum(1 for e in entries.values() if e.get("dead")),
            "blocked": sum(1 for e in entries.values() if e.get("blocked")),
        },
        "dead": sorted(u for u, e in entries.items() if e.get("dead")),
        "blocked": sorted(u for u, e in entries.items() if e.get("blocked")),
        "needs_snapshot": sorted(u for u, e in entries.items() if needs(e) and not e.get("dead")),
        "urls": dict(sorted(entries.items())),
    }
    out["summary"]["needs_snapshot"] = len(out["needs_snapshot"])
    hdr = ("# URL -> live status and closest Wayback Machine snapshot, for evidence refs.\n"
           "# Loaded by evidence/tools/refs.py (archive_for). Regenerate: rerun the lookup script; it resumes.\n"
           "# status: final HTTP status after redirects (via: direct | proxy; error = no connection).\n"
           "# dead: 404/410/5xx or no connection. blocked: 401/403/429 from a bot wall or rate limit\n"
           "# (direct and SOCKS proxy both refused), so liveness is unverified, not disproved.\n"
           "# needs_snapshot: no snapshot, or newest snapshot older than 2026-01-01; candidates for a\n"
           "# web.archive.org/save request, which needs the user's approval (none was made).\n")
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        f.write(hdr); yaml.safe_dump(out, f, sort_keys=False, width=200, allow_unicode=True)
    os.replace(tmp, OUT)

if __name__ == "__main__":
    extra = [l.strip() for l in open(sys.argv[1])] if len(sys.argv) > 1 else []
    main([x for x in extra if x])
