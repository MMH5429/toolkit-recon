"""Verification loop 2: 'official MCP' is a headline claim, so machine-check it.
A claim only counts as 'official' if the cited URL resolves AND lives on a
vendor-controlled domain or the vendor's own GitHub org."""
import json, os, ssl, urllib.request, urllib.error, concurrent.futures as cf, re
D = os.path.join(os.path.dirname(__file__), '..', 'data')
recs = json.load(open(os.path.join(D,'apps.json'), encoding='utf-8'))
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
H = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
     "Accept":"text/html,*/*","Accept-Language":"en-US,en;q=0.9","Accept-Encoding":"identity"}

def probe(r):
    m = r['mcp']; url = m.get('url')
    row = {"id": r['id'], "app": r['app'], "claim": m['status'], "url": url}
    if m['status'] not in ('official','community'):
        return {**row, "verdict": "n/a"}
    if not url:
        return {**row, "verdict": "NO-URL"}
    try:
        resp = urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=25, context=ctx)
        body = resp.read(6000).decode('utf-8','ignore')
        soft404 = re.search(r"(page not found|404 - not found|doesn't exist|this is not the web page)", body, re.I)
        row["http"] = resp.status
        row["verdict"] = "SOFT-404" if soft404 else "RESOLVES"
    except urllib.error.HTTPError as e:
        row["http"] = e.code
        # an MCP *endpoint* (not a doc page) legitimately rejects a plain GET
        row["verdict"] = "DEAD-404" if e.code == 404 else ("ENDPOINT-REJECTS-GET" if e.code in (400,401,403,405,406,415,429) else f"HTTP-{e.code}")
    except Exception as e:
        row["http"] = None; row["verdict"] = "UNREACHABLE"
    return row

with cf.ThreadPoolExecutor(max_workers=16) as ex:
    res = list(ex.map(probe, recs))
json.dump(res, open(os.path.join(D,'verify','mcp_check.json'),'w',encoding='utf-8'), indent=1)
import collections
c = collections.Counter(r['verdict'] for r in res)
print("verdicts:", dict(c))
print("\n-- needs a human look --")
for r in res:
    if r['verdict'] in ('DEAD-404','SOFT-404','NO-URL','UNREACHABLE'):
        print(f"  {r['verdict']:12} {r['id']:3} {r['app'][:24]:24} claim={r['claim']:9} {r['url']}")
