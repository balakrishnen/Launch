"""Pre-render every diagram the review snapshot references as minified SVG, one file per project (keeps each under the artifact file limit).
usage: python scripts/review_diagrams.py http://localhost:8780 email invite /home/claude/review"""
import json, re, sys, os, urllib.request, http.cookiejar
base, email, invite, outdir = sys.argv[1:5]
cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.open(urllib.request.Request(base + '/api/login', data=json.dumps({"invite": invite, "email": email}).encode(), headers={'content-type': 'application/json'}))
def g(p):
    try: return json.load(op.open(base + '/api/p/' + p))
    except Exception: return None
def mini(svg):
    svg = re.sub(r'<!--.*?-->', '', svg, flags=re.S); svg = re.sub(r'<title>.*?</title>', '', svg, flags=re.S); return re.sub(r'>\s+<', '><', svg)
D = json.load(open(os.path.join(outdir, 'data.json')))
for pid, P in D['projects'].items():
    out = {}
    for k in list(P):
        if k.startswith('/diagram/'):
            d = g(pid + k)
            if d and d.get('svg'): out[k] = {'view': d.get('view'), 'title': d.get('title'), 'text': d.get('text', ''), 'svg': mini(d['svg'])}
            P[k] = None   # keep only a marker in data.json; the diagrams file carries the SVG
    json.dump(out, open(os.path.join(outdir, f'diagrams_{pid}.json'), 'w'), ensure_ascii=False)
    print(pid, len(out), os.path.getsize(os.path.join(outdir, f'diagrams_{pid}.json')) // 1024, 'KB')
json.dump(D, open(os.path.join(outdir, 'data.json'), 'w'), ensure_ascii=False); print('data.json', os.path.getsize(os.path.join(outdir, 'data.json')) // 1024, 'KB')
