"""Loopt de volledige OIDC-code-flow door tegen de lokale FusionAuth.

Doet zonder browser wat gmt_auth.py straks in de app doet: loginformulier ophalen,
inloggen, de code inwisselen met PKCE, en kijken wat er in het id_token staat.
Handig om te controleren of de kickstart klopt voordat je appcode gaat schrijven.

    docker compose -f dev/docker-compose.yml up -d
    python dev/flowtest.py

Waarden komen uit dev/fusionauth/kickstart-gmt.json (alleen voor lokaal gebruik).
"""
import urllib.error
import base64, hashlib, http.cookiejar, json, re, secrets, urllib.parse, urllib.request

ISS   = "http://localhost:9011"
CID   = "22222222-2222-2222-2222-222222222222"
SEC   = "-cVGLS13YXqu-NCEm4FxwT1SgxtqxO6-3I_mWWM5zBg"
RURI  = "http://localhost:5100/auth/callback"
USER  = "evdbelt@dat.nl"
PW    = "GmtLokaal#1"

ver = secrets.token_urlsafe(32)
chal = base64.urlsafe_b64encode(hashlib.sha256(ver.encode()).digest()).decode().rstrip("=")
state, nonce = secrets.token_urlsafe(16), secrets.token_urlsafe(16)

jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(jar),
    type("NoRedirect", (urllib.request.HTTPRedirectHandler,),
         {"redirect_request": lambda *a, **k: None})())

q = dict(client_id=CID, response_type="code", redirect_uri=RURI,
         scope="openid profile email offline_access", state=state, nonce=nonce,
         code_challenge=chal, code_challenge_method="S256")
url = ISS + "/oauth2/authorize?" + urllib.parse.urlencode(q)

html = op.open(url).read().decode()
print("1. loginformulier opgehaald:", "form action=\"/oauth2/authorize\"" in html)
hidden = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', html))
print("   verborgen velden:", sorted(hidden))

form = {**hidden, "loginId": USER, "password": PW}
req = urllib.request.Request(ISS + "/oauth2/authorize",
                             data=urllib.parse.urlencode(form).encode(),
                             headers={"Content-Type": "application/x-www-form-urlencoded"})
try:
    resp = op.open(req)
except urllib.error.HTTPError as e:
    resp = e
loc = resp.headers.get("Location", "")
hops = 0
while loc and not loc.startswith(RURI):
    hops += 1
    try:
        r2 = op.open(ISS + loc if loc.startswith("/") else loc)
    except urllib.error.HTTPError as e:
        r2 = e
    loc = r2.headers.get("Location", "")
print("2. inloggen -> code na", hops, "tussenstap(pen):", loc[:70])
qs = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)
assert "code" in qs, f"geen code: {qs}"
assert qs["state"][0] == state, "state klopt niet"
code = qs["code"][0]

tok = urllib.request.urlopen(urllib.request.Request(
    ISS + "/oauth2/token",
    data=urllib.parse.urlencode(dict(
        grant_type="authorization_code", code=code, client_id=CID,
        client_secret=SEC, redirect_uri=RURI, code_verifier=ver)).encode(),
    headers={"Content-Type": "application/x-www-form-urlencoded"})).read()
tok = json.loads(tok)
print("3. tokens:", sorted(k for k in tok if k.endswith("token")), "| expires_in", tok.get("expires_in"))

def payload(t):
    b = t.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)))

idc = payload(tok["id_token"])
print("4. id_token: iss=%r aud=%r" % (idc["iss"], idc["aud"]))
print("   email=%r name=%r roles=%r nonce-ok=%s"
      % (idc.get("email"), idc.get("name"), idc.get("roles"), idc.get("nonce") == nonce))
print("5. access_token roles:", payload(tok["access_token"]).get("roles"))

rt = json.loads(urllib.request.urlopen(urllib.request.Request(
    ISS + "/oauth2/token",
    data=urllib.parse.urlencode(dict(grant_type="refresh_token",
        refresh_token=tok["refresh_token"], client_id=CID, client_secret=SEC)).encode(),
    headers={"Content-Type": "application/x-www-form-urlencoded"})).read())
print("6. refresh geeft nieuw access_token:", bool(rt.get("access_token")))
