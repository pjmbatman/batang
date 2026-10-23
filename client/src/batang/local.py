"""Reading Batang files on your own disk: the downloaded cache or a copy of a release (schema 2.0).

    store = batang.open("~/batang_cache/2.0")          # a download folder, releases/2.0, or releases/2.0/cells
    store.datasets                                     # dataset keys
    cell = store.record("STROEBL_S1_k01_01")
    cell.cycles(kind="aging", complete=True, exclude_flags=True)
    cell.cycle(12, columns=["voltage_v", "current_a"], quality="clean")

The filters mean what they mean on the server (batang.Client.cycles / cycle_samples): kind = cycle_kind (cells) or
segment_kind (devices), complete keeps complete cycles, exclude_flags drops capacity outliers and cycles with time
gaps, where = [[column, operator, value], ...], quality="clean" drops samples flagged as wrong readings.

Files downloaded from a 1.x release (timeseries.parquet, 1.x column names) are not read: download them again from
release 2.0. Column names given in arguments may still be 1.x names in release 2.0; they are translated.
"""
import json
import os

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from . import _names as N
from ._names import ID_COLUMN, KEY_COLUMN, QUALITY, SAMPLES, TABLE_FILES, TIME_COLUMN

CELL_CLEAN_MASK = 1 | 2 | 8            # wrong current, wrong voltage, row of another record
DEVICE_CLEAN_MASK = 1 | 2 | 8 | 16     # + value filled by the source
OPS = ("<", "<=", ">", ">=", "==", "!=", "in", "not in")
LEGACY_HINT = ("is in the 1.x layout (timeseries.parquet, 1.x column names); release 2.0 renamed files and "
               "columns, so download it again from release 2.0 (DATA_FORMAT.md, 'Changes from 1.x')")


class LegacyLayoutError(ValueError):
    """A folder written for schema 1.x (cell store 1.x or unit store); schema 2.0 needs a fresh download."""


# --------------------------------------------------------------------------- filters shared with the server

def where_mask(df, where):
    m = pd.Series(True, index=df.index)
    if not where:
        return m
    if isinstance(where, dict):
        where = [[k] + (list(v) if isinstance(v, (list, tuple)) else ["==", v]) for k, v in where.items()]
    for cond in where:
        if not isinstance(cond, (list, tuple)) or len(cond) != 3:
            raise ValueError("each condition is [column, operator, value]")
        col, op, val = cond
        if col not in df:
            raise ValueError(f"unknown column {col!r} for this table")
        if op not in OPS:
            raise ValueError(f"operator must be one of {OPS}")
        s = df[col]
        if op in ("in", "not in"):
            hit = s.isin(val if isinstance(val, (list, tuple, set)) else [val])
            m &= hit if op == "in" else ~hit
        else:
            m &= {"<": s < val, "<=": s <= val, ">": s > val, ">=": s >= val, "==": s == val, "!=": s != val}[op].fillna(False)
    return m


def cycle_mask(df, store, kind=None, complete=False, exclude_flags=False):
    m = pd.Series(True, index=df.index)
    kcol = "cycle_kind" if store == "cell" else "segment_kind"
    if kind is not None and kcol in df:
        m &= df[kcol].isin(kind if isinstance(kind, (list, tuple)) else [kind])
    if complete and "is_complete" in df:
        m &= df["is_complete"].fillna(False).astype(bool)
    if exclude_flags:
        for f in ("is_capacity_outlier", "has_time_gap"):
            if f in df:
                m &= ~df[f].fillna(False).astype(bool)
    return m


