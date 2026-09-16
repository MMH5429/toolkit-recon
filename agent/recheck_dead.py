"""Second pass on failed URLs with full browser-like headers.
Meta/Adobe return 400/403 to bare clients; this separates 'bot-blocked' from 'genuinely dead'."""
import json, os, ssl, urllib.request, urllib.error
D = os.path.join(os.path.dirname(__file__), '..', 'data')
res = json.load(open(os.path.join(D, 'verify', 'link_check.json'), encoding='utf-8'))
dead = [r for r in res if not r['ok']]
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
H = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
     "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
     "Accept-Language":"en-US,en;q=0.9","Accept-Encoding":"identity","Connection":"keep-alive",
     "Upgrade-Insecure-Requests":"1","Sec-Fetch-Dest":"document","Sec-Fetch-Mode":"navigate","Sec-Fetch-Site":"none"}
out=[]
for r in dead:
    try:
        req=urllib.request.Request(r['url'], headers=H)
        with urllib.request.urlopen(req, timeout=25, context=ctx) as resp:
            body = resp.read(4000).decode('utf-8','ignore').lower()
            hit = resp.status==200 and ('page not found' not in body and 'sorry, this page' not in body)
            out.append({**r,'retry_status':resp.status,'verdict':'LIVE' if hit else 'SOFT-404'})
    except urllib.error.HTTPError as e:
        out.append({**r,'retry_status':e.code,'verdict':'DEAD-404' if e.code==404 else f'BLOCKED-{e.code}'})
    except Exception as e:
        out.append({**r,'retry_status':None,'verdict':'UNREACHABLE'})
json.dump(out, open(os.path.join(D,'verify','link_recheck.json'),'w',encoding='utf-8'), indent=1)
for o in out: print(f"{o['verdict']:14} {o['id']:3} {o['app'][:22]:22} {o['url']}")
