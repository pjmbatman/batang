"""Batang from Python: find and read standardized battery ageing and fault data.

    import batang
    db = batang.connect()                     # logs in through your browser the first time (token kept for 7 days)
    lfp = db.find_records(tasks="aging", cathode_family="LFP")
    cyc = db.cycles(lfp["id"][:5], kind="aging", columns=["efc", "soh"])
    batang.fetch_grant("G-20261029-AB12", "~/batang_data")   # an approved request of the hub's 다운로드 tab
    store = batang.open("~/batang_data/2.0")  # its files, read locally

The package queries; whole record files are requested in the hub's 다운로드 tab (https://batanghub.com/#/downloads)
and, once approved, fetched with fetch_grant() or `batang download --grant <id> --to <folder>`.
Everything is read-only: the server never changes, and your downloaded copy is yours to process.
Names follow Batang schema 2.0 (release 2.0); see DATA_FORMAT.md in the repository.
"""
from ._auth import AuthError
from ._transport import BatangError
from .client import Client, OfflineError, Selection, SizeError
from .connectors import CycleWindows, export, to_numpy, torch_dataset
from .local import LegacyLayoutError, LocalStore, validate

__version__ = "0.3.0"
SCHEMA = "2.0.0"
__all__ = ["connect", "open", "fetch_grant", "validate", "Client", "Selection", "LocalStore", "CycleWindows", "to_numpy",
           "torch_dataset", "export", "BatangError", "AuthError", "OfflineError", "SizeError", "LegacyLayoutError"]


def connect(url=None, cache="~/batang_cache", release=None, prefer="auto", offline=False, **kw):
    """A Client for the Batang server (default https://api.batanghub.com/mcp, or $BATANG_URL)."""
    return Client(url=url, cache=cache, release=release, prefer=prefer, offline=offline, **kw)


def fetch_grant(grant, to=None, jobs=8, url=None, cache="~/batang_cache", **kw):
    """Download the files of an approved request of the hub's 다운로드 tab into <to>/<release>/ (default: the cache,
    where connect() reads them first); see Client.fetch_grant."""
    return Client(url=url, cache=cache, **kw).fetch_grant(grant, to=to, jobs=jobs)


def open(path):    # noqa: A001 (batang.open is the natural name)
    """A downloaded release folder, a copy of a release (releases/2.0) or of one of its stores, read locally."""
    return LocalStore(path)
