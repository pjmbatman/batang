"""A small stand-in for the Batang server (MCP Streamable HTTP + links + device login + the /dl routes of approved
downloads and a bucket behind them), for the client tests."""
import io
import json
import os
import re
import secrets
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

TOKEN = "btg_test_token"
OTHER = "btg_other_token"          # a signed-in account that owns no grant
LICENSES = {"SYN": {"license": "CC-BY-4.0", "commercial_use": "allowed", "cite": "10.0/syn"}}


def make_cell(folder, n_cycles=4, per=50, kind="aging"):
    """A synthetic cell in the 2.0 store layout: samples, cycles, meta."""
    os.makedirs(folder, exist_ok=True)
    cyc = np.repeat(np.arange(n_cycles, dtype=np.int32), per)
    t = np.tile(np.arange(per, dtype=float), n_cycles)
    v = (3.0 + 1.2 * np.sin(np.linspace(0, 3.14, per))).astype(np.float32)
    ts = pd.DataFrame({"cycle": cyc, "step": np.zeros_like(cyc), "step_type": pd.Categorical(["cc_discharge"] * len(cyc)),
                       "cycle_time_s": t, "test_time_s": t + cyc * per, "voltage_v": np.tile(v, n_cycles),
                       "current_a": np.full(len(cyc), -1.0, np.float32), "charge_ah": np.zeros(len(cyc), np.float32),
                       "discharge_ah": (t / 3600).astype(np.float32), "temperature_c": np.full(len(cyc), 25.0, np.float32),
                       "quality_flags": np.where(np.arange(len(cyc)) % 10 == 3, 2, 0).astype(np.uint8)})
    tbl = pa.Table.from_pandas(ts, preserve_index=False)
    pq.write_table(tbl, os.path.join(folder, "samples.parquet"), row_group_size=per)
    c = pd.DataFrame({"cycle": np.arange(n_cycles, dtype=np.int32), "cycle_kind": [kind] * (n_cycles - 1) + ["rpt"],
                      "efc": np.arange(n_cycles, dtype=float), "soh": np.linspace(1, 0.9, n_cycles),
                      "test_time_start_s": np.arange(n_cycles) * float(per), "duration_s": np.full(n_cycles, float(per)),
                      "n_samples": np.full(n_cycles, per, np.int32), "n_steps": np.ones(n_cycles, np.int32),
                      "charge_ah": np.ones(n_cycles), "discharge_ah": np.ones(n_cycles), "charge_wh": np.ones(n_cycles),
                      "discharge_wh": np.ones(n_cycles), "coulombic_efficiency": np.ones(n_cycles),
                      "charge_c_rate": np.ones(n_cycles), "discharge_c_rate": np.ones(n_cycles),
                      "voltage_max_v": np.full(n_cycles, 4.2), "voltage_min_v": np.array([3.0, 2.7, 3.0, 2.6][:n_cycles]),
                      "current_max_a": np.ones(n_cycles), "current_min_a": -np.ones(n_cycles),
                      "temperature_min_c": np.full(n_cycles, 25.0), "temperature_max_c": np.full(n_cycles, 25.0),
                      "temperature_mean_c": np.full(n_cycles, 25.0), "is_complete": [True, True, False, True][:n_cycles],
                      "is_off_protocol": [False] * n_cycles, "is_capacity_outlier": [False, True, False, False][:n_cycles],
                      "has_time_gap": [False] * n_cycles,
                      "procedure": ["cycling"] * n_cycles, "procedures": [["cycling"]] * n_cycles,
                      "procedure_source": ["detected"] * n_cycles})
    c.to_parquet(os.path.join(folder, "cycles.parquet"), index=False)
    with open(os.path.join(folder, "meta.json"), "w") as f:
        json.dump({"cell_id": os.path.basename(folder), "schema_version": "2.0.0"}, f)


