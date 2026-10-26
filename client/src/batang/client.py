"""batang.Client: the Batang operations from Python.

    db = batang.connect()                               # https://batang.yonsei.ac.kr, login on first use
    db.find_records(tasks="aging", cathode_family="LFP")
    db.cycles(["STROEBL_S1_k01_01"], kind="aging", columns=["efc", "soh"])
    db.cycle_samples("STROEBL_S1_k01_01", 12, columns=["voltage_v", "current_a"])
    db.query("SELECT cathode_family, count(*) FROM cells GROUP BY 1")
    sel = db.select(tasks="aging", cathode_family="NMC"); sel.size(); sel.download()

The methods are the tools of the Batang MCP server, with the same names and arguments. What a method reads comes
from your download cache when it is there (same release), otherwise from the server; df.attrs["source"] says which
("local", "remote" or "mixed"). Nothing is downloaded unless you call download() or download_catalog().

Names are those of schema 2.0 (DATA_FORMAT.md). In release 2.0, 1.x names in arguments (columns, where, metric,
group_by, filters such as task / cell_format / unit_level / domain, stats(level="cycle"), download file kinds) are
translated with a FutureWarning, as are the names the server reports it translated ("renamed" in an answer).
"""
import datetime
import hashlib
import io
import json
import os
import sys

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from . import _auth
from . import _names as N
from ._names import QUALITY, SAMPLES, TABLE_FILES, TIME_COLUMN
from ._transport import BatangError, Transport, Unauthorized
from .local import LocalStore

LARGE = 10 ** 9            # a remote read above this many bytes needs allow_large=True (or download it)
# sample-file columns a column-cut download always keeps
CUT_KEEP = ("cycle", "segment", "step", "block", "step_type", "operating_state", "cycle_time_s", "segment_time_s",
            "test_time_s")


class SizeError(BatangError):
    """A remote read larger than LARGE bytes without allow_large=True."""

    def __init__(self, nbytes, what):
        super().__init__("too_large", f"{what} is about {nbytes / 1e9:.1f} GB; download() it once and read it locally, "
                                      "or pass allow_large=True")
        self.nbytes = nbytes


class OfflineError(BatangError):
    def __init__(self, what):
        super().__init__("offline", f"{what} is not in the local cache and the client is offline")


def _release_key(info):
    rel = info.get("release") or (info.get("cell_store") or {}).get("release")
    if rel:
        return str(rel)
    c = info.get("cell_store") or {}
    u = info.get("device_store") or info.get("unit_store") or {}
    fp = json.dumps([c.get("schema_version"), c.get("totals"), u.get("schema_version"), u.get("totals")], sort_keys=True)
    return f"s{c.get('schema_version', 'x')}-{hashlib.sha1(fp.encode()).hexdigest()[:8]}"


def _cut_parquet(src, dest, columns):
    """Keep only these columns of a Parquet file, with its row groups (one per cycle or segment, for skipping) and its
    encodings (byte-stream-split floats, dictionary-coded rest), so the cut file is smaller than the original."""
    f = pq.ParquetFile(src)
    schema = f.schema_arrow
    floats = [c for c in columns if pa.types.is_floating(schema.field(c).type)]
    tmp = dest + ".part"
    with pq.ParquetWriter(tmp, pa.schema([schema.field(c) for c in columns], metadata=schema.metadata),
                          compression="zstd", use_dictionary=[c for c in columns if c not in floats],
                          use_byte_stream_split=floats or False) as w:
        for g in range(f.num_row_groups):
            w.write_table(f.read_row_group(g, columns=columns))
    os.replace(tmp, dest)


def _drop_none(d):
    return {k: v for k, v in d.items() if v is not None}


