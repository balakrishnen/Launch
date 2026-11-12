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
D = {"projects": {}, "list": get('/api/projects'), "examples": get('/api/examples') or [], "org": get('/api/org'), "org_templates": get('/api/org/templates')}
for pid in pids:
    P = {}; g = lambda p: get(f'/api/p/{pid}{p}')
    for k in ['/project', '/runs', '/threads', '/board', '/pdp', '/pdp/tailoring', '/dfx', '/trades', '/eda', '/rfq/P-TB', '/timeline', '/trend', '/harness', '/graph', '/artifacts', '/scorecard', '/requirements_quality', '/budgets', '/lifecycle', '/patches', '/comments?element=', '/notifications', '/history', '/baselines', '/documents', '/settings']:
        v = g(k);  P[k] = v if v is not None else {}
    for kind in list(schema.KINDS) + ['fmea', 'screened', 'unassessed', 'gaps', 'verification_matrix', 'certification_plan']: P['/collection/' + kind] = g('/collection/' + kind) or []
    for f in ['dfmea', 'dvpr', 'vcrm', 'reqspec', 'hazards', 'n2', 'n2l', 'icd', 'pugh', 'fta', 'drbfm', 'pfmea', 'control_plan', 'avl', 'risks', 'fracas', 'work_items', 'findings', 'handoffs', 'claims', 'cost', 'markets', 'staffing', 'procurement']: P['/form/' + f] = g('/form/' + f)
    for a, b in [('requirements', 'functions'), ('functions', 'parts'), ('requirements', 'tests'), ('needs', 'requirements'), ('regulations', 'requirements'), ('logical_components', 'parts'), ('functions', 'logical_components'), ('constraints', 'tests')]: P[f'/matrix/{a}/{b}'] = g(f'/matrix/{a}/{b}')
    for n in P['/graph'].get('nodes', []):
        eid = urllib.parse.quote(n['id'], safe=''); e = g(f"/element/{n['kind']}/{eid}")
        if e:
            for pr in e.get('provenance', []): pr['ops'] = [o for o in pr.get('ops', []) if o.get('id') == n['id']]
            P[f"/element/{n['kind']}/{eid}"] = e
            dg = g(f"/diagram/element/{n['kind']}/{eid}")
            if dg: dg.pop('svg', None); P[f"/diagram/element/{n['kind']}/{eid}"] = dg
            P[f"/where/{eid}"] = g(f"/where/{eid}")
            if n['kind'] != 'fmea': P[f"/impact/{eid}"] = g(f"/impact/{eid}"); P[f"/memory/{eid}"] = g(f"/memory/{eid}")
    for t in P.get('/collection/tables') or []: P['/table/' + t['id']] = g('/table/' + t['id'])
    for f in P.get('/collection/fmea') or []:
        k = f"/element/fmea/{urllib.parse.quote(f['id'], safe='')}"
        if k not in P: P[k] = g(k)
        dk = f"/diagram/element/fmea/{urllib.parse.quote(f['id'], safe='')}"; dg = g(dk)
        if dg: dg.pop('svg', None); P[dk] = dg
    for t in (P['/project'] or {}).get('teams', {}): P['/team/' + t] = g('/team/' + t); P[f'/team/{t}/deliverables'] = g(f'/team/{t}/deliverables')
    P['/me/team'] = g('/me/team')
    P['/diagrams'] = g('/diagrams')
    for v in (P['/diagrams'] or []): dg = g('/diagram/' + v['id']); dg and dg.pop('svg', None); P['/diagram/' + v['id']] = dg
    for t in (P['/project'] or {}).get('teams', {}): dg = g(f'/diagram/element/teams/{t}'); dg and dg.pop('svg', None); P[f'/diagram/element/teams/{t}'] = dg
    for pt in (P.get('/collection/parts') or []):
        c = g(f"/cad/{pt['id']}")
        if c and c.get('status','none') != 'none': P[f"/cad/{pt['id']}"] = c; P[f"/cadbrief/{pt['id']}"] = g(f"/cadbrief/{pt['id']}")
    for x in P.get('/dfx') or []: P['/dfx/' + x['id']] = g('/dfx/' + x['id'])
    for x in (P.get('/trades') or {}).get('studies', []): P['/trades/' + x['id']] = g('/trades/' + x['id'])
    for t in P.get('/threads') or []: P['/threads/' + t['id']] = g('/threads/' + t['id'])
    for r in P.get('/runs') or []: P['/run/' + r['id']] = g('/run/' + r['id'])
    for f in (P['/artifacts'] or {}).get('sysml', []): P['/file?path=out/sysml/' + f] = None
    D["projects"][pid] = P; print(pid, len(P), 'keys')
json.dump(D, open(out, 'w'), ensure_ascii=False); import os; print(os.path.getsize(out) // 1024, 'KB')
