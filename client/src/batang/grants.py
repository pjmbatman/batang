"""Approved downloads: the files of a download grant, fetched straight from its links.

Whole record files (samples, cycles or segments, meta ...) are requested in the hub's 다운로드 tab
(https://batanghub.com/#/downloads). Once the owner approves a request, its grant lists links that are valid for a
limited time and a limited number of downloads per file:

    batang download --grant G-20261029-AB12 --to ~/batang_data [--jobs 8]
    batang.fetch_grant("G-20261029-AB12", "~/batang_data")
    store = batang.open("~/batang_data/2.0")

GET <api>/dl/<grant>/manifest.json (with your login token) lists the files, their sizes, the downloads left and the
datasets' licences. Each file link needs no token: it answers with a redirect to the file in the bucket. Files are
written to <to>/<release>/<dataset>/<id>/<file>, with index.json, LICENSES.json and selections/grant-<id>.json, so
batang.open() and the client's local-first reads use them. A file that is already there with its size is not asked
for again; an interrupted one is resumed with a Range request, which does not use up one of its downloads.
"""
import concurrent.futures
import datetime
import http.client
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request

import pyarrow.parquet as pq

from . import _auth
from ._names import SAMPLES
from ._transport import UA, BatangError

DOWNLOADS_TAB = "https://batanghub.com/#/downloads"
GRANT_ID = re.compile(r"^G-\d{8}-[A-Z0-9]{4}$")
TRIES = 6                  # requests per file before giving up (a resume after a dropped connection is one more)
CHUNK = 1 << 20
STATUS = {"pending": "is waiting for the owner's approval; the 다운로드 tab shows when it is decided",
          "rejected": "was rejected", "revoked": "was revoked", "cancelled": "was cancelled",
          "expired": "has expired; request the files again in the 다운로드 tab"}
USE = {"allowed": "commercial use allowed", "not_allowed": "NO commercial use",
       "unclear": "commercial use unclear: ask the owner"}
TERMS = "follow each dataset's licence, cite it and Batang, do not redistribute"


def human_size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000.0


def _body(e):
    try:
        return e.read().decode("utf-8", "replace")
    except OSError:
        return ""


# ---------------------------------------------------------------- the manifest

def manifest(client, grant):
    """The grant's manifest (files with size, downloads left and link; licences; terms), read with the login token."""
    url = f"{_auth.origin_of(client.url)}/dl/{grant}/manifest.json"
    for attempt in range(2):
        try:
            r = client.t._urlopen(lambda: urllib.request.Request(url, headers={
                "Authorization": "Bearer " + client._bearer(), "Accept": "application/json", "User-Agent": UA}))
            with r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = _body(e)
            if e.code == 401:
                if not client._relogin(attempt):
                    raise _auth.AuthError("the server did not accept the token: run `batang login`") from None
                continue
            if e.code == 403:
                raise BatangError("forbidden", f"{grant} is not a download grant of the signed-in account") from None
            if e.code == 404:
                raise BatangError("not_found", f"there is no download grant {grant}") from None
            if e.code == 409:
                try:
                    j = json.loads(body)
                except ValueError:
                    j = {}
                st = j.get("status") or "not_approved"
                msg = f"{grant} {STATUS.get(st, 'is ' + st)}"
                raise BatangError(st, msg + (f": {j['reason']}" if j.get("reason") else "")) from None
            raise BatangError(f"http_{e.code}", body[:500]) from None
    raise _auth.AuthError("the server did not accept the token: run `batang login`")


def _dest(root, name):
    parts = str(name).split("/")
    if len(parts) != 3 or any(p in ("", ".", "..") or "\\" in p for p in parts):
        raise BatangError("bad_manifest", f"unexpected file name {name!r} in the manifest")
    return os.path.join(root, *parts)


# ---------------------------------------------------------------- one file

def _gone(e, name, body):
    try:
        j = json.loads(body)
        body = str(j.get("message") or j.get("reason") or j.get("error") or body) if isinstance(j, dict) else body
    except ValueError:
        pass
    if e.code == 410:
        return BatangError("gone", f"{name}: {body.strip()[:200] or 'no downloads left, or the grant expired or was revoked'}")
    if e.code == 404:
        return BatangError("not_found", f"{name} is not in the grant")
    return BatangError(f"http_{e.code}", f"{name}: {body.strip()[:200]}")


