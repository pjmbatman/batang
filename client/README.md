# batang — Python client for Batang

`batang` is the Python client for Batang: you can search records, read cycles and samples, run read-only SQL and download standardized battery data from Python or the command line.
Each method is a tool of the Batang MCP server, with the same name and the same arguments. So your Python code and an AI assistant connected to the MCP server ask the server for exactly the same things.

```bash
pip install "git+https://github.com/pjmbatman/batang#subdirectory=client"
pip install "batang[sql,torch,hdf5] @ git+https://github.com/pjmbatman/batang#subdirectory=client"   # optional extras
```

Version 0.2 reads Batang release 2.0 (schema 2.0.0); see [Schema 2.0](#schema-20-and-1x-downloads) below.
Requires Python 3.10+, with numpy, pandas and pyarrow. The extras add `sql` (duckdb, for SQL over your downloads), `torch` (`torch_dataset`) and `hdf5` (h5py, for `export(..., "x.h5")`).

## Log in

```bash
batang login        # shows a code, opens https://batang.yonsei.ac.kr/auth/device; approve it with your Google account
batang whoami
```

Access is open to @yonsei.ac.kr Google accounts. Anyone outside Yonsei can apply for access on the site. Once a request is approved, that person logs in the same way.
The token is valid for 7 days. It is stored in `~/.config/batang/token` (mode 600) and is never printed.
The first call in an interactive session logs you in by itself. Scripts and CI can set `BATANG_TOKEN` instead; you create a token on the account page.

## Use

```python
import batang

db = batang.connect()                      # https://batang.yonsei.ac.kr/mcp, cache in ~/batang_cache

lfp = db.find_records(tasks="aging", cathode_family="LFP")
lfp.attrs["matched"], lfp.attrs["by_dataset"]

db.describe("STROEBL_S1_k01_01")           # properties, test conditions, SOH definition, quality
db.schema("soh")                           # what a variable means, its unit and table

cyc = db.cycles(["STROEBL_S1_k01_01"], columns=["efc", "soh", "discharge_ah"], kind="aging", exclude_flags=True)
v = db.cycle_samples("STROEBL_S1_k01_01", 10, columns=["voltage_v", "current_a"], quality="clean")
db.query("SELECT cathode_family, count(*) AS n FROM cells GROUP BY 1 ORDER BY n DESC")
db.stats(metric="soh_end", agg="median", group_by="cathode_family")              # over the catalog (grain="record")
db.stats(metric="voltage_min_v", agg="p10", grain="cycle", kind="aging", tasks="aging", level="cell")
```

Every reading method returns a pandas DataFrame. `df.attrs["source"]` says where the rows came from: `"local"`, `"remote"` or `"mixed"`.

### Local first

The client never downloads anything unless you ask it to. Once you have downloaded a record, reads of that record use the local files whenever they hold the columns you asked for. Any other read goes to the server.

```python
sel = db.select(tasks="aging", cathode_family="NMC")
sel.size()                                  # bytes it would transfer; nothing is transferred yet
sel.download(columns=["voltage_v", "current_a"])   # keep only these sample columns (plus cycle, step, time, quality_flags)
sel.save("nmc_aging.json")                  # reproduce the same set later: batang.Selection.load("nmc_aging.json")

db.cycle_samples(sel.ids[0], 5).attrs["source"]    # "local"
db.query("SELECT cell_id, max(cycle) FROM cycles GROUP BY 1", local=True)   # DuckDB over your downloads
```

Downloads go to `~/batang_cache/<release>/<dataset>/<id>/` (release `2.0`), with the file names of the release:
`samples.parquet`, `cycles.parquet` (cells) or `segments.parquet` (devices), `meta.json`, and on request
`samples_preview`, `cell_voltages`, `temperatures`, `aux`. Each download leaves a manifest in `selections/`, so you can see later what you downloaded and why. A file that is already there with the right size is not downloaded again.
If a remote read would transfer more than 1 GB, the client stops and tells you so. Download that data once and read it locally, or pass `allow_large=True`.

### Offline

```python
db.download_catalog()                       # once, while online
off = batang.connect(offline=True)
off.find_records(cathode_family="LFP")      # from the cached catalog
off.cycles(["STROEBL_S1_k01_01"])           # from your downloads; anything else raises OfflineError
```

Local SQL (`query(..., local=True)`) has the server's view and macro names: `cycles`, `segments`, `samples`,
`device_samples` with `dataset` and `cell_id` / `device_id` columns, `cycle_samples(cell_id[, cycle])`,
`segment_samples(device_id[, segment])`, and `records` (with `cells` and `devices`) once `download_catalog()` ran.

### Your own files, models, other tools

```python
st = batang.open("~/batang_cache/2.0")      # a download folder, a copy of releases/2.0, or its cells/ or devices/
rec = st.record("STROEBL_S1_k01_01")
rec.cycles(kind="aging", complete=True, exclude_flags=True)
rec.cycle(10, columns=["voltage_v"], max_points=2000)   # LTTB reduction, same as the server

batang.validate("my_cell/")                 # check files you made against the Batang schema 2.0
batang.to_numpy(rec.cycles(), ["soh"])
batang.export(rec.cycles(), "cycles.csv")   # .parquet, .csv, .h5
ds = batang.torch_dataset(st, sel.ids, columns=["voltage_v", "current_a"], window=512, target="soh")
```

## Schema 2.0 and 1.x downloads

Release 2.0 renamed columns, files and folders; values did not change (the list is
[DATA_FORMAT.md](../DATA_FORMAT.md#changes-from-1x)). Client 0.2 uses the 2.0 names everywhere: `samples.parquet`,
`cycle_time_s` / `segment_time_s`, `quality_flags`, `efc`, `voltage_min_v`, `size_code`, `level`, `setting`,
`device_id` ...

- **Arguments.** Filters are `tasks`, `size_code`, `level` (cell, module, pack, system, vehicle) and `setting`;
  `stats()` chooses catalog or row statistics with `grain` (`record`, `cycle`, `segment`). In release 2.0 you may
  still pass 1.x names (`columns=["time_s", "v_min"]`, `find_records(task="aging", cell_format="18650")`,
  `stats(level="cycle")`, `download(files=["timeseries"])`); they are translated and a `FutureWarning` names the 2.0
  name. When the server reports a translation of its own (`renamed` in an answer), the client warns the same way.
  Results always carry 2.0 names.
- **Downloaded files.** A folder downloaded with client 0.1 (release 1.8 / unit 0.3: `timeseries.parquet`, 1.x
  columns) is not read: `batang.open()` raises `LegacyLayoutError`. Download the records again; 2.0 downloads go to
  `~/batang_cache/2.0/`, so the old folder stays until you delete it.

## Command line

```bash
batang info
batang find tasks=aging cathode_family=LFP --limit 20 --csv lfp.csv
batang schema 전압
batang download STROEBL_S1_k01_01 --columns voltage_v,current_a
batang download --filter dataset=STROEBL --files cycles
batang download nmc_aging.json
batang ls
batang validate my_cell/
```

## Settings

| | |
|---|---|
| `BATANG_URL` | MCP endpoint (default `https://batang.yonsei.ac.kr/mcp`) |
| `BATANG_AUTH_URL` | login service, when it is not at the endpoint's origin |
| `BATANG_TOKEN` | a token to use instead of the stored one |
| `BATANG_CONFIG_DIR` | where the token is kept (default `~/.config/batang`) |

`connect(url=..., cache=..., release=..., prefer="remote", offline=True, login=False)` takes the same settings as arguments.

## Data use

Batang is read-only. Each user has a daily transfer and query quota, which you can see on the account page. If you hit the per-minute request limit, the client waits and retries.
Each dataset keeps its own licence. `info()` and `describe()` show it, and you should cite the original dataset along with Batang.

## Development

```bash
cd client
python -m unittest discover -s tests              # a fake server, no network
BATANG_E2E_URL=http://localhost:4193/mcp BATANG_E2E_AUTH_URL=http://localhost:4192 \
  python -m unittest tests.test_e2e               # against a running server
```

The distribution and the import name are both `batang`. Do not install it into an environment that already has another package called `batang`, such as the server-side tooling. Keep a separate virtual environment for the client.
