"""Freeze projects from a running Launch server into a review bundle (data.json) for the static review build (VITE_REVIEW=1).
usage: python scripts/review_snapshot.py http://localhost:8780 bala@twinmo.ai twinmo out.json sabi also-tmb"""
import json, sys, urllib.request, http.cookiejar, urllib.parse
base, email, invite, out, *pids = sys.argv[1:]
cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.open(urllib.request.Request(base + '/api/login', data=json.dumps({"invite": invite, "email": email}).encode(), headers={'content-type': 'application/json'}))
def get(p):
    try: return json.load(op.open(base + p))
    except Exception as e: return None
from sethread import schema
from sethread.web.server import STAGE_OF
D = {"projects": {}, "list": get('/api/projects'), "examples": get('/api/examples') or []}
for pid in pids:
    P = {}; g = lambda p: get(f'/api/p/{pid}{p}')
    for k in ['/project', '/runs', '/threads', '/graph', '/artifacts', '/scorecard', '/requirements_quality', '/budgets', '/lifecycle', '/patches', '/comments?element=', '/notifications', '/history', '/baselines', '/documents', '/settings']:
        v = g(k);  P[k] = v if v is not None else {}
    for kind in list(schema.KINDS) + ['fmea', 'screened', 'unassessed', 'gaps', 'verification_matrix', 'certification_plan']: P['/collection/' + kind] = g('/collection/' + kind) or []
    for f in ['dfmea', 'dvpr', 'vcrm', 'reqspec', 'hazards', 'n2', 'n2l', 'icd', 'pugh', 'fta', 'drbfm', 'pfmea', 'control_plan', 'avl', 'risks', 'fracas', 'work_items', 'findings', 'handoffs']: P['/form/' + f] = g('/form/' + f)
    for a, b in [('requirements', 'functions'), ('functions', 'parts'), ('requirements', 'tests'), ('needs', 'requirements'), ('regulations', 'requirements'), ('logical_components', 'parts'), ('functions', 'logical_components'), ('constraints', 'tests')]: P[f'/matrix/{a}/{b}'] = g(f'/matrix/{a}/{b}')
    for n in P['/graph'].get('nodes', []):
        if n['kind'] in ('fmea',): continue
        eid = urllib.parse.quote(n['id'], safe=''); e = g(f"/element/{n['kind']}/{eid}")
        if e:
            for pr in e.get('provenance', []): pr['ops'] = [o for o in pr.get('ops', []) if o.get('id') == n['id']]
            P[f"/element/{n['kind']}/{eid}"] = e; P[f"/impact/{eid}"] = g(f"/impact/{eid}")
    for t in P.get('/collection/tables') or []: P['/table/' + t['id']] = g('/table/' + t['id'])
    for t in P.get('/threads') or []: P['/threads/' + t['id']] = g('/threads/' + t['id'])
    for r in P.get('/runs') or []: P['/run/' + r['id']] = g('/run/' + r['id'])
    for f in (P['/artifacts'] or {}).get('sysml', []): P['/file?path=out/sysml/' + f] = None
    D["projects"][pid] = P; print(pid, len(P), 'keys')
json.dump(D, open(out, 'w'), ensure_ascii=False); import os; print(os.path.getsize(out) // 1024, 'KB')
