from __future__ import annotations
import csv
from pathlib import Path

WEIGHTS = {"once_through": 1.40, "recirculating": 0.90}
ROOT = Path(__file__).parent

def load_rows(path: Path | None = None):
    with (path or ROOT / "data" / "power_plants.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def score(row: dict[str, str]) -> float:
    return float(row["capacity_mw"]) * float(row["annual_hot_days"]) * WEIGHTS[row["cooling_type"]]

def results(rows=None):
    rows = rows or load_rows()
    return sorted(({**r, "screening_score": round(score(r), 1)} for r in rows), key=lambda r: r["screening_score"], reverse=True)

def main():
    ranked = results()
    for r in ranked:
        print(f'{r["plant"]}: {r["screening_score"]:.1f}')
    total = sum(float(r["capacity_mw"]) for r in ranked)
    weighted = sum(score(r) for r in ranked) / total
    print(f"capacity_mw={total:.0f}")
    print(f"capacity_weighted_score={weighted:.2f}")

if __name__ == "__main__":
    main()