class Fake:
    """State of the fake server: the store folder, the tool calls seen, and links."""

    def __init__(self, store, big_rows=None):
        self.store, self.calls, self.links, self.big_rows = store, [], {}, big_rows
        self.device_polls = 0
        self.rate_limited = 0                 # answer this many file requests with a per-minute 429 first
        self.grants, self.bucket, self.dl_log = {}, {}, []       # grant id -> state; signed key -> path; redirects
        self.cut = {}                         # file name -> bytes after which the bucket drops the connection (once)
        self.bucket_delay, self.active, self.max_active = 0.0, 0, 0
        self.lock = threading.Lock()
        self.records = [{"id": "SYN_A", "dataset": "SYN", "kind": "cell", "cathode_family": "LFP", "size_code": "18650", "n_cycles": 4, "soh_end": 0.9},
                        {"id": "SYN_B", "dataset": "SYN", "kind": "cell", "cathode_family": "NMC", "size_code": "21700", "n_cycles": 8, "soh_end": 0.8}]

    def link(self, path, once=True):
        tok = secrets.token_hex(8)
        self.links[tok] = (path, once)
        return tok

    def grant(self, ids, status="approved", reason=None, per_file=3, files=("samples.parquet", "cycles.parquet", "meta.json"),
              size_delta=0):
        """An approved (or pending, rejected ...) download grant of these records; size_delta skews the listed sizes."""
        gid = "G-20261029-" + "".join(secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567") for _ in range(4))
        names = {f"SYN/{i}/{f}": os.path.join(self.store, "SYN", i, f) for i in ids for f in files}
        self.grants[gid] = {"status": status, "reason": reason, "token": secrets.token_urlsafe(16), "files": names,
                            "left": {n: per_file for n in names}, "per_file": per_file, "size_delta": size_delta}
        return gid

    def manifest(self, gid, base):
        g = self.grants[gid]
        return {"grant": gid, "status": "approved", "expires_at": "2026-11-05T00:00:00+00:00", "per_file_max": g["per_file"],
                "files": [{"name": n, "size": os.path.getsize(p) + g["size_delta"], "left": g["left"][n],
                           "url": f"{base}/dl/{gid}/{g['token']}/{n}"} for n, p in g["files"].items()],
                "licenses": LICENSES, "terms": "Follow each dataset's licence, cite it and Batang; do not redistribute."}

    def table_link(self, df):
        buf = io.BytesIO()
        df.to_parquet(buf, index=False)
        p = os.path.join(self.store, f"result_{secrets.token_hex(4)}.parquet")
        with open(p, "wb") as f:
            f.write(buf.getvalue())
        return p

    def tool(self, name, a, base):
        self.calls.append((name, a))
        if name == "info":
            return {"release": "2.0", "cell_store": {"schema_version": "2.0.0", "totals": {"cells": 2}},
                    "device_store": {"schema_version": "2.0.0", "totals": {}}, "records": {"cells": 2},
                    "datasets": [{"dataset": "SYN", "cells": 2, "tasks": ["aging"], "cathode_families": ["LFP", "NMC"]}]}
        if name == "stats":
            out = {"grain": a.get("grain", "record"), "rows": [{"n": 2}]}
            if "level" in a and a["level"] in ("record", "cycle", "segment"):
                out["renamed"] = {"level": "grain"}
            return out
        if name == "find_records":
            rows = [r for r in self.records
                    if all(r.get(k) == v for k, v in a.items() if k in ("cathode_family", "dataset", "size_code"))]
            if self.big_rows:
                p = self.table_link(pd.DataFrame(rows))
                return {"matched": len(rows), "by_kind": {"cell": len(rows)}, "records": rows[:1],
                        "full_result": {"table": "records", "rows": self.big_rows, "links": {"parquet": f"{base}/mcp/results/{self.link(p)}"}}}
            return {"matched": len(rows), "by_kind": {"cell": len(rows)}, "by_dataset": {"SYN": len(rows)}, "records": rows}
        if name == "describe":
            return {"id": a["id"], "kind": "cell", "dataset": "SYN"}
        if name == "cycles":
            out = []
            for i in a["ids"]:
                df = pd.read_parquet(os.path.join(self.store, "SYN", i, "cycles.parquet"))
                df.insert(0, "id", i)
                out.append(df[["id", "cycle", "soh"]])
            return {"table": "cycles", "rows": pd.concat(out).to_dict("records")}
        if name == "cycle_samples":
            df = pd.read_parquet(os.path.join(self.store, "SYN", a["id"], "samples.parquet"))
            df = df[df["cycle"] == a["cycle"]][["cycle_time_s", "voltage_v"]]
            return {"id": a["id"], "cycle": a["cycle"], "samples_in_window": len(df), "reduced": False,
                    "rows": df.to_dict("records")}
        if name == "query":
            if "boom" in a["sql"]:
                raise ToolErr({"error": "rejected", "message": "only one SELECT"})
            return {"rows": 1, "columns": ["n"], "types": ["int64"], "seconds": 0.01, "data": [{"n": 2}]}
        raise ToolErr({"error": "bad_request", "message": f"no tool {name}"})


class ToolErr(Exception):
    pass


def serve(fake):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _auth(self):
            return self.headers.get("Authorization") == "Bearer " + TOKEN

        def _json(self, code, obj, ctype="application/json"):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n).decode()
            if self.path.startswith("/auth/device/"):
                p = {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}
                if self.path.endswith("start"):
                    return self._json(200, {"device_code": "dev1", "user_code": "ABCD-EFGH", "verification_uri": "http://x/auth/device",
                                            "expires_in": 600, "interval": 0})
                fake.device_polls += 1
                if fake.device_polls < 2:
                    return self._json(400, {"error": "authorization_pending"})
                return self._json(200, {"access_token": TOKEN, "token_type": "Bearer", "expires_at": 9e12, "token_id": "t1"})
            if not self._auth():
                return self._json(401, {"error": "invalid_token"})
            msg = json.loads(raw)
            if "id" not in msg:
                self.send_response(202)
                self.end_headers()
                return
            if msg["method"] == "initialize":
                body = "event: message\ndata: " + json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {"protocolVersion": "2025-06-18"}}) + "\n\n"
                b = body.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Mcp-Session-Id", "s1")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
                return
            if msg["method"] == "tools/list":
                return self._json(200, {"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": [{"name": "info"}]}})
            base = f"http://127.0.0.1:{self.server.server_port}"
            try:
                out, err = fake.tool(msg["params"]["name"], msg["params"]["arguments"], base), False
            except ToolErr as e:
                out, err = e.args[0], True
            text = json.dumps(out, default=str)
            if err:
                text = "Error executing tool: " + text
            res = {"content": [{"type": "text", "text": text}], "isError": err}
            body = ("event: message\ndata: " + json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": res}) + "\n\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send(self, code, body=b"", headers=None):
            self.send_response(code)
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _dl(self, parts):
            """/dl/<grant>/manifest.json (token), /dl/<grant>/<link token>/urls.txt and .../<dataset>/<id>/<file>."""
            base = f"http://127.0.0.1:{self.server.server_port}"
            if not (self.headers.get("User-Agent") or "").startswith("batang-"):   # the CDN refuses urllib's default
                return self._send(403, b"error code: 1010")
            g = fake.grants.get(parts[0])
            if parts[1:] == ["manifest.json"]:
                who = self.headers.get("Authorization")
                if who not in ("Bearer " + TOKEN, "Bearer " + OTHER):
                    return self._json(401, {"error": "invalid_token"})
                if g is None:
                    return self._json(404, {"error": "not_found"})
                if who != "Bearer " + TOKEN:
                    return self._json(403, {"error": "forbidden"})
                if g["status"] != "approved":
                    return self._json(409, {"status": g["status"], "reason": g["reason"] or ""})
                return self._json(200, fake.manifest(parts[0], base))
            if g is None or len(parts) < 3 or parts[1] != g["token"]:
                return self._json(404, {"error": "not_found"})
            if parts[2:] == ["urls.txt"]:
                urls = [f["url"] for f in fake.manifest(parts[0], base)["files"]]
                return self._send(200, ("\n".join(urls) + "\n").encode(), {"Content-Type": "text/plain"})
            name = "/".join(parts[2:])
            if g["status"] != "approved":
                return self._json(410, {"error": g["status"]})
            if name not in g["files"]:
                return self._json(404, {"error": "not_in_grant"})
            rng = self.headers.get("Range")
            with fake.lock:
                if not (rng and not rng.startswith("bytes=0-")):        # a resume does not use up a download
                    if g["left"][name] <= 0:
                        return self._send(410, "이 파일의 다운로드 횟수를 모두 썼습니다.".encode())
                    g["left"][name] -= 1
                fake.dl_log.append((parts[0], name, rng))
                key = secrets.token_hex(8)
                fake.bucket[key] = (g["files"][name], name)
            return self._send(302, b"", {"Location": f"{base}/bucket/{key}/{parts[-1]}"})

        def _bucket(self, key):
            """A presigned GET: no Authorization header allowed (S3 refuses two kinds of authentication), Range honoured."""
            if self.headers.get("Authorization"):
                return self._send(400, b"InvalidArgument: only one auth mechanism allowed")
            e = fake.bucket.get(key)
            if e is None:
                return self._send(403, b"AccessDenied")
            path, name = e
            with open(path, "rb") as f:
                b = f.read()
            with fake.lock:
                fake.active += 1
                fake.max_active = max(fake.max_active, fake.active)
            try:
                time.sleep(fake.bucket_delay)
                start = 0
                m = re.match(r"bytes=(\d+)-$", self.headers.get("Range") or "")
                if m:
                    start = int(m.group(1))
                    if start >= len(b):
                        return self._send(416, b"InvalidRange", {"Content-Range": f"bytes */{len(b)}"})
                cut = fake.cut.pop(name, None)
                self.send_response(206 if m else 200)
                if m:
                    self.send_header("Content-Range", f"bytes {start}-{len(b) - 1}/{len(b)}")
                self.send_header("Content-Length", str(len(b) - start))
                self.end_headers()
                self.wfile.write(b[start:] if cut is None else b[start:start + cut])
                self.close_connection = True
            finally:
                with fake.lock:
                    fake.active -= 1

        def do_GET(self):
            parts = self.path.split("?")[0].strip("/").split("/")
            if parts[0] == "dl" and len(parts) >= 3:
                return self._dl(parts[1:])
            if parts[0] == "bucket" and len(parts) >= 2:
                return self._bucket(parts[1])
            if not self._auth():
                return self._json(401, {"error": "invalid_token"})
            if fake.rate_limited:
                fake.rate_limited -= 1
                b = "요청 한도(분당 120회)에 닿았습니다. 3초 뒤에 다시 시도하세요.".encode()
                self.send_response(429)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
                return
            tok = self.path.rsplit("/", 1)[-1]
            e = fake.links.get(tok)
            if e is None:
                return self._json(404, {"error": "gone"})
            path, once = e
            if once:
                del fake.links[tok]
            with open(path, "rb") as f:
                b = f.read()
            self.send_response(200)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
