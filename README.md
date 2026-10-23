<p align="center">
  <img src="docs/assets/logo.png" alt="MPMC Battery logo" width="160">
</p>

<h1 align="center">Batang</h1>

<p align="center">
  <b>The foundation for every battery experiment, model and insight.</b><br>
  <i>Batang</i> (바탕) means foundation in Korean. Public battery ageing and fault data, standardized into one schema:
  a web hub, an MCP server for AI assistants, a Python package, and the files.
</p>

<p align="center">
  <a href="https://batang.yonsei.ac.kr"><b>batang.yonsei.ac.kr</b></a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#option-2-ask-an-ai-assistant-mcp">MCP</a> ·
  <a href="DATASETS.md">Datasets</a> ·
  <a href="DATA_FORMAT.md">Data format</a> ·
  <a href="#citation">Citation</a> ·
  <a href="#license">License</a>
</p>

> **Access:** sign in with a Yonsei University Google account (`@yonsei.ac.kr`). Other researchers can apply on the
> sign-in page; access starts once the maintainer approves it. Everything is read-only.
> [Privacy policy](https://batang.yonsei.ac.kr/privacy) · [Terms](https://batang.yonsei.ac.kr/terms)

---

## What Batang is

Public battery ageing datasets come in dozens of formats, with different units, current signs, cycle definitions and
capacity references. Batang converts each dataset **cell by cell** into one documented schema and offers it in three
ways:

| | |
|---|---|
| **Database** | release 2.0 (schema 2.0.0), two stores: |
| | cell store: 43 public datasets · 3,400 cells (Li-ion, Na-ion, Zn-ion) · 10.0 M cycles · 17.0 G samples, at the source's own time resolution, with per-sample quality flags |
| | device store: 11 datasets of packs, storage systems, vehicles and fault tests · 1,513 devices and 31,449 charging sessions · 436 k segments · 336 M samples, with fault labels (normal / faulty / unknown) |
| **Hub** | the Batang web site: an overview dashboard, datasets to explore and filter, cell and device pages with cycle summaries and raw voltage / current / temperature, cell comparison, the data model, release notes |
| **AI assistants** | a remote MCP server: an assistant such as Claude searches, aggregates and reads the data for you, read-only |
| **Data** | the standardized files themselves (Apache Parquet), for your own analysis or model training |

What "standardized" means:

- **One schema**: one naming rule for every column (the unit is always last: `voltage_v`, `temperature_max_c`),
  current positive while charging, time, step and capacity counters that restart in every cycle.
- **One cycle definition**: a cycle is `charge → (rest) → discharge → (rest)`, independent of the cycler's own cycle
  counter.
- **Nothing deleted**: reference performance tests and irregular cycles are kept and tagged (`cycle_kind`:
  `aging` / `rpt` / `initial` / `partial` / `irregular`) instead of being removed.
- **One SOH definition**: `soh` = capacity of the cell's reference measurement ÷ the same measurement at the
  beginning of life, for every cell, plus `efc` (equivalent full cycles) as the ageing axis.
- **License kept with the data**: every cell carries its dataset's license and whether commercial use is allowed.

## Quick start

There are three ways to use Batang. All read the same standardized data, all need a sign-in, and all are read-only.

### Option 1: the Batang

Open [batang.yonsei.ac.kr](https://batang.yonsei.ac.kr) and sign in. Nothing to install.

| Page | What you can do |
|---|---|
| **Overview** | the current release at a glance: datasets, cells, devices and samples; ageing and fault side by side (SOH trajectories over equivalent full cycles, grouped by cathode, institution, form factor or dataset; normal / faulty / unknown per fault dataset); composition and test conditions, each clickable as a filter |
| **Datasets** | choose a task (ageing / fault), filter by level, setting, chemistry, cathode, form factor, size, commercial use and dataset, search, sort; one dataset shows its source, licence and quality tags; open a cell or a device |
| **Cell** | metadata and test conditions, SOH and capacity over cycles, cycle kinds and procedures, the voltage / current / temperature of any cycle at full resolution |
| **Device** | a pack's, system's, vehicle's or fault test's configuration, fault label, per-segment trend and signals |
| **Compare** | several cells on one axis: SOH, capacity, efficiency, C-rates, temperatures ... against cycles or equivalent full cycles |
| **Schema** | the data model: dataset → cell or device → cycle or segment → sample, with what every variable means |
| **Release notes**, **API · MCP**, **Docs** | what changed, how to connect an AI assistant, the data format and the dataset table |

### Option 2: ask an AI assistant (MCP)

An assistant connected to Batang answers questions like *"How many LFP ageing cells are there?"*, *"Which NMC
datasets allow commercial use?"* or *"For CALCE, how many ageing cycles per cell end below 2.8 V?"* by querying the
data itself: it searches the catalog, aggregates on the server and reads cycles and samples, with read-only SQL for
anything the tools do not cover. Large results come back as download links instead of filling the conversation.

**Remote (recommended).** Nothing to install; the assistant signs you in through the browser.

```bash
# Claude Code
claude mcp add --transport http batang https://batang.yonsei.ac.kr/mcp
```

On claude.ai or Claude Desktop: Settings → Connectors → Add custom connector → `https://batang.yonsei.ac.kr/mcp`.

**Local bridge.** [`mcp/`](mcp) runs on your computer and forwards to the same server, so it always has the same
tools; it adds sign-in by browser approval and saving result links to your disk. Needs
[uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
claude mcp add batang -- uvx --from "git+https://github.com/pjmbatman/batang#subdirectory=mcp" batang-mcp
```

Then ask the assistant to log in to Batang (`login`): open the link it shows and approve the code.

**Tools**

| Tool | What it does |
|---|---|
| `info` | releases, datasets with counts, licences and commercial use, filter vocabularies |
| `find_records` | cells and devices by task (`tasks`), dataset, cathode, form factor, size, chemistry, level, setting, label, commercial use, fault status, temperature or C-rate range |
| `describe` | one dataset, cell or device: properties, test conditions, SOH definition or fault label, quality, licence |
| `stats` | counts and statistics of catalog metrics (`grain="record"`), or of cycle and segment rows that match conditions (`grain="cycle"` / `"segment"`), grouped |
| `cycles` | cycle rows of cells, segment rows of devices |
| `cycle_samples` | the samples of one cycle or segment, at full resolution or reduced |
| `schema` | what a variable means, its unit and column name |
| `query` | any read-only SQL (`SELECT`) over the views `cells`, `devices`, `cycles`, `segments`, `samples`, `device_samples` and the macros `cycle_samples()`, `segment_samples()` |
| `download` | links to the files of selected cells and devices |
| `login`, `whoami`, `save_link` | local bridge only: sign in, check the sign-in, save a link to a file |

Tools take and return the 2.0 column names of [DATA_FORMAT.md](DATA_FORMAT.md); for release 2.0 they also accept the
1.x names in arguments. Use is limited per person (requests per minute, query time and data per day), not per tool. Check each dataset's
`license` and `commercial_use` before you use a result, and cite the original source. The bridge in [`mcp/`](mcp) is
MIT-licensed.

### Option 3: use the standardized data yourself

**Python package.** Install it from this repository, sign in once with your Yonsei Google account, and use the
same operations as the MCP tools (`find_records`, `describe`, `stats`, `cycles`, `cycle_samples`, `query`, `download`).
It reads what you have downloaded first and asks the server only for the rest; nothing is downloaded unless you call
`download()`.

```bash
pip install "git+https://github.com/pjmbatman/batang#subdirectory=client"
batang login
```

```python
import batang
db = batang.connect()
lfp = db.find_records(tasks="aging", cathode_family="LFP")
db.download(lfp.id[:10], columns=["voltage_v", "current_a"])
```

See [client/README.md](client/README.md) for offline use, validation of your own files and the PyTorch connector.

**Files you already have.** The files are plain Parquet; the examples need only `pandas`, `pyarrow`, `numpy` and
`matplotlib`. Every dataset folder is self-contained.

```bash
pip install pandas pyarrow numpy matplotlib
python examples/plot_cell.py /path/to/releases/2.0/cells MATR_b1c0        # SOH vs equivalent full cycles + one cycle's V / I
python examples/plot_cell.py /path/to/releases/2.0/cells MATR_b1c0 500    # a chosen cycle
```

[`examples/load_for_training.py`](examples/load_for_training.py) is a self-contained cycle-level dataset (one item =
one cycle) that reads only the columns and row groups you ask for and works as a PyTorch map-style dataset:

```python
from load_for_training import CycleDataset

ds = CycleDataset("/path/to/releases/2.0/cells",
                  columns=["voltage_v", "current_a", "temperature_c"],   # per-sample features
                  labels=["soh", "efc"],                                  # per-cycle labels
                  datasets=["MATR", "XJTU"])                              # or commercial_use="allowed"
item = ds[0]   # {"cell_id", "cycle", "voltage_v": array, "current_a": array, ..., "soh", "efc"}
```

Which features and labels exist, their units and how cycles, SOH and the flags are defined is the schema manual:
[DATA_FORMAT.md](DATA_FORMAT.md). Release 2.0 renamed columns, files and folders (values are unchanged); files
downloaded from a 1.x release keep the old names, so download 2.0 again
([Changes from 1.x](DATA_FORMAT.md#changes-from-1x)).

## Raw data (reference only)

Batang does not redistribute raw data and does not publish its standardization pipeline (the conversion from raw to
standardized data). If you need the original measurements, [DATASETS.md](DATASETS.md) lists for every dataset its
source, license and the article to cite; download them there, under that source's terms.

## Citation

If you use Batang, please cite it **and the original datasets you use** (see [DATASETS.md](DATASETS.md) and
[`docs/references.bib`](docs/references.bib)). GitHub's "Cite this repository" button reads
[`CITATION.cff`](CITATION.cff).

```bibtex
@misc{park2026batang,
  author = {Park, Jimin},
  title  = {{Batang}: Standardized Public Lithium-Ion Battery Ageing Data},
  year   = {2026},
  url    = {https://batang.yonsei.ac.kr},
  note   = {Release 2.0}
}
```

## License

- **Data**: Batang does not relicense any dataset. The standardized files remain under the license of their original
  source, listed per dataset in [DATASETS.md](DATASETS.md) together with whether commercial use is allowed. Attribute
  the original authors when you use or share them.
- Some sources state no data license, or one that could not yet be confirmed (cell store: ARGONNE_CAMP, CALCE,
  CALCE_PL, CALCE_STORAGE, HNEI, MATR, NASA, NASA_RW, SNL, TUM_50G, TUM_BAHRKE, TUM_SCHREIBER, UL_PUR; device store:
  HIT_ISC), and EVBATTERY states two different licenses. Use files derived from them for research with citation,
  and ask the authors before anything beyond that; the UL_PUR records are access-restricted by their authors.
- TURKU (CC BY-NC 3.0) and TUDA_LFP_FIELD (CC BY-NC 4.0) are non-commercial; MCMASTER_30T, MCMASTER_A123 (CC BY-SA
  4.0), OXFORD_DEG1, OXFORD_ENERGY_TRADING and OXFORD_PATH (ODbL) are share-alike.
- **This documentation**: [CC BY 4.0](LICENSE). The MCP bridge in [`mcp/`](mcp): MIT.

## Contact

Jimin Park, Department of Battery Conflation Engineering, Yonsei University (MPMC Battery) — pjm@yonsei.ac.kr

Batang exists only because the groups listed in [DATASETS.md](DATASETS.md) published their measurements openly.
