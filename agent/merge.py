import json, glob, os, random, collections
RAW = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
OUT = os.path.join(os.path.dirname(__file__), '..', 'data')
recs = []
for f in sorted(glob.glob(os.path.join(RAW, '*.json'))):
    recs.extend(json.load(open(f, encoding='utf-8')))
recs.sort(key=lambda r: r['id'])
assert len(recs) == 100, len(recs)
assert [r['id'] for r in recs] == list(range(1, 101)), "id gap"
json.dump(recs, open(os.path.join(OUT, 'apps.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)

# stratified sample: 2 per category, fixed seed -> reproducible
random.seed(42)
bycat = collections.defaultdict(list)
for r in recs: bycat[r['category']].append(r)
sample = []
for cat in sorted(bycat): sample.extend(sorted(random.sample(bycat[cat], 2), key=lambda r: r['id']))
sample.sort(key=lambda r: r['id'])
json.dump([{k: r[k] for k in ('id','app','category','hint')} for r in sample],
          open(os.path.join(OUT, 'sample.json'), 'w', encoding='utf-8'), indent=1)
print("SAMPLE:", ", ".join(f"{r['id']}:{r['app']}" for r in sample))
urls = [(r['id'], r['app'], u) for r in recs for u in r.get('evidence', [])]
print("records", len(recs), "evidence urls", len(urls), "unique", len({u for _,_,u in urls}))
json.dump(urls, open(os.path.join(OUT, 'evidence_urls.json'), 'w', encoding='utf-8'))