def lttb(x, y, n_out):
    """Largest-Triangle-Three-Buckets: indices that keep the visual shape of y(x) (the server reduces the same way)."""
    n = len(x)
    if n <= n_out:
        return np.arange(n)
    edges = np.linspace(1, n - 1, n_out - 1).astype(int)
    out, a = [0], 0
    for k in range(n_out - 2):
        s, e = edges[k], max(edges[k + 1], edges[k] + 1)
        ns, ne = e, max(edges[k + 2] if k + 2 < len(edges) else n, e + 1)
        cx, cy = x[ns:ne].mean(), y[ns:ne].mean()
        xs, ys = x[s:e], y[s:e]
        area = np.abs((x[a] - cx) * (ys - y[a]) - (x[a] - xs) * (cy - y[a]))
        a = s + int(np.argmax(area))
        out.append(a)
    out.append(n - 1)
    return np.unique(out)


def reduce_samples(t, max_points, time_col):
    if max_points is None or len(t) <= max_points:
        return t
    v = t["voltage_v"].to_numpy(dtype=float) if "voltage_v" in t else np.full(len(t), np.nan)
    if not np.isfinite(v).any() and "current_a" in t:
        v = t["current_a"].to_numpy(dtype=float)
    x = t[time_col].to_numpy(dtype=float) if time_col in t else np.arange(len(t), dtype=float)
    x = np.where(np.isfinite(x), x, np.arange(len(t), dtype=float))
    med = np.nanmedian(v) if np.isfinite(v).any() else 0.0
    return t.iloc[lttb(x, np.nan_to_num(v, nan=med), int(max_points))]


def _clean_mask(kind):
    return CELL_CLEAN_MASK if kind == "cell" else DEVICE_CLEAN_MASK


# --------------------------------------------------------------------------- the local store

class Record:
    """One cell or device on disk: its cycle (or segment) table, its samples and its metadata."""

    def __init__(self, store, rid, dataset, kind, folder):
        self.store, self.id, self.dataset, self.kind, self.folder = store, rid, dataset, kind, folder
        self.key, self.time = KEY_COLUMN[kind], TIME_COLUMN[kind]
        if not os.path.isfile(os.path.join(folder, SAMPLES)) and os.path.isfile(os.path.join(folder, "timeseries.parquet")):
            raise LegacyLayoutError(f"{folder} {LEGACY_HINT}")

    def __repr__(self):
        return f"<{self.kind} {self.id} ({self.dataset})>"

    def has(self, name):
        return os.path.isfile(os.path.join(self.folder, name))

    def columns(self, name=SAMPLES):
        return pq.read_schema(os.path.join(self.folder, name)).names

    @property
    def meta(self):
        with open(os.path.join(self.folder, "meta.json"), encoding="utf-8") as f:
            return json.load(f)

    def cycles(self, columns=None, kind=None, complete=False, exclude_flags=False, where=None, limit=None):
        """The cycle (cell) or segment (device) rows that pass the filters."""
        columns, where = N.columns(columns, self.kind), N.where(where, self.kind)
        path = os.path.join(self.folder, TABLE_FILES[self.kind])
        names = pq.read_schema(path).names
        need = None
        if columns is not None:
            bad = [c for c in columns if c not in names]
            if bad:
                raise ValueError(f"unknown columns {bad}")
            extra = ["cycle_kind", "segment_kind", "is_complete", "is_capacity_outlier", "has_time_gap"]
            extra += [c[0] for c in (where if isinstance(where, list) else [[k] for k in (where or {})])]
            need = list(dict.fromkeys([self.key] + list(columns) + [c for c in extra if c in names]))
        df = pq.read_table(path, columns=need).to_pandas()
        df = df[cycle_mask(df, self.kind, kind, complete, exclude_flags) & where_mask(df, where)]
        if columns is not None:
            df = df[list(dict.fromkeys([self.key] + list(columns)))]
        if limit is not None:
            df = df.head(int(limit))
        df = df.reset_index(drop=True)
        df.insert(0, "id", self.id)
        return df

    def cycle(self, cycle, columns=None, t0=None, t1=None, max_points=None, quality="all"):
        """The samples of one cycle (cell) or segment (device), cut to [t0, t1] s from its start (cycle_time_s /
        segment_time_s) and optionally reduced to max_points (LTTB on voltage over time)."""
        if quality not in ("all", "clean"):
            raise ValueError('quality must be "all" or "clean"')
        columns = N.columns(columns, self.kind)
        path = os.path.join(self.folder, SAMPLES)
        names = pq.read_schema(path).names
        want = list(dict.fromkeys([self.time] + list(columns or [c for c in names if c not in (self.key, QUALITY)])))
        bad = [c for c in want if c not in names]
        if bad:
            raise ValueError(f"unknown columns {bad}")
        read = list(dict.fromkeys([self.key] + want + [c for c in ("voltage_v", "current_a", QUALITY) if c in names]))
        t = pq.read_table(path, columns=read, filters=[(self.key, "==", int(cycle))]).to_pandas()
        if not len(t):
            raise KeyError(f"{self.id} has no {self.key} {cycle}")
        keep = np.ones(len(t), bool)
        ts = t[self.time].to_numpy(dtype=float)
        if t0 is not None:
            keep &= ts >= float(t0)
        if t1 is not None:
            keep &= ts <= float(t1)
        if quality == "clean" and QUALITY in t:
            keep &= (t[QUALITY].to_numpy() & _clean_mask(self.kind)) == 0
        t = reduce_samples(t[keep], max_points, self.time)
        return t[want].reset_index(drop=True)

    def samples(self, columns=None, quality="all"):
        """Every sample of the record (can be large: tens of millions of rows for long tests)."""
        columns = N.columns(columns, self.kind)
        path = os.path.join(self.folder, SAMPLES)
        names = pq.read_schema(path).names
        cols = None if columns is None else list(dict.fromkeys([self.key] + list(columns) + ([QUALITY] if quality == "clean" else [])))
        t = pq.read_table(path, columns=[c for c in cols if c in names] if cols else None).to_pandas()
        if quality == "clean" and QUALITY in t:
            t = t[(t[QUALITY].to_numpy() & _clean_mask(self.kind)) == 0]
        return t[[c for c in cols if c in t]] if columns is not None else t