def _copy(r, part, mode):
    """Write the response body to part; False when the connection dropped before the end (the bytes so far stay)."""
    with open(part, mode) as out:
        while True:
            try:
                b = r.read(CHUNK)
            except (http.client.HTTPException, OSError):
                return False
            if not b:
                return True
            out.write(b)


def fetch_file(f, dest, opener=urllib.request.urlopen, sleep=None, timeout=600):
    """Download one manifest entry to dest (through dest.part): "skipped" when dest already has the size,
    "downloaded" otherwise. Redirects are followed; an interrupted transfer is resumed from the bytes it has."""
    sleep = sleep or time.sleep
    size, name = int(f["size"]), f["name"]
    if os.path.isfile(dest) and os.path.getsize(dest) == size:
        return "skipped"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    for attempt in range(TRIES):
        have = os.path.getsize(part) if os.path.isfile(part) else 0
        if have > size:
            os.remove(part)
            have = 0
        if have and have == size:
            break
        headers = {"User-Agent": UA}           # never the login token: the link is the key, and the bucket refuses it
        if have:
            headers["Range"] = f"bytes={have}-"
        try:
            r = opener(urllib.request.Request(f["url"], headers=headers), timeout=timeout)
        except urllib.error.HTTPError as e:
            body = _body(e)
            if e.code == 416 and have:         # the part is as long as the object, or longer: not this file
                os.remove(part)
                raise BatangError("size", f"{name}: the server's file is shorter than the {size} bytes the grant lists") from None
            if e.code == 429 or e.code >= 500:
                h = e.headers.get("Retry-After") if e.headers is not None else None
                sleep(min(int(h), 65) if h and h.strip().isdigit() else min(2 ** attempt, 30))
                continue
            raise _gone(e, name, body) from None
        except (urllib.error.URLError, http.client.HTTPException, OSError):
            sleep(min(2 ** attempt, 30))
            continue
        with r:
            if have and r.status == 206:
                m = re.match(r"bytes (\d+)-", r.headers.get("Content-Range", ""))
                if not m or int(m.group(1)) != have:
                    raise BatangError("protocol", f"{name}: the server resumed at the wrong byte")
                mode = "ab"
            else:
                mode = "wb"                        # a whole file (a range the server did not honour starts over)
            whole = _copy(r, part, mode)
        if os.path.getsize(part) >= size:
            break
        if not whole:
            sleep(min(2 ** attempt, 30))
    else:
        have = os.path.getsize(part) if os.path.isfile(part) else 0
        raise BatangError("incomplete", f"{name}: {have} of {size} bytes after {TRIES} tries; run the same "
                                        "command again to resume")
    got = os.path.getsize(part)
    if got != size:
        os.remove(part)
        raise BatangError("size", f"{name}: got {got} bytes, the grant lists {size}")
    os.replace(part, dest)
    return "downloaded"


# ---------------------------------------------------------------- the whole grant

def _kind(folder, files, client, rid):
    if "cycles.parquet" in files:
        return "cell"
    if "segments.parquet" in files:
        return "device"
    p = os.path.join(folder, SAMPLES)
    if os.path.isfile(p):
        names = pq.read_schema(p).names
        if "cycle" in names or "segment" in names:
            return "cell" if "cycle" in names else "device"
    try:
        with open(os.path.join(folder, "meta.json"), encoding="utf-8") as fh:
            meta = json.load(fh)
        if "cell_id" in meta or "device_id" in meta:
            return "cell" if "cell_id" in meta else "device"
    except (OSError, ValueError):
        pass
    return "cell" if client.describe(rid).get("kind") == "cell" else "device"


