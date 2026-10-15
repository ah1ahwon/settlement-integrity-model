"""budget_sweep 결과에서 방식별 필요 예산 Ω*(목표 성공률)와 최적 방식을 계산한다."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

NAMES = ["synth_cv0.2", "synth_cv1.0", "settlement_csv", "cityrecord", "gharchive"]


def omega_star(curve: pd.Series, target: float):
    ok = curve[curve >= target]
    return float(ok.index.min()) if len(ok) else None


def main(d: str = "results/budget_sweep") -> None:
    rows, md = [], []
    for name in NAMES:
        p = Path(d) / f"{name}.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p)
        s = df.groupby(["m", "scheme", "budget", "seed"]).success.mean().reset_index()
        for m in sorted(s.m.unique()):
            for sch in sorted(s.scheme.unique()):
                sub = s[(s.m == m) & (s.scheme == sch)]
                curve = sub.groupby("budget").success.mean()
                row = dict(dataset=name, m=m, scheme=sch,
                           omega95=omega_star(curve, 0.95), omega90=omega_star(curve, 0.90),
                           succ_at20=curve.get(0.20), succ_at30=curve.get(0.30), succ_at50=curve.get(0.50))
                rows.append(row)
    out = pd.DataFrame(rows)
    out.to_csv(Path(d) / "omega_star.csv", index=False)
    fmt = lambda v: ">70%" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:.0%}"
    md.append("| 데이터 | m | " + " | ".join(sorted(out.scheme.unique())) + " | 최소 예산 방식 |")
    md.append("|---|---|" + "---|" * (out.scheme.nunique() + 1))
    for (name, m), g in out.groupby(["dataset", "m"], sort=False):
        g = g.set_index("scheme")
        best = g.omega95.fillna(9).idxmin() if g.omega95.notna().any() else "-"
        ties = list(g.index[g.omega95 == g.omega95.min()]) if g.omega95.notna().any() else []
        md.append(f"| {name} | {m} | " + " | ".join(fmt(g.omega95.get(s)) for s in sorted(out.scheme.unique())) + f" | {'/'.join(ties) or '-'} |")
    text = "\n".join(md)
    (Path(d) / "omega_star.md").write_text("Ω*(95%): 모든 삭제율·패턴을 합친 seed 평균 성공률이 95% 이상이 되는 최소 예산 격자값\n\n" + text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main(*(sys.argv[1:2]))
