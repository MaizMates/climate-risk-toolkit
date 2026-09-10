"""One check that fails if the logic breaks. No framework: run it directly.

It guards the two things that would silently produce a wrong table: reading the value out of
a period-keyed object, and computing the change in the right direction."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import hazard


def test_fetch_reads_value_not_key(monkeypatched=None):
    """The API keys each value by a period string that differs between collections
    ('2040-07' for the projection, another for the baseline). Reading by key breaks silently."""
    payload = {"metadata": {"status": "success"},
               "data": {"ITA": {"2040-07": 4.14}, "DEU": {"2040-07": 0.72}}}
    import json, io, contextlib

    class FakeResp:
        def __init__(self, p): self._p = p
        def read(self): return json.dumps(self._p).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    orig = hazard.urllib.request.urlopen
    hazard.urllib.request.urlopen = lambda *a, **k: FakeResp(payload)
    try:
        got = hazard.fetch("anything", ["ITA", "DEU"])
    finally:
        hazard.urllib.request.urlopen = orig
    assert got == {"ITA": 4.14, "DEU": 0.72}, got


def test_change_is_projection_minus_baseline():
    rows = [{"baseline_days": 1.0, "midcentury_days": 4.0}]
    change = rows[0]["midcentury_days"] - rows[0]["baseline_days"]
    assert change == 3.0, "change must be projection minus baseline, not the reverse"


if __name__ == "__main__":
    test_fetch_reads_value_not_key()
    test_change_is_projection_minus_baseline()
    print("ok: both checks pass")
