"""Quick look at one cell of the standardized Batang data.

    python plot_cell.py <store> <cell_id> [cycle]

<store> is the cell store of release 2.0 (releases/2.0/cells, the folder that holds catalog.parquet).
Draws the cell's SOH over equivalent full cycles and the voltage and current of one cycle (default:
the first ageing cycle). Needs pandas, pyarrow and matplotlib.
"""
import os
import sys

import matplotlib.pyplot as plt
import pandas as pd

store, cell_id = sys.argv[1], sys.argv[2]
cat = pd.read_parquet(os.path.join(store, "catalog.parquet"))
row = cat.set_index("cell_id").loc[cell_id]
folder = os.path.join(store, row.path)

cycles = pd.read_parquet(os.path.join(folder, "cycles.parquet"))
k = int(sys.argv[3]) if len(sys.argv) > 3 else int(cycles.cycle[cycles.cycle_kind == "aging"].iloc[0])
# only the rows of cycle k: row groups are cut at cycle boundaries, so the filter reads little
ts = pd.read_parquet(os.path.join(folder, "samples.parquet"), filters=[("cycle", "==", k)])
ts = ts[(ts.quality_flags & 11) == 0]     # leave out wrong current / voltage readings and foreign rows

fig, ax = plt.subplots(1, 2, figsize=(11, 4))
for kind, g in cycles.groupby("cycle_kind"):
    ax[0].plot(g.efc, g.soh, ".", ms=3, label=kind)
ax[0].set(xlabel="equivalent full cycles", ylabel="SOH", title=f"{cell_id} ({row.dataset})")
ax[0].legend(fontsize=8)
ax[1].plot(ts.cycle_time_s / 60, ts.voltage_v, label="voltage (V)")
ax[1].set(xlabel="time in cycle (min)", ylabel="V", title=f"cycle {k} ({cycles.set_index('cycle').cycle_kind[k]})")
ax2 = ax[1].twinx()
ax2.plot(ts.cycle_time_s / 60, ts.current_a, color="tab:orange", lw=0.8, label="current (A)")
ax2.set_ylabel("A (charge > 0)")
fig.tight_layout()
plt.show()
