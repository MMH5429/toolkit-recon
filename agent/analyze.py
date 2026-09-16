import json, os, collections
D = os.path.join(os.path.dirname(__file__), '..', 'data')
recs = json.load(open(os.path.join(D,'apps.json'), encoding='utf-8'))
def cnt(key, flat=False):
    c = collections.Counter()
    for r in recs:
        v = r[key]
        if flat:
            for x in v: c[x]+=1
        else: c[v]+=1
    return c
print("== AUTH (multi-count) =="); [print(f"  {k:16} {v}") for k,v in cnt('auth_methods',True).most_common()]
print("== ACCESS TIER =="); [print(f"  {k:22} {v}") for k,v in cnt('access_tier').most_common()]
print("== BUILDABILITY =="); [print(f"  {k:22} {v}") for k,v in cnt('buildability').most_common()]
print("== PROTOCOLS =="); [print(f"  {k:12} {v}") for k,v in cnt('api_protocols',True).most_common()]
print("== BREADTH =="); [print(f"  {k:10} {v}") for k,v in cnt('api_breadth').most_common()]
print("== MCP =="); [print(f"  {k:10} {v}") for k,v in collections.Counter(r['mcp']['status'] for r in recs).most_common()]
print("== WEBHOOKS =="); [print(f"  {k:10} {v}") for k,v in cnt('webhooks').most_common()]
print("== CONFIDENCE =="); [print(f"  {k:8} {v}") for k,v in cnt('confidence').most_common()]
print("\n== BUILDABILITY x CATEGORY ==")
m = collections.defaultdict(collections.Counter)
for r in recs: m[r['category']][r['buildability']]+=1
order=['build-now','build-with-caveats','needs-outreach','not-buildable-today']
print(f"  {'category':40} " + " ".join(f"{o[:9]:>10}" for o in order))
for c in sorted(m, key=lambda c:-m[c]['build-now']):
    print(f"  {c:40} " + " ".join(f"{m[c][o]:>10}" for o in order))
print("\n== AUTH x ACCESS (is OAuth2 correlated with gates?) ==")
oa=[r for r in recs if 'OAuth2' in r['auth_methods']]; ak=[r for r in recs if 'OAuth2' not in r['auth_methods']]
def selfserve(rs): return sum(1 for r in rs if r['access_tier'].startswith('self-serve'))
print(f"  OAuth2 apps        n={len(oa):3}  self-serve {selfserve(oa):3} ({selfserve(oa)/len(oa)*100:.0f}%)")
print(f"  non-OAuth2 apps    n={len(ak):3}  self-serve {selfserve(ak):3} ({selfserve(ak)/len(ak)*100:.0f}%)")
print("\n== BLOCKERS (non build-now) ==")
for r in recs:
    if r['buildability']!='build-now': print(f"  {r['id']:3} {r['app'][:26]:26} {r['buildability'][:18]:18} {r['blocker'][:70]}")
