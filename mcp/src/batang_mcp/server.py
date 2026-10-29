"""Batang MCP, local bridge: the tools of the remote Batang MCP server, run from your computer.

The tools are defined once, on the server (https://api.batanghub.com/mcp). This program connects to it with your
Batang token and re-exposes exactly the remote tool list, descriptions and instructions over stdio, forwarding every
call, so it always matches the remote server. It adds only what needs your computer:

    login      sign in through your browser (device authorization); the token is kept in ~/.config/batang/token
    whoami     the signed-in account and the token's expiry
    save_link  save a query result link from a remote answer (/mcp/results/...) to a local path

The tools query; they do not hand out whole record files. Those are requested in the hub's 다운로드 tab
(https://batanghub.com/#/downloads) and fetched with the Python package (`batang download --grant <id>`).
Read-only. Access needs a Batang account (sign up at https://batanghub.com/signup).

Environment: BATANG_MCP_URL (default https://api.batanghub.com/mcp), BATANG_TOKEN (a token, instead of the file).
"""
import json
import os
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

import anyio
from mcp import ClientSession, types
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.stdio import stdio_server

from . import __version__

MCP_URL = os.environ.get("BATANG_MCP_URL", "https://api.batanghub.com/mcp").rstrip("/")
UA = "batang-mcp"   # urllib's own User-Agent is refused by the site's CDN (Cloudflare 1010)
TOKEN_FILE = os.path.join(os.path.expanduser("~"), ".config", "batang", "token")
CLIENT_NAME = "Batang MCP (로컬 브리지)"
DOWNLOADS = ("원본 파일은 허브의 다운로드 탭에서 신청하세요: https://batanghub.com/#/downloads (Record files are requested "
             "in the hub's 다운로드 tab; once approved, `batang download --grant <id> --to <folder>` fetches them.)")

BASE_INSTRUCTIONS = """Batang local bridge: the tools of the Batang remote MCP server (battery
database: ageing and fault data in one schema), read-only and query-only. If only login, whoami and save_link are
listed, call login() first: it prints a link and a code to approve in the browser, then the Batang tools appear. When
an answer contains a query result link (/mcp/results/...), save_link(url, path) saves it on this computer. Whole record
files are not handed out here: they are requested in the hub's 다운로드 tab (https://batanghub.com/#/downloads)."""


# --------------------------------------------------------------------------- token

def _read_token():
    t = os.environ.get("BATANG_TOKEN", "").strip()
    if t:
        return t, "env"
    try:
        with open(TOKEN_FILE, encoding="utf-8") as f:
            j = json.load(f)
        if j.get("expires_at") and float(j["expires_at"]) <= time.time():
            return None, "expired"
        return j.get("access_token"), "file"
    except (OSError, ValueError):
        return None, "none"


def _write_token(body):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"access_token": body["access_token"], "expires_at": body.get("expires_at"), "saved": time.time()}, f)
    os.chmod(TOKEN_FILE, 0o600)


def _forget_token():
    try:
        os.remove(TOKEN_FILE)
    except OSError:
        pass


def _origin(url):
    p = urllib.parse.urlsplit(url)
    return f"{p.scheme}://{p.netloc}"


def _get_json(url, data=None, headers=None, timeout=30):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except ValueError:
            return e.code, {}


def _auth_server():
    """The authorization server named by the MCP server's protected-resource metadata."""
    origin, path = _origin(MCP_URL), urllib.parse.urlsplit(MCP_URL).path
    for meta in (origin + "/.well-known/oauth-protected-resource" + path, origin + "/.well-known/oauth-protected-resource"):
        try:
            code, j = _get_json(meta)
        except (OSError, ValueError):
            continue
        if code == 200 and j.get("authorization_servers"):
            return j["authorization_servers"][0].rstrip("/")
    return origin


# --------------------------------------------------------------------------- the remote server

