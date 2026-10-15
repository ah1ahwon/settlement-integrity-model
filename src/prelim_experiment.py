"""예비실험: 고정 블록 / CDC / 레코드 단위 소거복구 비교 (동일 중복정보 예산).

사용법: python -m src.prelim_experiment [--trials 10] [--budgets 0.2 0.3] [--ms 2 4] [--out results]
"""

from __future__ import annotations

import argparse
import csv
import math
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from . import unit_recovery as ur
from .data_generator import generate_transactions

SCHEMES = lambda: [ur.RecordScheme(), ur.SortedRecordScheme(), ur.RecordGroupScheme(1024), ur.RecordGroupScheme(512),
                   ur.BlockScheme(1024), ur.BlockScheme(512), ur.CDCScheme(512),
                   ur.CDCScheme(512, sort=True), ur.CDCScheme(1024, sort=True)]

# 개발(탐색)용 seed. 검증용 seed는 모델·방식 확정 전에는 사용하지 않는다(사전 분리).
DEV_SEEDS = range(0, 10)
RESERVED_VALIDATION_SEEDS = range(1000, 1030)
SEED_SETS = {"dev": DEV_SEEDS, "validation": RESERVED_VALIDATION_SEEDS}
SEEDS = DEV_SEEDS  # CLI의 --seeds로 교체
CV_GRID = [0.2, 0.6, 1.0, 1.5]
RATES = [0.01, 0.03, 0.05]
PATTERNS = ["scatter", "burst"]
BURST_LEN = 10


