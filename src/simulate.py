"""정산 파일 무결성 검증 모델의 재현 가능한 버전별 실험 오케스트레이터."""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from hash_vault import HashVault
from metrics import false_positive_rate, latency_overhead, localization_accuracy, tampering_detection_rate
from naive_baseline import naive_check, snapshot
from network import PROFILES, estimate_transfer_seconds
from settlement_batch import SettlementBatch
from tamper import tamper_file
from transfer_agent import TransferAgent


def _new_file_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def run_case_a(batch: SettlementBatch, agent: TransferAgent, trials: int, record_count: int):
    rows = []
    for i in range(trials):
        file_id = _new_file_id("caseA")
        b = batch.run(file_id, record_count, seed=1000 + i)
        r = agent.transmit(file_id, b.file_path)
        rows.append((b, r))
        print(f"  [Case A] {i + 1}/{trials} {file_id} -> {r.status}/{r.reason_code}")
    return rows


def run_case_b(batch: SettlementBatch, agent: TransferAgent, trials: int, record_count: int,
               tamper_count: int, tamper_mode: str):
    rows = []
    for i in range(trials):
        file_id = _new_file_id("caseB")
        b = batch.run(file_id, record_count, seed=2000 + i)
        report = tamper_file(b.file_path, tamper_count=tamper_count, mode=tamper_mode, seed=3000 + i)
        r = agent.transmit(file_id, b.file_path)
        rows.append((b, r, report))
        print(f"  [Case B] {i + 1}/{trials} {file_id} -> {r.status}/{r.reason_code}")
    return rows


def run_tamper_count_sweep(batch: SettlementBatch, agent: TransferAgent, record_count: int,
                           tamper_counts: list[int], mode: str, trials_per_count: int):
    rows = []
    for count in tamper_counts:
        if count > record_count:
            raise ValueError(f"tamper_count({count})는 record_count({record_count})보다 클 수 없습니다.")
        detected = localized_exact = 0
        for i in range(trials_per_count):
            file_id = _new_file_id(f"sweep{count}")
            b = batch.run(file_id, record_count, seed=8000 + i)
            report = tamper_file(b.file_path, tamper_count=count, mode=mode, seed=9000 + i)
            r = agent.transmit(file_id, b.file_path)
            detected += r.status == "BLOCKED"
            localized_exact += set(r.tampered_trans_ids) == set(report.tampered_rows)
        rows.append({"tamper_count": count, "record_count": record_count,
                     "trials": trials_per_count, "detection_rate": detected / trials_per_count,
                     "localization_accuracy": localized_exact / trials_per_count})
        print(f"  [Tamper Sweep] count={count} detection={detected}/{trials_per_count} "
              f"localization={localized_exact}/{trials_per_count}")
    return rows


def run_naive_baseline_comparison(batch: SettlementBatch, agent: TransferAgent,
                                  trials: int, record_count: int):
    """RQ4: 동일한 mtime 위조 공격에서 기존 방식과 제안 모델을 모두 직접 실행한다."""
    modes = ["amount", "account", "delete", "bitflip"]
    rows = []
    for mode in modes:
        caught_asis = caught_forged = proposed_blocked = 0
        reason_counts: dict[str, int] = {}
        for i in range(trials):
            file_id = _new_file_id(f"rq4_{mode}")
            b = batch.run(file_id, record_count, seed=6000 + i)
            before = snapshot(b.file_path)
            tamper_file(b.file_path, tamper_count=1, mode=mode, seed=7000 + i)
            caught_asis += not naive_check(before, b.file_path)
            os.utime(b.file_path, (before.mtime, before.mtime))
            caught_forged += not naive_check(before, b.file_path)

            proposed = agent.transmit(file_id, b.file_path)
            proposed_blocked += proposed.status == "BLOCKED"
            reason_counts[proposed.reason_code] = reason_counts.get(proposed.reason_code, 0) + 1

        row = {
            "mode": mode, "trials": trials,
            "naive_detection_rate_asis": caught_asis / trials,
            "naive_detection_rate_mtime_forged": caught_forged / trials,
            "proposed_detection_rate_mtime_forged": proposed_blocked / trials,
            "proposed_reason_codes": reason_counts,
        }
        rows.append(row)
        print(f"  [RQ4] {mode:8s} naive(as-is)={caught_asis}/{trials}, "
              f"naive(mtime)={caught_forged}/{trials}, proposed(mtime)={proposed_blocked}/{trials}")
    return rows


