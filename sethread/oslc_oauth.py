"""OAuth 1.0a provider for OSLC consumers (IBM DOORS Next / ELM "friends", Polarion, Windchill RV&S).

Jazz-based tools discover a provider through /rootservices, register as a consumer (key + secret), then run the
three-legged OAuth 1.0a dance: request token → user authorizes in the provider's UI → access token. Every later
OSLC call is signed (HMAC-SHA1). Launch stores consumers and tokens under <data>/.oslc/ and validates signatures.

Consumers are created by an administrator at /api/oslc/consumers (or in the Integrations page); the key/secret pair
is what the ELM admin types into "Add Friend". Jama Connect and Codebeamer use HTTP Basic / OAuth2 bearer instead,
which the main auth dependency already accepts."""
from __future__ import annotations
import base64, hashlib, hmac, json, os, secrets, time, urllib.parse
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

class OAuthStore:
    def __init__(self, root: str):
        self.root = os.path.join(root, ".oslc"); os.makedirs(self.root, exist_ok=True)
        self.path = os.path.join(self.root, "oauth.json"); self.d = json.load(open(self.path)) if os.path.exists(self.path) else {"consumers": {}, "request": {}, "access": {}}
    def save(self): json.dump(self.d, open(self.path, "w"), indent=1)
    def add_consumer(self, name: str, created_by: str, trusted: bool = False) -> dict:
        key = secrets.token_hex(8); sec = secrets.token_hex(16)
        self.d["consumers"][key] = {"name": name, "secret": sec, "created_by": created_by, "created": time.time(), "trusted": trusted}; self.save()
        return {"key": key, "secret": sec, "name": name}
    def consumers(self): return [{"key": k, **{kk: vv for kk, vv in v.items() if kk != "secret"}} for k, v in self.d["consumers"].items()]
    def remove_consumer(self, key): self.d["consumers"].pop(key, None); self.save()

def _pct(s): return urllib.parse.quote(str(s), safe="~")

def signature_base(method: str, url: str, params: dict) -> str:
    u = urllib.parse.urlsplit(url); norm_url = f"{u.scheme}://{u.netloc}{u.path}"
    items = sorted((_pct(k), _pct(v)) for k, v in params.items() if k != "oauth_signature")
    return "&".join([method.upper(), _pct(norm_url), _pct("&".join(f"{k}={v}" for k, v in items))])

def sign(method, url, params, consumer_secret, token_secret=""):
    key = f"{_pct(consumer_secret)}&{_pct(token_secret)}"
    return base64.b64encode(hmac.new(key.encode(), signature_base(method, url, params).encode(), hashlib.sha1).digest()).decode()

def parse_auth_header(h: str) -> dict:
    if not h or not h.lower().startswith("oauth "): return {}
    out = {}
    for part in h[6:].split(","):
        if "=" in part:
            k, v = part.strip().split("=", 1); out[k] = urllib.parse.unquote(v.strip().strip('"'))
    return out

def oauth_params(request: Request, body_form: dict | None = None) -> dict:
    p = dict(request.query_params); p.update(parse_auth_header(request.headers.get("authorization", "")))
    if body_form: p.update(body_form)
    return p

def verify(store: OAuthStore, request: Request, params: dict, require_access=True) -> str | None:
    """Return the user bound to a valid signed request, or None if the request carries no OAuth."""
    if "oauth_consumer_key" not in params: return None
    c = store.d["consumers"].get(params["oauth_consumer_key"])
    if not c: raise HTTPException(401, "unknown oauth consumer")
    tok = params.get("oauth_token", ""); tsec, user = "", None
    if tok:
        rec = store.d["access"].get(tok) or (None if require_access else store.d["request"].get(tok))
        if not rec: raise HTTPException(401, "unknown oauth token")
        tsec, user = rec["secret"], rec.get("user")
    elif require_access: raise HTTPException(401, "oauth token required")
    url = str(request.url).split("?")[0]
    # honour reverse-proxy scheme/host so signatures match what the consumer signed
    xf = request.headers.get("x-forwarded-proto"); xh = request.headers.get("x-forwarded-host")
    if xf or xh:
        u = urllib.parse.urlsplit(url); url = f"{xf or u.scheme}://{xh or u.netloc}{u.path}"
    expected = sign(request.method, url, params, c["secret"], tsec)
    if not hmac.compare_digest(expected, params.get("oauth_signature", "")): raise HTTPException(401, "bad oauth signature")
    if abs(time.time() - float(params.get("oauth_timestamp", 0))) > 600: raise HTTPException(401, "oauth timestamp out of window")
    return user or f"oauth:{c['name']}"