def _catalog_records(root, prefix=""):
    """{id: entry} from the catalog.parquet of a store copy (cells/ or devices/), or {} when there is none."""
    cat = os.path.join(root, "catalog.parquet")
    if not os.path.isfile(cat):
        return {}
    names = pq.read_schema(cat).names
    if "path" not in names:                       # a catalog stored by download_catalog(), not a store copy
        return {}
    if "unit_id" in names or ("cell_id" in names and "tasks" not in names):
        raise LegacyLayoutError(f"{root} {LEGACY_HINT}")
    kind = "cell" if "cell_id" in names else "device"
    key = ID_COLUMN[kind]
    return {r[key]: {"dataset": r["dataset"], "kind": kind, "folder": os.path.join(prefix, r["path"]), "files": {}}
            for r in pq.read_table(cat, columns=["dataset", key, "path"]).to_pylist()}


class LocalStore:
    """A folder of Batang data: a release folder of the download cache (index.json), a release copy with cells/ and
    devices/, or one store of it (catalog.parquet)."""

    def __init__(self, path):
        self.path = os.path.abspath(os.path.expanduser(path))
        self._index = {}
        idx = os.path.join(self.path, "index.json")
        if os.path.isfile(idx):
            with open(idx, encoding="utf-8") as f:
                j = json.load(f)
            if str(j.get("release", "")).startswith(("1.", "s1.", "unit")) or \
                    any(e.get("kind") == "unit" for e in j.get("records", {}).values()):
                raise LegacyLayoutError(f"{self.path} {LEGACY_HINT}")
            self._index = j.get("records", {})
        for sub in ("cells", "devices"):                                       # a release copy
            for k, e in _catalog_records(os.path.join(self.path, sub), sub).items():
                self._index.setdefault(k, e)
        for k, e in _catalog_records(self.path).items():                       # one store
            self._index.setdefault(k, e)
        if not self._index and not os.path.isdir(self.path):
            raise FileNotFoundError(self.path)

    def __repr__(self):
        return f"<LocalStore {self.path}: {len(self._index)} records>"

    def __contains__(self, rid):
        return rid in self._index

    @property
    def ids(self):
        return sorted(self._index)

    @property
    def datasets(self):
        return sorted({e["dataset"] for e in self._index.values()})

    @property
    def records(self):
        return pd.DataFrame([{"id": k, "dataset": e["dataset"], "kind": e["kind"]} for k, e in sorted(self._index.items())])

    def dataset(self, name):
        return [self.record(k) for k, e in sorted(self._index.items()) if e["dataset"] == name]

    def record(self, rid):
        e = self._index.get(rid)
        if e is None:
            raise KeyError(f"{rid} is not in {self.path}")
        folder = os.path.join(self.path, e.get("folder") or os.path.join(e["dataset"], rid))
        return Record(self, rid, e["dataset"], e["kind"], folder)

    def has(self, rid, filename, columns=None):
        """Whether the record's file is here (and, for column-subset downloads, holds the wanted columns)."""
        e = self._index.get(rid)
        if e is None:
            return False
        rec = self.record(rid)
        if not rec.has(filename):
            return False
        if columns:
            have = e.get("columns", {}).get(filename)
            names = have if have is not None else rec.columns(filename)
            return all(c in names for c in columns)
        return True


