"""Schema 2.0 names, and the translation of 1.x names that the client still accepts in arguments (release 2.0 only).

Files and results always use 2.0 names (DATA_FORMAT.md); the full list is docs/schema_2_renames.json."""
import re
import warnings

SCHEMA = "2.0.0"

# per-record files
SAMPLES = "samples.parquet"
SAMPLES_PREVIEW = "samples_preview.parquet"
TABLE_FILES = {"cell": "cycles.parquet", "device": "segments.parquet"}
TIME_COLUMN = {"cell": "cycle_time_s", "device": "segment_time_s"}
KEY_COLUMN = {"cell": "cycle", "device": "segment"}
ID_COLUMN = {"cell": "cell_id", "device": "device_id"}
QUALITY = "quality_flags"

# filter arguments of find_records / stats
LEGACY_FILTERS = {"cell_format": "size_code", "unit_level": "level", "domain": "setting", "task": "tasks"}
# stats(): the record-vs-rows argument is `grain`; 1.x called it `level`
GRAINS = ("record", "cycle", "segment")

# 1.x column name -> 2.0 name, over every table (time_s depends on the store: see column())
LEGACY = {
    "bytes": "size_bytes", "capacity_label_ah": "reported_capacity_ah", "capacity_outliers": "n_capacity_outliers",
    "categories": "tasks", "cell_format": "size_code", "cell_v_max_idx": "cell_voltage_max_index",
    "cell_v_max_v": "cell_voltage_max_v", "cell_v_mean_v": "cell_voltage_mean_v",
    "cell_v_min_idx": "cell_voltage_min_index", "cell_v_min_mode_idx": "cell_voltage_min_mode_index",
    "cell_v_min_v": "cell_voltage_min_v", "cell_v_spread_max_v": "cell_voltage_spread_max_v",
    "cell_v_spread_p50_v": "cell_voltage_spread_p50_v", "cell_v_spread_p99_v": "cell_voltage_spread_p99_v",
    "charge_time_s": "charge_duration_s", "charging_gun_temperature1_c": "connector_temperature_1_c",
    "charging_gun_temperature2_c": "connector_temperature_2_c", "complete": "n_complete",
    "corpus_qc_flag": "source_quality_flags", "cycles": "n_cycles", "days": "age_days", "days_end": "age_end_days",
    "discharge_time_s": "discharge_duration_s", "disp_penetrator_mm": "penetrator_displacement_mm",
    "domain": "setting", "dt_median_s": "sample_interval_median_s", "equiv_full_cycles": "efc",
    "f_expansion_n": "expansion_force_n", "f_penetrator_n": "penetrator_force_n",
    "fault_cell_idx": "fault_cell_index", "fault_cell_known": "has_fault_cell", "fault_label_source": "fault_source",
    "fault_onset_known": "has_fault_onset", "gas_total_mol": "gas_released_mol", "group": "group_id",
    "has_soc_bms": "has_bms_soc", "i_cr_a": "cr_current_a", "i_max": "current_max_a", "i_mean": "current_mean_a",
    "i_min": "current_min_a", "identity": "record_type", "initial_discharge_ah": "initial_capacity_ah",
    "interp_F_penetrator": "penetrator_force_interpolated", "interp_I": "current_interpolated",
    "interp_T_ambient": "ambient_temperature_interpolated", "interp_T_heater": "heater_temperature_interpolated",
    "interp_T_surface_max": "surface_temperature_max_interpolated",
    "interp_T_surface_mean": "surface_temperature_mean_interpolated",
    "interp_T_surface_mid": "surface_temperature_mid_interpolated", "interp_V_cell": "voltage_interpolated",
    "interp_gas_total_mol": "gas_released_interpolated", "ir_ohm": "reported_ir_ohm", "model": "cell_model",
    "n_cells_v": "n_cell_voltages", "n_flagged": "n_flagged_samples", "n_points": "n_samples",
    "n_temps": "n_temperature_sensors", "observed_charge_c_rate": "charge_c_rate_typical",
    "observed_discharge_c_rate": "discharge_c_rate_typical", "observed_v_max": "voltage_max_typical_v",
    "observed_v_min": "voltage_min_typical_v", "odometer_km_end": "odometer_end_km",
    "odometer_zhang_km": "zhang_odometer_km", "off_protocol": "n_off_protocol",
    "p_canister_gauge_kpa": "canister_pressure_gauge_kpa", "p_cassette_abs_kpa": "cassette_pressure_abs_kpa",
    "p_internal_gauge_kpa": "internal_pressure_gauge_kpa", "p_reactor_abs_kpa": "reactor_pressure_abs_kpa",
    "parallel": "n_parallel", "points": "n_samples", "protocol_text": "protocol", "q_bol_ah": "bol_capacity_ah",
    "quality": "quality_flags", "raw_ref_first": "source_ref_first", "raw_ref_last": "source_ref_last",
    "rct_ohm": "reported_rct_ohm", "re_ohm": "reported_re_ohm", "resolution": "cell_voltage_resolution",
    "segment_by": "segment_rule", "segments": "n_segments", "series": "n_series", "soc_bms": "bms_soc",
    "soc_end": "bms_soc_end", "soc_start": "bms_soc_start", "speed_raw": "speed_raw_count",
    "state": "operating_state", "strain1_ue": "strain_1_microstrain", "strain2_ue": "strain_2_microstrain",
    "t_heater_c": "heater_temperature_c", "t_surface_mean_c": "surface_temperature_mean_c",
    "t_vent_gas_2_c": "vent_gas_temperature_2_c", "t_vent_gas_c": "vent_gas_temperature_1_c",
    "temp_max_c": "temperature_max_c", "temp_max_idx": "temperature_max_index", "temp_mean_c": "temperature_mean_c",
    "temp_min_c": "temperature_min_c", "temp_min_idx": "temperature_min_index",
    "temp_spread_max_c": "temperature_spread_max_c", "test_type": "procedure",
    "test_type_source": "procedure_source", "test_types": "procedures", "time_absolute": "time_kind",
    "u_cr_v": "cr_voltage_v", "unit_id": "device_id", "unit_level": "level", "v_max": "voltage_max_v",
    "v_min": "voltage_min_v", "vin1_c3_norm": "vin1_col3_normalized", "vin1_c5_norm": "vin1_col5_normalized",
    "vin1_c6_norm": "vin1_col6_normalized", "volt_scaled": "zhang_voltage_scaled",
    "volt_scaled_next": "zhang_voltage_scaled_next", "with_time_gap": "n_time_gaps",

}
_V = re.compile(r"^v_(\d{3})$")
_T = re.compile(r"^t_(\d{3})$")
_warned = set()


