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
from batang import cli                            # noqa: E402
from fakeserver import OTHER, TOKEN, Fake, make_cell, serve  # noqa: E402


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

    def fetch(self, db, ids, **kw):
        """Approve a grant of these records on the fake server and fetch it into the cache, quietly."""
        with contextlib.redirect_stderr(io.StringIO()):
            return db.fetch_grant(self.fake.grant(ids), **kw)


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
        self.fake.big_rows = 2
        self.fake.rate_limited = 2
        self.assertEqual(len(db.find_records()), 2)                       # the spilled answer's link answered 429 twice
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
        paths = self.fetch(db, ["SYN_A"])
        self.assertEqual(len(paths), 3)
        self.assertTrue(all(os.path.isfile(p) for p in paths))
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


    def test_offline(self):
        db = self.client()
        self.fetch(db, ["SYN_A"])
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
        p = os.path.join(self.tmp.name, "sel.json")
        sel.save(p)
        again = batang.Selection.load(p, db)
        self.assertEqual(again.ids, ["SYN_A"])
        self.assertFalse(hasattr(again, "download"))                       # files come from the 다운로드 tab

    def test_local_query(self):
        try:
            import duckdb  # noqa: F401
        except ImportError:
            self.skipTest("duckdb not installed")
        db = self.client()
        self.fetch(db, ["SYN_A", "SYN_B"])
        df = db.query("SELECT cell_id, count(*) n FROM cycles GROUP BY 1 ORDER BY 1", local=True)
        self.assertEqual(list(df["n"]), [4, 4])
        s = db.query("SELECT count(*) n FROM cycle_samples('SYN_A', 2)", local=True)
        self.assertEqual(int(s["n"][0]), 50)
        s = db.query("SELECT count(*) n FROM cycle_samples('SYN_A')", local=True)
        self.assertEqual(int(s["n"][0]), 200)
        self.assertEqual(int(db.query("SELECT count(*) n FROM samples", local=True)["n"][0]), 400)