# --------------------------------------------------------------------------- schema check of your own files

CELL_SAMPLES = {"cycle": "int", "step": "int", "step_type": "str", "cycle_time_s": "float", "test_time_s": "float",
                "voltage_v": "float", "current_a": "float", "charge_ah": "float", "discharge_ah": "float",
                "temperature_c": "float", "quality_flags": "uint8"}
CELL_CYCLES = {"cycle": "int", "cycle_kind": "str", "efc": "float", "soh": "float", "test_time_start_s": "float",
               "duration_s": "float", "n_samples": "int", "n_steps": "int", "charge_ah": "float", "discharge_ah": "float",
               "charge_wh": "float", "discharge_wh": "float", "coulombic_efficiency": "float", "charge_c_rate": "float",
               "discharge_c_rate": "float", "voltage_max_v": "float", "voltage_min_v": "float", "current_max_a": "float",
               "current_min_a": "float", "temperature_min_c": "float", "temperature_max_c": "float",
               "temperature_mean_c": "float", "is_complete": "bool", "is_off_protocol": "bool",
               "is_capacity_outlier": "bool", "has_time_gap": "bool"}
DEVICE_SAMPLES = {"segment": "int", "block": "int", "segment_time_s": "float", "test_time_s": "float",
                  "voltage_v": "float", "current_a": "float", "operating_state": "str", "charge_ah": "float",
                  "discharge_ah": "float", "quality_flags": "uint8"}
DEVICE_SEGMENTS = {"segment": "int", "segment_kind": "str", "block": "int", "test_time_start_s": "float",
                   "duration_s": "float", "n_samples": "int", "charge_ah": "float", "discharge_ah": "float",
                   "fault_active": "int", "has_time_gap": "bool"}
CYCLE_KINDS = {"aging", "rpt", "initial", "partial", "irregular"}
# optional columns the schema defines, with their type
OPTIONAL_COLUMNS = {
    "source_ref_first": "str", "source_ref_last": "str", "ambient_temperature_c": "float", "charge_duration_s": "float",
    "discharge_duration_s": "float", "reported_ir_ohm": "float", "reported_capacity_ah": "float",
    "reported_re_ohm": "float", "reported_rct_ohm": "float", "procedure": "str", "procedures": "list",
    "procedure_source": "str", "power_w": "float", "bms_soc": "float", "cell_voltage_max_v": "float",
    "cell_voltage_min_v": "float", "cell_voltage_mean_v": "float", "cell_voltage_max_index": "int",
    "cell_voltage_min_index": "int", "temperature_max_c": "float", "temperature_min_c": "float",
    "temperature_mean_c": "float", "temperature_max_index": "int", "temperature_min_index": "int",
    "odometer_km": "float", "speed_kmh": "float", "sample_interval_median_s": "float", "bms_soc_start": "float",
    "bms_soc_end": "float", "voltage_min_v": "float", "voltage_max_v": "float", "current_min_a": "float",
    "current_max_a": "float", "current_mean_a": "float", "cell_voltage_spread_p50_v": "float",
    "cell_voltage_spread_p99_v": "float", "cell_voltage_spread_max_v": "float", "cell_voltage_min_mode_index": "int",
    "temperature_spread_max_c": "float", "efc": "float", "age_days": "float", "soh": "float", "soh_source": "str",
    "capacity_ah": "float", "is_reference": "bool", "fault_class": "str", "fault_cell_index": "int",
    "fault_severity": "float", "fault_severity_unit": "str", "n_flagged_samples": "int", "charge_wh": "float",
    "discharge_wh": "float"}
