"""SFTP/네트워크 전송 구간의 지연시간을 대역폭 가정으로 추정한다.

기존 지연시간 측정(§5.2)은 로컬 파일 시스템 I/O(해시 계산·검증·단순 복사)
만 다루며, 실제 정산 파일이 SFTP 등으로 외부 기관에 전송되는 네트워크
구간 자체는 범위 밖이었다. 이 모듈은 그 구간을 대역폭 기반 분석 모델로
추정해, 해시 체인 검증 오버헤드가 전체 종단간(end-to-end) 지연에서 차지
하는 비중을 가늠하기 위한 것이다.

주의: 이 값은 실측치가 아니라 대역폭 가정에 기반한 추정치(estimate)다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NetworkProfile:
    name: str
    bandwidth_mbps: float    # 회선 대역폭 (Mbps)
    base_latency_ms: float   # 연결 수립 등 고정 지연 (ms)


# 정산 배치가 실무에서 흔히 사용하는 회선 대역폭을 참고용으로 가정한 프로파일.
# 실제 계약 회선 사양에 따라 달라질 수 있으므로 연구용 추정 시나리오로만 사용한다.
PROFILES: dict[str, NetworkProfile] = {
    "leased_100m": NetworkProfile("전용회선 100Mbps", bandwidth_mbps=100.0, base_latency_ms=5.0),
    "leased_10m": NetworkProfile("전용회선 10Mbps", bandwidth_mbps=10.0, base_latency_ms=10.0),
    "internet_vpn": NetworkProfile("인터넷 VPN(평균)", bandwidth_mbps=50.0, base_latency_ms=30.0),
}


def estimate_transfer_seconds(file_size_bytes: int, profile: NetworkProfile) -> float:
    """파일 크기와 회선 프로파일로부터 전송 소요 시간(초)을 추정한다.

    base_latency_ms(연결 수립 등 고정 지연) + file_size_bytes를 대역폭으로
    나눈 순수 전송 시간의 합으로 근사한다.
    """
    bits = file_size_bytes * 8
    transfer_seconds = bits / (profile.bandwidth_mbps * 1_000_000)
    return profile.base_latency_ms / 1000 + transfer_seconds