class Grants(Base):
    """Approved downloads: the manifest with the login token, then the files straight from their links."""

    def quiet(self, fn, *a, **kw):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            return fn(*a, **kw), err.getvalue()

    def test_parallel_download_licences_and_skip(self):
        db = self.client()
        g = self.fake.grant(["SYN_A", "SYN_B"])
        self.fake.bucket_delay = 0.2
        to = os.path.join(self.tmp.name, "data")
        paths, err = self.quiet(batang.fetch_grant, g, to, jobs=4, url=self.url, login=False)
        self.assertEqual(len(paths), 6)
        self.assertGreater(self.fake.max_active, 1)                               # files fetched side by side
        for p in paths:                                                          # <to>/<release>/<dataset>/<id>/<file>
            rel = os.path.relpath(p, os.path.join(to, "2.0"))
            with open(p, "rb") as a, open(os.path.join(self.store, rel), "rb") as b:
                self.assertEqual(a.read(), b.read())
        st = batang.open(os.path.join(to, "2.0"))
        self.assertEqual(st.ids, ["SYN_A", "SYN_B"])
        self.assertEqual(st.record("SYN_B").kind, "cell")
        self.assertEqual(len(st.record("SYN_B").cycles()), 4)
        lic = json.load(open(os.path.join(to, "2.0", "LICENSES.json")))
        self.assertEqual(lic["SYN"], {"license": "CC-BY-4.0", "commercial_use": "allowed", "cite": "10.0/syn"})
        self.assertEqual(err.count("SYN: CC-BY-4.0 (commercial use allowed); cite 10.0/syn"), 1)
        rec = json.load(open(os.path.join(to, "2.0", "selections", f"grant-{g}.json")))
        self.assertEqual(len(rec["files"]), 6)
        self.assertNotIn(self.fake.grants[g]["token"], json.dumps(rec))           # the secret links are not kept
        self.assertEqual(set(self.fake.grants[g]["left"].values()), {2})          # one download used per file
        self.assertTrue(all(r is None for _, _, r in self.fake.dl_log))
        n = len(self.fake.dl_log)
        again, err = self.quiet(db.fetch_grant, g, to)                            # all there: nothing asked again
        self.assertEqual(sorted(again), sorted(paths))
        self.assertEqual(len(self.fake.dl_log), n)
        self.assertNotIn("CC-BY-4.0", err)                                        # each licence said once
        self.assertIn("0 downloaded, 6 already there", err)

    def test_resume_does_not_use_a_download(self):
        db = self.client()
        g = self.fake.grant(["SYN_A"], files=("samples.parquet", "cycles.parquet"))
        src = os.path.join(self.store, "SYN", "SYN_A", "samples.parquet")
        dest = os.path.join(self.cache, "2.0", "SYN", "SYN_A", "samples.parquet")
        os.makedirs(os.path.dirname(dest))
        with open(src, "rb") as f:
            data = f.read()
        with open(dest + ".part", "wb") as f:                                    # left by an interrupted run
            f.write(data[:1000])
        self.fake.cut["SYN/SYN_A/cycles.parquet"] = 500                          # this one drops the connection once
        db.t.sleep = lambda s: None
        self.quiet(db.fetch_grant, g)
        with open(dest, "rb") as f:
            self.assertEqual(f.read(), data)
        self.assertFalse(os.path.exists(dest + ".part"))
        log = {(name, r) for _, name, r in self.fake.dl_log}
        self.assertEqual(log, {("SYN/SYN_A/samples.parquet", "bytes=1000-"), ("SYN/SYN_A/cycles.parquet", None),
                               ("SYN/SYN_A/cycles.parquet", "bytes=500-")})
        self.assertEqual(self.fake.grants[g]["left"], {"SYN/SYN_A/samples.parquet": 3, "SYN/SYN_A/cycles.parquet": 2})
        cyc = os.path.join(self.store, "SYN", "SYN_A", "cycles.parquet")
        with open(cyc, "rb") as a, open(os.path.join(os.path.dirname(dest), "cycles.parquet"), "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_size_check(self):
        db = self.client()
        for delta in (-5, 5):                                    # the manifest lists fewer / more bytes than arrive
            g = self.fake.grant(["SYN_A"], files=("meta.json",), size_delta=delta)
            with self.assertRaises(batang.BatangError) as cm:
                self.quiet(db.fetch_grant, g)
            self.assertEqual(cm.exception.code, "incomplete")
            self.assertIn("SYN/SYN_A/meta.json", cm.exception.message)
            dest = os.path.join(self.cache, "2.0", "SYN", "SYN_A", "meta.json")
            self.assertFalse(os.path.exists(dest))
            self.assertFalse(os.path.exists(dest + ".part"))

    def test_refusals(self):
        db = self.client()
        for status, reason, word in (("pending", None, "waiting"), ("rejected", "목적이 불분명합니다", "목적이 불분명합니다"),
                                     ("revoked", "회수", "revoked"), ("expired", None, "expired")):
            with self.assertRaises(batang.BatangError) as cm:                      # 409 with the status and reason
                db.fetch_grant(self.fake.grant(["SYN_A"], status=status, reason=reason))
            self.assertEqual(cm.exception.code, status)
            self.assertIn(word, cm.exception.message)
        g = self.fake.grant(["SYN_A"])
        os.environ["BATANG_TOKEN"] = OTHER
        with self.assertRaises(batang.BatangError) as cm:                          # someone else's grant: 403
            self.client().fetch_grant(g)
        self.assertEqual(cm.exception.code, "forbidden")
        os.environ["BATANG_TOKEN"] = TOKEN
        with self.assertRaises(batang.BatangError) as cm:
            db.fetch_grant("G-20261029-ZZZZ")
        self.assertEqual(cm.exception.code, "not_found")
        with self.assertRaises(batang.BatangError) as cm:
            db.fetch_grant("../../etc")
        self.assertEqual(cm.exception.code, "bad_request")
        os.environ["BATANG_TOKEN"] = "btg_wrong"
        with self.assertRaises(batang.AuthError):
            self.client().fetch_grant(g)
        self.assertEqual(self.fake.dl_log, [])

    def test_used_up_and_revoked_links_are_410(self):
        db = self.client()
        g = self.fake.grant(["SYN_A"], per_file=1)
        paths = self.quiet(db.fetch_grant, g)[0]
        os.remove(paths[0])
        with self.assertRaises(batang.BatangError) as cm:                          # the one download is used
            self.quiet(db.fetch_grant, g)
        self.assertEqual(cm.exception.code, "incomplete")
        self.assertIn("1 of 3 files failed", cm.exception.message)
        self.assertIn("다운로드 횟수", cm.exception.message)
        base = f"http://127.0.0.1:{self.srv.server_port}"
        man = self.fake.manifest(g, base)
        self.fake.grants[g]["status"] = "revoked"                                  # revoked after the manifest was read
        with self.assertRaises(batang.BatangError) as cm:
            batang.grants.fetch_file(man["files"][0], os.path.join(self.tmp.name, "x"))
        self.assertEqual(cm.exception.code, "gone")

    def test_cli_and_the_removed_download(self):
        g = self.fake.grant(["SYN_B"])
        to = os.path.join(self.tmp.name, "cli")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--url", self.url, "--cache", self.cache, "download", "--grant", g.lower(), "--to", to,
                             "--jobs", "2"])
        self.assertEqual(code, 0, err.getvalue())
        self.assertIn("3 files", out.getvalue())
        self.assertTrue(os.path.isfile(os.path.join(to, "2.0", "SYN", "SYN_B", "samples.parquet")))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main(["--url", self.url, "--cache", self.cache, "download", "SYN_A"])     # --grant is required
        self.assertFalse(hasattr(self.client(), "download"))
        self.assertNotIn("download", [c[0] for c in self.fake.calls])


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
        self.fetch(db, ["SYN_A"])
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
        self.fetch(db, ["SYN_A"])                                         # 1.x names on local files too
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
