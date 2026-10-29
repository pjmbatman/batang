"""End-to-end test against a running Batang server (skipped unless BATANG_E2E_URL is set).

    BATANG_E2E_URL       the MCP endpoint, e.g. http://localhost:4193/mcp
    BATANG_E2E_AUTH_URL  the login service, e.g. http://localhost:4192 (default: the MCP endpoint's origin)
    BATANG_E2E_APPROVE   a shell command that approves a device code ({code} is replaced); without it the test uses
                         BATANG_TOKEN
    BATANG_E2E_GRANT     an approved download grant of STROEBL_S1_k01_01 (samples and cycles) of that account; without
                         it the download part is skipped
"""
import io
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import batang                         # noqa: E402
from batang import _auth              # noqa: E402

URL = os.environ.get("BATANG_E2E_URL")


@unittest.skipUnless(URL, "BATANG_E2E_URL not set")
class EndToEnd(unittest.TestCase):
    def test_find_read_download_local(self):
        auth_url = os.environ.get("BATANG_E2E_AUTH_URL", URL)
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["BATANG_CONFIG_DIR"] = os.path.join(tmp, "config")
            approve = os.environ.get("BATANG_E2E_APPROVE")
            if approve:
                os.environ.pop("BATANG_TOKEN", None)
                out = io.StringIO()
                done = []

                def sleep(_):
                    if not done:
                        code = re.search(r"code ([A-Z0-9]{4}-[A-Z0-9]{4})", out.getvalue()).group(1)
                        subprocess.run(approve.format(code=code), shell=True, check=True)
                        done.append(code)
                _auth.login(auth_url, open_browser=False, out=out, sleep=sleep)
            db = batang.connect(url=URL, auth_url=auth_url, cache=os.path.join(tmp, "cache"), login=False)
            self.assertTrue(db.whoami()["logged_in"])
            lfp = db.find_records(task="aging", cathode_family="LFP")
            self.assertGreater(lfp.attrs["matched"], 0)
            self.assertEqual(set(lfp["cathode_family"]), {"LFP"})
            cid = "STROEBL_S1_k01_01"
            self.assertEqual(db.describe(cid)["dataset"], "STROEBL")
            cyc = db.cycles([cid], columns=["soh"])
            self.assertEqual(cyc.attrs["source"], "remote")
            q = db.query("SELECT count(*) AS n FROM cells WHERE cathode_family = 'LFP'")
            self.assertGreater(int(q["n"][0]), 0)
            with self.assertRaises(batang.BatangError):
                db.download([cid])
            grant = os.environ.get("BATANG_E2E_GRANT")
            if not grant:
                return
            paths = db.fetch_grant(grant)
            self.assertTrue(any(p.endswith("samples.parquet") for p in paths))
            s = db.cycle_samples(cid, 10, columns=["voltage_v"])
            self.assertEqual(s.attrs["source"], "local")
            r = db.cycle_samples(cid, 10, columns=["voltage_v"], max_points=500)
            self.assertLessEqual(len(r), 500)
            self.assertEqual(db.cycles([cid], columns=["soh"]).attrs["source"], "local")
            self.assertEqual(len(db.cycles([cid], columns=["soh"])), len(cyc))


if __name__ == "__main__":
    unittest.main()
