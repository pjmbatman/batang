"""Cycle-level training samples from the standardized Batang data.

    python load_for_training.py <store>        # <store> = releases/2.0/cells

Builds an index of cycles (complete ageing cycles, optionally limited to datasets or to data whose
license allows commercial use), reads only the columns a model needs, and returns one cycle per item. Needs pandas, pyarrow
and numpy; the class works as a PyTorch map-style dataset without importing torch.
"""
import os
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


class CycleDataset:
    def __init__(self, store, columns=("voltage_v", "current_a", "temperature_c"), labels=("soh", "efc"),
                 datasets=None, commercial_use=None, kinds=("aging",)):
        self.store, self.columns, self.labels = store, list(columns), list(labels)
        cat = pd.read_parquet(os.path.join(store, "catalog.parquet"))
        if datasets is not None:
            cat = cat[cat.dataset.isin(datasets)]
        if commercial_use is not None:
            cat = cat[cat.commercial_use == commercial_use]
        self.path = dict(zip(cat.cell_id, cat.path))
        cy = pd.read_parquet(os.path.join(store, "cycles.parquet"),
                             columns=["cell_id", "cycle", "cycle_kind", "n_samples", "is_complete",
                                      "is_capacity_outlier", "has_time_gap", *self.labels],
                             filters=[("cell_id", "in", list(self.path))])
        # row offsets of every cycle inside its cell's samples.parquet
        cy["row_start"] = cy.groupby("cell_id").n_samples.cumsum() - cy.n_samples
        keep = cy.cycle_kind.isin(kinds) & cy.is_complete & ~cy.is_capacity_outlier & ~cy.has_time_gap
        self.index = cy[keep].reset_index(drop=True)
        self._files = {}

    def __len__(self):
        return len(self.index)

    def _file(self, cell_id):
        f = self._files.get(cell_id)
        if f is None:
            f = self._files[cell_id] = pq.ParquetFile(os.path.join(self.store, self.path[cell_id], "samples.parquet"))
        return f

    def __getitem__(self, i):
        r = self.index.iloc[i]
        f = self._file(r.cell_id)
        cols = self.columns + ["quality_flags"]
        # read just the row groups that hold this cycle
        md = f.metadata
        bounds = np.cumsum([0] + [md.row_group(g).num_rows for g in range(md.num_row_groups)])
        a, b = int(r.row_start), int(r.row_start + r.n_samples)
        g0, g1 = np.searchsorted(bounds, a, "right") - 1, np.searchsorted(bounds, b - 1, "right") - 1
        t = f.read_row_groups(list(range(g0, g1 + 1)), columns=cols).slice(a - bounds[g0], b - a)
        x = {c: t.column(c).to_numpy(zero_copy_only=False) for c in cols}
        q = x.pop("quality_flags")            # drop flagged samples, blank flagged temperatures
        if "temperature_c" in x:
            x["temperature_c"] = np.where(q & 4, np.nan, x["temperature_c"])
        x = {c: v[(q & 11) == 0] for c, v in x.items()}
        return {"cell_id": r.cell_id, "cycle": int(r.cycle), **x, **{l: r[l] for l in self.labels}}


if __name__ == "__main__":
    ds = CycleDataset(sys.argv[1], datasets=["MATR"])   # or commercial_use="allowed"
    print(len(ds), "cycles")
    item = ds[0]
    print({k: (v.shape if hasattr(v, "shape") else v) for k, v in item.items()})
    # torch: DataLoader(ds, batch_size=64, shuffle=True, collate_fn=...)  (cycles differ in length: pad them)
