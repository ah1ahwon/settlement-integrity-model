"""Phase 2·3 전송 에이전트: 이중 무결성 검증과 fail-closed 통제."""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum

from hash_vault import HashVault, VaultIntegrityError
from hashchain import ChainResult, build_chain, localize_tampering


class ReasonCode(str, Enum):
    OK = "OK"
    SNAPSHOT_CREATION_FAILED = "SNAPSHOT_CREATION_FAILED"
    VERIFICATION_ERROR = "VERIFICATION_ERROR"
    VAULT_LOOKUP_FAILED = "VAULT_LOOKUP_FAILED"
    FILE_HASH_MISMATCH = "FILE_HASH_MISMATCH"
    CHAIN_HASH_MISMATCH = "CHAIN_HASH_MISMATCH"
    FILE_AND_CHAIN_MISMATCH = "FILE_AND_CHAIN_MISMATCH"
    DESTINATION_CONFLICT = "DESTINATION_CONFLICT"
    PROMOTION_FAILED = "PROMOTION_FAILED"


@dataclass
class TransferResult:
    file_id: str
    status: str
    verified: bool
    original_hash: str
    recomputed_hash: str
    original_file_hash: str
    recomputed_file_hash: str
    verify_seconds: float
    io_seconds: float
    reason_code: str = ReasonCode.OK.value
    snapshot_seconds: float = 0.0
    phase3_gate_seconds: float = 0.0
    promotion_seconds: float = 0.0
    total_seconds: float = 0.0
    tampered_trans_ids: list[str] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)


