<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/batang-mark-dark.svg">
    <img src="docs/assets/batang-mark.svg" alt="Batang logo" width="96">
  </picture>
</p>

<h1 align="center">Batang</h1>

<p align="center">
  <b>The foundation for every battery experiment, model and insight.</b><br>
  <i>Batang</i> (바탕) means foundation in Korean. An open hub for battery research: public cycling and fault data
  standardized into one schema, physics-based cell simulation and AI modeling, from the web, Python or an AI
  assistant.
</p>

<p align="center">
  <a href="https://batanghub.com"><b>batanghub.com</b></a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#option-2-ask-an-ai-assistant-mcp">MCP</a> ·
  <a href="DATASETS.md">Datasets</a> ·
  <a href="DATA_FORMAT.md">Data format</a> ·
  <a href="#citation">Citation</a> ·
  <a href="#license">License</a> ·
  <a href="#acknowledgements">Acknowledgements</a>
</p>

> **Access:** create an account on [batanghub.com](https://batanghub.com/signup) with a Google account and agree to
> the terms. Yonsei University accounts (`@yonsei.ac.kr`) can use it at once; other researchers apply on the same page,
> and access starts once the maintainer approves it. The public data is read-only.
> [Privacy policy](https://batanghub.com/privacy) · [Terms](https://batanghub.com/terms)

---

## What Batang is

Batang brings the three things battery research keeps rebuilding into one place: the data, simulation and AI models.
Public battery ageing datasets come in dozens of formats, with different units, current signs, cycle definitions and
capacity references; Batang converts each dataset **cell by cell** into one documented schema, and on top of it lets
you simulate cells with physics-based models and build, train and evaluate AI models, all in the browser:

| | |
|---|---|
| **Database** | release 2.0 (schema 2.0.0), two stores: |
| | cell store: 43 public datasets · 3,400 cells (Li-ion, Na-ion, Zn-ion) · 10.0 M cycles · 17.0 G samples, at the source's own time resolution, with per-sample quality flags |
| | device store: 11 datasets of packs, storage systems, vehicles and fault tests · 1,513 devices and 31,449 charging sessions · 436 k segments · 336 M samples, with fault labels (normal / faulty / unknown) |
| **Hub** | the Batang web site: an overview dashboard, datasets to explore and filter, cell and device pages with cycle summaries and raw voltage / current / temperature, cell comparison, the data model, release notes |
| **Virtual Lab** | in the hub: **simulation** with PyBaMM (SPM, SPMe, DFN; cell parameter sets, experiment protocols built from steps, voltage and internal state variables) and **AI modeling** (pick records and preprocess them, build a model from blocks, train it on a GPU and watch it learn, evaluate a checkpoint on other data; the choices become PyTorch and NumPy code you can download) |
| **Research assistant** | 바탕이, a chat in the hub that finds data, explains it and opens the right screen (a cell, a comparison, a simulation filled in for you to run); each conversation is private to the person |
| **My data** | upload your own cycler files; they are converted into the same schema and can be explored and compared with the public cells, visible to you alone |
| **AI assistants** | a remote MCP server: an assistant such as Claude searches, aggregates and reads the data for you, read-only |
| **Downloads** | the standardized files themselves (Apache Parquet), for your own analysis or model training: requested in the hub's 다운로드 tab and fetched once the request is approved |

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
Batang is made for exploring, comparing, simulating and training inside the hub; the MCP server and the Python package
query the data, and whole record files leave only through the hub's **다운로드** (Downloads) tab, after approval.

### Option 1: the Batang

Open [batanghub.com](https://batanghub.com), sign up once and sign in. Nothing to install.

| Page | What you can do |
|---|---|
| **Overview** | the current release at a glance: datasets, cells, devices and samples; ageing and fault side by side (SOH trajectories over equivalent full cycles, grouped by cathode, institution, form factor or dataset; normal / faulty / unknown per fault dataset); composition and test conditions, each clickable as a filter |
| **Datasets** | choose a task (ageing / fault), filter by level, setting, chemistry, cathode, form factor, size, commercial use and dataset, search, sort; one dataset shows its source, licence and quality tags; open a cell or a device |
| **Cell** | metadata and test conditions, SOH and capacity over cycles, cycle kinds and procedures, the voltage / current / temperature of any cycle at full resolution |
| **Device** | a pack's, system's, vehicle's or fault test's configuration, fault label, per-segment trend and signals |
| **Compare** | several cells on one axis: SOH, capacity, efficiency, C-rates, temperatures ... against cycles or equivalent full cycles |
| **Schema** | the data model: dataset → cell or device → cycle or segment → sample, with what every variable means |
| **다운로드** (Downloads, under 내 공간) | put datasets, cells, devices or search results in a cart, see the size and the licences to acknowledge, and send a request with its purpose; the owner approves it (or rejects it with a reason), and an approved request gets download links valid for 7 days and 3 downloads per file, a `urls.txt` for `wget`, and the line for the Python package |
| **Release notes**, **API · MCP**, **Docs** | what changed, how to connect an AI assistant, the data format and the dataset table |

### Option 2: ask an AI assistant (MCP)

An assistant connected to Batang answers questions like *"How many LFP ageing cells are there?"*, *"Which NMC
datasets allow commercial use?"* or *"For CALCE, how many ageing cycles per cell end below 2.8 V?"* by querying the
data itself: it searches the catalog, aggregates on the server and reads cycles and samples, with read-only SQL for
anything the tools do not cover. Large query results come back as links instead of filling the conversation. The
tools query; they do not hand out whole record files (those come from the 다운로드 tab).

**Remote (recommended).** Nothing to install; the assistant signs you in through the browser.

```bash
# Claude Code
claude mcp add --transport http batang https://api.batanghub.com/mcp
```

On claude.ai or Claude Desktop: Settings → Connectors → Add custom connector → `https://api.batanghub.com/mcp`.

**Local bridge.** [`mcp/`](mcp) runs on your computer and forwards to the same server, so it always has the same
tools; it adds sign-in by browser approval and saving query result links to your disk. Needs
[uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
claude mcp add batang -- uvx --from "git+https://github.com/pjmbatman/batang#subdirectory=mcp" batang-mcp
```

Then ask the assistant to log in to Batang (`login`): open the link it shows and approve the code.

**Tools**

| Tool | What it does |
|---|---|
| `info` | releases, datasets with counts, licences and commercial use, filter vocabularies |
| `find_records` | cells and devices by task (`tasks`), dataset, cathode, form factor, size, chemistry, level, setting, label, commercial use, fault status, temperature, C-rate, cycle count, last SOH or EFC range; `sort` by cycles, EFC or SOH, `limit` the rows |
| `describe` | one dataset, cell or device: properties, test conditions, SOH definition or fault label, quality, licence |
| `stats` | counts and statistics of catalog metrics (`grain="record"`), or of cycle and segment rows that match conditions (`grain="cycle"` / `"segment"`), grouped |
| `cycles` | cycle rows of cells, segment rows of devices |
| `cycle_samples` | the samples of one cycle or segment, at full resolution or reduced |
| `schema` | what a variable means, its unit and column name |
| `query` | any read-only SQL (`SELECT`) over the views `cells`, `devices`, `cycles`, `segments`, `samples`, `device_samples` and the macros `cycle_samples()`, `segment_samples()` |
| `login`, `whoami`, `save_link` | local bridge only: sign in, check the sign-in, save a query result link to a file |

Tools take and return the 2.0 column names of [DATA_FORMAT.md](DATA_FORMAT.md); for release 2.0 they also accept the
1.x names in arguments. Use is limited per person (requests per minute, query time, and 2 GB of query results per day
unless the maintainer raised it for you), not per tool. Check each dataset's `license` and `commercial_use` before you
use a result, and cite the original source. The bridge in [`mcp/`](mcp) is MIT-licensed.

### Option 3: use the standardized data yourself

**Request the files.** In the hub's 다운로드 tab, put what you need in the cart and send the request with its
purpose. Once it is approved, the tab shows the grant id, the links (valid for 7 days, 3 downloads per file; the bytes
come straight from storage) and a `urls.txt` for `wget -c -x -nH --cut-dirs=3 -i urls.txt`, which keeps the
`<dataset>/<id>/` folders.

**Python package.** Install it from this repository and sign in once with your Batang account. It fetches an approved
request in parallel, resumes interrupted files, checks every file's size, and puts the files in the release layout
that it reads locally:

```bash
pip install "git+https://github.com/pjmbatman/batang#subdirectory=client"
batang login
batang download --grant G-20261029-AB12 --to ~/batang_data      # → ~/batang_data/2.0/<dataset>/<id>/
```

The licences of the request's datasets are kept in `LICENSES.json` next to the files and printed once per dataset:
follow them and cite the original sources. The package also queries, with the same operations as the MCP tools
(`find_records`, `describe`, `stats`, `cycles`, `cycle_samples`, `schema`, `query`); it reads your local files first
and asks the server only for the rest:

```python
import batang
store = batang.open("~/batang_data/2.0")
db = batang.connect()
lfp = db.find_records(tasks="aging", cathode_family="LFP")
db.cycles(lfp.id[:10], columns=["efc", "soh"])
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
downloaded from a 1.x release keep the old names, so request 2.0 again
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
  title  = {{Batang}: An Open Hub for Battery Data, Simulation and {AI} Modeling},
  year   = {2026},
  url    = {https://batanghub.com},
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

## Acknowledgements

<p>
  <a href="https://www.mpmc.yonsei.ac.kr/"><img src="docs/assets/mpmc-lab-logo.png" alt="MPMC Battery logo" width="120" align="right"></a>
</p>

The servers that run Batang for its users (the virtual machines, CPU and GPU behind the web hub, the MCP server and
the Virtual Lab) are provided by the [Multi-Physics Modeling & Computation Lab (MPMC)](https://www.mpmc.yonsei.ac.kr/),
Yonsei University, led by Prof. Jung-Il Choi. I thank Prof. Choi and the MPMC lab for supporting the operation of
this platform.

Batang is developed and maintained by Jimin Park, who holds its copyright; the licenses are listed
[above](#license).

<br clear="right">

## Contact

Jimin Park, Department of Battery Conflation Engineering, Yonsei University (MPMC Battery) — pjm@yonsei.ac.kr

Batang exists only because the groups listed in [DATASETS.md](DATASETS.md) published their measurements openly.