UNIT_SUFFIXES = tuple("_" + u for u in "v a ah wh w kwh s min c ohm km kmh kpa n mm mol ppm microstrain bytes days".split())
# ratios carry no unit (naming rule 3)
RATIO_SUFFIXES = ("soh", "soc", "efc", "_efficiency", "_c_rate", "_c_rate_typical", "_severity", "_interpolated",
                  "_normalized", "soc_start", "soc_end")


def _kind_of(t):
    import pyarrow as pa
    if pa.types.is_dictionary(t):
        t = t.value_type
    if pa.types.is_uint8(t):
        return "uint8"
    if pa.types.is_integer(t):
        return "int"
    if pa.types.is_floating(t):
        return "float"
    if pa.types.is_boolean(t):
        return "bool"
    if pa.types.is_string(t) or pa.types.is_large_string(t):
        return "str"
    if pa.types.is_list(t) or pa.types.is_large_list(t):
        return "list"
    return str(t)


def _type_ok(col, want, got):
    return got == want or (want == "int" and got == "uint8") or (want == "float" and got == "int" and col != QUALITY)


def _check_table(path, spec, errors, warnings, cut=False):
    sch = pq.read_schema(path)
    types = dict(zip(sch.names, sch.types))
    name = os.path.basename(path)
    for col, want in spec.items():
        if col not in types:
            if cut:
                warnings.append(f"{name}: column {col} was not downloaded (column-cut download)")
            else:
                errors.append(f"{name}: column {col} is missing")
            continue
        got = _kind_of(types[col])
        if not _type_ok(col, want, got):
            errors.append(f"{name}: {col} is {got}, expected {want}")
    for col, t in types.items():
        if col in spec:
            continue
        got = _kind_of(t)
        if col in OPTIONAL_COLUMNS:
            if not _type_ok(col, OPTIONAL_COLUMNS[col], got):
                errors.append(f"{name}: {col} is {got}, expected {OPTIONAL_COLUMNS[col]}")
            continue
        new = N.LEGACY.get(col) or ({"time_s": "cycle_time_s / segment_time_s"}.get(col))
        if new:
            errors.append(f"{name}: {col} is a 1.x name; schema 2.0 calls it {new}")
        elif got == "float" and not col.endswith(UNIT_SUFFIXES) and not col.endswith(RATIO_SUFFIXES):
            warnings.append(f"{name}: {col} has no unit suffix (names end with their unit: _v, _a, _ah, _s, _c …)")
    return sch.names


def _cut_columns(folder):
    """The columns kept by a column-cut download of this record (from the index.json of its cache), or None."""
    up = folder
    for _ in range(3):
        up = os.path.dirname(up)
        try:
            with open(os.path.join(up, "index.json"), encoding="utf-8") as f:
                rec = json.load(f).get("records", {}).get(os.path.basename(folder)) or {}
            return (rec.get("columns") or {}).get(SAMPLES)
        except (OSError, ValueError):
            continue
    return None


