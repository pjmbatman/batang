"""batang command line.

    batang login | logout | whoami
    batang info
    batang find tasks=aging cathode_family=LFP [--limit 20] [--csv out.csv]
    batang schema 전압
    batang download --grant G-20261029-AB12 [--to DIR] [--jobs 8]
    batang ls

Record files are requested in the hub's 다운로드 tab (https://batanghub.com/#/downloads); `batang download --grant`
fetches an approved request (into the cache when --to is not given).
"""
import argparse
import json
import os
import sys

from . import AuthError, BatangError, connect, validate
from .grants import human_size


def _kv(pairs):
    out = {}
    for p in pairs or []:
        if "=" not in p:
            raise SystemExit(f"expected key=value, got {p!r}")
        k, v = p.split("=", 1)
        try:
            v = json.loads(v)
        except ValueError:
            pass
        out[k] = v
    return out


def main(argv=None):
    try:
        return _main(argv)
    except (BatangError, AuthError) as e:
        print(f"batang: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


def _main(argv=None):
    ap = argparse.ArgumentParser(prog="batang", description="Batang client")
    ap.add_argument("--url", default=None, help="MCP endpoint (default https://api.batanghub.com/mcp or $BATANG_URL)")
    ap.add_argument("--cache", default="~/batang_cache")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login")
    sub.add_parser("logout")
    sub.add_parser("whoami")
    sub.add_parser("info")
    f = sub.add_parser("find")
    f.add_argument("filters", nargs="*", help="key=value, e.g. tasks=aging cathode_family=LFP level=pack")
    f.add_argument("--limit", type=int, default=20)
    f.add_argument("--csv", default=None, help="write every matching record to this CSV")
    s = sub.add_parser("schema")
    s.add_argument("term", nargs="?")
    d = sub.add_parser("download", help="fetch the files of an approved request of the hub's 다운로드 tab")
    d.add_argument("--grant", required=True, help="the request's grant id (G-yyyymmdd-XXXX)")
    d.add_argument("--to", default=None, help="folder; files go to <to>/<release>/<dataset>/<id>/ (default: the cache)")
    d.add_argument("--jobs", type=int, default=8, help="files downloaded at a time")
    sub.add_parser("ls")
    v = sub.add_parser("validate")
    v.add_argument("path")
    a = ap.parse_args(argv)

    if a.cmd == "validate":
        r = validate(a.path)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["ok"] else 1
    db = connect(url=a.url, cache=a.cache, login=True)
    if a.cmd == "login":
        db.login()
    elif a.cmd == "logout":
        db.logout()
        print("Logged out (the cached token is removed).")
    elif a.cmd == "whoami":
        print(json.dumps(db.whoami(), ensure_ascii=False, indent=1))
    elif a.cmd == "info":
        i = db.info()
        schema = i.get("schema_version") or (i.get("cell_store") or i.get("device_store") or {}).get("schema_version")
        print(f"release {db.release} · schema {schema} · {i.get('records')}")
        for ds in i.get("datasets", []):
            print(f"  {ds['dataset']:24s} {str(ds.get('store', '')):7s} cells {ds.get('cells', 0):5d} devices {ds.get('devices', 0):4d} "
                  f"sessions {ds.get('sessions', 0):6d}  {ds.get('license', '')}  {ds.get('commercial_use', '')}")
    elif a.cmd == "find":
        df = db.find_records(**_kv(a.filters))
        print(f"{df.attrs.get('matched', len(df))} records · {df.attrs.get('by_kind', {})}")
        print(df.head(a.limit).to_string(index=False))
        if a.csv:
            df.to_csv(a.csv, index=False)
            print(f"wrote {len(df)} rows to {a.csv}")
    elif a.cmd == "schema":
        r = db.schema(a.term)
        print(r.to_string(index=False) if hasattr(r, "to_string") else json.dumps(r, ensure_ascii=False, indent=1))
    elif a.cmd == "download":
        paths = db.fetch_grant(a.grant, to=a.to, jobs=a.jobs)
        total = sum(os.path.getsize(p) for p in paths)
        print(f"{len(paths)} files, {human_size(total)} in {os.path.dirname(os.path.commonpath(paths)) if paths else '-'}")
    elif a.cmd == "ls":
        root = os.path.abspath(os.path.expanduser(a.cache))
        if not os.path.isdir(root):
            print(f"{root}: empty")
            return 0
        for rel in sorted(os.listdir(root)):
            p = os.path.join(root, rel, "index.json")
            if os.path.isfile(p):
                with open(p, encoding="utf-8") as fh:
                    recs = json.load(fh).get("records", {})
                n = sum(sum(e.get("files", {}).values()) for e in recs.values())
                print(f"{rel}: {len(recs)} records, {human_size(n)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