def note_licenses(root, lic, terms=None, out=None):
    """Keep the licences in <root>/LICENSES.json and say once per dataset what they are."""
    if not lic:
        return
    out = out or sys.stderr
    p = os.path.join(root, "LICENSES.json")
    try:
        with open(p, encoding="utf-8") as f:
            known = json.load(f)
    except (OSError, ValueError):
        known = {}
    new = {d: v for d, v in lic.items() if d not in known}
    known.update(lic)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(known, f, indent=1, ensure_ascii=False)
    for d, v in sorted(new.items()):
        cite = v.get("cite") or v.get("source") or "the original source"
        print(f"batang: {d}: {v.get('license') or 'licence not stated'} "
              f"({USE.get(v.get('commercial_use'), 'see the source')}); cite {cite}"
              + (f" ({v['note']})" if v.get("note") else ""), file=out)
    if new:
        print(f"batang: {terms or TERMS}; list in {p}", file=out)


def fetch(client, grant, to, jobs=8, out=None):
    """Download every file of an approved grant into <to>/<release>/ (see the module docs); returns the paths."""
    out = out or sys.stderr
    grant = str(grant).strip().upper()
    if not GRANT_ID.match(grant):
        raise BatangError("bad_request", f"{grant!r} is not a grant id (G-yyyymmdd-XXXX, from the 다운로드 tab)")
    man = manifest(client, grant)
    release = str(man.get("release") or client.release)
    root = os.path.join(os.path.abspath(os.path.expanduser(to)), release)
    files = man.get("files") or []
    dests = [_dest(root, f["name"]) for f in files]
    os.makedirs(root, exist_ok=True)
    total = sum(int(f["size"]) for f in files)
    print(f"batang: {grant}: {len(files)} files, {human_size(total)}, valid until {man.get('expires_at') or '?'} "
          f"(at most {man.get('per_file_max', '?')} downloads per file) → {root}", file=out)
    lock, done, failed = threading.Lock(), [], []

    def one(f, dest):
        try:
            how = fetch_file(f, dest, opener=client.t._open, sleep=client.t.sleep)
        except BatangError as e:
            with lock:
                failed.append((f["name"], e))
                print(f"batang: failed {f['name']}: {e.message}", file=out)
            return
        with lock:
            done.append((f, dest, how))
            if how == "downloaded":
                print(f"batang: [{len(done)}/{len(files)}] {f['name']} ({human_size(int(f['size']))})", file=out)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, int(jobs))) as ex:
        list(ex.map(one, files, dests))

    idx_path = os.path.join(root, "index.json")
    try:
        with open(idx_path, encoding="utf-8") as fh:
            idx = json.load(fh)
    except (OSError, ValueError):
        idx = {"release": release, "server": client.url, "records": {}}
    recs = idx.setdefault("records", {})
    for f, dest, _ in done:
        ds, rid, fname = f["name"].split("/")
        e = recs.setdefault(rid, {"dataset": ds, "kind": None, "files": {}, "columns": {}})
        e.setdefault("files", {})[fname] = os.path.getsize(dest)
        e.setdefault("columns", {}).pop(fname, None)        # a whole file replaces a column-cut one of client 0.2
    for rid, e in recs.items():
        if e.get("kind") is None:
            e["kind"] = _kind(os.path.join(root, e["dataset"], rid), e.get("files", {}), client, rid)
    with open(idx_path, "w", encoding="utf-8") as fh:
        json.dump(idx, fh, indent=1)
    note_licenses(root, man.get("licenses") or {}, man.get("terms"), out=out)
    sel_dir = os.path.join(root, "selections")
    os.makedirs(sel_dir, exist_ok=True)
    with open(os.path.join(sel_dir, f"grant-{grant}.json"), "w", encoding="utf-8") as fh:   # the links stay out
        json.dump({"grant": grant, "release": release, "server": client.url, "expires_at": man.get("expires_at"),
                   "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
                   "files": [{"name": f["name"], "size": f["size"]} for f in files],
                   "licenses": man.get("licenses") or {}}, fh, indent=1, ensure_ascii=False)
    new = sum(1 for _, _, how in done if how == "downloaded")
    print(f"batang: {new} downloaded, {len(done) - new} already there, {len(failed)} failed", file=out)
    if failed:
        raise BatangError("incomplete", f"{len(failed)} of {len(files)} files failed ("
                          + "; ".join(e.message for _, e in failed[:5]) + (" ..." if len(failed) > 5 else "")
                          + f"); the others are in {root}")
    return [d for f, d in zip(files, dests) if os.path.isfile(d)]
