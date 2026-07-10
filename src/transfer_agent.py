"""Phase 2 & 3: 대기·전송 단계 + 교차 검증 및 통제 단계.

Phase 2: 정해진 스케줄링에 따라 파일 전송 에이전트(FTP/SFTP Client, 모사)가
기동되어 외부 기관으로 파일 전송을 시도한다.

Phase 3: 파일을 읽어 들이는 시점에 자체적으로 레코드 단위 해시 체인을
재계산하고, Hash Vault에 보관된 원본 체인 루트 해시와 논리적 대사
(Matching)를 수행한다. 값이 일치할 경우에만 전송을 허용하며, 단 1비트라도
불일치 시 프로세스를 즉각 차단(Drop)하고 관리자에게 알람을 전송한다.

체인 루트가 불일치하는 경우에만(=이상 상황에서만) Hash Vault의 체인
원장을 추가로 불러와, 레코드별 해시를 위치 대조하여 어느 거래(trans_id)가
변조되었는지 특정한다. 정상 경로(대다수)는 원장을 읽지 않으므로 평소
검증 성능에는 영향이 없다.
"""

from __future__ import annotations

import os
import shutil
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

    def transmit(self, file_id: str, file_path: str) -> TransferResult:
        os.makedirs(self.transmitted_dir, exist_ok=True)
        os.makedirs(self.quarantine_dir, exist_ok=True)

        # Phase 3: 전송 에이전트가 파일을 읽어들이는 시점에 해시 체인 재계산
        t0 = time.perf_counter()
        recomputed = build_chain(file_path, file_id)
        try:
            original_record = self.vault.retrieve(file_id)
        except VaultIntegrityError as e:
            t1 = time.perf_counter()
            return TransferResult(
                file_id=file_id, status="BLOCKED", verified=False,
                original_hash="", recomputed_hash=recomputed.root_hash,
                verify_seconds=t1 - t0, io_seconds=0.0,
                alerts=[f"Vault 조회 실패: {e}"],
            )
        matched = recomputed.root_hash == original_record.hash_value
        t1 = time.perf_counter()

        alerts: list[str] = []
        tampered_trans_ids: list[str] = []
        t2 = time.perf_counter()
        if matched:
            dest = os.path.join(self.transmitted_dir, os.path.basename(file_path))
            shutil.copy2(file_path, dest)
            status = "TRANSMITTED"
        else:
            # 이상 상황에서만 체인 원장을 불러와 변조된 거래를 특정한다 (포렌식 경로).
            try:
                ledger = self.vault.retrieve_chain(file_id)
                original_chain = ChainResult(
                    root_hash=original_record.hash_value,
                    header_hash=ledger.header_hash,
                    record_hashes=ledger.record_hashes,
                    trans_ids=ledger.trans_ids,
                )
                tampered_trans_ids = localize_tampering(original_chain, recomputed)
            except VaultIntegrityError:
                pass

            dest = os.path.join(self.quarantine_dir, os.path.basename(file_path))
            shutil.move(file_path, dest)
            status = "BLOCKED"
            alerts.append(
                f"[ALERT] file_id={file_id} 해시 체인 불일치 탐지 - 전송 차단됨 "
                f"(원본={original_record.hash_value[:12]}..., 재계산={recomputed.root_hash[:12]}..., "
                f"변조의심거래={tampered_trans_ids})"
            )
        t3 = time.perf_counter()

        return TransferResult(
            file_id=file_id,
            status=status,
            verified=matched,
            original_hash=original_record.hash_value,
            recomputed_hash=recomputed.root_hash,
            verify_seconds=t1 - t0,
            io_seconds=t3 - t2,
            tampered_trans_ids=tampered_trans_ids,
            alerts=alerts,
        )

    def transmit_without_verification(self, file_path: str) -> float:
        """기존 방식(무결성 검증 없는 단순 전송) 대비 지연시간 비교용 베이스라인."""
        os.makedirs(self.transmitted_dir, exist_ok=True)
        t0 = time.perf_counter()
        dest = os.path.join(self.transmitted_dir, os.path.basename(file_path))
        shutil.copy2(file_path, dest)
        return time.perf_counter() - t0
