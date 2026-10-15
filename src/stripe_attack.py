"""배치를 아는 공격자의 동일 스트라이프 집중 삭제 시험.

스트라이프 구성은 서명된 매니페스트(길이 표)에서 누구나 계산할 수 있으므로 공개 정보로 가정한다.
공격자는 한 스트라이프를 골라 그 스트라이프의 단위 t개를 각각 포함하는 레코드를 삭제한다.
t = m 이면 패리티 안, t = m+1 이면 패리티 초과이므로 모든 방식이 실패해야 한다(복구 한계의 확인).

사용법: python -m src.stripe_attack [--trials 10] [--stripes 20]
"""

from __future__ import annotations

import argparse
import csv
from bisect import bisect_right
from pathlib import Path

import numpy as np

from . import unit_recovery as ur
from .prelim_experiment import DEV_SEEDS, SCHEMES, SEED_SETS, settlement_file, synthetic_file


def targeted_records(prot: ur.Protected, data: bytes, t: int, rng) -> set[int]:
    man, sch = prot.manifest, prot.scheme
    lens = [x[1] for x in man.table]
    st_list = ur.stripes(man.n, man.k, lens if sch.sort_stripes else None)
    stripe = st_list[int(rng.integers(len(st_list)))]
    unit_off = np.concatenate(([0], np.cumsum(lens)))
    rec_off = np.concatenate(([0], np.cumsum([len(r) for r in ur._split_lines(data)])))
    picks = rng.choice(stripe, size=min(t, len(stripe)), replace=False)
    return {bisect_right(rec_off, unit_off[u]) - 1 for u in picks}


SEEDS = DEV_SEEDS


def run(trials: int, stripes_per: int, outdir: Path) -> list[dict]:
    sk, pk = ur.new_keypair()
    rows = []
    for ds, cv in [("synthetic_cv0.2", 0.2), ("synthetic_cv1.0", 1.0), ("settlement_csv", None)]:
        for seed in list(SEEDS)[:trials]:
            data = synthetic_file(1000, 1024, cv, seed) if cv else settlement_file(10000, seed)
            recs = ur._split_lines(data)
            for budget, m in [(0.3, 4), (0.2, 2)]:
                for sch in SCHEMES():
                    prot = ur.protect(sch, data, m, budget, sk)
                    if prot is None:
                        continue
                    for t in (m, m + 1):
                        for j in range(stripes_per):
                            rng = np.random.default_rng([seed, m, t, j])
                            drop = targeted_records(prot, data, t, rng)
                            dam = b"".join(r for i, r in enumerate(recs) if i not in drop)
                            out, res = ur.repair(prot, dam, pk, 1)
                            rows.append(dict(dataset=ds, seed=seed, budget=budget, m=m, scheme=sch.name, t=t,
                                             deleted_records=len(drop), erased_units=res.erased_units,
                                             success=int(out == data), reason=res.reason))
    outdir.mkdir(exist_ok=True)
    with open(outdir / "stripe_attack.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--stripes", type=int, default=10)
    ap.add_argument("--out", default="results")
    ap.add_argument("--seeds", choices=sorted(SEED_SETS), default="dev")
    a = ap.parse_args()
    SEEDS = SEED_SETS[a.seeds]
    Path(a.out).mkdir(parents=True, exist_ok=True)
    rows = run(a.trials, a.stripes, Path(a.out))
    import pandas as pd
    d = pd.DataFrame(rows)
    d["t_rel"] = np.where(d.t == d.m, "t=m", "t=m+1")
    print(d.groupby(["budget", "m", "scheme", "t_rel"]).agg(
        n=("success", "size"), success=("success", "mean"), erased=("erased_units", "mean")).round(2).to_string())
