"""Login: the device-authorization flow of the Batang login service, and the token cache.

    batang login        prints a link and a code, opens the browser; you sign in with your Google account there,
                        approve, and the token (valid for 7 days) is stored in ~/.config/batang/token (mode 600)

BATANG_TOKEN overrides the cache (servers, CI). Tokens are kept per login service, so a development server and the
production server do not overwrite each other.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_URL = "https://api.batanghub.com/mcp"
CLIENT_NAME = "batang (Python)"


class AuthError(Exception):
    """No valid token, or the login was refused."""


def token_path():
    return os.path.join(os.path.expanduser(os.environ.get("BATANG_CONFIG_DIR", "~/.config/batang")), "token")


def origin_of(url):
    p = urllib.parse.urlsplit(url)
    return f"{p.scheme}://{p.netloc}"


def _read_cache():
    try:
        with open(token_path(), encoding="utf-8") as f:
            j = json.load(f)
        return j if isinstance(j, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_cache(j):
    p = token_path()
    os.makedirs(os.path.dirname(p), mode=0o700, exist_ok=True)
    tmp = p + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(j, f, indent=1)
    os.replace(tmp, p)
    os.chmod(p, 0o600)


def cached(auth_url, clock=time.time):
    """The cached token entry for this login service, or None when there is none or it has expired."""
    env = os.environ.get("BATANG_TOKEN")
    if env:
        return {"access_token": env, "expires_at": None, "source": "BATANG_TOKEN"}
    e = _read_cache().get(origin_of(auth_url))
    if not e or not e.get("access_token"):
        return None
    if e.get("expires_at") and float(e["expires_at"]) <= clock() + 60:
        return None
    return dict(e, source="cache")


def forget(auth_url):
    j = _read_cache()
    if j.pop(origin_of(auth_url), None) is not None:
        _write_cache(j)


def _post(url, data, timeout=30):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json",
                                          "User-Agent": "batang-python"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {"error": f"http {e.code}"}


def login(auth_url, open_browser=True, out=None, sleep=time.sleep, clock=time.time, client_name=CLIENT_NAME):
    """Run the device flow against the login service at auth_url's origin; store and return the token entry."""
    out = out or sys.stderr
    base = origin_of(auth_url)
    code, start = _post(base + "/auth/device/start", {"client_name": client_name})
    if code != 200 or "device_code" not in start:
        raise AuthError(f"could not start the login at {base}: {start.get('error', code)}")
    link = start.get("verification_uri_complete") or start["verification_uri"]
    print(f"Open {link}\nand approve the code {start['user_code']} (sign in with your Google account if asked).", file=out)
    if open_browser:
        try:
            import webbrowser
            webbrowser.open(link)
        except Exception:
            pass
    interval = float(start.get("interval", 5))
    deadline = clock() + float(start.get("expires_in", 600))
    while clock() < deadline:
        sleep(interval)
        code, tok = _post(base + "/auth/device/token", {"device_code": start["device_code"]})
        if code == 200 and tok.get("access_token"):
            entry = {"access_token": tok["access_token"], "expires_at": tok.get("expires_at"), "token_id": tok.get("token_id"),
                     "obtained_at": clock()}
            j = _read_cache()
            j[base] = entry
            _write_cache(j)
            print("Logged in.", file=out)
            return dict(entry, source="cache")
        err = tok.get("error")
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            interval = float(tok.get("interval", interval + 5))
            continue
        if err == "access_denied":
            raise AuthError(tok.get("error_description") or "the login was refused")
        if err == "expired_token":
            break
        raise AuthError(f"login failed: {err or code}")
    raise AuthError("the code expired before it was approved; run the login again")
