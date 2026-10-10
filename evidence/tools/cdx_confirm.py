"""Second, read-only pass: confirm 'no snapshot' results of the availability API with the CDX index."""
import json, subprocess, time, urllib.parse, yaml, archive_check as a
d = yaml.safe_load(open(a.OUT)); E = d["urls"]
def cdx(u):
    q = "https://web.archive.org/cdx/search/cdx?" + urllib.parse.urlencode({"url": u, "output": "json", "fl": "timestamp,statuscode,original", "limit": "-5"})
    for attempt in range(4):
        time.sleep(10)
        r = subprocess.run(["curl", "-s", "-m", "90", q], capture_output=True, text=True)
        try: rows = json.loads(r.stdout or "[]"); break
        except Exception: time.sleep(90 * (attempt + 1))
    else: return "error"
    rows = rows[1:] if rows and rows[0][0] == "timestamp" else rows
    ok = [x for x in rows if x[1] in ("200", "-")] or rows
    return ok[-1] if ok else None
for u, e in E.items():
    if e.get("skipped") or e.get("archive_source") in ("cdx", "availability+cdx"): continue
    if e.get("archive") not in (None, "error") and str(e.get("archive_timestamp") or "") >= "20260101": continue
    cands = [u.split('#')[0]] + ([e["final_url"].split('#')[0]] if e.get("final_url") else [])
    if u.startswith("https://doi.org/"): cands.reverse()
    hit = None
    for c in cands:
        hit = cdx(c)
        if hit and hit != "error": break
    prev = str(e.get("archive_timestamp") or "")
    if hit and hit != "error" and hit[0] > prev:
        e.update(archive=f"https://web.archive.org/web/{hit[0]}/{hit[2]}", archive_timestamp=hit[0], archive_status=hit[1])
    e["archive_source"] = ("cdx" if not prev else "availability+cdx") if hit != "error" else "cdx-error"
    print(u, "cdx", hit, flush=True); a.write(E)
a.write(E)
