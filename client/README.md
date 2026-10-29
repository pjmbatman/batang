# batang — Python client for Batang

`batang` is the Python client for Batang: you can search records, read cycles and samples and run read-only SQL from Python or the command line, and fetch the files of an approved download request.
Each query method is a tool of the Batang MCP server, with the same name and the same arguments. So your Python code and an AI assistant connected to the MCP server ask the server for exactly the same things.
Whole record files are not handed out by the tools: you request them in the hub's 다운로드 tab (https://batanghub.com/#/downloads), and once the request is approved, `batang download --grant <id>` fetches them.

```bash
pip install "git+https://github.com/pjmbatman/batang#subdirectory=client"
pip install "batang[sql,torch,hdf5] @ git+https://github.com/pjmbatman/batang#subdirectory=client"   # optional extras
```

Version 0.3 reads Batang release 2.0 (schema 2.0.0); see [Schema 2.0](#schema-20-and-1x-downloads) below. It replaces `download()` of 0.2 with approved downloads ([Download files](#download-files)).
Requires Python 3.10+, with numpy, pandas and pyarrow. The extras add `sql` (duckdb, for SQL over your downloads), `torch` (`torch_dataset`) and `hdf5` (h5py, for `export(..., "x.h5")`).

## Log in

```bash
batang login        # shows a code, opens https://batanghub.com/auth/device; approve it with your Google account
batang whoami
```

You need a Batang account first: sign up at https://batanghub.com/signup with a Google account. Yonsei University accounts (@yonsei.ac.kr) can use it at once; anyone else applies there, and logs in the same way once the request is approved.
After the site moved to batanghub.com (2026-10-27), run `batang login` once more: tokens are kept per server.
The token is valid for 7 days. It is stored in `~/.config/batang/token` (mode 600) and is never printed.
The first call in an interactive session logs you in by itself. Scripts and CI can set `BATANG_TOKEN` instead; you create a token on the account page.

## Use

```python
import batang

db = batang.connect()                      # https://api.batanghub.com/mcp, cache in ~/batang_cache

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

### Download files

1. In the hub's 다운로드 tab, put whole datasets, cells, devices or search results in the cart, acknowledge the datasets' licences and send the request with a line on its purpose.
2. The owner approves it (or rejects it with a reason); the tab shows the status. An approved request has a grant id (`G-20261029-AB12`) and links that are valid for 7 days and 3 downloads per file.
3. Fetch it:

```bash
batang download --grant G-20261029-AB12 --to ~/batang_data          # 8 files at a time; --jobs to change it
```

```python
paths = batang.fetch_grant("G-20261029-AB12", "~/batang_data")
store = batang.open("~/batang_data/2.0")
```

The manifest of the grant is read with your login token; the files come straight from storage through their links (redirects are followed). Files go to `<to>/<release>/<dataset>/<id>/` with the file names of the release: `samples.parquet`, `cycles.parquet` (cells) or `segments.parquet` (devices), `meta.json`, and whatever else the request held (`samples_preview`, `cell_voltages`, `temperatures`, `aux`).
Every file's size is checked against the manifest. A file that is already there with its size is skipped, and an interrupted one is resumed where it stopped; a resume does not use up one of the file's downloads, so running the same command again is safe.
The folder also gets `index.json` (what is there, for `batang.open()`), `LICENSES.json` (each dataset's licence, commercial use and what to cite, printed once per dataset) and `selections/grant-<id>.json` (what the grant held; the links are not kept).
Without `--to` (or `to`), the files go to the cache, `~/batang_cache/<release>/`, where `connect()` reads them first.

Without Python, the grant's `urls.txt` (in the 다운로드 tab) works with `wget -c -x -nH --cut-dirs=3 -i urls.txt`, which keeps the `<dataset>/<id>/` folders and resumes; it writes no `index.json` or `LICENSES.json`.

### Local first

Once a record's files are in the cache, reads of that record use the local files whenever they hold the columns you asked for. Any other read goes to the server.

```python
db.fetch_grant("G-20261029-AB12")                  # into ~/batang_cache/2.0/
db.cycle_samples("STROEBL_S1_k01_01", 5).attrs["source"]    # "local"
db.query("SELECT cell_id, max(cycle) FROM cycles GROUP BY 1", local=True)   # DuckDB over your local files

sel = db.select(tasks="aging", cathode_family="NMC")
sel.save("nmc_aging.json")                  # the same set later: batang.Selection.load("nmc_aging.json")
```

If a remote read would transfer more than 1 GB, the client stops and tells you so. Request that data's files in the 다운로드 tab and read them locally, or pass `allow_large=True`.

### Offline

```python
db.download_catalog()                       # once, while online
off = batang.connect(offline=True)
off.find_records(cathode_family="LFP")      # from the cached catalog
off.cycles(["STROEBL_S1_k01_01"])           # from your local files; anything else raises OfflineError
```

Local SQL (`query(..., local=True)`) has the server's view and macro names: `cycles`, `segments`, `samples`,
`device_samples` with `dataset` and `cell_id` / `device_id` columns, `cycle_samples(cell_id[, cycle])`,
`segment_samples(device_id[, segment])`, and `records` (with `cells` and `devices`) once `download_catalog()` ran.

### Your own files, models, other tools

```python
st = batang.open("~/batang_data/2.0")       # a download folder, a copy of releases/2.0, or its cells/ or devices/
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
  `stats(level="cycle")`); they are translated and a `FutureWarning` names the 2.0
  name. When the server reports a translation of its own (`renamed` in an answer), the client warns the same way.
  Results always carry 2.0 names.
- **Downloaded files.** A folder downloaded with client 0.1 (release 1.8 / unit 0.3: `timeseries.parquet`, 1.x
  columns) is not read: `batang.open()` raises `LegacyLayoutError`. Request the records again; 2.0 files go to
  `<folder>/2.0/`, so the old folder stays until you delete it. Folders written by `download()` of client 0.2
  (also with `columns=`) are read as before.

## Command line

```bash
batang info
batang find tasks=aging cathode_family=LFP --limit 20 --csv lfp.csv
batang schema 전압
batang download --grant G-20261029-AB12 --to ~/batang_data [--jobs 8]
batang ls
batang validate my_cell/
```

## Settings

| | |
|---|---|
| `BATANG_URL` | MCP endpoint (default `https://api.batanghub.com/mcp`) |
| `BATANG_AUTH_URL` | login service, when it is not at the endpoint's origin |
| `BATANG_TOKEN` | a token to use instead of the stored one |
| `BATANG_CONFIG_DIR` | where the token is kept (default `~/.config/batang`) |

`connect(url=..., cache=..., release=..., prefer="remote", offline=True, login=False)` takes the same settings as arguments.

## Data use

Batang is read-only. Each user has a daily quota for query results (2 GB unless the maintainer raised it for you) and query time, which you can see on the account page. If you hit the per-minute request limit, the client waits and retries. Approved downloads are limited by their grant instead (time and downloads per file).
Each dataset keeps its own licence. `info()`, `describe()` and `LICENSES.json` show it, and you should cite the original dataset along with Batang.

## Development

```bash
cd client
python -m unittest discover -s tests              # a fake server, no network
BATANG_E2E_URL=http://localhost:4193/mcp BATANG_E2E_AUTH_URL=http://localhost:4192 \
  python -m unittest tests.test_e2e               # against a running server
```

The distribution and the import name are both `batang`. Do not install it into an environment that already has another package called `batang`, such as the server-side tooling. Keep a separate virtual environment for the client.
