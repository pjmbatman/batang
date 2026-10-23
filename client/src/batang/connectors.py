"""Connectors: Batang tables into the shapes models and other tools take.

    X = batang.to_numpy(df, ["voltage_v", "current_a", "temperature_c"])
    ds = batang.torch_dataset(store, ids, columns=["voltage_v", "current_a"], target="soh", kind="aging")
    batang.export(df, "out.csv")                       # or .parquet, .h5 (h5py)
"""
import os

import numpy as np
import pandas as pd


def to_numpy(df, columns=None, dtype=np.float32):
    """The given columns (all numeric columns by default) as a 2-D array."""
    cols = list(columns) if columns is not None else [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    return df[cols].to_numpy(dtype=dtype)


def export(df, path, format=None):
    """Write a table to Parquet, CSV or HDF5 (format from the extension unless given)."""
    path = os.path.expanduser(path)
    fmt = (format or os.path.splitext(path)[1].lstrip(".")).lower()
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    if fmt in ("parquet", "pq"):
        df.to_parquet(path, index=False)
    elif fmt == "csv":
        df.to_csv(path, index=False)
    elif fmt in ("h5", "hdf5"):
        try:
            import h5py
        except ImportError:
            raise ImportError('HDF5 export needs h5py: pip install "batang[hdf5]"') from None
        with h5py.File(path, "w") as f:
            for c in df.columns:
                v = df[c].to_numpy()
                if v.dtype == object or isinstance(df[c].dtype, pd.CategoricalDtype):
                    f.create_dataset(c, data=df[c].astype(str).to_numpy().astype("S"))
                else:
                    f.create_dataset(c, data=v)
    else:
        raise ValueError("format must be parquet, csv or hdf5")
    return path


class CycleWindows:
    """Windows of samples cut from cycles of local records, with an optional per-cycle target (e.g. soh).

    Each item is (x, y): x a float32 array [window, len(columns)], y the target of the cycle the window comes from
    (NaN when the cycle has none). Cycles shorter than the window give one zero-padded window. Works without torch;
    torch_dataset() wraps it as a torch Dataset."""

    def __init__(self, store, ids, columns=("voltage_v", "current_a"), window=512, stride=None, target=None,
                 kind="aging", complete=True, exclude_flags=True, quality="clean", max_cycles=None):
        self.store, self.columns = store, list(columns)
        self.window, self.stride, self.target, self.quality = int(window), int(stride or window), target, quality
        self.items = []
        for rid in ids:
            rec = store.record(rid)
            cyc = rec.cycles(kind=kind, complete=complete, exclude_flags=exclude_flags)
            if target is not None and target not in cyc:
                raise ValueError(f"{rid}: no column {target} in its cycle table")
            if max_cycles is not None:
                cyc = cyc.head(int(max_cycles))
            for _, row in cyc.iterrows():
                n = int(row["n_samples"]) if "n_samples" in cyc else self.window
                y = float(row[target]) if target is not None and pd.notna(row[target]) else np.nan
                starts = range(0, max(1, n - self.window + 1), self.stride)
                for s in starts:
                    self.items.append((rid, int(row[rec.key]), s, y))
        self._cache = {}

    def __len__(self):
        return len(self.items)

    def _samples(self, rid, cycle):
        k = (rid, cycle)
        if k not in self._cache:
            if len(self._cache) > 64:
                self._cache.clear()
            t = self.store.record(rid).cycle(cycle, columns=self.columns, quality=self.quality)
            self._cache[k] = t[self.columns].to_numpy(dtype=np.float32)
        return self._cache[k]

    def __getitem__(self, i):
        rid, cycle, s, y = self.items[i]
        a = self._samples(rid, cycle)[s:s + self.window]
        if len(a) < self.window:
            a = np.vstack([a, np.zeros((self.window - len(a), a.shape[1]), np.float32)])
        return a, np.float32(y)


def torch_dataset(store, ids, **kw):
    """CycleWindows as a torch.utils.data.Dataset (tensors)."""
    try:
        import torch
    except ImportError:
        raise ImportError('torch_dataset needs torch: pip install "batang[torch]"') from None
    w = CycleWindows(store, ids, **kw)

    class _DS(torch.utils.data.Dataset):
        def __len__(self):
            return len(w)

        def __getitem__(self, i):
            x, y = w[i]
            return torch.from_numpy(x), torch.tensor(y)

    ds = _DS()
    ds.windows = w
    return ds