class TransferAgent:
    def __init__(self, vault: HashVault, transmitted_dir: str, quarantine_dir: str,
                 algorithm: str = "sha256"):
        self.vault = vault
        self.transmitted_dir = transmitted_dir
        self.quarantine_dir = quarantine_dir
        self.algorithm = algorithm

    def _create_verification_snapshot(self, file_path: str) -> tuple[str, float]:
        spool_dir = os.path.join(self.transmitted_dir, ".verification_spool")
        os.makedirs(spool_dir, exist_ok=True)
        os.chmod(spool_dir, stat.S_IRWXU)
        started = time.perf_counter()
        fd, snapshot_path = tempfile.mkstemp(prefix="pending_", suffix=".csv", dir=spool_dir)
        try:
            with os.fdopen(fd, "wb") as snapshot, open(file_path, "rb") as source:
                shutil.copyfileobj(source, snapshot, length=1024 * 1024)
                snapshot.flush()
                os.fsync(snapshot.fileno())
            os.chmod(snapshot_path, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            if os.path.exists(snapshot_path):
                os.remove(snapshot_path)
            raise
        return snapshot_path, time.perf_counter() - started

    def _quarantine(self, snapshot_path: str, file_id: str, file_path: str) -> str:
        os.makedirs(self.quarantine_dir, exist_ok=True)
        base = os.path.basename(file_path)
        destination = os.path.join(self.quarantine_dir, base)
        if os.path.exists(destination):
            destination = os.path.join(self.quarantine_dir, f"{file_id}__{base}")
        os.replace(snapshot_path, destination)
        return destination

    @staticmethod
    def _mismatch_reason(file_matched: bool, chain_matched: bool) -> str:
        if not file_matched and not chain_matched:
            return ReasonCode.FILE_AND_CHAIN_MISMATCH.value
        if not file_matched:
            return ReasonCode.FILE_HASH_MISMATCH.value
        return ReasonCode.CHAIN_HASH_MISMATCH.value

    def _blocked(self, *, file_id: str, reason: ReasonCode | str, started: float,
                 snapshot_seconds: float = 0.0, verify_seconds: float = 0.0,
                 gate_seconds: float = 0.0, original_hash: str = "", recomputed_hash: str = "",
                 original_file_hash: str = "", recomputed_file_hash: str = "",
                 tampered: list[str] | None = None, alerts: list[str] | None = None) -> TransferResult:
        reason_value = reason.value if isinstance(reason, ReasonCode) else reason
        return TransferResult(
            file_id=file_id, status="BLOCKED", verified=False,
            original_hash=original_hash, recomputed_hash=recomputed_hash,
            original_file_hash=original_file_hash, recomputed_file_hash=recomputed_file_hash,
            verify_seconds=verify_seconds, io_seconds=snapshot_seconds,
            reason_code=reason_value, snapshot_seconds=snapshot_seconds,
            phase3_gate_seconds=gate_seconds, total_seconds=time.perf_counter() - started,
            tampered_trans_ids=tampered or [], alerts=alerts or [],
        )

    def transmit(self, file_id: str, file_path: str) -> TransferResult:
        """검증 중 어떤 오류가 나도 외부 전송을 허용하지 않는 fail-closed 경로."""
        started = time.perf_counter()
        try:
            os.makedirs(self.transmitted_dir, exist_ok=True)
            os.makedirs(self.quarantine_dir, exist_ok=True)
            snapshot_path, snapshot_seconds = self._create_verification_snapshot(file_path)
        except Exception as exc:
            return self._blocked(
                file_id=file_id, reason=ReasonCode.SNAPSHOT_CREATION_FAILED, started=started,
                alerts=[f"[ALERT] 스냅샷 생성 실패로 전송 차단: {type(exc).__name__}: {exc}"],
            )

        verify_started = time.perf_counter()
        recomputed: ChainResult | None = None
        try:
            recomputed = build_chain(snapshot_path, file_id)
            original_record = self.vault.retrieve(file_id)
        except VaultIntegrityError as exc:
            verify_seconds = time.perf_counter() - verify_started
            try:
                self._quarantine(snapshot_path, file_id, file_path)
            except OSError:
                if os.path.exists(snapshot_path):
                    os.remove(snapshot_path)
            return self._blocked(
                file_id=file_id, reason=ReasonCode.VAULT_LOOKUP_FAILED, started=started,
                snapshot_seconds=snapshot_seconds, verify_seconds=verify_seconds,
                gate_seconds=snapshot_seconds + verify_seconds,
                recomputed_hash=recomputed.root_hash if recomputed else "",
                recomputed_file_hash=recomputed.file_hash if recomputed else "",
                alerts=[f"[ALERT] Vault 조회 실패로 전송 차단: {exc}"],
            )
        except Exception as exc:
            verify_seconds = time.perf_counter() - verify_started
            try:
                self._quarantine(snapshot_path, file_id, file_path)
            except OSError:
                if os.path.exists(snapshot_path):
                    os.remove(snapshot_path)
            return self._blocked(
                file_id=file_id, reason=ReasonCode.VERIFICATION_ERROR, started=started,
                snapshot_seconds=snapshot_seconds, verify_seconds=verify_seconds,
                gate_seconds=snapshot_seconds + verify_seconds,
                alerts=[f"[ALERT] 검증 오류로 전송 차단: {type(exc).__name__}: {exc}"],
            )

        chain_matched = recomputed.root_hash == original_record.hash_value
        file_matched = bool(original_record.file_hash) and recomputed.file_hash == original_record.file_hash
        verify_seconds = time.perf_counter() - verify_started
        gate_seconds = snapshot_seconds + verify_seconds
        if not (chain_matched and file_matched):
            if chain_matched:
                tampered = ["FILE_BYTES_MISMATCH"]
            else:
                try:
                    ledger = self.vault.retrieve_chain(file_id)
                    original_chain = ChainResult(
                        file_hash=original_record.file_hash, root_hash=original_record.hash_value,
                        header_hash=ledger.header_hash, record_hashes=ledger.record_hashes,
                        trans_ids=ledger.trans_ids,
                    )
                    tampered = localize_tampering(original_chain, recomputed)
                except VaultIntegrityError:
                    tampered = ["LOCALIZATION_UNAVAILABLE"]
            quarantine_error = ""
            try:
                self._quarantine(snapshot_path, file_id, file_path)
            except OSError as exc:
                quarantine_error = f"; 격리 실패={type(exc).__name__}: {exc}"
                if os.path.exists(snapshot_path):
                    os.remove(snapshot_path)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError as exc:
                quarantine_error += f"; 원본 제거 실패={type(exc).__name__}: {exc}"
            reason = self._mismatch_reason(file_matched, chain_matched)
            return self._blocked(
                file_id=file_id, reason=reason, started=started,
                snapshot_seconds=snapshot_seconds, verify_seconds=verify_seconds,
                gate_seconds=gate_seconds, original_hash=original_record.hash_value,
                recomputed_hash=recomputed.root_hash, original_file_hash=original_record.file_hash,
                recomputed_file_hash=recomputed.file_hash, tampered=tampered,
                alerts=[f"[ALERT] file_id={file_id} 무결성 불일치({reason}) - 전송 차단{quarantine_error}"],
            )

        destination = os.path.join(self.transmitted_dir, os.path.basename(file_path))
        if os.path.exists(destination):
            quarantine_error = ""
            try:
                self._quarantine(snapshot_path, file_id, file_path)
            except OSError as exc:
                quarantine_error = f"; 격리 실패={type(exc).__name__}: {exc}"
                if os.path.exists(snapshot_path):
                    os.remove(snapshot_path)
            return self._blocked(
                file_id=file_id, reason=ReasonCode.DESTINATION_CONFLICT, started=started,
                snapshot_seconds=snapshot_seconds, verify_seconds=verify_seconds,
                gate_seconds=gate_seconds, original_hash=original_record.hash_value,
                recomputed_hash=recomputed.root_hash, original_file_hash=original_record.file_hash,
                recomputed_file_hash=recomputed.file_hash,
                alerts=[f"[ALERT] 동일 이름의 전송 완료 파일이 이미 존재하여 덮어쓰기를 차단{quarantine_error}"],
            )

        promotion_started = time.perf_counter()
        try:
            os.replace(snapshot_path, destination)
        except OSError as exc:
            try:
                self._quarantine(snapshot_path, file_id, file_path)
            except OSError:
                if os.path.exists(snapshot_path):
                    os.remove(snapshot_path)
            return self._blocked(
                file_id=file_id, reason=ReasonCode.PROMOTION_FAILED, started=started,
                snapshot_seconds=snapshot_seconds, verify_seconds=verify_seconds,
                gate_seconds=gate_seconds, original_hash=original_record.hash_value,
                recomputed_hash=recomputed.root_hash, original_file_hash=original_record.file_hash,
                recomputed_file_hash=recomputed.file_hash,
                alerts=[f"[ALERT] 검증 파일 승격 실패로 전송 차단: {exc}"],
            )
        promotion_seconds = time.perf_counter() - promotion_started
        return TransferResult(
            file_id=file_id, status="TRANSMITTED", verified=True,
            original_hash=original_record.hash_value, recomputed_hash=recomputed.root_hash,
            original_file_hash=original_record.file_hash, recomputed_file_hash=recomputed.file_hash,
            verify_seconds=verify_seconds, io_seconds=snapshot_seconds + promotion_seconds,
            reason_code=ReasonCode.OK.value, snapshot_seconds=snapshot_seconds,
            phase3_gate_seconds=gate_seconds, promotion_seconds=promotion_seconds,
            total_seconds=time.perf_counter() - started,
        )

    def transmit_without_verification(self, file_path: str) -> float:
        """동일 파일을 한 번 복사하는 무결성 검증 없는 전송 베이스라인."""
        os.makedirs(self.transmitted_dir, exist_ok=True)
        started = time.perf_counter()
        destination = os.path.join(self.transmitted_dir, f"baseline_{os.path.basename(file_path)}")
        shutil.copyfile(file_path, destination)
        return time.perf_counter() - started
