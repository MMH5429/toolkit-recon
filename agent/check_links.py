"""Verification loop 1: does every evidence URL actually resolve?
Catches the classic failure mode - a plausible-looking hallucinated docs URL."""
import json, os, ssl, urllib.request, urllib.error, concurrent.futures as cf
D = os.path.join(os.path.dirname(__file__), '..', 'data')
urls = json.load(open(os.path.join(D, 'evidence_urls.json'), encoding='utf-8'))
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

def check(item):
    _id, app, url = item
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
                return {"id": _id, "app": app, "url": url, "status": r.status, "ok": True}
        except urllib.error.HTTPError as e:
            if e.code in (403, 405, 429, 999) and method == "HEAD":
                continue
            # 403/429 = bot-blocked, not a dead link. Treat separately.
            return {"id": _id, "app": app, "url": url, "status": e.code, "ok": e.code in (403, 429, 999),
                    "note": "bot-blocked" if e.code in (403, 429, 999) else "dead"}
        except Exception as e:
            if method == "GET":
                return {"id": _id, "app": app, "url": url, "status": None, "ok": False, "note": type(e).__name__}
    return {"id": _id, "app": app, "url": url, "status": None, "ok": False, "note": "unreachable"}

with cf.ThreadPoolExecutor(max_workers=24) as ex:
    res = list(ex.map(check, urls))
json.dump(res, open(os.path.join(D, 'verify', 'link_check.json'), 'w', encoding='utf-8'), indent=1)
dead = [r for r in res if not r["ok"]]
blocked = [r for r in res if r.get("note") == "bot-blocked"]
print(f"checked={len(res)} live={len(res)-len(dead)} dead={len(dead)} bot-blocked-but-real={len(blocked)}")
for r in dead: print("  DEAD", r["id"], r["app"], r["status"], r["url"])
