import contextlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
import warnings

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import batang                                     # noqa: E402
from batang import _auth                          # noqa: E402
from fakeserver import TOKEN, Fake, make_cell, serve  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = os.path.join(self.tmp.name, "store")
        for i in ("SYN_A", "SYN_B"):
            make_cell(os.path.join(self.store, "SYN", i))
        self.fake = Fake(self.store)
        self.srv = serve(self.fake)
        self.url = f"http://127.0.0.1:{self.srv.server_port}/mcp"
        self.cache = os.path.join(self.tmp.name, "cache")
        self.env = dict(os.environ)
        os.environ["BATANG_CONFIG_DIR"] = os.path.join(self.tmp.name, "config")
        os.environ["BATANG_TOKEN"] = TOKEN

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        os.environ.clear()
        os.environ.update(self.env)
        self.tmp.cleanup()

    def client(self, **kw):
        return batang.connect(url=self.url, cache=self.cache, login=False, **kw)

    def tools(self):
        return [c[0] for c in self.fake.calls]


class Auth(Base):
    def test_device_login_caches_the_token_privately(self):
        del os.environ["BATANG_TOKEN"]
        e = _auth.login(self.url, open_browser=False, out=open(os.devnull, "w"), sleep=lambda s: None)
        self.assertEqual(e["access_token"], TOKEN)
        p = _auth.token_path()
        self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o600)
        self.assertEqual(_auth.cached(self.url)["access_token"], TOKEN)
        self.assertIsNone(_auth.cached("http://other.example/mcp"))       # kept per login service
        _auth.forget(self.url)
        self.assertIsNone(_auth.cached(self.url))

    def test_no_token_and_no_login_is_an_error(self):
        del os.environ["BATANG_TOKEN"]
        with self.assertRaises(batang.AuthError):
            self.client().info()

    def test_rejected_token(self):
        os.environ["BATANG_TOKEN"] = "btg_wrong"
        with self.assertRaises(batang.AuthError):
            self.client().info()


class Remote(Base):
    def test_tools_and_errors(self):
        db = self.client()
        self.assertEqual(db.release, "2.0")
        st = db.stats(metric="n_cycles", agg="sum", grain="cycle", tasks="aging", level="cell")
        self.assertEqual(self.fake.calls[-1], ("stats", {"metric": "n_cycles", "agg": "sum", "grain": "cycle",
                                                         "tasks": "aging", "level": "cell"}))
        self.assertEqual(st.attrs["grain"], "cycle")
        df = db.find_records(cathode_family="LFP")
        self.assertEqual(list(df["id"]), ["SYN_A"])
        self.assertEqual(df.attrs["matched"], 1)
        self.assertEqual(df.attrs["source"], "remote")
        self.assertEqual(int(db.query("SELECT 2 AS n")["n"][0]), 2)
        with self.assertRaises(batang.BatangError) as cm:
            db.query("boom")
        self.assertEqual(cm.exception.code, "rejected")

    def test_spilled_answer_is_fetched_from_its_link(self):
        self.fake.big_rows = 2
        df = self.client().find_records()
        self.assertEqual(len(df), 2)

    def test_rate_limit_is_waited_out(self):
        db = self.client()
        waits = []
        db.t.sleep = waits.append
        self.fake.rate_limited = 2
        self.assertEqual(len(db.download(["SYN_A"])), 3)
        self.assertEqual(waits, [4, 4])

    def test_size_guard(self):
        self.fake.big_rows = 10 ** 9                                     # the answer says the full table is huge
        base = f"http://127.0.0.1:{self.srv.server_port}"
        with self.assertRaises(batang.SizeError):
            self.client()._table(self.fake.tool("find_records", {}, base), "records")
        df = self.client()._table(self.fake.tool("find_records", {}, base), "records", allow_large=True)
        self.assertEqual(len(df), 2)