def synthetic_file(n: int, mean: int, cv: float, seed: int) -> bytes:
    """레코드 길이가 로그정규분포(평균 mean, 변동계수 cv)인 개행 구분 파일."""
    rng = np.random.default_rng(seed)
    sig2 = math.log(1 + cv * cv)
    sizes = np.clip(rng.lognormal(math.log(mean) - sig2 / 2, math.sqrt(sig2), n), 40, 16384).astype(int)
    out = []
    for i, size in enumerate(sizes):
        head = f"R{i:08d},"
        pay = rng.bytes((size + 1) // 2).hex()[: max(size - len(head) - 1, 1)]
        out.append(f"{head}{pay}\n")
    return "".join(out).encode()


def settlement_file(n: int, seed: int) -> bytes:
    df = generate_transactions(n=n, seed=seed)
    return df.to_csv(index=False, header=False).encode()


def delete_records(data: bytes, rate: float, pattern: str, rng) -> tuple[bytes, int, int]:
    recs = ur._split_lines(data)
    n, want = len(recs), max(1, int(round(n_rate(len(recs), rate))))
    drop: set[int] = set()
    if pattern == "scatter":
        drop = set(rng.choice(n, size=want, replace=False).tolist())
    else:
        while len(drop) < want:
            s = int(rng.integers(0, n))
            drop |= set(range(s, min(s + BURST_LEN, n)))
    kept = b"".join(r for i, r in enumerate(recs) if i not in drop)
    return kept, len(drop), sum(len(recs[i]) for i in drop)


def n_rate(n: int, rate: float) -> float:
    return n * rate


def run(trials: int, budgets: list[float], ms: list[int], outdir: Path, quick: bool = False) -> list[dict]:
    datasets = [(f"synthetic_cv{cv}", cv) for cv in CV_GRID] + [("settlement_csv", None)]
    if quick:
        datasets = datasets[:1] + datasets[-1:]
    rows: list[dict] = []
    sk, pk = ur.new_keypair()
    t0 = time.time()
    for ds, cv in datasets:
        for seed in list(SEEDS)[:trials]:
            data = synthetic_file(1000, 1024, cv, seed) if cv else settlement_file(10000, seed)
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
                    for name, prot in prots.items():
                        base = dict(dataset=ds, seed=seed, scheme=name, budget=budget, m=m, rate=rate, pattern=pat,
                                    records=nrec, deleted=ndel, deleted_bytes=delb, file_bytes=len(data))
                        if prot is None:
                            rows.append({**base, "feasible": 0, "success": 0, "reason": "infeasible_budget"})
                            continue
                        t = time.perf_counter()
                        out, res = ur.repair(prot, dam, pk, 1)
                        rows.append({**base, "feasible": 1, "k": prot.manifest.k, "o_total": prot.o_total,
                                     "meta_ratio": prot.meta_bytes / len(data),
                                     "parity_ratio": prot.parity_total / len(data),
                                     "padded_ratio": prot.padded_bytes / len(data),
                                     "success": int(res.success and out == data), "reason": res.reason,
                                     "erased_units": res.erased_units, "erased_bytes": res.erased_bytes,
                                     "repair_read_bytes": res.repair_read_bytes, "coverage": res.coverage,
                                     "a_io": res.repair_read_bytes / delb if res.success else "",
                                     "total_read_bytes": res.total_read_bytes,
                                     "a_io_total": res.total_read_bytes / delb,
                                     "scan_bytes": res.scan_bytes, "manifest_bytes": res.manifest_bytes,
                                     "parity_verify_bytes": res.parity_verify_bytes,
                                     "reverify_bytes": res.reverify_bytes, "written_bytes": res.written_bytes,
                                     "sec": time.perf_counter() - t})
        print(f"[{time.time() - t0:6.1f}s] {ds} 완료", flush=True)
    outdir.mkdir(exist_ok=True)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(outdir / "prelim_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    return rows


def summarize(rows: list[dict], outdir: Path) -> str:
    agg: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        agg[(r["dataset"], r["budget"], r["m"], r["pattern"], r["rate"], r["scheme"])].append(r)
    lines = ["| 데이터 | 예산 | m | 패턴 | 삭제율 | 방식 | 실행가능 | O_total | k | 성공률 | 평균 커버리지 | A_IO 중앙값(성공 시) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key in sorted(agg):
        ds, budget, m, pat, rate, scheme = key
        head = f"| {ds} | {budget:.2f} | {m} | {pat} | {rate:.0%} | {scheme} |"
        g = agg[key]
        ok = [r for r in g if r.get("feasible")]
        if not ok:
            lines.append(f"{head} 0/{len(g)} | - | - | - | - | - |")
            continue
        aio = [r["a_io"] for r in ok if r.get("a_io") not in ("", None)]
        lines.append(f"{head} {len(ok)}/{len(g)} | {np.mean([r['o_total'] for r in ok]):.3f} "
                     f"| {np.mean([r['k'] for r in ok]):.0f} | {sum(r['success'] for r in g) / len(g):.2f} "
                     f"| {np.mean([r['coverage'] for r in ok]):.3f} | {np.median(aio):.1f} |" if aio else
                     f"{head} {len(ok)}/{len(g)} | {np.mean([r['o_total'] for r in ok]):.3f} "
                     f"| {np.mean([r['k'] for r in ok]):.0f} | {sum(r['success'] for r in g) / len(g):.2f} "
                     f"| {np.mean([r['coverage'] for r in ok]):.3f} | - |")
    text = "\n".join(lines)
    (outdir / "prelim_summary.md").write_text(text + "\n", encoding="utf-8")
    return text


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--budgets", type=float, nargs="+", default=[0.2, 0.3])
    ap.add_argument("--ms", type=int, nargs="+", default=[2, 4])
    ap.add_argument("--out", default="results")
    ap.add_argument("--seeds", choices=sorted(SEED_SETS), default="dev")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--summarize-only", action="store_true", help="기존 CSV로 요약만 다시 만든다")
    a = ap.parse_args()
    SEEDS = SEED_SETS[a.seeds]
    Path(a.out).mkdir(parents=True, exist_ok=True)
    if a.summarize_only:
        with open(Path(a.out) / "prelim_results.csv", newline="") as f:
            rows = [{k: (float(v) if k in ("budget", "rate", "o_total", "k", "success", "feasible", "coverage") and v != "" else v)
                     for k, v in r.items() if v != "" or k == "a_io"} for r in csv.DictReader(f)]
        for r in rows:
            r["m"] = int(r["m"])
            if r.get("a_io") not in ("", None):
                r["a_io"] = float(r["a_io"])
        print(f"{len(rows)}행 로드")
        summarize(rows, Path(a.out))
        raise SystemExit
    rows = run(a.trials, a.budgets, a.ms, Path(a.out), a.quick)
    print(summarize(rows, Path(a.out)))
