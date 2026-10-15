"""예산 스윕: 방식별로 목표 성공률(95%)에 필요한 최소 예산 Ω*를 구한다.

사용법: python -m src.budget_sweep --name cityrecord --source <줄 단위 파일> --out results/budget_sweep
        python -m src.budget_sweep --name synth_cv0.2 --synthetic 0.2 --out results/budget_sweep
        python -m src.budget_sweep --name settlement_csv --settlement --out results/budget_sweep
seed 3000-3029(예약)만 사용한다.
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import numpy as np

from . import unit_recovery as ur
from .prelim_experiment import PATTERNS, RATES, delete_records, settlement_file, synthetic_file
from .real_data_experiment import load_lines, window

SWEEP_SEEDS = range(3000, 3030)
BUDGETS = [0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.70]
MS = [2, 4]
SCHEMES = lambda: [ur.RecordScheme(), ur.SortedRecordScheme(), ur.BlockScheme(1024), ur.BlockScheme(512),
                   ur.CDCScheme(1024, sort=True)]


def run(name, make_data, outdir: Path, seeds) -> None:
    rows = []
    sk, pk = ur.new_keypair()
    t0 = time.time()
    for seed in seeds:
        data = make_data(seed)
        nrec = len(ur._split_lines(data))
        damaged = {}
        for rate in RATES:
            for pat in PATTERNS:
                rng = np.random.default_rng([seed, int(rate * 1000), PATTERNS.index(pat)])
                damaged[(rate, pat)] = delete_records(data, rate, pat, rng)
        for budget in BUDGETS:
            for m in MS:
                prots = {s.name: ur.protect(s, data, m, budget, sk) for s in SCHEMES()}
                for (rate, pat), (dam, ndel, delb) in damaged.items():
                    for sname, prot in prots.items():
                        base = dict(dataset=name, seed=seed, scheme=sname, budget=budget, m=m, rate=rate, pattern=pat,
                                    records=nrec, deleted=ndel, deleted_bytes=delb, file_bytes=len(data))
                        if prot is None:
                            rows.append({**base, "feasible": 0, "success": 0})
                            continue
                        out, res = ur.repair(prot, dam, pk, 1)
                        rows.append({**base, "feasible": 1, "k": prot.manifest.k, "o_total": prot.o_total,
                                     "success": int(res.success and out == data), "coverage": res.coverage,
                                     "total_read_bytes": res.total_read_bytes})
        print(f"[{time.time() - t0:6.1f}s] seed {seed} 완료", flush=True)
    outdir.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(outdir / f"{name}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--source")
    ap.add_argument("--synthetic", type=float)
    ap.add_argument("--settlement", action="store_true")
    ap.add_argument("--out", default="results/budget_sweep")
    ap.add_argument("--seeds", type=int, default=30)
    a = ap.parse_args()
    if a.source:
        lines = load_lines(a.source)
        mk = lambda seed: window(lines, seed)
    elif a.synthetic:
        mk = lambda seed: synthetic_file(1000, 1024, a.synthetic, seed)
    else:
        mk = lambda seed: settlement_file(10000, seed)
    run(a.name, mk, Path(a.out), list(SWEEP_SEEDS)[: a.seeds])
