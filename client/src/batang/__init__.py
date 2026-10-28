"""Batang from Python: find, read and download standardized battery ageing and fault data.

    import batang
    db = batang.connect()                     # logs in through your browser the first time (token kept for 7 days)
    lfp = db.find_records(tasks="aging", cathode_family="LFP")
    cyc = db.cycles(lfp["id"][:5], kind="aging", columns=["efc", "soh"])
    sel = db.select(tasks="aging", cathode_family="NMC"); sel.download(columns=["voltage_v", "current_a"])
    store = batang.open(db.local.path)        # the downloaded files, read locally

Everything is read-only: the server never changes, and your downloaded copy is yours to process.
Names follow Batang schema 2.0 (release 2.0); see DATA_FORMAT.md in the repository.
"""
from ._auth import AuthError
from ._transport import BatangError
from .client import Client, OfflineError, Selection, SizeError
from .connectors import CycleWindows, export, to_numpy, torch_dataset
from .local import LegacyLayoutError, LocalStore, validate

__version__ = "0.2.1"
SCHEMA = "2.0.0"
__all__ = ["connect", "open", "validate", "Client", "Selection", "LocalStore", "CycleWindows", "to_numpy",
           "torch_dataset", "export", "BatangError", "AuthError", "OfflineError", "SizeError", "LegacyLayoutError"]


def connect(url=None, cache="~/batang_cache", release=None, prefer="auto", offline=False, **kw):
    """A Client for the Batang server (default https://api.batanghub.com/mcp, or $BATANG_URL)."""
    return Client(url=url, cache=cache, release=release, prefer=prefer, offline=offline, **kw)


def open(path):    # noqa: A001 (batang.open is the natural name)
    """A downloaded release folder, a copy of a release (releases/2.0) or of one of its stores, read locally."""
    return LocalStore(path)