def router(store: OAuthStore, current_user, admin_check=None):
    r = APIRouter()
    @r.post("/oslc/oauth/request_token")
    async def request_token(request: Request):
        form = dict(urllib.parse.parse_qsl((await request.body()).decode())) if request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded") else {}
        p = oauth_params(request, form); verify(store, request, p, require_access=False)
        tok, sec = secrets.token_hex(12), secrets.token_hex(16)
        store.d["request"][tok] = {"secret": sec, "consumer": p["oauth_consumer_key"], "callback": p.get("oauth_callback", "oob"), "created": time.time(), "verifier": None, "user": None}; store.save()
        return PlainTextResponse(urllib.parse.urlencode({"oauth_token": tok, "oauth_token_secret": sec, "oauth_callback_confirmed": "true"}), media_type="application/x-www-form-urlencoded")

    @r.get("/oslc/oauth/authorize", response_class=HTMLResponse)
    def authorize(request: Request, oauth_token: str):
        rec = store.d["request"].get(oauth_token)
        if not rec: raise HTTPException(400, "unknown request token")
        try: user = current_user(request)
        except HTTPException: return RedirectResponse(f"/app/?next={urllib.parse.quote('/oslc/oauth/authorize?oauth_token=' + oauth_token)}")
        c = store.d["consumers"][rec["consumer"]]
        if c.get("trusted"): return _grant(store, oauth_token, user)
        return HTMLResponse(f"""<!doctype html><html><body style="font:14px -apple-system,Segoe UI,sans-serif;max-width:480px;margin:10vh auto"><h2>Launch</h2>
<p><b>{c['name']}</b> wants to read and write the Launch model on your behalf (<b>{user}</b>) through OSLC.</p>
<form method="post" action="/oslc/oauth/authorize"><input type="hidden" name="oauth_token" value="{oauth_token}"><button style="padding:8px 14px">Allow</button> <a href="/">Cancel</a></form></body></html>""")

    @r.post("/oslc/oauth/authorize")
    async def authorize_post(request: Request):
        form = dict(urllib.parse.parse_qsl((await request.body()).decode())); user = current_user(request)
        return _grant(store, form["oauth_token"], user)

    def _grant(store, tok, user):
        rec = store.d["request"][tok]; rec["verifier"] = secrets.token_hex(6); rec["user"] = user; store.save()
        cb = rec["callback"]
        if cb and cb != "oob":
            sep = "&" if "?" in cb else "?"; return RedirectResponse(f"{cb}{sep}oauth_token={tok}&oauth_verifier={rec['verifier']}", status_code=303)
        return HTMLResponse(f"<p>Authorized. Verifier: <code>{rec['verifier']}</code></p>")

    @r.post("/oslc/oauth/access_token")
    async def access_token(request: Request):
        form = dict(urllib.parse.parse_qsl((await request.body()).decode())) if request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded") else {}
        p = oauth_params(request, form); verify(store, request, p, require_access=False)
        rec = store.d["request"].get(p.get("oauth_token", ""))
        if not rec or rec.get("verifier") != p.get("oauth_verifier"): raise HTTPException(401, "bad verifier")
        tok, sec = secrets.token_hex(12), secrets.token_hex(16)
        store.d["access"][tok] = {"secret": sec, "consumer": rec["consumer"], "user": rec["user"], "created": time.time()}; store.d["request"].pop(p["oauth_token"], None); store.save()
        return PlainTextResponse(urllib.parse.urlencode({"oauth_token": tok, "oauth_token_secret": sec}), media_type="application/x-www-form-urlencoded")

    # consumer administration (the key/secret an ELM admin enters under "Add Friend")
    @r.get("/api/oslc/consumers")
    def list_consumers(request: Request): current_user(request); return store.consumers()
    @r.post("/api/oslc/consumers")
    async def add_consumer(request: Request):
        user = current_user(request); body = await request.json()
        return store.add_consumer(body.get("name", "consumer"), user, bool(body.get("trusted")))
    @r.delete("/api/oslc/consumers/{key}")
    def del_consumer(key: str, request: Request): current_user(request); store.remove_consumer(key); return {"ok": True}
    return r
