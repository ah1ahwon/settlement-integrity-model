"""변조 탐지·위치 특정·공정한 종단간 처리 지연 지표."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from transfer_agent import TransferResult


def tampering_detection_rate(results: list[TransferResult]) -> float:
    return sum(r.status == "BLOCKED" for r in results) / len(results) if results else 0.0


def false_positive_rate(results: list[TransferResult]) -> float:
    return sum(r.status == "BLOCKED" for r in results) / len(results) if results else 0.0


def localization_accuracy(pairs: list[tuple[list[str], list[str]]]) -> float:
    if not pairs:
        return 0.0
    return sum(set(predicted) == set(truth) for predicted, truth in pairs) / len(pairs)


@dataclass
class LatencySummary:
    record_count: int
    phase1_integrity_seconds: float
    phase3_gate_seconds: float
    proposed_total_seconds: float
    baseline_transfer_seconds: float
    overhead_seconds: float
    overhead_ratio: float


def latency_overhead(record_count: int, phase1_seconds: list[float], phase3_gate_seconds: list[float],
                     proposed_total_seconds: list[float], baseline_seconds: list[float]) -> LatencySummary:
    """명시한 측정 경계별 중앙값을 계산한다.

    Phase 1은 해시 계산과 원자적 Vault 저장 전체, Phase 3은 스냅샷 생성부터
    전송 허용 결정까지다. proposed_total은 Phase 1과 TransferAgent 전체를
    합친 값이며 baseline은 동일 파일의 1회 복사 시간이다.
    """
    phase1 = median(phase1_seconds) if phase1_seconds else 0.0
    phase3 = median(phase3_gate_seconds) if phase3_gate_seconds else 0.0
    proposed = median(proposed_total_seconds) if proposed_total_seconds else 0.0
    baseline = median(baseline_seconds) if baseline_seconds else 0.0
    overhead = proposed - baseline
    ratio = overhead / baseline if baseline > 0 else float("inf")
    return LatencySummary(record_count, phase1, phase3, proposed, baseline, overhead, ratio)
