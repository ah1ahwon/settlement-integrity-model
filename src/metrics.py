"""평가 지표: 변조 탐지율(Tampering Detection Rate), 처리 지연 시간(Latency Overhead)."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from transfer_agent import TransferResult


def tampering_detection_rate(results: list[TransferResult]) -> float:
    """변조 시나리오(Case B) 결과 중 정확히 BLOCKED 처리된 비율. 1.0이면 오탐/미탐 없이 100% 탐지."""
    if not results:
        return 0.0
    detected = sum(1 for r in results if r.status == "BLOCKED")
    return detected / len(results)


def false_positive_rate(results: list[TransferResult]) -> float:
    """정상 시나리오(Case A) 결과 중 잘못 BLOCKED 처리된 비율. 0.0이 이상적."""
    if not results:
        return 0.0
    false_blocked = sum(1 for r in results if r.status == "BLOCKED")
    return false_blocked / len(results)


def localization_accuracy(pairs: list[tuple[list[str], list[str]]]) -> float:
    """체인 기반 변조 위치 특정 결과가 실제 변조된 거래(trans_id) 집합과 정확히
    일치하는 비율. pairs는 (탐지된 trans_id 목록, tamper.py가 실제 변조한
    trans_id 목록)의 리스트. 1.0이면 매 시행마다 오차 없이 정확히 특정."""
    if not pairs:
        return 0.0
    exact = sum(1 for predicted, truth in pairs if set(predicted) == set(truth))
    return exact / len(pairs)


@dataclass
class LatencySummary:
    record_count: int
    avg_hash_seconds: float          # Phase 1: 생성 직후 해시 계산 평균 시간
    avg_verify_seconds: float         # Phase 3: 재계산+대사 평균 시간
    avg_baseline_seconds: float        # 검증 없는 단순 전송 평균 시간
    overhead_seconds: float             # (hash + verify) - baseline
    overhead_ratio: float                 # overhead_seconds / baseline_seconds


def latency_overhead(record_count: int, hash_seconds: list[float], verify_seconds: list[float],
                      baseline_seconds: list[float]) -> LatencySummary:
    # 밀리초 단위 I/O 타이밍은 OS 파일 캐시/GC 등에 의한 변동폭이 크므로,
    # 평균보다 이상치에 강건한 중앙값을 사용한다.
    avg_hash = median(hash_seconds) if hash_seconds else 0.0
    avg_verify = median(verify_seconds) if verify_seconds else 0.0
    avg_baseline = median(baseline_seconds) if baseline_seconds else 0.0
    overhead = (avg_hash + avg_verify) - avg_baseline
    ratio = (overhead / avg_baseline) if avg_baseline > 0 else float("inf")
    return LatencySummary(
        record_count=record_count,
        avg_hash_seconds=avg_hash,
        avg_verify_seconds=avg_verify,
        avg_baseline_seconds=avg_baseline,
        overhead_seconds=overhead,
        overhead_ratio=ratio,
    )
