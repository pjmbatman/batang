# Data format

The standardized data is a folder of [Apache Parquet](https://parquet.apache.org) files plus a few JSON files. Any
Parquet reader works: pandas, pyarrow, polars, DuckDB, R arrow, MATLAB `parquetread`. No Batang software is needed.

This page is the schema manual of **release 2.0** (schema 2.1.0). One release covers three stores:

- the **cell store** (`cells/`): lab cells cycled for ageing;
- the **device store** (`devices/`): modules, packs, storage systems, vehicles and every fault test, including fault
  tests on single cells. In releases before 2.0 it was called the unit store;
- the **parameter-set store** (`parameter_sets/`): cell parameter sets for physics-based models (PyBaMM DFN, SPMe,
  SPM). Added on 2026-10-26 with schema 2.1.0; the cell and device stores did not change.

Schema 2.0 renamed columns, files and folders; no value changed. [Changes from 1.x](#changes-from-1x) at the end
of this page lists what moved; every release is listed in [CHANGELOG.md](CHANGELOG.md).

Contents: [Layout](#layout) · [Naming rules](#naming-rules) · [Common rules](#common-rules) ·
[Shared catalog core](#shared-catalog-core) · [Cell store](#cell-store) · [Device store](#device-store) ·
[Parameter-set store](#parameter-set-store) ·
[Server views (SQL)](#server-views-sql) · [Licenses in the data](#licenses-in-the-data) ·
[Changes from 1.x](#changes-from-1x)

## Layout

```
releases/2.0/
  manifest.json                  release, schema version, the stores and their totals
  PUBLISHED.jsonl                one line per change to a store: date, files added / changed / removed, datasets
  cells/
    SHA256SUMS                   every file's SHA-256 (sha256sum -c format); the same in devices/ and parameter_sets/
    manifest.json                format and schema versions, columns, dtypes and units, license per dataset,
                                 per-file sizes and SHA-256
    catalog.parquet              one row per cell
    cycles.parquet               the cycles table of every cell, keyed by (dataset, cell_id)
    cycles_preview.parquet       up to 120 cycles per cell: cycle, cycle_kind, efc, soh (overview plots)
    <DATASET>/<cell_id>/
      samples.parquet            one row per sample, at the source's resolution
      samples_preview.parquet    a row subset of samples.parquet (up to 160 cycles x about 80 rows), same columns
      cycles.parquet             one row per cycle
      meta.json                  cell and test information, SOH definition, counts, notes, source files
  devices/
    manifest.json                schema version, column dtypes, license per dataset, totals
    catalog.parquet              one row per device (or session)
    segments.parquet             the segment table of every device, keyed by (dataset, device_id)
    <DATASET>/<device_id>/
      samples.parquet            one row per sample, as recorded (no resampling)
      samples_preview.parquet    a row subset of samples.parquet for quick plots, same columns
      cell_voltages.parquet      optional, same rows as samples: one column per cell in series (cell_000_v ...)
      cell_voltages_preview.parquet  optional, the same rows as samples_preview
      temperatures.parquet       optional, same rows as samples: one column per sensor (sensor_000_c ...)
      aux.parquet                optional, same rows as samples: other measured quantities (pressure, gas, strain ...)
      segments.parquet           one row per segment
      meta.json                  configuration, channel map, labels, notes on the raw data, source files
  parameter_sets/
    manifest.json                format, schema version, sets and their files
    catalog.parquet              one row per parameter set
    index.json                   what a simulation lists: per set its catalog fields, model options and hints
    <PROVIDER>/<set_id>/
      parameters.json            the set as PyBaMM ParameterValues JSON (ParameterValues.from_json)
      meta.json                  the catalog fields, where each value came from, model options
      preview.json               scalar values and the functions sampled over their range
      checks.json                SPM, SPMe and DFN discharges solved when the set was stored
      source/                    the as-published file (BPX, tables), when its licence allows
```

Every dataset and record folder is self-contained, so you can request and use only the datasets or records you
need. A download from the server (Python client or MCP `download`) keeps the `<DATASET>/<id>/` part of this layout.
Old releases are not kept; `SHA256SUMS` (on the hub's release page) tells which publication a downloaded file
belongs to.

## Naming rules

One set of rules produces every name in both stores:

| # | Rule | Examples |
|---|---|---|
| 1 | snake_case, English, full words; abbreviations only from the list below | `temperature_max_c` |
| 2 | order `[scope_]quantity[_statistic][_unit]`; the unit is always last | `cell_voltage_spread_p99_v`, `odometer_end_km` |
| 3 | a physical quantity ends with its unit: `v a ah wh w kwh s min c ohm km kmh kpa n mm mol ppm microstrain bytes days`; SOC, SOH, efficiencies and C-rates are ratios and have none | `voltage_min_v`, `soh`, `charge_c_rate` |
| 4 | one quantity has one name in every table; the table gives the grain (sample, cycle, segment, record) | `efc` per cycle and segment, `efc_end` per record |
| 5 | counts start with `n_` | `n_cycles`, `n_samples`, `n_time_gaps` |
| 6 | booleans start with `is_` or `has_` | `is_complete`, `has_fault_onset` |
| 7 | a column holding several values is a `list<string>`, named in the plural | `tasks`, `procedures`, `fault_classes` |
| 8 | positions into an array file end in `_index`, counted from 0 (the column order of `cell_voltages` / `temperatures`) | `cell_voltage_max_index` |
| 9 | values supplied by the source rather than computed by Batang start with `reported_` (labels) or `source_` (references, flags) | `reported_capacity_ah`, `source_ref_first` |
| 10 | no SQL keywords as names | `group_id` |

Abbreviations: `soh`, `soc`, `efc` (equivalent full cycles), `bol` (beginning of life), `ocv`, `rpt` (reference
performance test), `bms`, `eis`, `ir`, `re`, `rct`, `cc`, `cv`, `p50` / `p99`, `id`.

## Common rules

| Item | Rule |
|---|---|
| Units | in the column name (rule 3): V, A, Ah, Wh, W, s, °C, Ω, km, km/h ... |
| Current sign | charge positive, discharge negative |
| Cycle (cells) | starts where a charge following a discharge (or the first charge of the test) begins, so every cycle is `charge → (rest) → discharge → (rest)`; the source's own cycle counter is kept only as `source_ref_first` / `source_ref_last` |
| Per-cycle reset (cells) | `cycle_time_s`, `step`, `charge_ah`, `discharge_ah` start at 0 in every cycle |
| Two clocks | `cycle_time_s` (cells) or `segment_time_s` (devices): seconds since the start of the cycle or segment; `test_time_s`: seconds since the first sample of the record, NaN when the source has no clock |
| Capacity | the cycler's own Ah counter when the source has one, otherwise the integral of the current; recording gaps are not integrated |
| Nothing deleted | no cycle or segment is removed or duplicated; use `cycle_kind` / `segment_kind` and the flags to filter |
| Readings kept | a wrong reading keeps its value and gets a bit in `quality_flags` (see the quality flag sections) |
| Rated capacity | the manufacturer's rating (`rated_capacity_ah`); where the source states none, the value used is explained in the record's notes |
| Normalized sources | a source that publishes only normalized current and capacity keeps them: `meta.cell.capacity_units = "normalized"`, `rated_capacity_ah` = 1, `current_a` is a C-rate and every `*_ah` column a fraction of nominal capacity (STANFORD_GESLIN); in the device store `meta.signals.current_unit` says the same |
| Lists | `tasks`, `aliases`, `soh_sources`, `fault_classes`, `procedures` are `list<string>` |
| Missing values | NaN (float), null (string, list), -1 (`_index` columns without a value) |

## Shared catalog core

The two catalogs start with the same 17 columns, with the same names, types and vocabularies, so they can be read
as one list of records (`pd.concat([cells, devices])`):

| Column | Type | Meaning |
|---|---|---|
| `dataset` | string | dataset key (see [DATASETS.md](DATASETS.md)) |
| `cell_id` / `device_id` | string | record id; devices may list ids of the same battery in another release in `aliases` |
| `path` | string | `<DATASET>/<id>` under the store root |
| `tasks` | list<string> | `aging`, `fault` (cells: `[aging]`) |
| `record_type` | string | `device`: a physical battery the source identifies; `session`: one record of a battery the source does not identify |
| `level` | string | `cell`, `module`, `pack`, `system`, `vehicle` |
| `setting` | string | `lab`, `field`, `field_returned` (systems returned to the manufacturer: a biased sample) |
| `cell_model` | string | the cell's model name |
| `rated_capacity_ah` | float64 | rated capacity of the cell (cell store) or of the device (device store) |
| `form_factor` | string | shape: `cylindrical`, `prismatic`, `pouch`, `coin`; empty when the source does not state it |
| `size_code` | string | size designation as the source states it or as its stated model implies: `18650`, `21700`, `26650`, `502030` ...; empty when not stated |
| `cathode`, `anode` | string | the source's wording; empty when not stated |
| `cathode_family` | string | `LFP`, `LCO`, `LMO`, `LNMO` (5 V spinel), `LMR` (Li-rich), `NMC`, `NCA`, `blend`, `unknown` |
| `chemistry_family` | string | `Li-ion`, `Na-ion`, `Zn-ion` |
| `license` | string | the dataset's data license |
| `commercial_use` | string | `allowed`, `not_allowed`, `unclear` |

`form_factor`, `size_code`, `rated_capacity_ah`, `cathode`, `anode` and the model are also in `meta.cell`.

# Cell store

## `cells/catalog.parquet`

One row per cell: the shared core, then

| Column | Type | Meaning |
|---|---|---|
| `ambient_temperature_c` | float64 | chamber or room temperature of the test |
| `soc_window` | string | SOC window of the ageing protocol where the source sets one (e.g. `0.1-0.9`) |
| `protocol` | string | the source's protocol in words |
| `charge_c_rate_typical`, `discharge_c_rate_typical` | float64 | the most common charge / discharge C-rate of the complete cycles |
| `voltage_min_typical_v`, `voltage_max_typical_v` | float64 | median over the usable cycles of their minimum / maximum voltage |
| `initial_capacity_ah` | float64 | median discharge capacity of the first usable cycles |
| `time_kind` | string | `absolute`: the source has a clock and `test_time_s` is real; `relative`: it has not |
| `n_cycles`, `n_complete`, `n_off_protocol` | int64 | cycles; complete cycles; off-protocol cycles |
| `n_aging`, `n_rpt`, `n_initial`, `n_partial`, `n_irregular` | int64 | cycles per `cycle_kind` |
| `n_capacity_outliers`, `n_time_gaps`, `n_samples` | int64 | flagged cycles; samples |
| `label_tier` | string | `soh` (SOH labels), `capacity_only` (capacities but no reference measurement), `none` |
| `soh_source` | string | where the SOH comes from: `aging` (the ageing cycles), `rpt` (the reference tests), `label` (capacity check-ups the source reports outside the time series) |
| `bol_capacity_ah` | float64 | capacity of the SOH reference measurement at the beginning of life |
| `soh_reference` | string | the reference measurement, e.g. `0.50C/1.00C 2.70-4.20 V` |
| `soh_end`, `soh_min` | float64 | SOH of the last labelled cycle; lowest SOH |
| `soh_coverage` | float64 | fraction of the cycles that have an SOH value |
| `efc_end` | float64 | equivalent full cycles at the end of the test |
| `n_phases` | int64 | ageing phases chained for the SOH (see [SOH across test phases](#soh-across-test-phases)) |
| `has_temperature` | bool | the cell temperature was measured |
| `capacity_source` | string | `counter` (the cycler's Ah counter) or `integrated` (integral of the current) |
| `coulomb_closure_discharge` | float64 | check: median ratio of the integrated discharge current to the discharge capacity used, over complete cycles (close to 1) |
| `size_bytes` | int64 | bytes of the cell's files |
| `meta_json` | string | the cell's `meta.json` as text |

## `samples.parquet` (cells)

Sorted by (`cycle`, `cycle_time_s`). Row groups are cut at cycle boundaries, so a reader can fetch one cycle
without reading the whole file. The rows of cycle *k* are `offsets[k]:offsets[k+1]` with
`offsets = cumsum([0] + cycles.n_samples)`.

| Column | Type | Meaning |
|---|---|---|
| `cycle` | int32 | consecutive from 0 |
| `step` | int32 | step within the cycle, from 0 |
| `step_type` | dictionary | `rest`, `cc_charge`, `cv_charge`, `cc_discharge`, `cv_discharge` |
| `cycle_time_s` | float64 | seconds since the start of the cycle |
| `test_time_s` | float64 | seconds since the first sample of the test (NaN without a clock: `time_kind` `relative`) |
| `voltage_v` | float32 | cell voltage, V |
| `current_a` | float32 | current, A (charge positive) |
| `charge_ah`, `discharge_ah` | float32 | cumulative Ah within the cycle |
| `temperature_c` | float32 | cell temperature, °C (NaN when not measured) |
| `quality_flags` | uint8 | per-sample flags, 0 = good ([below](#quality-flags-cells)) |

`samples_preview.parquet` has the same columns: up to 160 evenly spaced cycles with about 80 rows each, chosen to
keep the curve's shape and the step boundaries.

## `cycles.parquet` (cells)

One row per cycle. `cells/cycles.parquet` holds the same rows for every cell, with `dataset` and `cell_id` in front
(one row group per cell, in catalog order).

| Column | Type | Meaning |
|---|---|---|
| `cycle` | int32 | cycle number |
| `cycle_kind` | string | the cycle's role: `aging` (the ageing protocol), `rpt` (a repeated reference / characterization test), `initial` (a test only at the start), `partial` (incomplete or merged), `irregular` (any other one-off deviation) |
| `efc` | float64 | equivalent full cycles: cumulative discharge Ah ÷ rated capacity at the end of the cycle (reference tests included) |
| `soh` | float64 | capacity of the cell's reference measurement ÷ the same measurement at the beginning of life; interpolated between measurements |
| `source_ref_first`, `source_ref_last` | string | the source's cycle or record label of the first and last sample |
| `test_time_start_s` | float64 | `test_time_s` of the first sample |
| `duration_s` | float64 | cycle duration, s |
| `n_samples`, `n_steps` | int32 | samples and steps in the cycle |
| `charge_ah`, `discharge_ah`, `charge_wh`, `discharge_wh` | float64 | charge and discharge capacity and energy of the cycle |
| `coulombic_efficiency` | float64 | discharge Ah ÷ charge Ah |
| `charge_duration_s`, `discharge_duration_s` | float64 | time spent charging / discharging, s |
| `charge_c_rate`, `discharge_c_rate` | float64 | mean current of the constant-current part ÷ rated capacity (what a protocol calls "0.5C") |
| `voltage_max_v`, `voltage_min_v` | float64 | voltage range, V |
| `current_max_a`, `current_min_a` | float64 | current range, A |
| `temperature_min_c`, `temperature_max_c`, `temperature_mean_c` | float64 | cell temperature, °C (flagged readings left out) |
| `ambient_temperature_c` | float64 | chamber or room temperature, °C |
| `reported_ir_ohm` | float64 | internal resistance reported by the source (MATR), Ω |
| `reported_capacity_ah` | float64 | capacity reported by the source (NASA, MATR, OXFORD_ENERGY_TRADING check-ups), Ah |
| `reported_re_ohm`, `reported_rct_ohm` | float64 | EIS resistances reported by the source (NASA), Ω |
| `is_complete` | bool | the cycle has a real charge and a real discharge |
| `is_off_protocol` | bool | `cycle_kind` is `rpt`, `initial` or `irregular` |
| `is_capacity_outlier` | bool | ageing cycle whose discharge capacity is far from the rolling median of its neighbours |
| `has_time_gap` | bool | logging stopped while current was flowing |
| `procedure` | string | what test the cycle is (its main discharge): `capacity`, `cycling`, `drive_profile`, `pulse`, `hppc`, `gitt`, `ocv` (pseudo-OCV, C/10 or slower), `eis`, `storage`, `formation`, `other`, `unknown` |
| `procedures` | list<string> | every procedure found in the cycle |
| `procedure_source` | string | `source` (the source's file or step tags, or its documented test design), `detected` (waveform rules), `unknown` (not determined; never guessed) |

`procedure` is separate from `cycle_kind`: an HPPC inside a reference test is `cycle_kind` `rpt`, `procedure`
`hppc`. Every `reported_*` column is NaN where the source gives no value.

For training on ageing cycles, a common selection is
`cycle_kind == "aging" and is_complete and not is_capacity_outlier and not has_time_gap`. To find a kind of test,
e.g. every HPPC, keep the rows whose `procedures` contain `"hppc"`.

`cycles_preview.parquet` holds `dataset`, `cell_id`, `cycle`, `cycle_kind`, `efc`, `soh` for up to 120 cycles per
cell.

## `meta.json` (cells)

| Key | Content |
|---|---|
| `cell_id`, `dataset`, `schema_version` | identity; `"2.0.0"` |
| `record_type`, `level`, `tasks`, `setting` | as in the catalog (`device`, `cell`, `["aging"]`, `lab`) |
| `cell` | `rated_capacity_ah`, `form_factor`, `size_code`, `cathode`, `cathode_family`, `anode`, `model`, `chemistry_family`; `capacity_units` for normalized sources |
| `test` | `ambient_temperature_c`, `soc_window`, `protocol`, `charge_c_rate_typical`, `discharge_c_rate_typical`, `voltage_min_typical_v`, `voltage_max_typical_v`, `initial_capacity_ah`, `time_kind` |
| `counts` | `cycles`, `complete`, `off_protocol`, `by_kind` (cycles per `cycle_kind`), `procedures` (`primary`, `contained`, `source`: cycles per value), `capacity_outliers`, `time_gaps`, `samples` |
| `soh` | `definition`, `source`, `reference`, `interpolation`, `bol_capacity_ah`, `n_reference`, `phases_chained`, `note` |
| `protocol` | the ageing protocol as found in the data: `aging` (C-rates, voltage limits, `n_cycles`), `phases`, `deviation_groups` |
| `qc` | counts of what was found and handled in the raw data, `capacity_source`, coulomb closure |
| `source_files`, `notes`, `extra` | the raw files used; what was found in the raw data and how it was handled; source-specific fields |

### SOH across test phases

`meta.soh` describes how the cell's SOH was obtained: the reference measurement (`reference`, e.g.
`0.50C/0.50C 2.80-4.20 V`), its capacity at the beginning of life (`bol_capacity_ah`), the number of measurements and
how values between them are interpolated.

When the ageing conditions of a cell change during the test, for example a cell cycled at several discharge rates
one after another, each phase is measured against its own capacity and the phases are chained so that the SOH curve
continues across the change. `meta.soh.phases_chained` lists every chained phase (`phase`, `first_cycle`, the
scale `factor`, and `discharge_c_rate` when phases are split by rate); it is `null` for a single-phase cell, and
`catalog.n_phases` counts the phases. Where a short conditioning block precedes the main ageing phase, the main
phase is the reference and the cycles before it have no SOH (`meta.soh.note` says so).

Where the source reports capacity check-ups that are not in the time series (OXFORD_ENERGY_TRADING), `soh` is
`reported_capacity_ah` ÷ the first check-up, at the cycle of each check-up and linear in `efc` between them
(`soh_source` `label`).

## Quality flags (cells)

`samples.quality_flags` (uint8) marks samples whose reading is wrong; 0 = good.

| Bit | Meaning | Examples |
|---|---|---|
| 1 | current reading wrong | the cycler's false current reading |
| 2 | voltage reading wrong | floating voltage input (no cell connected) |
| 4 | temperature reading wrong | failed sensor, single-sample spikes |
| 8 | row of another record interleaved into the file | rows of another channel, rows re-inserted out of order |

Readings are kept as recorded. Rows with bits 1, 2 or 8 were left out when capacities, cycles and statistics were
computed; bit 4 only keeps the reading out of the temperature statistics. For training, drop rows with
`(quality_flags & 11) != 0` and treat the temperature of rows with bit 4 as missing.

## Catalog classes

| Column | Values |
|---|---|
| `cathode_family` | `cathode` keeps the source's wording; NASA and NASA_RW are `unknown` (no primary source states their chemistry) |
| `chemistry_family` | `Li-ion`, `Na-ion` (BATTERYLIFE_NA, TUM_BAHRKE), `Zn-ion` (BATTERYLIFE_ZN: aqueous Zn / MnO2 coin cells rated in mAh) |
| `form_factor` | empty = not stated by the source (ARGONNE_CAMP) |
| `size_code` | empty when not stated (STANFORD_GESLIN and UPPSALA_GUO: cylindrical, size not stated; coin sizes) |

## Reading (cells)

Ready-made examples: [`examples/plot_cell.py`](examples/plot_cell.py) (quick plots of one cell) and
[`examples/load_for_training.py`](examples/load_for_training.py) (one cycle per item, chosen columns only).

```python
import pandas as pd

root = "releases/2.0/cells"
cat = pd.read_parquet(f"{root}/catalog.parquet")                       # one row per cell
cy  = pd.read_parquet(f"{root}/MATR/MATR_b1c0/cycles.parquet")         # one row per cycle
s   = pd.read_parquet(f"{root}/MATR/MATR_b1c0/samples.parquet",
                      filters=[("cycle", "==", 100)])                    # the samples of cycle 100 only

aging = cy[(cy.cycle_kind == "aging") & cy.is_complete]                # the ageing cycles
hppc  = cy[cy.procedures.map(lambda p: p is not None and "hppc" in p)]  # every cycle with an HPPC
clean = s[(s.quality_flags & 11) == 0]                                  # drop wrong readings
```

# Device store

Everything recorded as a **device** with its own record of operation is in the device store: lab modules and packs,
field storage systems, electric vehicles, and every fault dataset, including fault tests on single cells. Ageing and
fault data share one schema; the task is a property of the record (`tasks`: `aging`, `fault`, or both: a returned
field system can carry capacity measurements and a fault label). The datasets are listed in
[DATASETS.md](DATASETS.md#device-store-packs-systems-vehicles-fault-tests).

Row *k* of `cell_voltages`, `temperatures` and `aux` is row *k* of `samples`. `meta.channels` maps every array column
to its series position or sensor location and the source's channel name.

## What a device is

| Field | Values |
|---|---|
| `level` | `cell`, `module`, `pack`, `system`, `vehicle` |
| `setting` | `lab`, `field`, `field_returned` (systems returned to the manufacturer: a biased sample) |
| `record_type` | `device`: a physical battery the source identifies (cell, pack, system, vehicle); `session`: one record of a battery the source does not identify (AUTOSUN: one charging session, no vehicle id). Sessions of the same battery cannot be joined, so count devices and sessions separately. |
| `aliases` | ids of the same battery in another release (see below) |
| `cell_voltage_resolution` | `L0`: device voltage only; `L1`: per sample the highest and lowest cell voltage; `L2`: every cell voltage (`cell_voltages.parquet`). A single-cell device is `L2`; its cell voltage is `voltage_v`. |
| `time_kind` | `absolute` (`meta.time.start` and `meta.time.clock` give the start and which clock it is), `relative` (seconds without a date), `order_only` (sample order without time) |

**Twins.** A vehicle that two releases published (Zhang et al. 2023 and EVBattery) is one device, listed under the
release its samples come from, with the other release's id in `aliases` (catalog) and `meta.extra.aliases`. Where
the other release holds stretches of the record that this one lacks, they are appended as their own blocks, and
`source_ref_first` / `source_ref_last` say which release each block comes from.

## `devices/catalog.parquet`

One row per device or session: the shared core, then

| Column | Type | Meaning |
|---|---|---|
| `aliases` | list<string> | ids of the same battery in another release |
| `application` | string | what the battery was used for |
| `group_id` | string | the source's grouping of devices, where it has one |
| `n_series`, `n_parallel` | int64 | cells in series; in parallel |
| `cell_voltage_resolution` | string | `L0`, `L1`, `L2` (above) |
| `n_cell_voltages`, `n_temperature_sensors` | int64 | columns of `cell_voltages.parquet` / `temperatures.parquet` |
| `has_current`, `has_voltage`, `has_bms_soc` | bool | which signals the source records |
| `time_kind` | string | `absolute`, `relative`, `order_only` |
| `sample_interval_median_s` | float64 | median time between samples, s |
| `current_unit` | string | `A`, or `C-rate` for a source that publishes normalized current |
| `segment_rule` | string | how the record is cut into segments ([Segments](#segments)) |
| `n_segments`, `n_samples` | int64 | segments; samples |
| `label_tier` | string | `soh`, `capacity_only`, `fault`, `none` |
| `soh_sources` | list<string> | kinds of SOH the record has: `measured`, `reference_test`, `estimated`, `bms` |
| `soh_end` | float64 | last SOH value |
| `fault_status` | string | `normal` (the source states it), `faulty`, `unknown` (the source does not say) |
| `fault_classes` | list<string> | fault classes of the record ([Labels](#labels)) |
| `has_fault_onset` | bool | the source says when the fault started |
| `has_fault_cell` | bool | the source says which cell is faulty |
| `fault_source` | string | how the source knows: `injected`, `postmortem`, `maintenance`, `author`, `alarm`, `returned` |
| `efc_end`, `age_end_days`, `odometer_end_km` | float64 | ageing axes at the end of the record: equivalent full cycles, days, km |
| `size_bytes` | int64 | bytes of the record's files |
| `meta_json` | string | the record's `meta.json` as text |

## `samples.parquet` (devices)

| Column | Type | Meaning |
|---|---|---|
| `segment`, `block` | int32 | segment from 0; the source's recording block (file, snippet, session) |
| `segment_time_s` | float64 | seconds since the segment start |
| `test_time_s` | float64 | seconds since the device's first sample (NaN without a clock) |
| `voltage_v`, `current_a`, `power_w` | float32 | device terminal voltage, device current (charge positive), measured power |
| `bms_soc` | float32 | the BMS's state of charge, 0–1 |
| `temperature_c` | float32 | the source's single battery temperature, °C |
| `ambient_temperature_c` | float32 | room, chamber or outside air, °C |
| `cell_voltage_max_v`, `cell_voltage_min_v`, `cell_voltage_mean_v` | float32 | highest / lowest / mean cell voltage, V |
| `cell_voltage_max_index`, `cell_voltage_min_index` | int16 | series position (from 0) of the highest / lowest cell |
| `temperature_max_c`, `temperature_min_c`, `temperature_mean_c` | float32 | over the device's temperature sensors, °C |
| `temperature_max_index`, `temperature_min_index` | int16 | sensor (from 0) of the highest / lowest temperature |
| `odometer_km` | float64 | vehicles |
| `speed_kmh` | float32 | vehicles |
| `operating_state` | dictionary | `rest`, `charge`, `discharge`, `drive`, `park`, `test`, `unknown` |
| `charge_ah`, `discharge_ah` | float32 | cumulative within the segment |
| `quality_flags` | uint8 | per-sample flags, 0 = good ([below](#quality-flags-devices)) |

Every quantity any source measures has a column; a source without it leaves the column empty (NaN, or -1 for
`_index` columns). The same quantity measured at the same place is one column whatever the source's unit; different
quantities or places (cell vs. device voltage, cell surface vs. ambient temperature, BMS SOC vs. charge counter) are
separate columns. Sentinel codes that mean "no value" are NaN and listed under `meta.sentinels`.

## Array files

| File | Columns | Meaning |
|---|---|---|
| `cell_voltages.parquet` | `cell_000_v`, `cell_001_v` ... (float32) | voltage of every cell in series, V; the number is the index used by `cell_voltage_*_index` and `fault_cell_index` |
| `temperatures.parquet` | `sensor_000_c`, `sensor_001_c` ... (float32) | every temperature sensor, °C; `meta.channels.temperatures` gives each sensor's location |
| `aux.parquet` | named by the naming rules | other measured quantities, e.g. `surface_temperature_mean_c`, `penetrator_force_n`, `reactor_pressure_abs_kpa`, `gas_released_mol`, `strain_1_microstrain`, `h2_ppm`, `cell_000_balancing_current_a`; a column ending in `_interpolated` holds a value the source interpolated; `meta.channels.aux` describes each column |

## `segments.parquet` (devices)

One row per segment. `devices/segments.parquet` holds the same rows for every device, with `dataset` and `device_id`
in front.

| Column | Type | Meaning |
|---|---|---|
| `segment`, `segment_kind`, `block` | int32, string, int32 | segment number, its kind ([Segments](#segments)), recording block |
| `source_ref_first`, `source_ref_last` | string | the source's file, snippet or session label of the first and last sample |
| `test_time_start_s`, `duration_s` | float64 | start (`test_time_s` of the first sample) and duration, s |
| `sample_interval_median_s` | float64 | median time between samples, s |
| `n_samples` | int32 | samples in the segment |
| `charge_ah`, `discharge_ah`, `charge_wh`, `discharge_wh` | float64 | capacities and energies |
| `bms_soc_start`, `bms_soc_end` | float64 | BMS SOC at the start and end |
| `voltage_min_v`, `voltage_max_v` | float64 | device voltage range, V |
| `current_min_a`, `current_max_a`, `current_mean_a` | float64 | device current range and mean, A |
| `cell_voltage_min_v`, `cell_voltage_max_v` | float64 | cell voltage range, V |
| `cell_voltage_spread_p50_v`, `cell_voltage_spread_p99_v`, `cell_voltage_spread_max_v` | float64 | spread between the highest and lowest cell: median, 99th percentile, maximum, V |
| `cell_voltage_min_mode_index` | int16 | the cell most often lowest |
| `temperature_min_c`, `temperature_max_c`, `temperature_mean_c`, `temperature_spread_max_c` | float64 | temperature range, mean and largest spread between sensors, °C |
| `efc`, `age_days`, `odometer_km` | float64 | ageing axes at the segment end: equivalent full cycles, days since the first sample, km |
| `soh`, `soh_source`, `capacity_ah`, `is_reference` | float64, string, float64, bool | ageing label of the segment ([Labels](#labels)) |
| `fault_active` | int8 | `1` inside a fault event, `0` known normal, `-1` unknown |
| `fault_class`, `fault_cell_index`, `fault_severity`, `fault_severity_unit` | string, int16, float64, string | the fault event the segment lies in |
| `has_time_gap` | bool | logging stopped while current was flowing |
| `n_flagged_samples` | int32 | samples with a quality flag |

## Segments

A segment is a stretch of a device's record; `meta.segments.rule` (catalog `segment_rule`) names the rule used for
the dataset:

| Rule | `segment_kind` | Used for |
|---|---|---|
| `mode` | `charge`, `discharge`, `rest`, `mixed` | field records: runs of one current state |
| `cycle` | `cycle` | lab packs cycled charge → discharge, as in the cell store |
| `charge_session` | `charge_session`, `other` | vehicles: a charging session, joined across short pauses |
| `day` | `day` | stationary storage |
| `loader` | `test`, `cycle`, `charge`, `discharge`, `rest`, `charge_session` ... | the source's own test, cycle or session structure (lab fault tests, AUTOSUN sessions) |

## Labels

**Fault.** `meta.label.fault` keeps the source's wording (`label_raw`) and maps it onto one vocabulary:

| Field | Meaning |
|---|---|
| `status` | `normal` (the source states it), `faulty`, `unknown` (the source does not say) |
| `source` | how the source knows: `injected`, `postmortem`, `maintenance`, `author`, `alarm`, `returned` |
| `is_exhaustive` | the events list every fault of the device, so time outside them is known to be normal |
| `classes`, `families` | the fault classes and their families |
| `has_onset`, `has_cell`, `has_severity` | the source gives when the fault started, which cell, how severe |
| `events` | per fault: `class` and `family`, `cause`, `cell_index`, start and end (`t_start_s` / `t_end_s` or `blocks`), `severity` with `severity_unit`, `label_raw`; a field the source does not give stays empty |

Segment `fault_active`: `1` inside a fault event; `0` for a normal device, before a known onset, or outside the
events of an exhaustive list; `-1` (unknown) otherwise, e.g. every segment of a vehicle the source marks faulty
without saying when. The catalog summarizes per record: `fault_status`, `fault_classes`, `has_fault_onset`,
`has_fault_cell`, `fault_source`.

Fault classes (family): `internal_short`, `self_discharge`, `li_plating`, `capacity_resistance`, `inconsistency`
(internal); `external_short`, `overcharge`, `overdischarge`, `external_heating`, `mechanical_abuse` (abuse);
`thermal_runaway`, `thermal_management` (thermal); `sensor`, `connection` (system); `unspecified` (the source marks
a fault without its type).

**Ageing.** Every capacity or SOH measurement the source gives is kept in `meta.label.soh_points` and attached to
the segment that holds it; `soh_source` says what kind: `measured` (a bench test of the whole device),
`reference_test` (the device's own reference discharge in the record), `estimated` (Ah over a SOC swing), `bms` (the
BMS's own value). `meta.label.n_soh_measurements` counts them. A device with capacities but no SOH reference has
`label_tier` `capacity_only`.

## Quality flags (devices)

`samples.quality_flags` uses the bits of the cell store (1 current, 2 voltage, 4 temperature, 8 row of another
record) and two more:

| Bit | Meaning |
|---|---|
| 16 | filled by the source: the value was interpolated or gap-filled by the publisher, not measured |
| 32 | odometer reading wrong: it steps backward or reads 0 inside the record |

In the device store bit 2 refers to the device voltage (`voltage_v`): such rows are left out of voltage ranges and
Wh but still count for the current. Rows with bit 1, 8 or 16 are left out of capacities, states and segment
statistics; odometer readings with bit 32 are left out of the segments' `odometer_km`. A single wrong channel of
`cell_voltages` or `temperatures` does not flag the row: `meta.channels.<cell_voltages|temperatures>[k].flagged_rows`
lists its row ranges (half-open), the readings stay in the file, and the cell-voltage and temperature extremes leave
them out.

## `meta.json` (devices)

| Key | Content |
|---|---|
| `device_id`, `dataset`, `schema_version` | identity; `"2.0.0"` |
| `record_type`, `level`, `tasks`, `setting`, `group_id`, `application` | as in the catalog |
| `configuration` | `n_series`, `n_parallel`, `n_cells`, `rated_capacity_ah`, `rated_energy_kwh`, `nominal_voltage_v`, `cell_voltage_limits_v` |
| `cell` | `model`, `rated_capacity_ah`, `chemistry_family`, `cathode`, `cathode_family`, `anode`, `form_factor`, `size_code` |
| `signals` | `cell_voltage_resolution`, `n_cell_voltages`, `n_temperature_sensors`, `has_current`, `has_voltage`, `has_bms_soc`, `has_odometer`, `time_kind`, `is_time_anonymized`, `sample_interval_median_s`, `current_unit` |
| `time` | `start` (ISO time of the first sample on the source's clock), `clock` (which clock, e.g. `UTC`) |
| `channels` | `cell_voltages`, `temperatures`, `aux`: per array column its `column`, position or location, the source's channel name, `flagged_rows` |
| `segments` | `rule` and its parameters |
| `label` | `fault` ([Labels](#labels)), `soh_points`, `n_soh_measurements` |
| `sentinels` | source codes read as "no value" |
| `protocol` | the source's test or operation in words |
| `counts` | `segments`, `samples`, `blocks`, `segments_with_soh`, `fault_active` (segments per value) |
| `qc`, `source_files`, `notes`, `extra` | what was found in the raw data and how it was handled; raw files used; source-specific fields (`extra.aliases` for twins) |

## Reading (devices)

```python
import pandas as pd

root = "releases/2.0/devices"
dev = pd.read_parquet(f"{root}/catalog.parquet")                       # one row per device or session
seg = pd.read_parquet(f"{root}/segments.parquet")                      # one row per segment, all devices
s   = pd.read_parquet(f"{root}/TUDA_LFP_FIELD/TUDA_LFP_FIELD_SYS01/samples.parquet")
cv  = pd.read_parquet(f"{root}/TUDA_LFP_FIELD/TUDA_LFP_FIELD_SYS01/cell_voltages.parquet")   # same rows

devices = dev[dev.record_type == "device"]                              # count devices and sessions apart
faulty  = seg[seg.fault_active == 1]                                    # segments inside a known fault
```

# Parameter-set store

A parameter set is what a physics-based cell model needs to stand for one cell: geometry, material properties,
open-circuit potentials, kinetics, transport, electrolyte and voltage limits. Every set is stored as PyBaMM
ParameterValues JSON: functions are expression trees and tables are interpolants, so the file holds no code and loads
with `pybamm.ParameterValues.from_json`. Sets published in BPX (Battery Parameter eXchange) also keep their BPX file in
`source/` when the licence allows.

A set is included only when PyBaMM's DFN runs with it **as that cell**: every value the isothermal DFN reads comes
from the set's source (a file, a paper's tables, supplementary information or figures) or is derived from what the
source gives (capacity balance, composition, OCV balancing); no value is taken from another cell. Values with a
standard default may be defaulted, and are marked: Bruggeman exponent 1.5, thermodynamic factor 1, OCP entropic change
0, reference temperature. When the set was stored, its SPM, SPMe and DFN discharges at 1C and C/20 were solved
(`checks.json`); `models` lists the models that solved. The sets are listed in [DATASETS.md](DATASETS.md#parameter-sets).

## `parameter_sets/catalog.parquet`

| Column | Type | Meaning |
|---|---|---|
| `set_id` | string | the set, in PyBaMM's style: author + year (+ the cell when one paper has several). PyBaMM's own sets keep their PyBaMM names |
| `dataset` | string | the provider (`PYBAMM`, `ABOUT_ENERGY`, `DLR`, ...) |
| `title` | string | a short display name |
| `cell_model`, `manufacturer` | string | the cell, spelled as in the cell store so a set links to measured data of the same cell; empty for a lab or unnamed cell |
| `cathode`, `anode`, `electrolyte`, `cathode_family`, `chemistry_family` | string | chemistry; `chemistry_family` is Li-ion, Na-ion or K-ion |
| `form_factor`, `size_code` | string | shape and size, as in the cell store |
| `rated_capacity_ah`, `voltage_min_v`, `voltage_max_v` | float64 | the set's nominal capacity and voltage cut-offs |
| `origin` | string | `measured` (teardown and cell measurements), `fitted` (fitted to cell data), `literature` (assembled from published values), `fictitious` (a demonstration or design cell) |
| `source_format` | string | `pybamm_builtin`, `pybamm`, `bpx`, `battmo`, `mpet`, `matlab`, `julia`, `paper` |
| `is_bpx_source` | bool | the source is a BPX file |
| `variant_of` | string | the set this one re-fits or modifies |
| `has_thermal`, `has_sei`, `has_plating`, `has_particle_phases`, `has_msmr` | bool | what the set can be solved with: the lumped thermal model, SEI growth, lithium plating; two particle phases in an electrode; MSMR thermodynamics |
| `n_parameters`, `n_derived`, `n_defaulted` | int32 | values in the set; of them, derived from the source and set to a standard default |
| `dfn_capacity_ratio` | float64 | DFN C/20 discharge capacity / nominal capacity when the set was stored |
| `models` | list<string> | the models (SPM, SPMe, DFN) whose every stored check solved |
| `related_datasets` | list<string> | cell-store datasets that measured the same cell model |
| `citation`, `doi`, `url` | string | the source to cite |
| `license`, `commercial_use` | string | as in the other stores |
| `pybamm_version`, `notes` | string | the PyBaMM the set was stored with; valid ranges and other notes |
| `path` | string | the set's folder, `<PROVIDER>/<set_id>/` |

## `meta.json` (parameter sets)

The catalog fields, plus `parameters`: for each PyBaMM parameter name, `from` (`source`, `derived` or `default`),
`where` (the table, figure or file path the value came from) and `note` (how a derived value was obtained);
`pybamm_options` (the model options the set needs: particle phases, OCP hysteresis, MSMR, contact resistance);
`source_files`.

## Reading (parameter sets)

```python
import json, pybamm
meta = json.load(open("meta.json"))
pv = pybamm.ParameterValues.from_json(json.load(open("parameters.json")))
model = pybamm.lithium_ion.DFN(options=meta["pybamm_options"])
sim = pybamm.Simulation(model, parameter_values=pv, experiment=pybamm.Experiment(["Discharge at 1C until 2.5 V"]))
sim.solve()
```

# Server views (SQL)

The read-only SQL of the server (MCP `query`, `batang.Client.query`) sees the release as these DuckDB views:

| View | Rows | Key |
|---|---|---|
| `cells` | cell catalog | `cell_id` |
| `devices` | device catalog | `device_id` |
| `cycles` | cycles of every cell | `cell_id`, `cycle` |
| `segments` | segments of every device | `device_id`, `segment` |
| `samples` | samples of every cell | `cell_id`, `cycle` |
| `device_samples` | samples of every device | `device_id`, `segment` |

and two table macros that read one record quickly: `cycle_samples(cell_id[, cycle])` and
`segment_samples(device_id[, segment])`.

```sql
SELECT c.cathode_family, count(DISTINCT y.cell_id) AS cells
FROM cycles y JOIN cells c USING (cell_id)
WHERE y.cycle_kind = 'aging' AND y.voltage_min_v < 3.0
GROUP BY 1 ORDER BY 2 DESC
```

# Licenses in the data

Every catalog row carries `license` and `commercial_use` (`allowed` / `not_allowed` / `unclear`) of its dataset, and
the stores' `manifest.json` lists them per dataset with the source and a note (for example where the record and the
readme state different licenses). To keep only data that may be used commercially:

```python
cat = pd.read_parquet("releases/2.0/cells/catalog.parquet")
cells = cat[cat.commercial_use == "allowed"].cell_id
```

# Changes from 1.x

Schema 2.0 renames columns, files and folders so that the [naming rules](#naming-rules) produce every name; every
value is the same as in release 1.8 (cells) and unit 0.3 (devices). The complete old → new list, per table, is
[`docs/schema_2_renames.json`](docs/schema_2_renames.json). The main changes:

| 1.x | 2.0 |
|---|---|
| `standardized/`, `standardized_unit/` (cell store release 1.8, unit store release unit 0.3) | `releases/2.0/cells/`, `releases/2.0/devices/` (one release number) |
| unit store, `unit_id` | device store, `device_id` |
| `timeseries.parquet`, `preview.parquet` | `samples.parquet`, `samples_preview.parquet` |
| `cells_v.parquet` (`v_000` ...), `preview_cells_v.parquet` | `cell_voltages.parquet` (`cell_000_v` ...), `cell_voltages_preview.parquet` |
| `temps.parquet` (`t_000` ...) | `temperatures.parquet` (`sensor_000_c` ...) |
| `index.csv` | removed (the catalog lists every cell) |
| `categories`, `identity`, `unit_level`, `domain`, `group` | `tasks`, `record_type`, `level`, `setting`, `group_id` |
| `cell_format`; `model` (= `cell_model`) | `size_code`; removed |
| `time_s` | `cycle_time_s` (cells), `segment_time_s` (devices) |
| `quality`, `state`, `soc_bms` | `quality_flags`, `operating_state`, `bms_soc` |
| `equiv_full_cycles`, `days`, `days_end`, `odometer_km_end` | `efc`, `age_days`, `age_end_days`, `odometer_end_km` |
| `v_min`, `v_max`, `i_min`, `i_max`, `i_mean`, `temp_*_c`, `cell_v_*` | `voltage_min_v`, `voltage_max_v`, `current_min_a`, `current_max_a`, `current_mean_a`, `temperature_*_c`, `cell_voltage_*` |
| `*_idx` | `*_index` |
| `charge_time_s`, `discharge_time_s` | `charge_duration_s`, `discharge_duration_s` |
| `n_points`, `points`, `cycles`, `segments`, `complete` ... (counts) | `n_samples`, `n_cycles`, `n_segments`, `n_complete` ... |
| `test_type`, `test_types`, `test_type_source` | `procedure`, `procedures`, `procedure_source` |
| `ir_ohm`, `capacity_label_ah`, `re_ohm`, `rct_ohm`, `raw_ref_first`, `raw_ref_last` | `reported_ir_ohm`, `reported_capacity_ah`, `reported_re_ohm`, `reported_rct_ohm`, `source_ref_first`, `source_ref_last` |
| `observed_*_c_rate`, `observed_v_min`, `observed_v_max`, `initial_discharge_ah`, `q_bol_ah` | `*_c_rate_typical`, `voltage_min_typical_v`, `voltage_max_typical_v`, `initial_capacity_ah`, `bol_capacity_ah` |
| `time_absolute` (bool, cells) | `time_kind` (`absolute` / `relative`, as in devices) |
| `fault_onset_known`, `fault_cell_known`, `fault_label_source` | `has_fault_onset`, `has_fault_cell`, `fault_source` |
| comma-joined text: `categories`, `aliases`, `soh_sources`, `fault_classes`, `test_types` | `list<string>` |
| catalog bookkeeping `cycles_row_start`, `preview_cycles`, `preview_rows`; `bytes` | removed (the manifest holds it); `size_bytes` |
| SQL views `units`, `timeseries`, `unit_timeseries`; macros `samples()`, `unit_samples()` | `devices`, `samples`, `device_samples`; `cycle_samples()`, `segment_samples()` |
| tool arguments `task`, `cell_format`, `unit_level`, `domain`; `stats(level="record" / "cycle" / "segment")` | `tasks`, `size_code`, `level`, `setting`; `stats(grain=...)` (`level` is the catalog column) |
| `info()` keys `unit_store`; comma-joined `tasks`, `cathode_families` per dataset | `device_store`; lists |

`meta.json` follows the same rules (`meta.cell.size_code`, `meta.test.time_kind`, `meta.soh.bol_capacity_ah`,
`meta.channels.cell_voltages[].column`, `meta.label.fault.is_exhaustive` ...); the `meta` section of the rename list
has every key.

For release 2.0 the server (MCP tools and API) and the Python client still accept 1.x column and argument names
in tool arguments and translate them; an answer lists what the server translated under `renamed` (`{old: new}`).
Files and query results use 2.0 names only; SQL text is not rewritten. A 1.x download is not converted: download
2.0 again (see [client/README.md](client/README.md)).