class Local(Base):
    def test_download_then_local_first(self):
        db = self.client()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            paths = db.download(["SYN_A"])
        self.assertEqual(len(paths), 3)
        self.assertTrue(all(os.path.isfile(p) for p in paths))
        lic = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(paths[0]))), "LICENSES.json")))
        self.assertEqual(lic["SYN"]["commercial_use"], "allowed")
        self.assertIn("SYN: CC-BY-4.0", err.getvalue())
        before = len(self.fake.calls)
        df = db.cycles(["SYN_A"], kind="aging", exclude_flags=True)
        self.assertEqual(df.attrs["source"], "local")
        self.assertEqual(list(df["cycle"]), [0, 2])                       # cycle 1 is an outlier, cycle 3 an rpt
        s = db.cycle_samples("SYN_A", 1, columns=["voltage_v"], quality="clean")
        self.assertEqual(s.attrs["source"], "local")
        self.assertEqual(len(s), 45)                                     # 5 flagged samples dropped
        self.assertEqual(list(s.columns), ["cycle_time_s", "voltage_v"])
        r = db.cycle_samples("SYN_A", 1, max_points=10)
        self.assertLessEqual(len(r), 10)
        self.assertEqual(len(self.fake.calls), before)                    # nothing asked of the server
        mixed = db.cycles(["SYN_A", "SYN_B"])
        self.assertEqual(mixed.attrs["source"], "mixed")
        self.assertEqual(sorted(set(mixed["id"])), ["SYN_A", "SYN_B"])
        again = db.download(["SYN_A"])                                    # same sizes: nothing rewritten
        self.assertEqual(again, paths)
        sel = [n for n in os.listdir(os.path.join(self.cache, "2.0", "selections"))]
        self.assertTrue(sel)

    def test_column_cut_download(self):
        db = self.client()
        db.download(["SYN_B"], columns=["voltage_v"])
        st = batang.open(os.path.join(self.cache, "2.0"))
        cols = st.record("SYN_B").columns()
        self.assertIn("voltage_v", cols)
        self.assertNotIn("current_a", cols)
        import pyarrow.parquet as pq
        cut = os.path.join(self.cache, "2.0", "SYN", "SYN_B", "samples.parquet")
        self.assertEqual(pq.ParquetFile(cut).num_row_groups, 4)                # row groups kept (one per cycle)
        rep = batang.validate(os.path.dirname(cut))
        self.assertTrue(rep["ok"], rep)
        self.assertTrue(any("not downloaded" in w for w in rep["warnings"]))
        self.assertEqual(db.cycle_samples("SYN_B", 0, columns=["voltage_v"]).attrs["source"], "local")
        self.assertEqual(db.cycle_samples("SYN_B", 0, columns=["current_a"]).attrs["source"], "remote")

    def test_offline(self):
        db = self.client()
        db.download(["SYN_A"])
        db.download_catalog()
        off = batang.connect(url="http://127.0.0.1:9/mcp", cache=self.cache, offline=True, login=False)
        self.assertEqual(off.release, "2.0")
        self.assertEqual(off.cycles(["SYN_A"]).attrs["source"], "local")
        self.assertEqual(list(off.find_records(cathode_family="NMC")["id"]), ["SYN_B"])
        self.assertEqual(len(off.find_records(tasks="aging")), 2)
        self.assertEqual(list(off.find_records(cycles_min=5)["id"]), ["SYN_B"])                 # ranges and order offline too
        self.assertEqual(list(off.find_records(sort="soh", limit=1)["id"]), ["SYN_B"])
        self.assertEqual(list(off.find_records(sort="cycles")["id"]), ["SYN_B", "SYN_A"])
        with self.assertRaises(batang.OfflineError):
            off.cycles(["SYN_B"])
        with self.assertRaises(batang.OfflineError):
            off.info()

    def test_selection_roundtrip(self):
        db = self.client()
        sel = db.select(cathode_family="LFP")
        self.assertEqual(sel.ids, ["SYN_A"])
        self.assertGreater(sel.size(), 0)
        p = os.path.join(self.tmp.name, "sel.json")
        sel.save(p)
        again = batang.Selection.load(p, db)
        self.assertEqual(again.ids, ["SYN_A"])
        self.assertEqual(len(again.download()), 3)

    def test_local_query(self):
        try:
            import duckdb  # noqa: F401
        except ImportError:
            self.skipTest("duckdb not installed")
        db = self.client()
        db.download(["SYN_A", "SYN_B"])
        df = db.query("SELECT cell_id, count(*) n FROM cycles GROUP BY 1 ORDER BY 1", local=True)
        self.assertEqual(list(df["n"]), [4, 4])
        s = db.query("SELECT count(*) n FROM cycle_samples('SYN_A', 2)", local=True)
        self.assertEqual(int(s["n"][0]), 50)
        s = db.query("SELECT count(*) n FROM cycle_samples('SYN_A')", local=True)
        self.assertEqual(int(s["n"][0]), 200)
        self.assertEqual(int(db.query("SELECT count(*) n FROM samples", local=True)["n"][0]), 400)


class Tools(Base):
    def test_validate_and_connectors(self):
        rep = batang.validate(os.path.join(self.store, "SYN", "SYN_A"))
        self.assertTrue(rep["ok"], rep)
        bad = os.path.join(self.tmp.name, "bad")
        make_cell(bad)
        import pandas as pd
        c = pd.read_parquet(os.path.join(bad, "cycles.parquet"))
        c.loc[0, "n_samples"] = 7
        c.loc[1, "cycle_kind"] = "weird"
        c.to_parquet(os.path.join(bad, "cycles.parquet"), index=False)
        rep = batang.validate(bad)
        self.assertFalse(rep["ok"])
        self.assertTrue(any("n_samples" in e for e in rep["errors"]))
        self.assertTrue(any("cycle_kind" in e for e in rep["errors"]))
        db = self.client()
        db.download(["SYN_A"])
        st = db.local
        w = batang.CycleWindows(st, ["SYN_A"], columns=["voltage_v", "current_a"], window=20, target="soh",
                                kind="aging", complete=False, exclude_flags=False)
        x, y = w[0]
        self.assertEqual(x.shape, (20, 2))
        self.assertAlmostEqual(float(y), 1.0)
        out = batang.export(st.record("SYN_A").cycles(), os.path.join(self.tmp.name, "c.csv"))
        self.assertTrue(os.path.isfile(out))
        self.assertEqual(batang.to_numpy(st.record("SYN_A").cycles(), ["soh"]).shape, (4, 1))


