"""실제 공개 데이터 실험: 파일에서 seed별로 약 1MB 연속 구간을 잘라 prelim_experiment와 같은 조건으로 실행한다.

사용법: python -m src.real_data_experiment --name cityrecord --source <한 줄 한 레코드 파일> --out results/real_data
시드는 예약 seed 2000-2029(프로토콜 고정 문서에 기록)만 사용한다.
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import numpy as np

from . import unit_recovery as ur
from .prelim_experiment import PATTERNS, RATES, SCHEMES, delete_records

REAL_SEEDS = range(2000, 2030)
WINDOW_BYTES = 1_000_000


def load_lines(path: str) -> list[bytes]:
    with open(path, "rb") as f:
        return [l if l.endswith(b"\n") else l + b"\n" for l in f if l.strip()]


def window(lines: list[bytes], seed: int) -> bytes:
    """seed로 시작 위치를 정해 약 WINDOW_BYTES가 되도록 연속 레코드를 취한다."""
    rng = np.random.default_rng([seed, 77])
    start = int(rng.integers(0, len(lines)))
    out, size, i = [], 0, start
    while size < WINDOW_BYTES:
        out.append(lines[i % len(lines)])
        size += len(out[-1])
        i += 1
    return b"".join(out)


def run(name: str, lines: list[bytes], budgets, ms, outdir: Path) -> None:
    rows = []
    sk, pk = ur.new_keypair()
    t0 = time.time()
    for seed in REAL_SEEDS:
        data = window(lines, seed)
        nrec = len(ur._split_lines(data))
        damaged = {}
        for rate in RATES:
            for pat in PATTERNS:
                rng = np.random.default_rng([seed, int(rate * 1000), PATTERNS.index(pat)])
                damaged[(rate, pat)] = delete_records(data, rate, pat, rng)
        for budget in budgets:
            for m in ms:
                prots = {s.name: ur.protect(s, data, m, budget, sk) for s in SCHEMES()}
                for (rate, pat), (dam, ndel, delb) in damaged.items():
                    for sname, prot in prots.items():
                        base = dict(dataset=name, seed=seed, scheme=sname, budget=budget, m=m, rate=rate, pattern=pat,
                                    records=nrec, deleted=ndel, deleted_bytes=delb, file_bytes=len(data))
                        if prot is None:
                            rows.append({**base, "feasible": 0, "success": 0, "reason": "infeasible_budget"})
                            continue
                        out, res = ur.repair(prot, dam, pk, 1)
                        rows.append({**base, "feasible": 1, "k": prot.manifest.k, "o_total": prot.o_total,
                                     "success": int(res.success and out == data), "reason": res.reason,
                                     "erased_units": res.erased_units, "coverage": res.coverage,
                                     "repair_read_bytes": res.repair_read_bytes,
                                     "a_io": res.repair_read_bytes / delb if res.success else "",
                                     "total_read_bytes": res.total_read_bytes})
        print(f"[{time.time() - t0:6.1f}s] seed {seed} 완료", flush=True)
    outdir.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(outdir / f"{name}_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--out", default="results/real_data")
    ap.add_argument("--budgets", type=float, nargs="+", default=[0.2, 0.3])
    ap.add_argument("--ms", type=int, nargs="+", default=[2, 4])
    ap.add_argument("--seeds", type=int, default=30, help="디버깅용 seed 수 제한")
    a = ap.parse_args()
    REAL_SEEDS = list(REAL_SEEDS)[: a.seeds]
    run(a.name, load_lines(a.source), a.budgets, a.ms, Path(a.out))
