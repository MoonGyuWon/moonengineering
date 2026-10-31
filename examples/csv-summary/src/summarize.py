"""CSV 요약 — 숫자 열은 평균 · 최소 · 최대, 범주 열은 값별 빈도."""
import csv
import sys
from collections import Counter
from pathlib import Path


def _num(v):
    try:
        return float(v)
    except ValueError:
        return None


def summarize(rows: list[dict]) -> dict:
    out = {"rows": len(rows), "numeric": {}, "categorical": {}}
    for col in (rows[0].keys() if rows else []):
        vals = [r[col] for r in rows]
        nums = [_num(v) for v in vals]
        if all(n is not None for n in nums):
            out["numeric"][col] = {"mean": sum(nums) / len(nums), "min": min(nums), "max": max(nums)}
        else:
            out["categorical"][col] = dict(Counter(vals).most_common())
    return out


def to_md(s: dict) -> str:
    lines = ["# CSV 요약", "", f"행 수: {s['rows']}", ""]
    if s["numeric"]:
        lines += ["## 숫자 열", "", "| 열 | 평균 | 최소 | 최대 |", "| --- | --- | --- | --- |"]
        lines += [f"| {c} | {v['mean']:.2f} | {v['min']:g} | {v['max']:g} |" for c, v in s["numeric"].items()]
        lines.append("")
    for c, freq in s["categorical"].items():
        lines += [f"## {c} 빈도", "", "| 값 | 개수 |", "| --- | --- |"] + [f"| {k} | {n} |" for k, n in freq.items()] + [""]
    return "\n".join(lines)


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    with src.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(to_md(summarize(rows)), encoding="utf-8")
