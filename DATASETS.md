# Datasets

Batang release 2.0 (schema 2.0.0) has two stores: the cell store, 43 public life-cycling datasets with 3,400 cells,
and the [device store](#device-store-packs-systems-vehicles-fault-tests) of packs, storage systems, vehicles and fault
tests. Every record was converted and checked one by one; what was found and how it was handled (unit errors,
interleaved records, sensor faults, how the reference test was chosen) is recorded in each record's notes, shown on
its page on the site and stored in its `meta.json`. The file format is [DATA_FORMAT.md](DATA_FORMAT.md).

**Raw data is not redistributed by Batang.** Get it from the source in the table, under that source's terms. The
standardized files keep the license of their source.

## Cell store (life cycling)

Release 2.0: 43 datasets, 3,400 cells (OXFORD_ENERGY_TRADING and UMICH_WAN are new in 2.0).

| Dataset | Institution | Cells | Cell | Source | Data license | Cite | Commercial use |
|---|---|---:|---|---|---|---|---|
| `AALBORG_FORKLIFT` | Aalborg Univ. | 3 | LFP prismatic, 180 Ah; forklift load profile | [10.17632/yz4pttm73n.2](https://doi.org/10.17632/yz4pttm73n.2) | CC BY 4.0 | Vilsen 2024 [`vilsen2024`] | allowed |
| `ARGONNE_CAMP` | Argonne National Laboratory (CAMP) | 590 | lab-built cells, 9 cathodes (NMC111 / 532 / 622 / 811, 5 V spinel LNMO, Li-rich LMR and others), 8 mAh – 1.5 Ah; shape not stated | [10.18126/fdxq-7yul](https://doi.org/10.18126/fdxq-7yul) | not stated⁵ | Paulson 2022 [`paulson2022`] | not stated |
| `BATTERYLIFE_NA` | BatteryLife (Tan et al.) | 69 | Na-ion 18650, 1.0 Ah (rating assumed by BatteryLife; no datasheet) | [10.5281/zenodo.17960956](https://doi.org/10.5281/zenodo.17960956) | CC BY 4.0 | Tan 2025 [`tan2025`] | allowed |
| `BATTERYLIFE_ZN` | BatteryLife (Tan et al.) | 153 | aqueous Zn / MnO2 coin cells, 0.3–1.0 mAh | [10.5281/zenodo.17960956](https://doi.org/10.5281/zenodo.17960956) | CC BY 4.0 | Tan 2025 [`tan2025`] | allowed |
| `CALCE` | Univ. of Maryland CALCE | 13 | LCO prismatic, 1.1 / 1.35 Ah | [calce.umd.edu](https://calce.umd.edu/battery-data) | not stated¹ | He 2011 [`he2011`]; Xing 2013 [`xing2013`] | not stated |
| `CALCE_PL` | Univ. of Maryland CALCE | 16 | LCO pouch, 1.5 Ah; partial-SOC windows | [calce.umd.edu](https://calce.umd.edu/battery-data) | not stated¹ | Saxena 2016 [`saxena2016`] | not stated |
| `CALCE_STORAGE` | Univ. of Maryland CALCE | 144 | LCO pouch, 1.5 Ah; storage at 0 / 50 / 100 % SOC, −40 to 50 °C | [calce.umd.edu](https://calce.umd.edu/battery-data) | not stated¹ | CALCE data page [`calcedata`] | not stated |
| `CMU_EVTOL` | Carnegie Mellon Univ. | 22 | Sony-Murata VTC6 18650, 3.0 Ah | [10.1184/R1/14226830](https://doi.org/10.1184/R1/14226830) | CC BY 4.0 | Bills 2023 [`bills2023`] | allowed |
| `FARASIS` | Farasis Energy · Univ. of Michigan | 123 | large pouch, 76–86 Ah | [10.5281/zenodo.17654407](https://doi.org/10.5281/zenodo.17654407) | CC BY 4.0 | Zhang 2026 [`zhang2026`] | allowed |
| `HNEI` | Hawaii Natural Energy Institute | 14 | NMC/LCO 18650, 2.8 Ah | [batteryarchive.org](https://www.batteryarchive.org) | not stated² | Devie 2018 [`devie2018`] | not stated |
| `HUST` | Huazhong Univ. of Sci. & Tech. | 77 | A123 LFP 18650, 1.1 Ah | [10.17632/nsc7hnsg4s.2](https://doi.org/10.17632/nsc7hnsg4s.2) | CC BY 4.0 | Ma 2022 [`ma2022`] | allowed |
| `IMPERIAL` | Imperial College London | 40 | LG M50T 21700 NMC811, 5.0 Ah | [10.5281/zenodo.10637534](https://doi.org/10.5281/zenodo.10637534) | CC BY 4.0 | Kirkaldy 2024 [`kirkaldy2024`] | allowed |
| `ISU_ILCC` | Iowa State Univ. · Iowa Lakes CC | 251 | 502030 NMC pouch, 0.25 Ah | [10.25380/iastate.22582234.v2](https://doi.org/10.25380/iastate.22582234.v2) | CC BY 4.0 | Li 2024 [`li2024`] | allowed |
| `KIT_LUH` | Karlsruhe Institute of Technology | 228 | LG INR18650HG2, 3.0 Ah | [10.35097/kww7jv8ajuvchcah](https://doi.org/10.35097/kww7jv8ajuvchcah) | CC BY 4.0 | Luh 2024 [`luh2024`] | allowed |
| `LYON_A123` | Univ. Lyon · Univ. Grenoble Alpes | 20 | A123 APR18650M1A LFP, 1.1 Ah; first and second life | [10.57745/OLBXKT](https://doi.org/10.57745/OLBXKT) | CC BY 4.0 | Wheeler 2025 [`wheeler2025`] | allowed |
| `MATR` | MIT · Stanford · Toyota Research Inst. | 180 | A123 LFP 18650, 1.1 Ah | [data.matr.io](https://data.matr.io/1) | not stated | Severson 2019 [`severson2019`]; Attia 2020 [`attia2020`] | not stated |
| `MCMASTER_30T` | McMaster Univ. | 6 | Samsung INR21700-30T, 3.0 Ah; 15-minute fast charge | [10.5683/SP3/UYPYDJ](https://doi.org/10.5683/SP3/UYPYDJ) | CC BY-SA 4.0⁶ | Duque 2023 [`duque2023`] | allowed (share-alike) |
| `MCMASTER_A123` | McMaster Univ. | 3 | A123 ANR26650M1 LFP, 2.5 Ah; HEV WLTP power profiles | [10.5683/SP3/23MFNE](https://doi.org/10.5683/SP3/23MFNE) | CC BY-SA 4.0⁶ | Anselma 2023 [`anselma2023`]; Anselma 2021 [`anselma2021`] | allowed (share-alike) |
| `NASA` | NASA Ames PCoE | 34 | 18650, 2.0 Ah (chemistry not stated by NASA) | [PCoE repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/) | not stated³ | Saha 2007 [`saha2007`] | not stated |
| `NASA_RW` | NASA Ames PCoE | 28 | LG Chem 18650, 2.1 Ah | [PCoE repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/) | not stated³ | Bole 2014 [`bole2014`] | not stated |
| `OXFORD_DEG1` | Univ. of Oxford | 8 | Kokam SLPB533459H4 pouch, 740 mAh; characterization every 100 urban drive cycles at 40 °C | [10.5287/bodleian:KO2kdmYGg](https://doi.org/10.5287/bodleian:KO2kdmYGg) | ODbL 1.0 | Birkl 2017 [`birkl2017`] | allowed (share-alike) |
| `OXFORD_ENERGY_TRADING` | Univ. of Oxford · VITO / EnergyVille | 6 | Kokam SLPB78205130H NMC pouch, 16 Ah; a year of day-ahead energy-trading current profiles, capacity check-ups about every 30 days (SOH from the check-ups) | [10.5287/bodleian:gJPdDzvP4](https://doi.org/10.5287/bodleian:gJPdDzvP4) | ODbL 1.0 (contents DbCL 1.0) | Reniers 2018 [`reniers2018`] | allowed (share-alike) |
| `OXFORD_PATH` | Univ. of Oxford | 12 | Panasonic NCR18650BD NCA, 3.0 Ah; cycling combined with storage | [10.5287/bodleian:v0ervBv6p](https://doi.org/10.5287/bodleian:v0ervBv6p) | ODbL 1.0⁷ | Raj 2020 [`raj2020`] | allowed (share-alike) |
| `RWTH` | RWTH Aachen ISEA | 48 | Sanyo UR18650E NMC, 1.85 Ah | [10.18154/RWTH-2021-04545](https://doi.org/10.18154/RWTH-2021-04545) | CC BY 4.0 | Li 2021 [`li2021`] | allowed |
| `RWTH_DRIVE` | RWTH Aachen ISEA | 28 | Samsung INR18650-35E NCA, 3.4 Ah | [10.18154/RWTH-2021-02814](https://doi.org/10.18154/RWTH-2021-02814) | CC BY 4.0 | Jöst 2021 [`jost2021`] | allowed |
| `SDU` | Shandong Univ. | 86 | Lishen LR1865SZ NMC532, 2.4 Ah | [10.5281/zenodo.14859405](https://doi.org/10.5281/zenodo.14859405) | CC BY 4.0 | Wang 2025 [`wang2025`] | allowed |
| `SNL` | Sandia National Laboratories | 86 | LFP / NCA / NMC 18650 | [batteryarchive.org](https://www.batteryarchive.org) | not stated² | Preger 2020 [`preger2020`] | not stated |
| `STANFORD_GESLIN` | Stanford Univ. | 92 | NCA cylindrical, size and rating not disclosed; current and capacity normalized by the source⁹ | [10.25740/td676xr4322](https://doi.org/10.25740/td676xr4322) | CC BY 4.0 | Geslin 2025 [`geslin2025`] | allowed |
| `STANFORD_MOY` | Stanford Univ. | 6 | LG INR21700-M50T NMC811, 5.0 Ah; second life, grid-storage duty | [10.17605/OSF.IO/8JNR5](https://doi.org/10.17605/OSF.IO/8JNR5) | CC BY 4.0 | Onori 2024 [`onori2024`] | allowed |
| `STROEBL` | Stroebl et al. | 279 | Samsung INR21700-50E, 4.9 Ah | [10.6084/m9.figshare.25975315](https://doi.org/10.6084/m9.figshare.25975315) | CC BY 4.0 | Stroebl 2024 [`stroebl2024`] | allowed |
| `TONGJI` | Tongji Univ. | 130 | 18650 NCA / NCM / blend, 2.5–3.5 Ah | [10.5281/zenodo.6405084](https://doi.org/10.5281/zenodo.6405084) | CC BY 4.0 | Zhu 2022 [`zhu2022`] | allowed |
| `TUB_NEUPERT` | TU Berlin | 30 | LG INR18650-HE4, 2.5 Ah | [10.14279/depositonce-17598](https://doi.org/10.14279/depositonce-17598) | CC BY 4.0 | Neupert 2023 [`neupert2023`] | allowed |
| `TUM_50G` | Technical Univ. of Munich | 18 | Samsung INR21700-50G NCA, 4.85 Ah | [10.14459/2025mp1772888](https://doi.org/10.14459/2025mp1772888) | CC BY 4.0 per the repository page, to be confirmed⁸ | Schreiber 2025 [`schreiber2025`] | not stated (until confirmed) |
| `TUM_BAHRKE` | Technical Univ. of Munich | 70 | Na-ion 18650 (CY 18650-12P), 1.25 Ah; calendar and cycle ageing, check-ups only | [10.14459/2026mp1840745](https://doi.org/10.14459/2026mp1840745) | not stated⁸ | Bahrke 2026 [`bahrke2026`] | not stated |
| `TUM_SCHREIBER` | Technical Univ. of Munich | 3 | LG Energy Solution 78 Ah NMC pouch (VW ID.3) | [10.14459/2024mp1755598](https://doi.org/10.14459/2024mp1755598) | CC BY 4.0⁸ | Schreiber 2024 [`schreiber2024`] | allowed |
| `TUM_WILDFEUER` | Technical Univ. of Munich | 196 | Sony/Murata US18650VTC5A NCA, 2.5 Ah; calendar and cycle ageing | [10.14459/2023mp1713382](https://doi.org/10.14459/2023mp1713382) | CC BY 4.0 (release readme) | Wildfeuer 2023 [`wildfeuer2023`] | allowed |
| `TURKU` | Turku Univ. of Applied Sciences | 8 | Samsung ICR18650-26J (NCA as stated by the source) 2.55 Ah, Samsung INR21700-40T NMC 4.0 Ah, JGNE 26650 LFP 3.0 Ah; randomized load | [10.23729/b07462e8-9e31-428c-bdd5-deb1890c608b](https://doi.org/10.23729/b07462e8-9e31-428c-bdd5-deb1890c608b) | CC BY-NC 3.0 | Heydarzadeh 2025 [`heydarzadeh2025`] | **not allowed** |
| `UL_PUR` | UL Research Institutes · Purdue Univ. | 22 | NCA 18650 3.4 Ah / pouch 3.3 Ah | [10.5281/zenodo.4443456](https://doi.org/10.5281/zenodo.4443456), [10.5281/zenodo.4444113](https://doi.org/10.5281/zenodo.4444113) | not stated⁴ | Juarez-Robles 2020 [`juarezrobles2020`], 2021 [`juarezrobles2021`] | not stated |
| `UMICH_WAN` | Univ. of Michigan | 60 | NMC622 / SiO-graphite pouch, 2.5 Ah (from the test matrix currents; no rating stated); 24 conditions of stack pressure, temperature (0–60 °C), C-rate, SOC window, fast charge, multi-rate and US06 discharge, calendar storage; reference tests between ageing blocks | [10.5281/zenodo.20259651](https://doi.org/10.5281/zenodo.20259651) | CC BY 4.0 | Wan 2026 [`wan2026`] | allowed |
| `UPPSALA_GUO` | Uppsala Univ. · Aalborg Univ. | 9 | NMC cylindrical, model not stated, 2.0 Ah (estimated from 1C = 2 A); WLTC with fast charge | [10.5281/zenodo.16538328](https://doi.org/10.5281/zenodo.16538328) | CC BY 4.0 | Guo 2025 [`guo2025`] | allowed |
| `VVEHICLE` | VIRTUAL VEHICLE Research | 116 | Panasonic NCR18650B NCA, 3.25 Ah | [10.5281/zenodo.7896429](https://doi.org/10.5281/zenodo.7896429) | CC BY 4.0 | Galijatovics 2023 [`galijatovics2023`] | allowed |
| `WARWICK_M50` | Univ. of Warwick (WMG) | 18 | LG INR21700-M50 NMC811, 5 Ah (nominal; the data paper states no rating); first and second life | [10.17632/rvhjw633df.1](https://doi.org/10.17632/rvhjw633df.1) | CC BY 4.0 | Mowri 2025 [`mowri2025`] | allowed |
| `XJTU` | Xi'an Jiaotong Univ. | 55 | LISHEN 18650 NCM523, 2.0 Ah | [10.5281/zenodo.10963339](https://doi.org/10.5281/zenodo.10963339) | CC BY 4.0 | Wang 2024 [`wang2024`] | allowed |

"Commercial use": *allowed* = the license permits it (CC BY 4.0; with *share-alike* (CC BY-SA 4.0, ODbL) data you
share or derive must carry the same license); **not allowed** = a non-commercial license (CC BY-NC); *not stated* =
the source states no license (or it could not be confirmed), so use it for research with citation and ask the
authors before anything else. Citation keys refer to [`docs/references.bib`](docs/references.bib). Licenses were
checked on the repository records (DataCite, Zenodo, figshare, Borealis, mediaTUM, RWTH Publications) in October 2026;
the source page is authoritative.

1. CALCE asks that publications using the data cite its articles.
2. Battery Archive states no data license; it asks users to cite the article describing the experiments and
   www.batteryarchive.org as the download source.
3. NASA's PCoE repository states no license ("users employ the data at their own risk"); as a US Government work it
   may be in the public domain, but NASA does not say so.
4. The authors' Zenodo records are access-restricted and carry no license; request access from the authors.
5. Materials Data Facility record `camp_2023` v1.1 (also [10.18126/s90e-dq90](https://doi.org/10.18126/s90e-dq90)):
   no license in DataCite, the record or the files. Cite Paulson et al. 2022.
6. The Borealis records state CC BY-SA 4.0 (share-alike); the readme inside the dataset states CC BY 4.0. The
   stricter record license is listed.
7. The Oxford Research Archive record states ODbL 1.0 (attribution, share-alike); the readme inside the dataset
   states only "copyright, all rights reserved". The record license is listed; ask the authors if in doubt.
8. mediaTUM: the TUM_SCHREIBER record's rights field reads CC BY 4.0. For TUM_50G the repository page shows CC BY
   4.0 but the record metadata carries no license, so the catalog lists it as not stated until this is confirmed.
   For TUM_BAHRKE no license was found.
9. STANFORD_GESLIN publishes current and capacity divided by an undisclosed nominal capacity: its `current_a` is a
   C-rate and its `*_ah` columns are fractions of nominal capacity (`rated_capacity_ah` = 1,
   `meta.cell.capacity_units` = `"normalized"`).

Not every cell of a source is in the store. Left out, each for one reason: ARGONNE_CAMP 11 of 601 records (8 without
a cycle, 3 without a beginning-of-life reference); BATTERYLIFE_NA 1 of 70 (a 2-second file); BATTERYLIFE_ZN 7 of 160
(empty records or no capacity from the start); TUM_WILDFEUER 50 cells that are in the files but not in the authors' overview
(no documented conditions); TUM_BAHRKE 24 cells whose initial check-ups exist only as MATLAB `timetable` objects.

## Device store (packs, systems, vehicles, fault tests)

Release 2.0 (until 2.0: the unit store, release unit 0.3; the records are unchanged): 11 datasets, 1,513 devices
(cells, modules, packs, storage systems and vehicles the source identifies) and 31,449 charging sessions of vehicles
the source does not identify. A record is one battery with its own record of operation; the format is in
[DATA_FORMAT.md](DATA_FORMAT.md#device-store). Fault labels: *normal* (the source states it), *faulty*, *unknown*
(the source does not say).

| Dataset | Organisation | Records | What a record is | Labels | Source | Data license | Cite | Commercial use |
|---|---|---:|---|---|---|---|---|---|
| `AUTOSUN` | Autosun (Shenzhen) · Hong Kong Polytechnic Univ. | 31,449 sessions | one public DC charging session of an electric vehicle at 30 stations in Shenzhen; charger voltage, current, SOC; no vehicle id | per session: 25,769 normal, 5,680 faulty (fault type not given); the authors note that labels go with data owner and session length | [10.17632/c7gg94tmvz.3](https://doi.org/10.17632/c7gg94tmvz.3) | CC BY 4.0 | Yang 2024 [`yang2024`] | allowed |
| `CAO_DTI` | Cao et al. | 80 | electric vehicle (manufacturer "DTI", anonymized), onboard BMS data, 85 cell voltages | per vehicle: 77 normal, 3 faulty (determined after disassembly) | [10.5281/zenodo.10656500](https://doi.org/10.5281/zenodo.10656500) | CC BY 4.0 | Cao 2025 [`cao2025`] | allowed |
| `CAO_GIS` | Cao et al. | 41 | electric vehicle (manufacturer "GIS"), current and BMS SOC only | none released (unknown) | [10.5281/zenodo.10656500](https://doi.org/10.5281/zenodo.10656500) | CC BY 4.0 | Cao 2025 [`cao2025`] | allowed |
| `CAO_QAS` | Cao et al. | 393 | electric vehicle (manufacturer "QAS"), 110 cell voltages | per vehicle: 335 normal, 58 faulty (determined after disassembly) | [10.5281/zenodo.10656500](https://doi.org/10.5281/zenodo.10656500) | CC BY 4.0 | Cao 2025 [`cao2025`] | allowed |
| `EVBATTERY` | Tsinghua Univ. (He et al.) | 463 | electric vehicle of three makes, charging records at 10 s, cell voltage max / min, temperatures, odometer; 245 vehicles also released by Zhang et al. (Zhang id in `aliases`) | per vehicle: 416 normal, 47 faulty (fire incidents, lithium-plating reports); capacity labels for 191 vehicles | [10.6084/m9.figshare.23301881](https://doi.org/10.6084/m9.figshare.23301881) | CC BY 4.0 (figshare record) vs. CC BY-NC-SA (article)¹⁰ | He 2023 [`he2023`] | unclear |
| `HIT_ISC` | Harbin Institute of Technology | 48 | 18650 NCM811 cell, 2.7 Ah, one per charge / discharge protocol; normal tests and tests with a resistor in parallel (equivalent internal short) | internal short, injected, resistance per test; the test list is complete | [10.5281/zenodo.7703318](https://doi.org/10.5281/zenodo.7703318) | not stated¹¹ | Cui 2023 [`cui2023`] | not stated |
| `MCMASTER_PHEV_PACK` | McMaster Univ. | 14 | test run of a 72-cell air-cooled PHEV pack (SB LiMotive 5.2 Ah NMC prismatic), per-cell voltage and temperature; drive cycles and fast charges | 4 runs with an introduced cooling fault (fan off, fan at high speed, blocked air flow; thermal management), 10 normal | [10.5683/SP3/THZTJC](https://doi.org/10.5683/SP3/THZTJC) | CC BY 4.0 | Naguib 2025 [`naguib2025`] | allowed |
| `STRAIN_FAILURE` | Imperial College London | 1 | Samsung INR21700-50S, 5 Ah, cycled at 106 % depth of discharge until it failed; surface strain and temperature | over-discharge, internal short (failure at cycle 28) | [10.5281/zenodo.17651045](https://doi.org/10.5281/zenodo.17651045) | CC BY 4.0 | Gao 2026 [`gao2026`] | allowed |
| `TR_CORPUS` | Song et al. (corpus of six published studies) | 343 | thermal-runaway abuse test of a cell (341) or module (2): external heating, overcharge, indentation, accelerating-rate calorimetry | trigger type and time, thermal-runaway outcome | [10.5281/zenodo.23181869](https://doi.org/10.5281/zenodo.23181869) | CC BY 4.0 (one sub-source CC0)¹² | Song 2026 [`song2026`] and the original studies | allowed¹² |
| `TUDA_LFP_FIELD` | Schaeffer et al. (TU Darmstadt · MIT) | 28 | returned 24 V LFP storage system (8 cells in series, about 160 Ah), up to 5 years of field operation (2013–2022), per-cell voltages, 4 temperatures, BMS SOC | all faulty: returned to the manufacturer, reason not recorded (a biased sample); capacity / resistance findings of the article where given | [10.5281/zenodo.13715694](https://doi.org/10.5281/zenodo.13715694) | CC BY-NC 4.0 | Schaeffer 2024 [`schaeffer2024`] | **not allowed** |
| `ZHANG` | Tsinghua Univ. (Zhang et al.) | 102 | electric vehicle, charging records at 10 s, cell voltage max / min, temperatures, odometer; the release's other 245 vehicles are listed under `EVBATTERY` | per vehicle: 91 normal, 11 faulty (reported by the driver, confirmed by engineers) | [10.6084/m9.figshare.23659323](https://doi.org/10.6084/m9.figshare.23659323) | CC BY 4.0 | Zhang 2023 [`zhang2023`] | allowed |

10. The figshare record states CC BY 4.0; the article (arXiv:2201.12358) states CC BY-NC-SA for the data. Until the
    authors resolve this, treat EVBATTERY as non-commercial. The Zhang-only stretches appended to its twin vehicles
    come from the Zhang release (CC BY 4.0).
11. Zenodo lists the rights as "Other (Open)" without terms, the authors' code repositories carry no license file,
    and the article is CC BY-NC-ND.
12. The corpus is CC BY 4.0 and its sub-source `ds04` CC0; the corpus license says that third-party (cell
    manufacturer) rights need review before commercial use. Cite the corpus and the original study of each
    experiment (listed in the corpus registry).

Vehicles that both Zhang et al. and EVBattery released are one device each, listed under the release its samples come
from, with the other release's id in `aliases` (see [CHANGELOG.md](CHANGELOG.md)).

## Coming next

More datasets are being standardized for the next releases, among them Stanford (Pozzato et al.).