class Legacy(Base):
    """1.x names in arguments are translated (release 2.0 only); 1.x files are not read."""

    def test_old_names_in_arguments(self):
        db = self.client()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            df = db.find_records(cell_format="21700")
        self.assertEqual(list(df["id"]), ["SYN_B"])
        self.assertEqual(self.fake.calls[-1], ("find_records", {"size_code": "21700"}))
        self.assertTrue(any(issubclass(x.category, FutureWarning) for x in w))
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            db.stats(level="segment", unit_level="pack", task="fault")
        self.assertEqual(self.fake.calls[-1][1], {"metric": "count", "agg": "count", "grain": "segment",
                                                  "level": "pack", "tasks": "fault"})
        self.assertTrue(any("grain" in str(x.message) for x in w))
        self.fake.calls.clear()
        with warnings.catch_warnings(record=True) as w:                  # a translation the server reports
            warnings.simplefilter("always")
            db._call("stats", level="cycle")
        self.assertTrue(any("'level'" in str(x.message) and "grain" in str(x.message) for x in w))
        db.download(["SYN_A"], files=["timeseries", "cycles"])
        self.assertEqual([a for n, a in self.fake.calls if n == "download"][-1]["files"], ["samples", "cycles"])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cyc = db.cycles(["SYN_A"], columns=["v_min", "equiv_full_cycles"], where=[["v_min", "<", 2.8]])
            s = db.cycle_samples("SYN_A", 0, columns=["time_s", "voltage_v"], t1=9)
        self.assertEqual(list(cyc.columns), ["id", "cycle", "voltage_min_v", "efc"])
        self.assertEqual(list(cyc["cycle"]), [1, 3])
        self.assertEqual(list(s.columns), ["cycle_time_s", "voltage_v"])
        self.assertEqual(len(s), 10)

    def test_1x_folder_needs_a_fresh_download(self):
        old = os.path.join(self.tmp.name, "old", "1.8")
        cell = os.path.join(old, "SYN", "SYN_A")
        shutil.copytree(os.path.join(self.store, "SYN", "SYN_A"), cell)
        os.rename(os.path.join(cell, "samples.parquet"), os.path.join(cell, "timeseries.parquet"))
        with open(os.path.join(old, "index.json"), "w") as f:
            json.dump({"release": "1.8", "records": {"SYN_A": {"dataset": "SYN", "kind": "cell", "files": {}}}}, f)
        with self.assertRaises(batang.LegacyLayoutError):
            batang.open(old)
        rep = batang.validate(cell)
        self.assertFalse(rep["ok"])
        self.assertTrue(any("1.x name" in e for e in rep["errors"]))


TEST_STORE = os.environ.get("BATANG_TEST_STORE", "")   # a copy of releases/2.0 (read only)


@unittest.skipUnless(os.path.isdir(os.path.join(TEST_STORE, "cells")), "no 2.0 store copy (set BATANG_TEST_STORE)")
class ReleaseCopy(unittest.TestCase):
    """Reading a copy of release 2.0 (read only)."""

    def test_cells_and_devices(self):
        st = batang.open(TEST_STORE)
        self.assertIn("MATR_b1c0", st)
        cell = st.record("MATR_b1c0")
        self.assertEqual(cell.kind, "cell")
        cyc = cell.cycles(columns=["efc", "soh"], kind="aging", complete=True, exclude_flags=True)
        self.assertGreater(len(cyc), 100)
        s = cell.cycle(int(cyc["cycle"].iloc[0]), columns=["voltage_v", "current_a"], quality="clean", max_points=300)
        self.assertEqual(list(s.columns), ["cycle_time_s", "voltage_v", "current_a"])
        self.assertLessEqual(len(s), 300)
        dev = st.record("TUDA_LFP_FIELD_SYS01")
        self.assertEqual(dev.kind, "device")
        seg = dev.cycles(columns=["fault_active", "cell_voltage_spread_max_v"], limit=5)
        self.assertEqual(len(seg), 5)
        s = dev.cycle(int(seg["segment"].iloc[0]), columns=["voltage_v", "bms_soc"])
        self.assertEqual(list(s.columns), ["segment_time_s", "voltage_v", "bms_soc"])
        self.assertTrue(dev.has("cell_voltages.parquet"))
        rep = batang.validate(cell.folder)
        self.assertTrue(rep["ok"], rep)
        rep = batang.validate(dev.folder)
        self.assertTrue(rep["ok"], rep)
        self.assertEqual(batang.open(os.path.join(TEST_STORE, "cells")).record("MATR_b1c0").kind, "cell")


if __name__ == "__main__":
    unittest.main()
