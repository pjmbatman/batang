"""The connection to the Batang server: the same tools as the MCP server, called over its HTTP endpoint.

Every method of batang.Client is one tool call (tools/call over MCP Streamable HTTP, JSON-RPC 2.0), so the Python
package and the MCP server always offer the same operations with the same arguments. Large answers come back as
links to Parquet files, which are fetched here with the same token.
"""
import itertools
import json
import os
import re
import time
import urllib.error
import urllib.request

PROTOCOL_VERSION = "2025-06-18"
UA = "batang-python"          # urllib's own User-Agent is refused by the site's CDN (Cloudflare 1010)


class BatangError(Exception):
    """An error answer of a tool; .code is the kind (bad_request, rejected, query_failed, quota, …)."""

    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code, self.message = code, message


class Unauthorized(Exception):
    """The server did not accept the token (missing, expired or revoked)."""


def _parse_error(text):
    try:
        j = json.loads(text[text.index("{"):])
        return BatangError(j.get("error", "error"), j.get("message", text))
    except (ValueError, AttributeError):
        return BatangError("error", text)


def _retry_after(e, body):
    """Seconds to wait before retrying a 429 that is a per-minute rate limit (not the daily quota), or None."""
    h = e.headers.get("Retry-After") if e.headers is not None else None
    if h and h.strip().isdigit():
        return min(int(h), 65)
    m = re.search(r"(\d+)\s*초", body) if ("분당" in body or "per minute" in body) else None
    return min(int(m.group(1)) + 1, 65) if m else None


class Transport:
    def __init__(self, url, token, timeout=600, opener=None):
        self.url, self.timeout = url, timeout
        self.token = token                      # callable returning the bearer token
        self.session_id = None
        self._ids = itertools.count(1)
        self._open = opener or urllib.request.urlopen
        self.sleep = time.sleep

    def _urlopen(self, make_req):
        """Open a request, waiting out per-minute rate limits (HTTP 429 with a retry time) a few times."""
        for attempt in range(4):
            try:
                return self._open(make_req(), timeout=self.timeout)
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == 3:
                    raise
                body = e.read().decode("utf-8", "replace")
                wait = _retry_after(e, body)
                if wait is None:
                    raise BatangError("quota", body[:500]) from None
                self.sleep(wait)

    def _headers(self, extra=None):
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
             "Authorization": "Bearer " + self.token(), "User-Agent": UA}
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
            h["MCP-Protocol-Version"] = PROTOCOL_VERSION
        h.update(extra or {})
        return h

    def _post(self, msg):
        data = json.dumps(msg).encode()
        try:
            r = self._urlopen(lambda: urllib.request.Request(self.url, data=data, headers=self._headers(), method="POST"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise Unauthorized(e.read().decode("utf-8", "replace")[:300]) from None
            if e.code == 404 and self.session_id:          # the server forgot the session (restart): start a new one
                self.session_id = None
                raise ConnectionResetError("session expired") from None
            raise BatangError(f"http_{e.code}", e.read().decode("utf-8", "replace")[:500]) from None
        with r:
            sid = r.headers.get("Mcp-Session-Id")
            if sid:
                self.session_id = sid
            ctype = r.headers.get("Content-Type", "")
            body = r.read().decode("utf-8")
        if "id" not in msg:
            return None
        msgs = []
        if "text/event-stream" in ctype:
            data = []
            for line in body.splitlines() + [""]:
                if line.startswith("data:"):
                    data.append(line[5:].lstrip())
                elif not line.strip() and data:
                    msgs.append(json.loads("\n".join(data)))
                    data = []
        elif body.strip():
            j = json.loads(body)
            msgs = j if isinstance(j, list) else [j]
        for m in msgs:
            if m.get("id") == msg["id"]:
                if "error" in m:
                    raise BatangError("rpc", m["error"].get("message", str(m["error"])))
                return m.get("result")
        raise BatangError("protocol", "no answer to the request")

    def _initialize(self):
        self._post({"jsonrpc": "2.0", "id": next(self._ids), "method": "initialize",
                    "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                               "clientInfo": {"name": "batang-python", "version": "0.3.0"}}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def request(self, method, params):
        for attempt in range(2):
            if self.session_id is None:
                self._initialize()
            try:
                return self._post({"jsonrpc": "2.0", "id": next(self._ids), "method": method, "params": params})
            except ConnectionResetError:
                if attempt:
                    raise BatangError("protocol", "the server keeps dropping the session") from None

    def tools(self):
        return self.request("tools/list", {}).get("tools", [])

    def call(self, name, args):
        """One tool call; returns the tool's JSON answer, raises BatangError for an error answer."""
        res = self.request("tools/call", {"name": name, "arguments": {k: v for k, v in args.items()}})
        text = "".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        if res.get("isError"):
            raise _parse_error(text)
        try:
            return json.loads(text)
        except ValueError:
            return {"text": text}

    def fetch(self, url, dest=None, expected_size=None):
        """GET a result or file link with the token: bytes, or written to dest (skipped when dest already has the
        expected size; written to dest.part first, then renamed)."""
        if url.startswith("file://"):
            path = url[7:]
            if dest is None:
                with open(path, "rb") as f:
                    return f.read()
            import shutil
            shutil.copyfile(path, dest)
            return dest
        if dest is not None and expected_size is not None and os.path.isfile(dest) and os.path.getsize(dest) == expected_size:
            return dest
        try:
            r = self._urlopen(lambda: urllib.request.Request(url, headers={"Authorization": "Bearer " + self.token(),
                                                                             "User-Agent": UA}))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise Unauthorized(e.read().decode("utf-8", "replace")[:300]) from None
            raise BatangError(f"http_{e.code}", e.read().decode("utf-8", "replace")[:500]) from None
        with r:
            if dest is None:
                return r.read()
            os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
            part = dest + ".part"
            with open(part, "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
        if expected_size is not None and os.path.getsize(part) != expected_size:
            raise BatangError("incomplete", f"{os.path.basename(dest)}: got {os.path.getsize(part)} of {expected_size} bytes")
        os.replace(part, dest)
        return dest