class Remote:
    """One short connection per request: tools, instructions, a call."""

    def __init__(self):
        self.tools, self.instructions = None, None

    async def _run(self, fn):
        token, why = _read_token()
        if not token:
            raise PermissionError("token_expired" if why == "expired" else "login_required")
        client = create_mcp_http_client(headers={"Authorization": "Bearer " + token})
        async with client, streamable_http_client(MCP_URL, http_client=client) as streams:
            async with ClientSession(streams[0], streams[1]) as s:
                init = await s.initialize()
                return await fn(s, init)

    async def refresh(self):
        async def go(s, init):
            self.instructions = getattr(init, "instructions", None)
            self.tools = (await s.list_tools()).tools
            return self.tools
        return await self._run(go)

    async def call(self, name, args):
        return await self._run(lambda s, init: s.call_tool(name, args))


def _unauthorized(e):
    """True for a missing, expired or refused token, also inside exception groups of the HTTP transport."""
    if isinstance(e, PermissionError):
        return True
    if getattr(getattr(e, "response", None), "status_code", None) == 401:
        return True
    if any(_unauthorized(x) for x in getattr(e, "exceptions", ()) or ()):
        return True
    s = repr(e) + str(e)
    return "401" in s or "Unauthorized" in s or "invalid_token" in s


def _token_refused():
    """The SDK reports a refused token only as a generic error: ask the server directly whether it accepts ours."""
    token, _ = _read_token()
    if not token:
        return True
    req = urllib.request.Request(MCP_URL, data=b"{}", method="POST",
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "User-Agent": UA,
                                          "Accept": "application/json, text/event-stream"})
    try:
        with urllib.request.urlopen(req, timeout=20):
            return False
    except urllib.error.HTTPError as e:
        return e.code == 401
    except OSError:
        return False


def _text(t, error=False):
    return types.CallToolResult(content=[types.TextContent(type="text", text=t)], is_error=error)


# --------------------------------------------------------------------------- local tools

LOCAL_TOOLS = [
    types.Tool(name="login",
               description="Sign in to Batang through your browser (device authorization). Prints a link and a code; "
                           "approve them with your Google account, then the Batang tools appear. "
                           "브라우저에서 승인해 로그인합니다. The token lasts 7 days.",
               input_schema={"type": "object", "properties": {"wait_seconds": {"type": "integer", "default": 300}}}),
    types.Tool(name="whoami", description="Whether this computer is signed in to Batang, where the token comes from, and when it expires.",
               input_schema={"type": "object", "properties": {}}),
    types.Tool(name="save_link",
               description="Save a query result link from a Batang answer (/mcp/results/...) to a file on this computer "
                           "and return its path and size. 질의 결과 링크를 이 컴퓨터에 저장합니다. Record files are "
                           "requested in the hub's 다운로드 tab instead.",
               input_schema={"type": "object", "required": ["url", "path"],
                             "properties": {"url": {"type": "string"}, "path": {"type": "string"}}}),
]


def _post_form(url, fields):
    return _get_json(url, urllib.parse.urlencode(fields).encode(), {"Content-Type": "application/x-www-form-urlencoded"})


async def _login(wait_seconds=300):
    """(error result or None, token body or None)."""
    auth = _auth_server()
    code, start = await anyio.to_thread.run_sync(lambda: _post_form(auth + "/auth/device/start", {"client_name": CLIENT_NAME}))
    if code != 200 or "device_code" not in start:
        return _text(f"login could not start ({code}): {start}", True), None
    url = start.get("verification_uri_complete") or start["verification_uri"]
    try:
        webbrowser.open(url)
    except Exception:
        pass
    print(f"Batang login: open {url} and approve code {start['user_code']}", file=sys.stderr, flush=True)
    interval = int(start.get("interval", 5))
    deadline = time.time() + min(int(wait_seconds), int(start.get("expires_in", 600)))
    while time.time() < deadline:
        await anyio.sleep(interval)
        code, body = await anyio.to_thread.run_sync(lambda: _post_form(auth + "/auth/device/token", {"device_code": start["device_code"]}))
        if code == 200 and body.get("access_token"):
            _write_token(body)
            return None, body
        err = body.get("error")
        if err == "slow_down":
            interval = int(body.get("interval", interval + 5))
        elif err != "authorization_pending":
            return _text(f"login failed: {err} {body.get('error_description', '')}".strip(), True), None
    return _text(f"login timed out. Open {url}, approve code {start['user_code']}, then call login again.", True), None