class Client:
    def __init__(self, url=None, cache="~/batang_cache", release=None, prefer="auto", offline=False, auth_url=None,
                 login="auto", timeout=600, transport=None):
        if prefer not in ("auto", "remote"):
            raise ValueError('prefer must be "auto" or "remote"')
        self.url = (url or os.environ.get("BATANG_URL") or _auth.DEFAULT_URL).rstrip("/")
        self.auth_url = auth_url or os.environ.get("BATANG_AUTH_URL") or self.url
        self.cache = os.path.abspath(os.path.expanduser(cache))
        self.prefer, self.offline = prefer, bool(offline)
        self._login = sys.stdin.isatty() if login == "auto" else bool(login)
        self._release = release
        self._token = None
        self.t = transport or Transport(self.url, self._bearer, timeout=timeout)
        self._local = None

    # ---------------------------------------------------------------- login and calls
    def _bearer(self):
        if self._token is None:
            self._token = _auth.cached(self.auth_url)
        if self._token is None:
            if not self._login:
                raise _auth.AuthError("not logged in: run `batang login` (or set BATANG_TOKEN)")
            self._token = _auth.login(self.auth_url)
        return self._token["access_token"]

    def login(self, open_browser=True):
        """Log in again (device flow in the browser) and keep the new token."""
        self._token = _auth.login(self.auth_url, open_browser=open_browser)
        self.t.session_id = None
        return {k: v for k, v in self._token.items() if k != "access_token"}

    def logout(self):
        _auth.forget(self.auth_url)
        self._token = None
        self.t.session_id = None

    def whoami(self):
        """The token in use (where it comes from, when it expires) and whether the server accepts it."""
        e = _auth.cached(self.auth_url)
        if e is None:
            return {"logged_in": False, "server": self.url}
        ok = True
        try:
            self._token = e
            self.t.tools()
        except (Unauthorized, _auth.AuthError):
            ok = False
        exp = e.get("expires_at")
        return {"logged_in": ok, "server": self.url, "source": e.get("source"), "token_id": e.get("token_id"),
                "expires": datetime.datetime.fromtimestamp(float(exp)).isoformat(timespec="minutes") if exp else None}

    def _call(self, tool, _keep=(), **args):
        if self.offline:
            raise OfflineError(f"{tool}()")
        args = {k: v for k, v in args.items() if v is not None or k in _keep}
        for attempt in range(2):
            try:
                ans = self.t.call(tool, args)
                N.server_renamed(ans)
                return ans
            except Unauthorized:
                if attempt or not self._login or (self._token or {}).get("source") == "BATANG_TOKEN":
                    raise _auth.AuthError("the server did not accept the token: run `batang login`") from None
                _auth.forget(self.auth_url)
                self._token = None
                self.t.session_id = None

    def _fetch_table(self, links, fmt="parquet"):
        data = self.t.fetch(links[fmt])
        return pq.read_table(io.BytesIO(data)).to_pandas()

    def _table(self, ans, key, allow_large=False, what="the result"):
        """ans[key] as a DataFrame; a spilled answer (full_result) is fetched from its link."""
        full = ans.get("full_result")
        if full and full.get("table", key) == key and full.get("links"):
            cols = max(1, len((ans.get(key) or [{}])[0])) if ans.get(key) else 8
            nbytes = full.get("bytes", {}).get("parquet") if isinstance(full.get("bytes"), dict) else None
            nbytes = nbytes or int(full.get("rows", 0)) * cols * 8
            if nbytes > LARGE and not allow_large:
                raise SizeError(nbytes, what)
            return self._fetch_table(full["links"])
        return pd.DataFrame(ans.get(key) or [])

    # ---------------------------------------------------------------- release and cache
    @property
    def release(self):
        if self._release is None:
            if self.offline:
                rels = [d for d in os.listdir(self.cache) if os.path.isfile(os.path.join(self.cache, d, "index.json"))] \
                    if os.path.isdir(self.cache) else []
                if len(rels) != 1:
                    raise OfflineError("the release (pass release=… when the cache holds none or several)")
                self._release = rels[0]
            else:
                self._release = _release_key(self.info())
        return self._release

    @property
    def local(self):
        """The cache folder of this release as a LocalStore (None when nothing is downloaded yet)."""
        root = os.path.join(self.cache, self.release)
        if not os.path.isdir(root):
            return None
        if self._local is None or self._local.path != root:
            self._local = LocalStore(root)
        return self._local

    def _use_local(self):
        return self.offline or self.prefer == "auto"

    # ---------------------------------------------------------------- the tools
    def info(self):
        """Releases, schema versions, datasets with counts and licences, filter vocabularies."""
        return self._call("info")

    def find_records(self, tasks=None, dataset=None, cathode_family=None, form_factor=None, size_code=None, chemistry=None,
                     level=None, setting=None, label_tier=None, commercial_use=None, fault_status=None, kind=None,
                     temp_min=None, temp_max=None, crate_min=None, crate_max=None, text=None, limit=None, **legacy):
        """Cells and devices by their properties → DataFrame (df.attrs: matched, by_kind, by_dataset, by_cathode_family).
        tasks: aging | fault. kind: cell | device | session. level: cell, module, pack, system, vehicle. setting: lab,
        field, field_returned. 1.x filter names (task, cell_format, unit_level, domain) are still accepted."""
        args = _drop_none(dict(tasks=tasks, dataset=dataset, cathode_family=cathode_family, form_factor=form_factor,
                               size_code=size_code, chemistry=chemistry, level=level, setting=setting,
                               label_tier=label_tier, commercial_use=commercial_use, fault_status=fault_status, kind=kind,
                               temp_min=temp_min, temp_max=temp_max, crate_min=crate_min, crate_max=crate_max, text=text,
                               limit=limit))
        args.update(_drop_none(self._legacy_filters(legacy)))
        if self.offline:
            return self._find_local(**args)
        ans = self._call("find_records", **args)
        df = self._table(ans, "records", allow_large=True)
        for k in ("matched", "by_kind", "by_dataset", "by_cathode_family"):
            if k in ans:
                df.attrs[k] = ans[k]
        df.attrs["source"] = "remote"
        return df

    @staticmethod
    def _legacy_filters(legacy):
        bad = [k for k in legacy if k not in N.LEGACY_FILTERS]
        if bad:
            raise TypeError(f"unknown filter {bad[0]!r}")
        return N.filters(legacy)

    def _find_local(self, limit=None, **f):
        p = os.path.join(self.cache, self.release, "catalog.parquet")
        if not os.path.isfile(p):
            raise OfflineError("the catalog (download_catalog() it first)")
        df = pd.read_parquet(p)
        m = pd.Series(True, index=df.index)
        for k, v in f.items():
            if k == "tasks":
                want = set(v if isinstance(v, (list, tuple)) else [v])
                m &= df["tasks"].map(lambda t: bool(want & set(t.split(",") if isinstance(t, str) else
                                                               list(t if t is not None else []))))
            elif k in ("temp_min", "temp_max", "crate_min", "crate_max"):
                col = "ambient_temperature_c" if k.startswith("temp") else "discharge_c_rate_typical"
                if col not in df:
                    raise OfflineError(f"filtering by {k}")
                m &= (df[col] >= v) if k.endswith("min") else (df[col] <= v)
            elif k == "chemistry" and "chemistry_family" in df:
                m &= df["chemistry_family"].isin(v if isinstance(v, (list, tuple)) else [v])
            elif k == "text":
                hay = df["id"].astype(str) + " " + df["dataset"].astype(str)
                for c in ("cathode", "cell_model"):
                    if c in df:
                        hay = hay + " " + df[c].astype(str)
                hay = hay.str.lower()
                for w in str(v).lower().split():
                    m &= hay.str.contains(w, regex=False)
            elif k in df:
                m &= df[k].isin(v if isinstance(v, (list, tuple)) else [v])
            else:
                raise OfflineError(f"filtering by {k}")
        out = df[m]
        res = (out.head(int(limit)) if limit is not None else out).reset_index(drop=True)
        res.attrs.update(matched=int(len(out)), by_kind=out["kind"].value_counts().to_dict(),
                         by_dataset=out["dataset"].value_counts().to_dict(), source="local")
        return res

    def describe(self, id, detail=False):
        """One dataset (its key), cell or device: properties, test conditions, SOH definition or fault labels, quality."""
        return self._call("describe", id=id, detail=bool(detail))

    def stats(self, metric="count", agg="count", group_by=None, grain="record", where=None, kind=None, complete=False,
              exclude_flags=False, record_kind=None, **filters):
        """Aggregates over the catalog (grain="record") or over cycle / segment rows (grain="cycle" / "segment")
        → DataFrame. filters: those of find_records (tasks, dataset, cathode_family, size_code, level, setting ...);
        level is the catalog column (cell, module, pack, system, vehicle). 1.x level="record" / "cycle" / "segment"
        is read as grain."""
        if filters.get("level") in N.GRAINS:
            N._note(f"level={filters['level']!r}", f"grain={filters['level']!r}", stacklevel=3)
            grain = filters.pop("level")
        metric = N.column(metric) if metric != "count" else metric
        group_by, where, filters = N.columns(group_by), N.where(where), N.filters(filters)
        ans = self._call("stats", metric=metric, agg=agg, group_by=group_by, grain=grain, where=where, kind=kind,
                         complete=complete or None, exclude_flags=exclude_flags or None, record_kind=record_kind, **filters)
        df = self._table(ans, "rows", allow_large=True)
        df.attrs.update({k: v for k, v in ans.items() if k != "rows"}, source="remote")
        return df

    def schema(self, term=None, store=None, table=None):
        """What a variable means: meaning (Korean), unit, type, code name, table, values."""
        ans = self._call("schema", term=term, store=store, table=table)
        if term is None:
            return ans
        return pd.DataFrame(ans.get("variables") or [])

    def query(self, sql, local=False, allow_large=False):
        """A read-only SQL SELECT. local=False: on the server (views cells, devices, cycles, segments, samples,
        device_samples; macros cycle_samples(cell_id[, cycle]) / segment_samples(device_id[, segment])).
        local=True: DuckDB over your download cache, with the same view and macro names (cells and devices only when
        the catalog was downloaded; records = the catalog stored by download_catalog())."""
        if local or self.offline:
            return self._query_local(sql)
        ans = self._call("query", sql=sql)
        if "data" in ans:
            df = pd.DataFrame(ans["data"], columns=ans.get("columns"))
        else:
            full = ans.get("full_result") or {}
            nbytes = (full.get("bytes") or {}).get("parquet", 0) if isinstance(full.get("bytes"), dict) else 0
            if nbytes > LARGE and not allow_large:
                raise SizeError(nbytes, "the query result")
            df = self._fetch_table(full["links"])
        df.attrs.update(rows=ans.get("rows"), seconds=ans.get("seconds"), source="remote")
        return df

    def _query_local(self, sql):
        try:
            import duckdb
        except ImportError:
            raise ImportError('local queries need duckdb: pip install "batang[sql]"') from None
        st = self.local
        if st is None:
            raise OfflineError("the cache of this release")
        con = duckdb.connect()

        def q(s):
            return "'" + str(s).replace("'", "''") + "'"
        root = st.path
        cat = os.path.join(root, "catalog.parquet")
        if os.path.isfile(cat):
            con.execute(f"CREATE VIEW records AS SELECT * FROM read_parquet({q(cat)})")
            names = pq.read_schema(cat).names
            if "kind" in names:
                con.execute("CREATE VIEW cells AS SELECT * FROM records WHERE kind = 'cell'")
                con.execute("CREATE VIEW devices AS SELECT * FROM records WHERE kind <> 'cell'")
        groups = {}
        for rid in st.ids:
            rec = st.record(rid)
            idc = "cell_id" if rec.kind == "cell" else "device_id"
            for fname, view in (("cycles.parquet", "cycles"), ("segments.parquet", "segments"),
                                (SAMPLES, "samples" if rec.kind == "cell" else "device_samples")):
                if rec.has(fname):
                    groups.setdefault(view, []).append((idc, rec.dataset, rid, os.path.join(rec.folder, fname)))
        for view, items in groups.items():
            parts = " UNION ALL BY NAME ".join(f"SELECT {q(ds)} AS dataset, {q(rid)} AS {idc}, * FROM read_parquet({q(p)})"
                                               for idc, ds, rid, p in items)
            con.execute(f"CREATE VIEW {view} AS {parts}")
        if "samples" in groups:
            con.execute("CREATE MACRO cycle_samples(i, c := NULL) AS TABLE "
                        "SELECT * FROM samples WHERE cell_id = i AND (c IS NULL OR cycle = c)")
        if "device_samples" in groups:
            con.execute("CREATE MACRO segment_samples(i, s := NULL) AS TABLE "
                        "SELECT * FROM device_samples WHERE device_id = i AND (s IS NULL OR segment = s)")
        df = con.execute(sql).df()
        df.attrs["source"] = "local"
        return df

    def cycles(self, ids, columns=None, kind=None, complete=False, exclude_flags=False, where=None, limit=None,
               allow_large=False):
        """Cycle rows (cells) or segment rows (devices) of the given records → DataFrame with an id column."""
        ids = [ids] if isinstance(ids, str) else list(ids)
        columns, where = N.columns(columns), N.where(where)
        st = self.local if self._use_local() else None
        local_ids, remote_ids = [], []
        for i in ids:
            fname = TABLE_FILES[st._index[i]["kind"]] if st is not None and i in st else None
            (local_ids if fname and st.has(i, fname, N.columns(columns, st._index[i]["kind"])) else remote_ids).append(i)
        frames = []
        for i in local_ids:
            frames.append(st.record(i).cycles(columns=columns, kind=kind, complete=complete, exclude_flags=exclude_flags,
                                              where=where))
        if remote_ids:
            if self.offline:
                raise OfflineError(f"cycles of {remote_ids[:3]}")
            ans = self._call("cycles", ids=remote_ids, columns=columns, kind=kind, complete=complete or None,
                             exclude_flags=exclude_flags or None, where=where)
            frames.append(self._table(ans, "rows", allow_large=allow_large, what="the cycle table"))
        df = pd.concat([f for f in frames if len(f)], ignore_index=True) if any(len(f) for f in frames) else \
            (frames[0] if frames else pd.DataFrame())
        if limit is not None:
            df = df.head(int(limit))
        df.attrs["source"] = "local" if not remote_ids else "remote" if not local_ids else "mixed"
        return df

    def cycle_samples(self, id, cycle, columns=None, t0=None, t1=None, max_points=None, quality="all", allow_large=False):
        """The samples of one cycle (cell) or segment (device), at full resolution unless max_points is given. t0 / t1
        are seconds from the cycle or segment start (cycle_time_s / segment_time_s)."""
        st = self.local if self._use_local() else None
        if st is not None and id in st:
            kind = st._index[id]["kind"]
            cols = N.columns(columns, kind)
            want = None if cols is None else list(dict.fromkeys([TIME_COLUMN[kind]] + list(cols)))
            if st.has(id, SAMPLES, want):
                df = st.record(id).cycle(cycle, columns=cols, t0=t0, t1=t1, max_points=max_points, quality=quality)
                df.attrs["source"] = "local"
                return df
        if self.offline:
            raise OfflineError(f"samples of {id}")
        columns = N.columns(columns)
        res = self._call("cycle_samples", _keep=("max_points",), id=id, cycle=int(cycle), columns=columns, t0=t0, t1=t1,
                         quality=quality, max_points=max_points)      # max_points None → every sample (sent as null)
        df = self._table(res, "rows", allow_large=allow_large, what="the samples")
        df.attrs.update(samples_in_window=res.get("samples_in_window"), reduced=res.get("reduced"), source="remote")
        return df

    # ---------------------------------------------------------------- selection and download
    def select(self, **filters):
        """The records that match the filters of find_records, as a Selection (nothing is downloaded)."""
        df = self.find_records(**filters)
        return Selection(self, list(df["id"]), filters=filters, release=self.release, records=df)

    def _download_links(self, ids=None, files=None, **filters):
        ans = self._call("download", ids=ids, files=N.files(files), **N.filters(filters))
        self._licenses = ans.get("licenses") or {}
        return ans.get("links", [])

    def _note_licenses(self, root):
        """Keep the licences of what was downloaded in <root>/LICENSES.json and say once per dataset what they are."""
        lic = getattr(self, "_licenses", None) or {}
        if not lic:
            return
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
            use = {"allowed": "commercial use allowed", "not_allowed": "NO commercial use", "unclear": "commercial use unclear: ask the owner"}
            print(f"batang: {d}: {v.get('license') or 'licence not stated'} ({use.get(v.get('commercial_use'), 'see the source')}); "
                  f"cite {v.get('source') or 'the original source'}" + (f" ({v['note']})" if v.get("note") else ""), file=sys.stderr)
        if new:
            print(f"batang: follow each dataset's licence, cite it and Batang, do not redistribute; list in {p}", file=sys.stderr)

    def download(self, selection=None, columns=None, to=None, files=None, **filters):
        """Download the files of a Selection, a list of ids or the records matching filters, into the cache (or `to`).
        Files already there with the right size are skipped. files: samples, cycles (cells) / segments (devices), meta,
        samples_preview, cell_voltages, temperatures, aux (default: samples, cycles or segments, meta). columns: keep
        only these sample columns in the stored samples files (the whole file is transferred, then cut; the cycle or
        segment, step, block and time columns and quality_flags are always kept). Returns the local paths."""
        if isinstance(selection, Selection):
            ids = selection.ids
        elif isinstance(selection, str):
            ids = [selection]
        elif selection is not None:
            ids = list(selection)
        else:
            ids = None
        if files is not None:
            files = [files] if isinstance(files, str) else list(files)
        if columns is not None:
            columns = N.columns([columns] if isinstance(columns, str) else columns)
        links = self._download_links(ids=ids, files=files, **filters)
        root = os.path.abspath(os.path.expanduser(to)) if to else os.path.join(self.cache, self.release)
        idx_path = os.path.join(root, "index.json")
        try:
            with open(idx_path, encoding="utf-8") as f:
                idx = json.load(f)
        except (OSError, ValueError):
            idx = {"release": self.release, "server": self.url, "records": {}}
        recs = idx.setdefault("records", {})
        paths = []
        for ln in links:
            dest = os.path.join(root, ln["name"])
            e = recs.setdefault(ln["id"], {"dataset": ln["dataset"], "kind": None, "files": {}, "columns": {}})
            if ln["file"] == "segments.parquet":
                e["kind"] = "device"
            elif ln["file"] == "cycles.parquet":
                e["kind"] = "cell"
            cut = columns is not None and ln["file"] == SAMPLES
            if cut:
                have = e.get("columns", {}).get(ln["file"])
                if have is not None and os.path.isfile(dest) and all(c in have for c in columns):
                    paths.append(dest)
                    continue
                tmp = self.t.fetch(ln["url"], dest + ".full", expected_size=ln["size"])
                names = pq.read_schema(tmp).names
                keep = [c for c in dict.fromkeys(list(CUT_KEEP) + list(columns) + [QUALITY]) if c in names]
                _cut_parquet(tmp, dest, keep)
                os.remove(tmp)
                e.setdefault("columns", {})[ln["file"]] = keep
            else:
                self.t.fetch(ln["url"], dest, expected_size=ln["size"])
                e.setdefault("columns", {}).pop(ln["file"], None)
            e["files"][ln["file"]] = os.path.getsize(dest)
            paths.append(dest)
        for rid, e in recs.items():
            if e.get("kind") is None:
                d = self.describe(rid)
                e["kind"] = "cell" if d.get("kind") == "cell" else "device"
        os.makedirs(root, exist_ok=True)
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=1)
        self._note_licenses(root)
        sel_dir = os.path.join(root, "selections")
        os.makedirs(sel_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        with open(os.path.join(sel_dir, f"download-{stamp}.json"), "w", encoding="utf-8") as f:
            json.dump({"release": self.release, "server": self.url, "ids": sorted({ln["id"] for ln in links}),
                       "filters": filters or None, "columns": columns,
                       "files": [{"name": ln["name"], "size": ln["size"]} for ln in links]}, f, indent=1)
        self._local = None
        return paths

    def download_catalog(self):
        """Store the record catalog of this release in the cache (for find_records() offline). Returns its path."""
        df = self.find_records()
        tasks = {}
        for t in ("aging", "fault"):
            for i in self.find_records(tasks=t)["id"]:
                tasks.setdefault(i, []).append(t)
        df["tasks"] = df["id"].map(lambda i: tasks.get(i, []))
        root = os.path.join(self.cache, self.release)
        os.makedirs(root, exist_ok=True)
        p = os.path.join(root, "catalog.parquet")
        df.to_parquet(p, index=False)
        idx_path = os.path.join(root, "index.json")
        if not os.path.isfile(idx_path):
            with open(idx_path, "w", encoding="utf-8") as f:
                json.dump({"release": self.release, "server": self.url, "records": {}}, f)
        return p


class Selection:
    """A set of records: what to download or read together. Save it to reproduce a data set later."""

    def __init__(self, client, ids, filters=None, release=None, records=None):
        self.client, self.ids, self.filters, self.release, self.records = client, list(ids), filters or {}, release, records

    def __len__(self):
        return len(self.ids)

    def __repr__(self):
        return f"<Selection {len(self.ids)} records, release {self.release}>"

    def size(self, files=None):
        """Bytes the download would transfer (asks the server for the file list; nothing is transferred)."""
        links = self.client._download_links(ids=self.ids, files=files)
        return sum(ln["size"] for ln in links)

    def save(self, path):
        with open(os.path.expanduser(path), "w", encoding="utf-8") as f:
            json.dump({"release": self.release, "filters": self.filters, "ids": self.ids}, f, indent=1)
        return path

    @classmethod
    def load(cls, path, client=None):
        with open(os.path.expanduser(path), encoding="utf-8") as f:
            j = json.load(f)
        client = client or Client(release=j.get("release"))
        if j.get("release") and client.release != j["release"]:
            raise BatangError("release", f"the selection is from release {j['release']}, the client uses {client.release}")
        return cls(client, j["ids"], filters=j.get("filters"), release=j.get("release"))

    def download(self, columns=None, to=None, files=None):
        return self.client.download(self, columns=columns, to=to, files=files)
