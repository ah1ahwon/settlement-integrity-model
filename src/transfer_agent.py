"""Phase 2 & 3: 대기·전송 단계 + 교차 검증 및 통제 단계.

Phase 2: 정해진 스케줄링에 따라 파일 전송 에이전트(FTP/SFTP Client, 모사)가
기동되어 외부 기관으로 파일 전송을 시도한다.

Phase 3: 보호된 임시 스냅샷의 파일 전체 해시와 레코드 단위 해시 체인을
재계산하고, Hash Vault에 보관된 두 원본값과 논리적 대사(Matching)를
수행한다. 두 값이 모두 일치할 경우에만 전송을 허용하며, 단 1비트라도
불일치하면 프로세스를 즉각 차단(Drop)하고 관리자에게 알람을 전송한다.

체인 루트가 불일치하는 경우에만(=이상 상황에서만) Hash Vault의 체인
원장을 추가로 불러와, 레코드별 해시를 위치 대조하여 어느 거래(trans_id)가
변조되었는지 특정한다. 정상 경로(대다수)는 원장을 읽지 않으므로 평소
검증 성능에는 영향이 없다.
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
import time
from dataclasses import dataclass, field

from hash_vault import HashVault, VaultIntegrityError
from hashchain import ChainResult, build_chain, localize_tampering


@dataclass
class TransferResult:
    file_id: str
    status: str          # 'TRANSMITTED' | 'BLOCKED'
    verified: bool
    original_hash: str
    recomputed_hash: str
    original_file_hash: str
    recomputed_file_hash: str
    verify_seconds: float   # Phase 3: 체인 재계산 + 대사 소요 시간
    io_seconds: float        # Phase 2/3: 파일 복사 또는 격리 이동 소요 시간
    tampered_trans_ids: list[str] = field(default_factory=list)  # 변조 위치 특정 결과
    alerts: list[str] = field(default_factory=list)


class TransferAgent:
    def __init__(self, vault: HashVault, transmitted_dir: str, quarantine_dir: str,
                 algorithm: str = "sha256"):
        self.vault = vault
        self.transmitted_dir = transmitted_dir
        self.quarantine_dir = quarantine_dir
        self.algorithm = algorithm

    def _create_verification_snapshot(self, file_path: str) -> tuple[str, float]:
        """전송 대상 파일을 보호된 임시 영역에 복제하고 그 경로를 반환한다.

        이후 검증과 전송 승격은 모두 이 스냅샷을 대상으로 수행한다. 따라서
        원본 staging 파일이 스냅샷 생성 이후 변경되더라도, 검증한 바이트와
        실제 전송 대상으로 승격되는 바이트는 동일하다.
        """
        spool_dir = os.path.join(self.transmitted_dir, ".verification_spool")
        os.makedirs(spool_dir, exist_ok=True)
        os.chmod(spool_dir, stat.S_IRWXU)  # 0700: 에이전트 소유자만 접근

        started = time.perf_counter()
        fd, snapshot_path = tempfile.mkstemp(prefix="pending_", suffix=".csv", dir=spool_dir)
        try:
            with os.fdopen(fd, "wb") as snapshot, open(file_path, "rb") as source:
                shutil.copyfileobj(source, snapshot, length=1024 * 1024)
                snapshot.flush()
                os.fsync(snapshot.fileno())
            os.chmod(snapshot_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            if os.path.exists(snapshot_path):
                os.remove(snapshot_path)
            raise
        return snapshot_path, time.perf_counter() - started

    def transmit(self, file_id: str, file_path: str) -> TransferResult:
        os.makedirs(self.transmitted_dir, exist_ok=True)
        os.makedirs(self.quarantine_dir, exist_ok=True)

        # 원본 경로를 검증한 뒤 다시 여는 TOCTOU를 막기 위해 먼저 보호된
        # 스냅샷을 만든다. 이후 검증과 최종 승격은 동일한 스냅샷을 사용한다.
        snapshot_path, snapshot_seconds = self._create_verification_snapshot(file_path)
        try:
            # Phase 3: 보호된 스냅샷의 해시 체인을 재계산
            t0 = time.perf_counter()
            recomputed = build_chain(snapshot_path, file_id)
            original_record = self.vault.retrieve(file_id)
        except VaultIntegrityError as e:
            t1 = time.perf_counter()
            if os.path.exists(snapshot_path):
                os.remove(snapshot_path)
            return TransferResult(
                file_id=file_id, status="BLOCKED", verified=False,
                original_hash="", recomputed_hash=recomputed.root_hash,
                original_file_hash="", recomputed_file_hash=recomputed.file_hash,
                verify_seconds=t1 - t0, io_seconds=snapshot_seconds,
                alerts=[f"Vault 조회 실패: {e}"],
            )
        except Exception:
            if os.path.exists(snapshot_path):
                os.remove(snapshot_path)
            raise
        try:
            chain_matched = recomputed.root_hash == original_record.hash_value
            file_matched = bool(original_record.file_hash) and recomputed.file_hash == original_record.file_hash
            matched = chain_matched and file_matched
            t1 = time.perf_counter()

            alerts: list[str] = []
            tampered_trans_ids: list[str] = []
            t2 = time.perf_counter()
            if matched:
                dest = os.path.join(self.transmitted_dir, os.path.basename(file_path))
                os.replace(snapshot_path, dest)
                status = "TRANSMITTED"
            else:
                # 이상 상황에서만 체인 원장을 불러와 변조된 거래를 특정한다 (포렌식 경로).
                if chain_matched and not file_matched:
                    tampered_trans_ids = ["FILE_BYTES_MISMATCH"]
                else:
                    try:
                        ledger = self.vault.retrieve_chain(file_id)
                        original_chain = ChainResult(
                            file_hash=original_record.file_hash,
                            root_hash=original_record.hash_value,
                            header_hash=ledger.header_hash,
                            record_hashes=ledger.record_hashes,
                            trans_ids=ledger.trans_ids,
                        )
                        tampered_trans_ids = localize_tampering(original_chain, recomputed)
                    except VaultIntegrityError:
                        pass

                # 실제로 검증한 스냅샷을 격리 증적으로 보존한다.
                dest = os.path.join(self.quarantine_dir, os.path.basename(file_path))
                os.replace(snapshot_path, dest)
                if os.path.exists(file_path):
                    os.remove(file_path)
                status = "BLOCKED"
                alerts.append(
                    f"[ALERT] file_id={file_id} 무결성 값 불일치 탐지 - 전송 차단됨 "
                    f"(파일해시일치={file_matched}, 체인일치={chain_matched}, "
                    f"원본체인={original_record.hash_value[:12]}..., 재계산체인={recomputed.root_hash[:12]}..., "
                    f"변조의심거래={tampered_trans_ids})"
                )
            t3 = time.perf_counter()

            return TransferResult(
                file_id=file_id,
                status=status,
                verified=matched,
                original_hash=original_record.hash_value,
                recomputed_hash=recomputed.root_hash,
                original_file_hash=original_record.file_hash,
                recomputed_file_hash=recomputed.file_hash,
                verify_seconds=t1 - t0,
                io_seconds=snapshot_seconds + (t3 - t2),
                tampered_trans_ids=tampered_trans_ids,
                alerts=alerts,
            )
        finally:
            # 조회 실패나 예외 발생 시 미완료 스냅샷을 남기지 않는다.
            if os.path.exists(snapshot_path):
                os.remove(snapshot_path)

    def transmit_without_verification(self, file_path: str) -> float:
        """기존 방식(무결성 검증 없는 단순 전송) 대비 지연시간 비교용 베이스라인."""
        os.makedirs(self.transmitted_dir, exist_ok=True)
        t0 = time.perf_counter()
        dest = os.path.join(self.transmitted_dir, os.path.basename(file_path))
        shutil.copy2(file_path, dest)
        return time.perf_counter() - t0