async def _save_link(url, path):
    token, _ = _read_token()
    if not token:
        return _text("login first (call login)", True)
    if not str(url).startswith(_origin(MCP_URL) + "/mcp/results/"):
        return _text("only query result links of this Batang server (/mcp/results/...) are saved. " + DOWNLOADS, True)
    dest = os.path.abspath(os.path.expanduser(str(path)))
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)

    def get():
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "User-Agent": UA})
        n = 0
        with urllib.request.urlopen(req, timeout=600) as r, open(dest + ".part", "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
                n += len(b)
        os.replace(dest + ".part", dest)
        return n
    try:
        n = await anyio.to_thread.run_sync(get)
    except urllib.error.HTTPError as e:
        return _text(f"download failed: HTTP {e.code} {e.read()[:300].decode('utf-8', 'replace')}", True)
    return _text(json.dumps({"saved": dest, "bytes": n}, ensure_ascii=False))


async def _whoami(remote):
    token, how = _read_token()
    if not token:
        return _text("not signed in" + (" (the token expired)" if how == "expired" else "") + ": call login")
    info = {"token": how, "mcp": MCP_URL}
    if how == "file":
        try:
            with open(TOKEN_FILE, encoding="utf-8") as f:
                j = json.load(f)
            if j.get("expires_at"):
                info["expires"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(j["expires_at"])))
        except (OSError, ValueError):
            pass
    try:
        await remote.refresh()
        info["status"] = f"accepted by the server ({len(remote.tools or [])} tools)"
    except Exception as e:
        refused = _unauthorized(e) or await anyio.to_thread.run_sync(_token_refused)
        info["status"] = "token refused: call login" if refused else f"server not reachable: {e}"
    return _text(json.dumps(info, ensure_ascii=False))


# --------------------------------------------------------------------------- the bridge

def build(remote, instructions):
    local = {t.name for t in LOCAL_TOOLS}

    async def list_tools(ctx, params):
        if remote.tools is None:
            try:
                await remote.refresh()
            except Exception:
                pass
        return types.ListToolsResult(tools=LOCAL_TOOLS + [t for t in (remote.tools or []) if t.name not in local])

    async def call_tool(ctx, params):
        name, args = params.name, dict(params.arguments or {})
        if name == "login":
            fail, body = await _login(args.get("wait_seconds", 300))
            if fail:
                return fail
            try:
                await remote.refresh()
                await ctx.session.send_tool_list_changed()
            except Exception as e:
                return _text(f"signed in, but the Batang server could not be reached: {e}", True)
            until = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(body["expires_at"]))) if body.get("expires_at") else "?"
            return _text(f"signed in to Batang (token valid until {until}). The Batang tools are now available.\n\n"
                         f"Server instructions:\n{remote.instructions or ''}")
        if name == "whoami":
            return await _whoami(remote)
        if name == "save_link":
            return await _save_link(args.get("url", ""), args.get("path", ""))
        try:
            return await remote.call(name, args)
        except Exception as e:
            if _unauthorized(e) or await anyio.to_thread.run_sync(_token_refused):
                remote.tools = None
                if os.environ.get("BATANG_TOKEN"):
                    return _text("BATANG_TOKEN was refused (expired or revoked): set a new one, or unset it and call login", True)
                _forget_token()
                return _text("the Batang token is missing or expired: call login to sign in again (tokens last 7 days)", True)
            return _text(f"Batang server error: {e}", True)

    return Server("batang", version=__version__, instructions=instructions, website_url=_origin(MCP_URL),
                  on_list_tools=list_tools, on_call_tool=call_tool)


async def amain():
    remote = Remote()
    instructions = BASE_INSTRUCTIONS
    try:
        await remote.refresh()
        if remote.instructions:
            instructions = remote.instructions + "\n\nLocal bridge: login, whoami, save_link(url, path) for query result links."
    except Exception as e:
        if not (_unauthorized(e) or _token_refused()):
            print(f"Batang: server not reachable now ({e}); its tools appear once it is", file=sys.stderr, flush=True)
    server = build(remote, instructions)
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options(NotificationOptions(tools_changed=True)))


def main():
    anyio.run(amain)


if __name__ == "__main__":
    main()