def validate(path):
    """Check files you made or edited against the Batang schema 2.0 (it does not convert anything).

    path: a record folder (samples.parquet + cycles.parquet or segments.parquet), or a store root with
    catalog.parquet (every record is checked). Returns {"ok", "records", "errors", "warnings"}."""
    path = os.path.abspath(os.path.expanduser(path))
    if os.path.isfile(os.path.join(path, "catalog.parquet")) and not os.path.isfile(os.path.join(path, SAMPLES)):
        store = LocalStore(path)
        folders = [os.path.join(store.path, store._index[r].get("folder") or os.path.join(store._index[r]["dataset"], r))
                   for r in store.ids]
    else:
        folders = [path]
    errors, warnings = [], []
    for folder in folders:
        e0 = len(errors)
        ts = os.path.join(folder, SAMPLES)
        cyc, seg = os.path.join(folder, "cycles.parquet"), os.path.join(folder, "segments.parquet")
        if not os.path.isfile(ts):
            if os.path.isfile(os.path.join(folder, "timeseries.parquet")):
                errors.append(f"{folder}: timeseries.parquet is the 1.x name; schema 2.0 calls it samples.parquet")
            else:
                errors.append(f"{folder}: samples.parquet is missing")
            continue
        kind = "device" if os.path.isfile(seg) else "cell"
        table = seg if kind == "device" else cyc
        if not os.path.isfile(table):
            errors.append(f"{folder}: {os.path.basename(table)} is missing")
            continue
        _check_table(ts, DEVICE_SAMPLES if kind == "device" else CELL_SAMPLES, errors, warnings,
                     cut=_cut_columns(folder) is not None)
        _check_table(table, DEVICE_SEGMENTS if kind == "device" else CELL_CYCLES, errors, warnings)
        if len(errors) > e0:
            continue
        key = KEY_COLUMN[kind]
        t = pq.read_table(table, columns=[key, "n_samples"] + (["cycle_kind"] if kind == "cell" else [])).to_pandas()
        tsk = pq.read_table(ts, columns=[key, QUALITY]).to_pandas()
        if int(t["n_samples"].sum()) != len(tsk):
            errors.append(f"{folder}: n_samples sums to {int(t['n_samples'].sum())}, samples has {len(tsk)} rows")
        if not t[key].is_monotonic_increasing or t[key].duplicated().any():
            errors.append(f"{folder}: {key} numbers must increase without repeats")
        missing = set(tsk[key].unique()) - set(t[key])
        if missing:
            errors.append(f"{folder}: samples of {key} {sorted(missing)[:5]} have no row in {os.path.basename(table)}")
        allowed = (CELL_CLEAN_MASK | 4) if kind == "cell" else (DEVICE_CLEAN_MASK | 4 | 32)
        bad = int(((tsk[QUALITY].to_numpy().astype(int) & ~allowed) != 0).sum())
        if bad:
            errors.append(f"{folder}: {bad} samples use quality bits that are not defined")
        if kind == "cell":
            odd = set(t["cycle_kind"].dropna()) - CYCLE_KINDS
            if odd:
                errors.append(f"{folder}: unknown cycle_kind values {sorted(odd)}")
        for f in ("cell_voltages.parquet", "temperatures.parquet", "aux.parquet"):
            p = os.path.join(folder, f)
            if os.path.isfile(p) and pq.ParquetFile(p).metadata.num_rows != len(tsk):
                errors.append(f"{folder}: {f} has {pq.ParquetFile(p).metadata.num_rows} rows, samples has {len(tsk)}")
        for old, new in (("cells_v.parquet", "cell_voltages.parquet"), ("temps.parquet", "temperatures.parquet")):
            if os.path.isfile(os.path.join(folder, old)):
                errors.append(f"{folder}: {old} is the 1.x name; schema 2.0 calls it {new}")
        if not os.path.isfile(os.path.join(folder, "meta.json")):
            warnings.append(f"{folder}: meta.json is missing")
    return {"ok": not errors, "records": len(folders), "errors": errors, "warnings": warnings}
