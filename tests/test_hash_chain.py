"""이중 해시 체이닝 검증 모델의 핵심 로직에 대한 테스트.

Case A(정상)는 통과, Case B(변조)는 100% 차단되어야 함을 검증한다.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

import transfer_agent as transfer_agent_module
from hash_vault import HashVault, VaultIntegrityError
from hashchain import build_chain as real_build_chain
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


def test_transmitted_file_is_the_verified_snapshot_when_source_changes(env, monkeypatch):
    """스냅샷 생성 후 staging 원본이 바뀌어도 검증한 바이트만 전송되어야 한다."""
    vault, batch, agent = env
    b = batch.run("file_toctou", RECORD_COUNT, seed=101)
    with open(b.file_path, "rb") as f:
        expected_bytes = f.read()

    def build_snapshot_then_mutate_source(snapshot_path, file_id):
        with open(b.file_path, "ab") as source:
            source.write(b"ATTACK_AFTER_SNAPSHOT")
        return real_build_chain(snapshot_path, file_id)

    monkeypatch.setattr(transfer_agent_module, "build_chain", build_snapshot_then_mutate_source)
    r = agent.transmit(b.file_id, b.file_path)

    transmitted_path = os.path.join(agent.transmitted_dir, "file_toctou.csv")
    assert r.status == "TRANSMITTED"
    with open(transmitted_path, "rb") as f:
        assert f.read() == expected_bytes
    with open(b.file_path, "rb") as f:
        assert f.read() != expected_bytes


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


def test_header_tampering_is_blocked(env):
    """컬럼명/헤더 변조도 체인 루트에 반영되어 차단되어야 한다."""
    vault, batch, agent = env
    b = batch.run("file_header_tamper", RECORD_COUNT, seed=6)
    tamper_file(b.file_path, mode="header", seed=14)
    r = agent.transmit(b.file_id, b.file_path)

    assert r.status == "BLOCKED"
    assert r.verified is False
    assert "HEADER_MISMATCH" in r.tampered_trans_ids


def test_deleted_record_is_blocked(env):
    """레코드 삭제 공격은 차단되고, 삭제된 거래ID가 연쇄 오탐 없이 정확히 특정되어야 한다."""
    vault, batch, agent = env
    b = batch.run("file_delete_tamper", RECORD_COUNT, seed=7)
    report = tamper_file(b.file_path, tamper_count=1, mode="delete", seed=15)
    r = agent.transmit(b.file_id, b.file_path)

    assert r.status == "BLOCKED"
    assert r.verified is False
    assert any(item.startswith("RECORD_COUNT_MISMATCH") for item in r.tampered_trans_ids)
    non_marker = [x for x in r.tampered_trans_ids if not x.startswith("RECORD_COUNT_MISMATCH")]
    assert non_marker == report.tampered_rows


def test_multiple_deleted_records_are_localized_without_cascade(env):
    """여러 건을 삭제해도 삭제 지점 이후 레코드까지 오탐하지 않고 삭제된 건만 특정해야 한다."""
    vault, batch, agent = env
    b = batch.run("file_multi_delete_tamper", 3_000, seed=9)
    report = tamper_file(b.file_path, tamper_count=5, mode="delete", seed=17)
    r = agent.transmit(b.file_id, b.file_path)

    assert r.status == "BLOCKED"
    non_marker = [x for x in r.tampered_trans_ids if not x.startswith("RECORD_COUNT_MISMATCH")]
    assert set(non_marker) == set(report.tampered_rows)
    assert len(non_marker) == 5


def test_inserted_record_is_blocked(env):
    """레코드 삽입 공격은 차단되고, 삽입된 가짜 거래ID가 정확히 특정되어야 한다."""
    vault, batch, agent = env
    b = batch.run("file_insert_tamper", RECORD_COUNT, seed=8)
    report = tamper_file(b.file_path, tamper_count=1, mode="insert", seed=16)
    r = agent.transmit(b.file_id, b.file_path)

    assert r.status == "BLOCKED"
    assert r.verified is False
    assert any(item.startswith("RECORD_COUNT_MISMATCH") for item in r.tampered_trans_ids)
    non_marker = [x for x in r.tampered_trans_ids if not x.startswith("RECORD_COUNT_MISMATCH")]
    assert non_marker == report.tampered_rows


def test_account_tampering_preserves_file_size(env):
    """계좌번호는 자릿수가 그대로이므로, 계좌 변조는 파일 크기를 전혀 바꾸지 않아야 한다
    (다른 레코드를 pandas로 재직렬화하면서 개행 문자 등이 바뀌어 크기가 흔들리면 안 됨)."""
    vault, batch, agent = env
    b = batch.run("file_account_size_check", RECORD_COUNT, seed=25)
    size_before = os.path.getsize(b.file_path)
    tamper_file(b.file_path, tamper_count=1, mode="account", seed=26)
    size_after = os.path.getsize(b.file_path)

    assert size_after == size_before


def test_single_bit_flip_is_detected_and_localized(env):
    """필드 전체가 아니라 단 1비트만 뒤집혀도 체인 루트가 달라져 탐지·차단되어야 한다."""
    vault, batch, agent = env
    b = batch.run("file_bitflip_tamper", RECORD_COUNT, seed=20)
    report = tamper_file(b.file_path, mode="bitflip", seed=21)
    r = agent.transmit(b.file_id, b.file_path)

    assert r.status == "BLOCKED"
    assert r.verified is False
    assert r.original_hash != r.recomputed_hash
    assert r.tampered_trans_ids == report.tampered_rows


def test_repeated_single_bit_flips_are_always_detected(env):
    """여러 다른 위치의 1비트 변조를 반복 시행해도 매번 탐지되어야 한다 (탐지가 우연에 의존하지 않음)."""
    vault, batch, agent = env
    for i in range(10):
        b = batch.run(f"file_bitflip_{i}", RECORD_COUNT, seed=30 + i)
        tamper_file(b.file_path, mode="bitflip", seed=40 + i)
        r = agent.transmit(b.file_id, b.file_path)
        assert r.status == "BLOCKED"


def test_vault_rejects_duplicate_registration(tmp_path):
    vault = HashVault(str(tmp_path / "vault" / "hash_vault.json"))
    vault.store("dup", "abc123", "sha256", 10)
    with pytest.raises(VaultIntegrityError):
        vault.store("dup", "def456", "sha256", 10)


def test_vault_rejects_missing_file_id(tmp_path):
    vault = HashVault(str(tmp_path / "vault" / "hash_vault.json"))
    with pytest.raises(VaultIntegrityError):
        vault.retrieve("nonexistent")
