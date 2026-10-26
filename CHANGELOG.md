# Changelog

Releases of the standardized data. Each release is a complete, versioned copy of the store. From 2.0 one release
number covers both stores.

## Service (2026-10-26)

- Every store has a `SHA256SUMS` file (the format of `sha256sum -c`), and every change to a store is logged with its
  date and the datasets it touched. Both are on the hub's release page. Old releases are not kept: the checksums tell
  which publication a downloaded file belongs to.
- Downloads (`download()` in the Python package, the `download` MCP tool) now come with each dataset's licence,
  commercial-use status and source; the package keeps them in `LICENSES.json`.

## 2.0 + parameter sets (2026-10-26, schema 2.1.0)

- **Parameter-set store** `releases/2.0/parameter_sets/`, a third store next to cells and devices: 43 cell parameter
  sets for PyBaMM's DFN, SPMe and SPM, stored as ParameterValues JSON with the source of every value, the BPX file when
  the set was published as BPX, and the DFN / SPMe / SPM discharges solved when the set was stored
  ([DATA_FORMAT.md](DATA_FORMAT.md#parameter-set-store), list in [DATASETS.md](DATASETS.md#parameter-sets)).
- The cell and device stores are unchanged.

## 2.0 (2026-10-23)

- **Schema 2.0.0**, for the cell store and the device store: every column, file and folder name follows one set of
  naming rules ([DATA_FORMAT.md](DATA_FORMAT.md#naming-rules)). Values are unchanged: each 2.0 file holds the same
  numbers as its 1.x file under the new names. The complete old → new list is
  [docs/schema_2_renames.json](docs/schema_2_renames.json); the main changes are in
  [DATA_FORMAT.md](DATA_FORMAT.md#changes-from-1x).
- One release for both stores: `releases/2.0/cells/` (was `standardized/`, cell store 1.8) and
  `releases/2.0/devices/` (was `standardized_unit/`, unit store unit 0.3). The unit store is now the **device
  store**, `unit_id` is `device_id`.
- Per-record files: `samples.parquet` (was `timeseries.parquet`), `samples_preview.parquet` (was `preview.parquet`),
  `cell_voltages.parquet` with columns `cell_000_v` ... (was `cells_v.parquet`, `v_000` ...),
  `temperatures.parquet` with columns `sensor_000_c` ... (was `temps.parquet`, `t_000` ...), `aux.parquet` with
  renamed columns. `index.csv` is dropped.
- Columns that hold several values (`tasks`, `aliases`, `soh_sources`, `fault_classes`, `procedures`) are
  `list<string>` instead of comma-joined text; the cell catalog's `time_absolute` (bool) is `time_kind`
  (`absolute` / `relative`), as in the device store.
- Server: SQL views `cells`, `devices`, `cycles`, `segments`, `samples`, `device_samples` and macros
  `cycle_samples(id[, cycle])`, `segment_samples(id[, segment])`. MCP tool names are unchanged; `find_records`
  `kind` is `cell`, `device` or `session`. Filter arguments are `tasks`, `size_code`, `level`, `setting`; `stats`
  chooses catalog or row statistics with `grain` (`record`, `cycle`, `segment`), and `level` is the catalog column.
  `info()` reports `release`, `cell_store` and `device_store`, with `tasks` and `cathode_families` as lists. For
  release 2.0 the MCP tools, the API and the Python client also accept 1.x column and argument names and translate
  them; answers list the server's translations under `renamed`.
- Cell store: 2 datasets added, 66 cells: OXFORD_ENERGY_TRADING (Reniers et al., 6 Kokam 16 Ah NMC pouch cells
  under a year of energy-trading current profiles; SOH from the source's capacity check-ups, ODbL 1.0) and UMICH_WAN
  (Wan et al. 2026, 60 NMC622 / SiO-graphite 2.5 Ah pouch cells in 24 conditions, CC BY 4.0). 43 datasets, 3,400
  cells. Cells of release 1.8 are unchanged.
- Device store: the records of unit 0.3, unchanged (11 datasets, 1,513 devices and 31,449 sessions).
- Python client `batang` 0.2.0: 2.0 names everywhere; local reading of the 2.0 layout and of a copy of
  `releases/2.0`; files downloaded from a 1.x release are not read (download them again). MCP bridge
  `batang-mcp` 0.3.0 (documentation only).

## Cell store (until 2.0)

Names in the entries below are the 1.x names of their time.

### 1.8 (2026-10-22)

- Schema 1.6.0: three per-cycle columns say what test a cycle is, separate from its role (`cycle_kind`).
  `test_type` is the procedure of the main discharge (`capacity`, `cycling`, `drive_profile`, `pulse`, `hppc`,
  `gitt`, `ocv`, `eis`, `storage`, `formation`, `other`, `unknown`), `test_types` every procedure found in the
  cycle, and `test_type_source` the evidence: `source` (the source's file or step tags, or its documented test
  design; 81 % of cycles), `detected` (waveform rules; 18.3 %) or `unknown` (0.7 %, left unknown rather than
  guessed). An HPPC inside a reference test is `cycle_kind` `rpt`, `test_type` `hppc`. `meta.counts.test_types`
  summarizes them per cell.
- CALCE: a pause between two files is treated as a rest when the voltage relaxes away from the last current and no
  unlogged step crosses it; 38 cycles that 1.7 had excluded from SOH get their 1.6 values back.
- Only `cycles.parquet` and `meta.json` changed; time series and previews are byte-identical to 1.7.

### 1.7 (2026-10-22)

- OXFORD_DEG1 (Birkl 2017, 8 Kokam 740 mAh pouch cells, ODbL). The release holds the characterization tests every
  100 drive cycles; `equiv_full_cycles` adds the drive cycles between them, as stated in the readme.
- STANFORD_GESLIN: the cycler's capacity counter is used where the 50–100 s logging misses the protocol's pulses;
  all 92 cells are in (84 before), and cycles with a time gap drop from 13,640 to 1.
- STANFORD_MOY: the current of the sparsely logged cycling is held over each logging interval; cycling capacities
  are no longer lower bounds.
- Temperature flags: a smooth departure of the cell from the chamber set point (a cold test, cells warming up after
  a cold test) is a real reading and is no longer flagged; sensor faults stay flagged.
- `has_time_gap` also marks cycles that span missing files between two recording blocks; they are no longer SOH
  reference points.
- ARGONNE_CAMP: 5 V spinel cells are checked against their own voltage window; `cathode_family` adds `LNMO` and
  `LMR`.
- TUM_SCHREIBER: CC BY 4.0 (the record's rights field), commercial use allowed.
- Catalog: `categories` (`aging`), `identity` (`device`) and `cell_model` join the columns shared with the unit
  store (`model` is kept).
- 41 datasets, 3,334 cells.

### 1.6 (2026-10-21)

- 4 datasets from the Technical University of Munich, 287 cells: TUM_WILDFEUER (196, Sony/Murata VTC5A, calendar
  and cycle ageing), TUM_BAHRKE (70, sodium-ion 18650), TUM_50G (18, Samsung 50G), TUM_SCHREIBER (3, 78 Ah VW ID.3
  pouch cells).
- 40 datasets, 3,318 cells, 10.0 M cycles, 16.4 G samples. Cells of release 1.5.3 are unchanged.
- The licenses of TUM_50G and TUM_SCHREIBER (CC BY 4.0 per the repository page) and of TUM_BAHRKE are not yet
  confirmed; the catalog lists them as not stated.

### 1.5.3 (2026-10-21)

- BATTERYLIFE_ZN, 20 cells of batch 2: the SOH reference is the longest ageing phase, with its own beginning of
  life; the short conditioning blocks before it (7–41 cycles at other rates) have no SOH (`meta.soh.note`).

### 1.5.2 (2026-10-21)

- BATTERYLIFE_ZN, 20 cells: a later rate phase is chained to the one before by continuity (the SOH at the end of the
  previous phase against the first capacities of the new one, `anchor` in `meta.soh.phases_chained`). Zn cells
  keep gaining capacity after a rate change, and chaining at the new phase's initial maximum left steps in the SOH
  curve.

### 1.5.1 (2026-10-21)

- Schema 1.5.0: `form_factor` is the shape only (`cylindrical`, `prismatic`, `pouch`, `coin`, empty = not stated);
  the new `cell_format` holds the size designation (`18650`, `21700`, `26650`, `502030` ...). Both are in the
  catalog and `meta.cell`. Only `meta.json` changed, apart from the cycles tables of the BATTERYLIFE_ZN cells
  below; no time series changed.
- BATTERYLIFE_ZN, 21 cells: ageing phases are split where the discharge rate changes (e.g. 2.42C → 3.33C), each
  with its own beginning of life, chained per phase; empty cycles of dead cells no longer get an infinite C-rate.

### 1.5 (2026-10-21)

- 15 datasets added, 1,141 cells: AALBORG_FORKLIFT, ARGONNE_CAMP, BATTERYLIFE_NA, BATTERYLIFE_ZN, CALCE_PL,
  CALCE_STORAGE, LYON_A123, MCMASTER_30T, MCMASTER_A123, OXFORD_PATH, STANFORD_GESLIN, STANFORD_MOY, TURKU,
  UPPSALA_GUO, WARWICK_M50.
- 36 datasets, 3,031 cells, 9.0 M cycles, 15.4 G samples.
- First non-lithium chemistries (`chemistry_family` `Na-ion`, `Zn-ion`), first coin cells, calendar (storage)
  ageing with sparse check-ups (CALCE_STORAGE), and a source that publishes only normalized current and capacity
  (STANFORD_GESLIN, `meta.cell.capacity_units = "normalized"`).
- New license classes: share-alike (CC BY-SA 4.0, ODbL) and non-commercial (TURKU, CC BY-NC 3.0).

### 1.4 (2026-10-21)

- Per-sample quality flags (`timeseries.quality`) for errors found in a sample-level audit of all 12.8 G samples:
  the cycler's false current reading and interleaved rows of another record (RWTH_DRIVE), floating voltage inputs
  (IMPERIAL, FARASIS, MATR, NASA), rows re-inserted out of order (SNL), failed temperature sensors (NASA_RW,
  STROEBL, VVEHICLE, IMPERIAL, RWTH).
- Cathode chemistry checked against primary sources; `cathode_family` added; NASA and NASA_RW set to unknown
  (no primary source states it).
- Catalog classes `cathode_family`, `chemistry_family`, `label_tier`, `domain`, `unit_level`.
- No row was added or removed; cycle kinds changed in 12 cells where a flagged reading had split or merged a
  cycle, and the final SOH of NASA_B0050 moved from 0.915 to 0.969 (a contaminated cycle no longer counts).

### 1.3 (2026-10-20)

- 21 life-cycling datasets, 1,890 cells (13 datasets added since the first internal version: CMU_EVTOL, FARASIS,
  IMPERIAL, ISU_ILCC, KIT_LUH, NASA_RW, RWTH_DRIVE, SDU, STROEBL, TONGJI, TUB_NEUPERT, VVEHICLE, XJTU).
- Store format 3: zstd-compressed Parquet with row groups cut at cycle boundaries, per-cell previews, root catalog
  and cycles tables, SHA-256 checksums in `manifest.json`.
- License and commercial-use class of every dataset in the catalog and the manifest.

## Unit store (packs, systems, vehicles, fault tests; the device store from 2.0)

### unit 0.3 (2026-10-21)

- The returned LFP storage systems are published by TU Darmstadt and MIT (Schaeffer et al.), not TUM: the dataset key
  is now `TUDA_LFP_FIELD` (units `TUDA_LFP_FIELD_SYS01` … `SYS28`); the former ids `TUM_LFP_FIELD_*` are kept as
  aliases.
- Unit catalog carries the same shared core as the cell catalog: `anode`, `form_factor`, `cell_format` added.

### unit 0.2 (2026-10-21)

- 2 datasets of electric-vehicle charging records: ZHANG (Zhang et al. 2023, 102 vehicles) and EVBATTERY (463
  vehicles).
- The two releases come from the same group and platform and share 246 vehicles. Each such vehicle is one unit,
  listed under the release its samples come from, with the other release's id in `aliases`: 245 are EVBATTERY units
  (the EVBattery copy covers the Zhang record; the stretches only the Zhang release holds are appended as their own
  blocks, and the unit keeps Zhang's fault label); one stays a ZHANG unit because its EVBattery copy holds only its
  first session.
- 11 datasets, 32,962 units (1,513 devices, 31,449 sessions), 436,111 segments, 336 M samples.

### unit 0.1 (2026-10-21)

- First release of the unit store (unit schema 0.1.0): 9 datasets, AUTOSUN, CAO_DTI, CAO_GIS, CAO_QAS, HIT_ISC,
  MCMASTER_PHEV_PACK, STRAIN_FAILURE, TR_CORPUS, TUDA_LFP_FIELD.
- 32,397 units (948 devices, 31,449 sessions), 226,973 segments, 168 M samples.
- One schema for ageing and fault data: segments, fault labels with status `normal` / `faulty` / `unknown`,
  `fault_active` per segment, unit identity `device` / `session`, quality bits 16 (filled by the source) and 32
  (odometer).

## Access

- 2026-10-23: the Batang replaces the Atlas. Sign-in with a Yonsei University Google account is required for
  the site, the API and MCP (other researchers can apply). The MCP server is remote at https://batang.yonsei.ac.kr/mcp
  (tools: info, find_records, describe, stats, cycles, cycle_samples, schema, read-only query, download), with limits per
  person instead of per call; `mcp/` becomes a local bridge to it (batang-mcp 0.2.0).
- 2026-10-21: the Atlas reads the data through a query API; the site no longer serves Parquet files. The MCP package
  (`mcp/`) lets an AI assistant query Batang through the same API.
- 2026-10-21: the Atlas shows the unit store (unit and fault pages) next to the cells.

## Coming next

- More cell datasets, among them Stanford (Pozzato et al.).
