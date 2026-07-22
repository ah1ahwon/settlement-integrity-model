"""네트워크 전송 지연 추정 모듈에 대한 테스트."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from network import PROFILES, estimate_transfer_seconds


def test_larger_file_takes_longer_to_transfer():
    profile = PROFILES["leased_100m"]
    small = estimate_transfer_seconds(1_000_000, profile)
    large = estimate_transfer_seconds(10_000_000, profile)
    assert large > small


def test_slower_profile_takes_longer_for_same_file():
    file_size = 5_000_000
    fast = estimate_transfer_seconds(file_size, PROFILES["leased_100m"])
    slow = estimate_transfer_seconds(file_size, PROFILES["leased_10m"])
    assert slow > fast


def test_estimate_matches_bandwidth_arithmetic():
    profile = PROFILES["leased_100m"]
    file_size_bytes = 12_500_000  # 100Mbit == 12.5MB
    seconds = estimate_transfer_seconds(file_size_bytes, profile)
    expected = profile.base_latency_ms / 1000 + 1.0  # 100Mbit / 100Mbps = 1초
    assert abs(seconds - expected) < 1e-9