def _note(old, new, stacklevel=4):
    if old not in _warned:
        _warned.add(old)
        warnings.warn(f"{old!r} is a 1.x name; schema 2.0 calls it {new!r} (1.x names are accepted in release 2.0 only)",
                      FutureWarning, stacklevel=stacklevel)


def server_renamed(ans):
    """Warn about the 1.x names the server translated ("renamed": {old: new} in an answer)."""
    ren = ans.get("renamed") if isinstance(ans, dict) else None
    if isinstance(ren, dict):
        for old, new in ren.items():
            _note(str(old), str(new), stacklevel=5)


def column(name, kind=None):
    """The 2.0 name of a column name given in an argument. kind ("cell" / "device") resolves time_s; without it,
    time_s is left for the server to resolve."""
    if not isinstance(name, str):
        return name
    if name == "time_s":
        if kind is None:
            return name
        new = TIME_COLUMN[kind]
    elif name in LEGACY:
        new = LEGACY[name]
    elif _V.match(name):
        new = f"cell_{name[2:]}_v"
    elif _T.match(name):
        new = f"sensor_{name[2:]}_c"
    else:
        return name
    _note(name, new)
    return new


def columns(names, kind=None):
    if names is None:
        return None
    if isinstance(names, str):
        return column(names, kind)
    return [column(c, kind) for c in names]


def where(conds, kind=None):
    """[[column, op, value], ...] or {column: value} with 2.0 column names."""
    if not conds:
        return conds
    if isinstance(conds, dict):
        return {column(k, kind): v for k, v in conds.items()}
    return [[column(c[0], kind)] + list(c[1:]) if isinstance(c, (list, tuple)) and c else c for c in conds]


def filters(args):
    """Filter keyword arguments with 2.0 names (cell_format -> size_code, unit_level -> level, domain -> setting,
    task -> tasks)."""
    out = {}
    for k, v in args.items():
        if k in LEGACY_FILTERS:
            _note(k, LEGACY_FILTERS[k])
            k = LEGACY_FILTERS[k]
        out[k] = v
    return out