def run_latency_sweep(batch: SettlementBatch, agent: TransferAgent, sizes: list[int], repeats: int):
    summaries = []
    network_estimates: dict[int, dict[str, float]] = {}
    for size in sizes:
        phase1, phase3, proposed_total, baseline, file_sizes = [], [], [], [], []
        for i in range(repeats):
            file_id = _new_file_id(f"lat{size}")
            b = batch.run(file_id, size, seed=4000 + i)
            file_sizes.append(os.path.getsize(b.file_path))
            r = agent.transmit(file_id, b.file_path)
            phase1.append(b.integrity_seconds)
            phase3.append(r.phase3_gate_seconds)
            proposed_total.append(b.integrity_seconds + r.total_seconds)

            baseline_id = _new_file_id(f"latbase{size}")
            b2 = batch.run(baseline_id, size, seed=5000 + i)
            baseline.append(agent.transmit_without_verification(b2.file_path))

        summary = latency_overhead(size, phase1, phase3, proposed_total, baseline)
        summaries.append(summary)
        median_size = sorted(file_sizes)[len(file_sizes) // 2]
        network_estimates[size] = {
            key: estimate_transfer_seconds(median_size, profile) for key, profile in PROFILES.items()
        }
        print(f"  [Latency] n={size:,} phase1={summary.phase1_integrity_seconds*1000:.2f}ms "
              f"phase3_gate={summary.phase3_gate_seconds*1000:.2f}ms "
              f"proposed_total={summary.proposed_total_seconds*1000:.2f}ms "
              f"baseline={summary.baseline_transfer_seconds*1000:.2f}ms")
    return summaries, network_estimates


def _write_case_csv(path: str, rows: list[tuple]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["file_id", "record_count", "status", "reason_code", "verified",
                         "hashing_ms", "vault_store_ms", "phase1_integrity_ms",
                         "snapshot_ms", "verify_ms", "phase3_gate_ms", "promotion_ms", "agent_total_ms",
                         "original_file_hash", "recomputed_file_hash", "original_chain_hash",
                         "recomputed_chain_hash", "tampered_rows_ground_truth", "tampered_rows_localized"])
        for row in rows:
            if len(row) == 3:
                b, r, report = row
                truth = ";".join(report.tampered_rows)
                localized = ";".join(r.tampered_trans_ids)
            else:
                b, r = row
                truth = localized = ""
            writer.writerow([b.file_id, b.record_count, r.status, r.reason_code, r.verified,
                             round(b.hashing_seconds * 1000, 3), round(b.vault_store_seconds * 1000, 3),
                             round(b.integrity_seconds * 1000, 3), round(r.snapshot_seconds * 1000, 3),
                             round(r.verify_seconds * 1000, 3), round(r.phase3_gate_seconds * 1000, 3),
                             round(r.promotion_seconds * 1000, 3), round(r.total_seconds * 1000, 3),
                             r.original_file_hash, r.recomputed_file_hash, r.original_hash,
                             r.recomputed_hash, truth, localized])


def _write_sweep_csv(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["tamper_count", "record_count", "trials", "detection_rate_pct",
                         "localization_accuracy_pct"])
        for row in rows:
            writer.writerow([row["tamper_count"], row["record_count"], row["trials"],
                             round(row["detection_rate"] * 100, 1),
                             round(row["localization_accuracy"] * 100, 1)])


def _write_rq4_csv(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["mode", "trials", "naive_detection_rate_asis_pct",
                         "naive_detection_rate_mtime_forged_pct",
                         "proposed_detection_rate_mtime_forged_pct", "proposed_reason_codes"])
        for row in rows:
            writer.writerow([row["mode"], row["trials"],
                             round(row["naive_detection_rate_asis"] * 100, 1),
                             round(row["naive_detection_rate_mtime_forged"] * 100, 1),
                             round(row["proposed_detection_rate_mtime_forged"] * 100, 1),
                             json.dumps(row["proposed_reason_codes"], ensure_ascii=False, sort_keys=True)])


def _write_latency_csv(path: str, summaries, network_estimates: dict[int, dict[str, float]]) -> None:
    profile_keys = list(PROFILES)
    with open(path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["record_count", "phase1_integrity_ms", "phase3_gate_ms", "proposed_total_ms",
                         "baseline_transfer_ms", "overhead_ms", "overhead_ratio_pct"]
                        + [f"net_{key}_ms" for key in profile_keys])
        for summary in summaries:
            writer.writerow([summary.record_count, round(summary.phase1_integrity_seconds * 1000, 3),
                             round(summary.phase3_gate_seconds * 1000, 3),
                             round(summary.proposed_total_seconds * 1000, 3),
                             round(summary.baseline_transfer_seconds * 1000, 3),
                             round(summary.overhead_seconds * 1000, 3),
                             round(summary.overhead_ratio * 100, 2)]
                            + [round(network_estimates[summary.record_count][key] * 1000, 2)
                               for key in profile_keys])


def _plot_latency(summaries, path: str) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib이 없어 그래프 생성을 건너뜁니다.")
        return
    for font_name in ("AppleGothic", "Malgun Gothic", "Nanum Gothic", "Noto Sans CJK KR"):
        if font_name in {font.name for font in matplotlib.font_manager.fontManager.ttflist}:
            matplotlib.rcParams["font.family"] = font_name
            break
    matplotlib.rcParams["axes.unicode_minus"] = False
    sizes = [summary.record_count for summary in summaries]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(sizes, [s.baseline_transfer_seconds * 1000 for s in summaries], marker="o",
            label="베이스라인 전송")
    ax.plot(sizes, [s.proposed_total_seconds * 1000 for s in summaries], marker="o",
            label="제안 모델 전체")
    ax.set_xlabel("레코드 수")
    ax.set_ylabel("소요 시간 (ms)")
    ax.set_title("동일 측정 경계의 데이터 규모별 처리 지연")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=config.BASE_DIR,
                              check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description="정산 파일 무결성 검증 모델 시뮬레이션")
    parser.add_argument("--case", choices=["a", "b", "latency", "naive", "sweep", "all"], default="all")
    parser.add_argument("--records", type=int, default=config.DEFAULT_RECORD_COUNT)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--tamper-count", type=int, default=1)
    parser.add_argument("--tamper-mode", choices=["amount", "account", "both", "header", "delete", "insert", "bitflip"], default="amount")
    parser.add_argument("--latency-sizes", type=int, nargs="+", default=[1_000, 10_000, 50_000, 100_000])
    parser.add_argument("--latency-repeats", type=int, default=5)
    parser.add_argument("--sweep-counts", type=int, nargs="+", default=[1, 5, 10, 50, 100])
    parser.add_argument("--sweep-trials", type=int, default=5)
    parser.add_argument("--run-id", help="results/runs 아래에 생성할 고유 실행 ID")
    args = parser.parse_args()
    if min(args.records, args.trials, args.latency_repeats, args.sweep_trials) <= 0:
        parser.error("레코드 수와 반복 횟수는 1 이상이어야 합니다.")

    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id):
        parser.error("run-id는 영문·숫자로 시작하고 영문·숫자·점·밑줄·하이픈만 허용합니다.")
    result_dir = os.path.join(config.RESULTS_DIR, "runs", run_id)
    data_dir = os.path.join(config.DATA_DIR, "runs", run_id)
    try:
        os.makedirs(result_dir, exist_ok=False)
        os.makedirs(data_dir, exist_ok=False)
    except FileExistsError:
        parser.error(f"기존 결과 보호를 위해 이미 존재하는 run-id는 사용할 수 없습니다: {run_id}")

    staging = os.path.join(data_dir, "staging")
    transmitted = os.path.join(data_dir, "transmitted")
    quarantine = os.path.join(data_dir, "quarantine")
    vault = HashVault(os.path.join(data_dir, "hash_vault", "hash_vault.json"))
    batch = SettlementBatch(vault, staging)
    agent = TransferAgent(vault, transmitted, quarantine)
    started_at = datetime.now(timezone.utc)
    monotonic_started = time.perf_counter()
    report = ["# 시뮬레이션 결과 리포트", "", f"- 실행 ID: `{run_id}`",
              f"- Git commit: `{_git_commit()}`", "- 기존 결과를 덮어쓰지 않은 신규 버전 실행", ""]

    if args.case in ("a", "all"):
        rows_a = run_case_a(batch, agent, args.trials, args.records)
        _write_case_csv(os.path.join(result_dir, "case_a_results.csv"), rows_a)
        report += ["## Case A: 정상 시나리오", f"- 오탐률: {false_positive_rate([r for _, r in rows_a])*100:.2f}%", ""]

    if args.case in ("b", "all"):
        rows_b = run_case_b(batch, agent, args.trials, args.records, args.tamper_count, args.tamper_mode)
        _write_case_csv(os.path.join(result_dir, "case_b_results.csv"), rows_b)
        tdr = tampering_detection_rate([r for _, r, _ in rows_b])
        loc = localization_accuracy([(r.tampered_trans_ids, t.tampered_rows) for _, r, t in rows_b])
        report += ["## Case B: 변조 공격", f"- 탐지율: {tdr*100:.2f}%",
                   f"- 위치 특정 정확도: {loc*100:.2f}%", ""]

    if args.case in ("sweep", "all"):
        sweep = run_tamper_count_sweep(batch, agent, args.records, args.sweep_counts,
                                       args.tamper_mode, args.sweep_trials)
        _write_sweep_csv(os.path.join(result_dir, "tamper_count_sweep.csv"), sweep)
        report += ["## 공격 규모·경계조건 스윕", "", "| 변조 건수 | 탐지율 | 위치 특정 정확도 |",
                   "|---:|---:|---:|"]
        report += [f"| {row['tamper_count']} | {row['detection_rate']*100:.0f}% | {row['localization_accuracy']*100:.0f}% |" for row in sweep]
        report.append("")

    if args.case in ("naive", "all"):
        rq4 = run_naive_baseline_comparison(batch, agent, args.trials, args.records)
        _write_rq4_csv(os.path.join(result_dir, "rq4_comparison.csv"), rq4)
        report += ["## RQ4: 기존 방식과 제안 모델 직접 실행 비교", "",
                   "| 공격 | 기존(as-is) | 기존(mtime 위조) | 제안 모델(mtime 위조) |",
                   "|---|---:|---:|---:|"]
        report += [f"| {row['mode']} | {row['naive_detection_rate_asis']*100:.0f}% | "
                   f"{row['naive_detection_rate_mtime_forged']*100:.0f}% | "
                   f"{row['proposed_detection_rate_mtime_forged']*100:.0f}% |" for row in rq4]
        report.append("")

    if args.case in ("latency", "all"):
        summaries, network = run_latency_sweep(batch, agent, args.latency_sizes, args.latency_repeats)
        _write_latency_csv(os.path.join(result_dir, "latency_sweep.csv"), summaries, network)
        _plot_latency(summaries, os.path.join(result_dir, "latency_overhead.png"))
        report += ["## 수정된 성능 측정 구간", "",
                   "Phase 1은 해시 계산+원자적 Vault 저장, Phase 3은 스냅샷 생성부터 허용 결정까지 포함한다.", "",
                   "| 레코드 | Phase 1(ms) | Phase 3 gate(ms) | 제안 전체(ms) | 베이스라인(ms) |",
                   "|---:|---:|---:|---:|---:|"]
        report += [f"| {s.record_count:,} | {s.phase1_integrity_seconds*1000:.2f} | "
                   f"{s.phase3_gate_seconds*1000:.2f} | {s.proposed_total_seconds*1000:.2f} | "
                   f"{s.baseline_transfer_seconds*1000:.2f} |" for s in summaries]
        report.append("")

    with open(os.path.join(result_dir, "report.md"), "w", encoding="utf-8") as stream:
        stream.write("\n".join(report))
    finished_at = datetime.now(timezone.utc)
    manifest = {
        "schema_version": 1, "run_id": run_id, "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(), "elapsed_seconds": time.perf_counter() - monotonic_started,
        "git_commit": _git_commit(), "python": sys.version, "platform": platform.platform(),
        "arguments": vars(args), "result_directory": result_dir, "data_directory": data_dir,
    }
    with open(os.path.join(result_dir, "manifest.json"), "w", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
    print(f"\n신규 버전 결과 저장 완료: {result_dir}")


if __name__ == "__main__":
    main()
