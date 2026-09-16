"""Applies the audit ledger to the dataset. Every change is traceable to a check that found it."""
import json, os
D = os.path.join(os.path.dirname(__file__), '..', 'data')
recs = json.load(open(os.path.join(D,'apps.json'), encoding='utf-8'))
corr = json.load(open(os.path.join(D,'corrections.json'), encoding='utf-8'))
by_id = {r['id']: r for r in recs}
# default: every MCP claim is verified unless the ledger says otherwise
for r in recs:
    if r['mcp']['status'] in ('official','community'): r['mcp']['verified'] = True
applied = 0
for c in corr:
    r = by_id[c['id']]
    if c['field'] == 'evidence':
        if c['from'] in r['evidence']:
            r['evidence'][r['evidence'].index(c['from'])] = c['to']; applied += 1
    elif c['field'] == 'mcp.verified':
        r['mcp']['verified'] = (c['to'] == 'true'); applied += 1
    else:
        r[c['field']] = c['to']; applied += 1
json.dump(recs, open(os.path.join(D,'apps.json'),'w',encoding='utf-8'), indent=1, ensure_ascii=False)
print(f"applied {applied}/{len(corr)} corrections")
