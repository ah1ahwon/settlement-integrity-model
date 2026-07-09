"""이중 해시 체이닝 검증 모델의 핵심 로직에 대한 테스트.

Case A(정상)는 통과, Case B(변조)는 100% 차단되어야 함을 검증한다.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from hash_vault import HashVault, VaultIntegrityError
from settlement_batch import SettlementBatch
from tamper import tamper_file
from transfer_agent import TransferAgent

RECORD_COUNT = 200


@pytest.fixture
def env(tmp_path):
    vault = HashVault(str(tmp_path / "vault" / "hash_vault.json"))
    batch = SettlementBatch(vault, str(tmp_path / "staging"))
    agent = TransferAgent(vault, str(tmp_path / "transmitted"), str(tmp_path / "quarantine"))
    return vault, batch, agent


def test_normal_file_is_transmitted(env):
    vault, batch, agent = env
    b = batch.run("file_normal", RECORD_COUNT, seed=1)
    r = agent.transmit(b.file_id, b.file_path)

    assert r.status == "TRANSMITTED"
    assert r.verified is True
    assert r.original_hash == r.recomputed_hash
    assert os.path.exists(os.path.join(agent.transmitted_dir, "file_normal.csv"))


def test_amount_tampering_is_blocked(env):
    vault, batch, agent = env
    b = batch.run("file_tamper_amount", RECORD_COUNT, seed=2)
    report = tamper_file(b.file_path, tamper_count=1, mode="amount", seed=10)
    r = agent.transmit(b.file_id, b.file_path)

    assert r.status == "BLOCKED"
    assert r.verified is False
    assert r.original_hash != r.recomputed_hash
    assert os.path.exists(os.path.join(agent.quarantine_dir, "file_tamper_amount.csv"))
    assert not os.path.exists(os.path.join(agent.transmitted_dir, "file_tamper_amount.csv"))
    assert len(r.alerts) == 1
    # 체인 기반 변조 위치 특정: 실제로 변조한 거래 ID와 정확히 일치해야 함
    assert r.tampered_trans_ids == report.tampered_rows


def test_account_tampering_is_blocked(env):
    vault, batch, agent = env
    b = batch.run("file_tamper_account", RECORD_COUNT, seed=3)
    tamper_file(b.file_path, tamper_count=1, mode="account", seed=11)
    r = agent.transmit(b.file_id, b.file_path)

    assert r.status == "BLOCKED"
    assert r.verified is False


def test_salami_slicing_single_record_among_many_is_detected(env):
    """5,000건 중 단 1건만 변조해도 체인 루트가 달라져 탐지되고, 그 1건이 정확히 특정되어야 한다."""
    vault, batch, agent = env
    b = batch.run("file_salami", 5_000, seed=4)
    report = tamper_file(b.file_path, tamper_count=1, mode="amount", seed=12)
    r = agent.transmit(b.file_id, b.file_path)

    assert r.status == "BLOCKED"
    assert r.tampered_trans_ids == report.tampered_rows


def test_multiple_tampered_records_are_all_localized(env):
    """여러 건을 동시에 변조해도 체인 원장 대조로 전부 특정되어야 한다."""
    vault, batch, agent = env
    b = batch.run("file_multi_tamper", 3_000, seed=5)
    report = tamper_file(b.file_path, tamper_count=5, mode="both", seed=13)
    r = agent.transmit(b.file_id, b.file_path)

    assert r.status == "BLOCKED"
    assert set(r.tampered_trans_ids) == set(report.tampered_rows)
    assert len(r.tampered_trans_ids) == 5


def test_vault_rejects_duplicate_registration(tmp_path):
    vault = HashVault(str(tmp_path / "vault" / "hash_vault.json"))
    vault.store("dup", "abc123", "sha256", 10)
    with pytest.raises(VaultIntegrityError):
        vault.store("dup", "def456", "sha256", 10)


def test_vault_rejects_missing_file_id(tmp_path):
    vault = HashVault(str(tmp_path / "vault" / "hash_vault.json"))
    with pytest.raises(VaultIntegrityError):
        vault.retrieve("nonexistent")
