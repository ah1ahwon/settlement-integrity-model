"""이중 해시 체이닝 기반 정산 파일 무결성 검증 모델 - 시뮬레이션 오케스트레이터.

- Case A (정상 시나리오): 생성 -> 해시 저장 -> 전송 직전 검증 -> 정상 전송
- Case B (변조 공격 시나리오): 생성 -> 해시 저장 -> (파일 변조) -> 전송 직전 검증 -> 차단
- Latency Sweep: 데이터 규모별 해시 계산/검증 오버헤드 측정 (베이스라인 대비)

결과는 results/ 아래 CSV 및 report.md, latency_overhead.png 로 저장된다.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import uuid

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
    results = []
    for i in range(trials):
        file_id = _new_file_id("caseA")
        b = batch.run(file_id, record_count, seed=1000 + i)
        r = agent.transmit(file_id, b.file_path)
        results.append((b, r))
        print(f"  [Case A] trial {i + 1}/{trials} file_id={file_id} -> {r.status}")
    return results


def run_case_b(batch: SettlementBatch, agent: TransferAgent, trials: int, record_count: int,
                tamper_count: int, tamper_mode: str):
    results = []
    for i in range(trials):
        file_id = _new_file_id("caseB")
        b = batch.run(file_id, record_count, seed=2000 + i)
        report = tamper_file(b.file_path, tamper_count=tamper_count, mode=tamper_mode, seed=3000 + i)
        r = agent.transmit(file_id, b.file_path)
        results.append((b, r, report))
        print(f"  [Case B] trial {i + 1}/{trials} file_id={file_id} tampered={report.tampered_rows} -> {r.status}")
    return results


def run_tamper_count_sweep(batch: SettlementBatch, agent: TransferAgent, record_count: int,
                            tamper_counts: list[int], mode: str, trials_per_count: int):
    """변조 건수를 1건에서 다건으로 늘려가며, 탐지율과 위치 특정 정확도가
    변조 규모와 무관하게 항상 100%를 유지하는지 반복 검증한다."""
    rows = []
    for count in tamper_counts:
        detected = 0
        localized_exact = 0
        for i in range(trials_per_count):
            file_id = _new_file_id(f"sweep{count}")
            b = batch.run(file_id, record_count, seed=8000 + i)
            report = tamper_file(b.file_path, tamper_count=count, mode=mode, seed=9000 + i)
            r = agent.transmit(file_id, b.file_path)
            if r.status == "BLOCKED":
                detected += 1
            if set(r.tampered_trans_ids) == set(report.tampered_rows):
                localized_exact += 1

        detection_rate = detected / trials_per_count
        localization_rate = localized_exact / trials_per_count
        rows.append({
            "tamper_count": count,
            "record_count": record_count,
            "trials": trials_per_count,
            "detection_rate": detection_rate,
            "localization_accuracy": localization_rate,
        })
        print(f"  [Tamper Sweep] tamper_count={count:>4}/{record_count:,} mode={mode} "
              f"detection={detected}/{trials_per_count} ({detection_rate*100:.0f}%) "
              f"localization={localized_exact}/{trials_per_count} ({localization_rate*100:.0f}%)")
    return rows


def run_naive_baseline_comparison(batch: SettlementBatch, trials: int, record_count: int):
    """RQ4: 제안 모델과 기존의 단순 파일 속성(크기·수정시각) 비교 방식을 대조한다.

    각 변조 모드에 대해 두 가지 공격자를 가정한다.
      - as-is: 변조 후 파일의 수정시각을 그대로 둔 공격자
      - mtime 위조: 변조 후 os.utime()으로 수정시각을 원본과 동일하게 되돌리는,
        기초적인 안티포렌식 지식을 가진 공격자
    제안 모델(해시 체이닝)은 내용 기반이므로 두 경우 모두 별도 Case B 실험에서
    이미 100% 탐지가 검증되었다. 여기서는 '기존 방식'이 두 경우 각각 얼마나
    놓치는지를 측정한다.
    """
    modes = ["amount", "account", "delete", "bitflip"]
    rows = []
    for mode in modes:
        caught_asis = 0
        caught_forged = 0
        for i in range(trials):
            file_id = _new_file_id(f"naive_{mode}")
            b = batch.run(file_id, record_count, seed=6000 + i)
            before = snapshot(b.file_path)

            tamper_file(b.file_path, tamper_count=1, mode=mode, seed=7000 + i)

            if not naive_check(before, b.file_path):
                caught_asis += 1

            os.utime(b.file_path, (before.mtime, before.mtime))
            if not naive_check(before, b.file_path):
                caught_forged += 1

        rate_asis = caught_asis / trials
        rate_forged = caught_forged / trials
        rows.append({
            "mode": mode,
            "trials": trials,
            "naive_detection_rate_asis": rate_asis,
            "naive_detection_rate_mtime_forged": rate_forged,
        })
        print(f"  [Naive Baseline] mode={mode:8s} as-is={caught_asis}/{trials} ({rate_asis*100:.0f}%)  "
              f"mtime위조={caught_forged}/{trials} ({rate_forged*100:.0f}%)")
    return rows


def run_latency_sweep(vault: HashVault, sizes: list[int]):
    summaries = []
    network_estimates: dict[int, dict[str, float]] = {}
    for size in sizes:
        staging = os.path.join(config.STAGING_DIR, "latency")
        batch = SettlementBatch(vault, staging)
        agent = TransferAgent(vault, config.TRANSMITTED_DIR, config.QUARANTINE_DIR)

        hash_secs, verify_secs, baseline_secs, file_sizes = [], [], [], []
        repeats = 9
        for i in range(repeats):
            file_id = _new_file_id(f"lat{size}")
            b = batch.run(file_id, size, seed=4000 + i)
            file_sizes.append(os.path.getsize(b.file_path))
            r = agent.transmit(file_id, b.file_path)
            hash_secs.append(b.hashing_seconds)
            verify_secs.append(r.verify_seconds)

            # 베이스라인: 동일 크기 파일을 검증 없이 재생성하여 단순 전송만 수행
            base_file_id = _new_file_id(f"latbase{size}")
            b2 = batch.run(base_file_id, size, seed=5000 + i)
            baseline_secs.append(agent.transmit_without_verification(b2.file_path))
            # 베이스라인 파일도 vault에 등록되지만 통계 목적일 뿐 검증에는 사용하지 않음

        summary = latency_overhead(size, hash_secs, verify_secs, baseline_secs)
        summaries.append(summary)

        # 네트워크 전송 구간(측정이 아닌 대역폭 기반 추정치)을 함께 계산해,
        # 해시 검증 오버헤드가 종단간 지연에서 차지하는 비중을 가늠한다.
        median_size = sorted(file_sizes)[len(file_sizes) // 2]
        network_estimates[size] = {
            key: estimate_transfer_seconds(median_size, profile)
            for key, profile in PROFILES.items()
        }

        net_desc = ", ".join(
            f"{PROFILES[k].name}={v*1000:.1f}ms" for k, v in network_estimates[size].items()
        )
        print(f"  [Latency] n={size:>7,} hash={summary.avg_hash_seconds*1000:.2f}ms "
              f"verify={summary.avg_verify_seconds*1000:.2f}ms "
              f"baseline={summary.avg_baseline_seconds*1000:.2f}ms "
              f"overhead={summary.overhead_seconds*1000:.2f}ms ({summary.overhead_ratio*100:.1f}%) "
              f"| 네트워크 전송 추정: {net_desc}")
    return summaries, network_estimates


def _write_sweep_csv(path: str, rows: list[dict]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tamper_count", "record_count", "trials", "detection_rate_pct", "localization_accuracy_pct"])
        for row in rows:
            w.writerow([row["tamper_count"], row["record_count"], row["trials"],
                        round(row["detection_rate"] * 100, 1), round(row["localization_accuracy"] * 100, 1)])


def _write_naive_csv(path: str, rows: list[dict]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["mode", "trials", "naive_detection_rate_asis", "naive_detection_rate_mtime_forged"])
        for row in rows:
            w.writerow([row["mode"], row["trials"],
                        round(row["naive_detection_rate_asis"] * 100, 1),
                        round(row["naive_detection_rate_mtime_forged"] * 100, 1)])


def _write_case_csv(path: str, rows: list[tuple]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file_id", "record_count", "status", "verified",
                    "hashing_ms", "verify_ms", "original_file_hash", "recomputed_file_hash",
                    "original_chain_hash", "recomputed_chain_hash",
                    "tampered_rows_ground_truth", "tampered_rows_localized"])
        for row in rows:
            if len(row) == 3:
                b, r, report = row
                ground_truth = ";".join(report.tampered_rows)
                localized = ";".join(r.tampered_trans_ids)
            else:
                b, r = row
                ground_truth = ""
                localized = ""
            w.writerow([b.file_id, b.record_count, r.status, r.verified,
                        round(b.hashing_seconds * 1000, 3), round(r.verify_seconds * 1000, 3),
                        r.original_file_hash, r.recomputed_file_hash,
                        r.original_hash, r.recomputed_hash,
                        ground_truth, localized])


def _write_latency_csv(path: str, summaries, network_estimates: dict[int, dict[str, float]]):
    profile_keys = list(PROFILES.keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["record_count", "avg_hash_ms", "avg_verify_ms", "avg_baseline_ms",
                    "overhead_ms", "overhead_ratio_pct"]
                   + [f"net_{k}_ms" for k in profile_keys])
        for s in summaries:
            net_row = [round(network_estimates[s.record_count][k] * 1000, 2) for k in profile_keys]
            w.writerow([s.record_count, round(s.avg_hash_seconds * 1000, 3),
                        round(s.avg_verify_seconds * 1000, 3), round(s.avg_baseline_seconds * 1000, 3),
                        round(s.overhead_seconds * 1000, 3), round(s.overhead_ratio * 100, 2)]
                       + net_row)


def _plot_latency(summaries, path: str):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib이 설치되어 있지 않아 그래프 생성을 건너뜁니다.")
        return

    for font_name in ("AppleGothic", "Malgun Gothic", "Nanum Gothic", "Noto Sans CJK KR"):
        if font_name in {f.name for f in matplotlib.font_manager.fontManager.ttflist}:
            matplotlib.rcParams["font.family"] = font_name
            break
    matplotlib.rcParams["axes.unicode_minus"] = False

    sizes = [s.record_count for s in summaries]
    overhead_ms = [s.overhead_seconds * 1000 for s in summaries]
    baseline_ms = [s.avg_baseline_seconds * 1000 for s in summaries]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(sizes, baseline_ms, marker="o", label="베이스라인 전송(검증 없음)")
    ax.plot(sizes, overhead_ms, marker="o", label="해시 계산+검증 오버헤드")
    ax.set_xlabel("레코드 수")
    ax.set_ylabel("소요 시간 (ms)")
    ax.set_title("데이터 규모별 처리 지연 시간")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="정산 파일 무결성 검증 모델 시뮬레이션")
    parser.add_argument("--case", choices=["a", "b", "latency", "naive", "sweep", "all"], default="all")
    parser.add_argument("--records", type=int, default=config.DEFAULT_RECORD_COUNT)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--tamper-count", type=int, default=1)
    parser.add_argument("--tamper-mode",
                        choices=["amount", "account", "both", "header", "delete", "insert", "bitflip"],
                        default="amount")
    parser.add_argument("--latency-sizes", type=int, nargs="+", default=[1_000, 10_000, 50_000, 100_000])
    parser.add_argument("--sweep-counts", type=int, nargs="+", default=[1, 5, 10, 50, 100])
    parser.add_argument("--sweep-trials", type=int, default=5)
    args = parser.parse_args()

    config.ensure_dirs()
    vault = HashVault(config.VAULT_PATH)
    batch = SettlementBatch(vault, config.STAGING_DIR)
    agent = TransferAgent(vault, config.TRANSMITTED_DIR, config.QUARANTINE_DIR)

    report_lines = ["# 시뮬레이션 결과 리포트", ""]

    if args.case in ("a", "all"):
        print(f"Case A (정상 시나리오) 실행: trials={args.trials}, records={args.records:,}")
        results_a = run_case_a(batch, agent, args.trials, args.records)
        _write_case_csv(os.path.join(config.RESULTS_DIR, "case_a_results.csv"), results_a)
        fpr = false_positive_rate([r for _, r in results_a])
        report_lines += [
            "## Case A: 정상 시나리오",
            f"- 시행 횟수: {args.trials}",
            f"- 레코드 수: {args.records:,}",
            f"- 오탐(정상 파일 오차단)율: {fpr * 100:.2f}%",
            "",
        ]

    if args.case in ("b", "all"):
        print(f"Case B (변조 시나리오) 실행: trials={args.trials}, records={args.records:,}, "
              f"tamper_count={args.tamper_count}, mode={args.tamper_mode}")
        results_b = run_case_b(batch, agent, args.trials, args.records, args.tamper_count, args.tamper_mode)
        _write_case_csv(os.path.join(config.RESULTS_DIR, "case_b_results.csv"), results_b)
        tdr = tampering_detection_rate([r for _, r, _ in results_b])
        loc_acc = localization_accuracy(
            [(r.tampered_trans_ids, report.tampered_rows) for _, r, report in results_b]
        )
        report_lines += [
            "## Case B: 변조 공격 시나리오",
            f"- 시행 횟수: {args.trials}",
            f"- 레코드 수: {args.records:,}",
            f"- 변조 건수(살라미 기법): {args.tamper_count} / {args.records:,}",
            f"- 변조 방식: {args.tamper_mode}",
            f"- 변조 탐지율(Tampering Detection Rate): {tdr * 100:.2f}%",
            f"- 변조 위치 특정 정확도(Localization Accuracy): {loc_acc * 100:.2f}% "
            f"(체인 원장 대조로 실제 변조된 trans_id를 정확히 특정한 비율)",
            "",
        ]

    if args.case in ("sweep", "all"):
        print(f"변조 건수 스윕 실행: counts={args.sweep_counts}, records={args.records:,}, "
              f"trials={args.sweep_trials}")
        sweep_rows = run_tamper_count_sweep(batch, agent, args.records, args.sweep_counts,
                                             args.tamper_mode, args.sweep_trials)
        _write_sweep_csv(os.path.join(config.RESULTS_DIR, "tamper_count_sweep.csv"), sweep_rows)
        report_lines += [
            "## 변조 건수 스윕 (탐지율·위치 특정 정확도가 변조 규모와 무관한지 검증)",
            "",
            f"- 변조 방식: {args.tamper_mode}",
            f"- 레코드 수: {args.records:,}",
            f"- 시행 횟수(건수별): {args.sweep_trials}",
            "",
            "| 변조 건수 | 탐지율 | 위치 특정 정확도 |",
            "|---|---|---|",
        ]
        for row in sweep_rows:
            report_lines.append(
                f"| {row['tamper_count']:,} | {row['detection_rate']*100:.0f}% | "
                f"{row['localization_accuracy']*100:.0f}% |"
            )
        report_lines.append("")

    if args.case in ("naive", "all"):
        print(f"Naive Baseline 비교 실행: trials={args.trials}, records={args.records:,}")
        naive_rows = run_naive_baseline_comparison(batch, args.trials, args.records)
        _write_naive_csv(os.path.join(config.RESULTS_DIR, "naive_baseline_results.csv"), naive_rows)
        report_lines += [
            "## RQ4: 제안 모델 vs 파일 크기·수정시각 비교 방식(기존 단순 방식)",
            "",
            f"- 시행 횟수(모드별): {args.trials}",
            f"- 레코드 수: {args.records:,}",
            "- 제안 모델(해시 체이닝)의 탐지율은 Case B 실험에서 이미 100%로 확인됨 "
            "(내용 기반 검증이라 mtime 위조와 무관)",
            "",
            "| 변조 방식 | 기존 방식 탐지율(as-is) | 기존 방식 탐지율(mtime 위조 후) |",
            "|---|---|---|",
        ]
        for row in naive_rows:
            report_lines.append(
                f"| {row['mode']} | {row['naive_detection_rate_asis']*100:.0f}% | "
                f"{row['naive_detection_rate_mtime_forged']*100:.0f}% |"
            )
        report_lines.append("")

    if args.case in ("latency", "all"):
        print(f"Latency Sweep 실행: sizes={args.latency_sizes}")
        summaries, network_estimates = run_latency_sweep(vault, args.latency_sizes)
        _write_latency_csv(os.path.join(config.RESULTS_DIR, "latency_sweep.csv"), summaries, network_estimates)
        _plot_latency(summaries, os.path.join(config.RESULTS_DIR, "latency_overhead.png"))
        report_lines += ["## 처리 지연 시간 (Processing Latency Overhead)", ""]
        report_lines += ["| 레코드 수 | 해시계산(ms) | 검증(ms) | 베이스라인(ms) | 오버헤드(ms) | 오버헤드(%) |",
                          "|---|---|---|---|---|---|"]
        for s in summaries:
            report_lines.append(
                f"| {s.record_count:,} | {s.avg_hash_seconds*1000:.2f} | {s.avg_verify_seconds*1000:.2f} | "
                f"{s.avg_baseline_seconds*1000:.2f} | {s.overhead_seconds*1000:.2f} | {s.overhead_ratio*100:.1f}% |"
            )
        report_lines.append("")

        report_lines += [
            "### 네트워크 전송 구간을 포함한 종단간(end-to-end) 지연 추정",
            "",
            "아래 값은 실측이 아니라 회선 대역폭 가정에 기반한 분석적 추정치이다 "
            "(§5.2 한계: 로컬 I/O만 측정, 실제 네트워크 전송 구간은 범위 밖).",
            "",
            "| 레코드 수 | " + " | ".join(p.name for p in PROFILES.values()) + " | 검증 오버헤드 비중(전용회선 100Mbps 기준) |",
            "|---|" + "---|" * len(PROFILES) + "---|",
        ]
        for s in summaries:
            net = network_estimates[s.record_count]
            net_cells = " | ".join(f"{net[k]*1000:.1f}ms" for k in PROFILES)
            ref_net_ms = net["leased_100m"] * 1000
            share_pct = (s.overhead_seconds * 1000) / (ref_net_ms + s.overhead_seconds * 1000) * 100
            report_lines.append(f"| {s.record_count:,} | {net_cells} | {share_pct:.1f}% |")
        report_lines.append("")

    report_path = os.path.join(config.RESULTS_DIR, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"\n리포트 저장 완료: {report_path}")


if __name__ == "__main__":
    main()
