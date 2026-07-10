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


def run_latency_sweep(vault: HashVault, sizes: list[int]):
    summaries = []
    for size in sizes:
        staging = os.path.join(config.STAGING_DIR, "latency")
        batch = SettlementBatch(vault, staging)
        agent = TransferAgent(vault, config.TRANSMITTED_DIR, config.QUARANTINE_DIR)

        hash_secs, verify_secs, baseline_secs = [], [], []
        repeats = 9
        for i in range(repeats):
            file_id = _new_file_id(f"lat{size}")
            b = batch.run(file_id, size, seed=4000 + i)
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
        print(f"  [Latency] n={size:>7,} hash={summary.avg_hash_seconds*1000:.2f}ms "
              f"verify={summary.avg_verify_seconds*1000:.2f}ms "
              f"baseline={summary.avg_baseline_seconds*1000:.2f}ms "
              f"overhead={summary.overhead_seconds*1000:.2f}ms ({summary.overhead_ratio*100:.1f}%)")
    return summaries


def _write_case_csv(path: str, rows: list[tuple]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file_id", "record_count", "status", "verified",
                    "hashing_ms", "verify_ms", "tampered_rows_ground_truth", "tampered_rows_localized"])
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
                        ground_truth, localized])


def _write_latency_csv(path: str, summaries):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["record_count", "avg_hash_ms", "avg_verify_ms", "avg_baseline_ms",
                    "overhead_ms", "overhead_ratio_pct"])
        for s in summaries:
            w.writerow([s.record_count, round(s.avg_hash_seconds * 1000, 3),
                        round(s.avg_verify_seconds * 1000, 3), round(s.avg_baseline_seconds * 1000, 3),
                        round(s.overhead_seconds * 1000, 3), round(s.overhead_ratio * 100, 2)])


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
    parser.add_argument("--case", choices=["a", "b", "latency", "all"], default="all")
    parser.add_argument("--records", type=int, default=config.DEFAULT_RECORD_COUNT)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--tamper-count", type=int, default=1)
    parser.add_argument("--tamper-mode", choices=["amount", "account", "both", "header", "delete", "insert"],
                        default="amount")
    parser.add_argument("--latency-sizes", type=int, nargs="+", default=[1_000, 10_000, 50_000, 100_000])
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

    if args.case in ("latency", "all"):
        print(f"Latency Sweep 실행: sizes={args.latency_sizes}")
        summaries = run_latency_sweep(vault, args.latency_sizes)
        _write_latency_csv(os.path.join(config.RESULTS_DIR, "latency_sweep.csv"), summaries)
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

    report_path = os.path.join(config.RESULTS_DIR, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"\n리포트 저장 완료: {report_path}")


if __name__ == "__main__":
    main()
