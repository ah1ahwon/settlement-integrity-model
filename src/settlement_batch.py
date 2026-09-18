"""Phase 1: 생성 및 격리 단계 (Generation & Isolation Phase).

정산 추출 배치 프로그램이 DB(모사: 더미데이터 생성기)에서 데이터를 읽어
로컬 서버에 정산 파일(.csv)을 생성한다. 파일 스트림이 닫히는 즉시 레코드
파일 전체 해시와 레코드 단위 해시 체인(hashchain.build_chain)을 계산하여,
두 무결성 값과 레코드 원장을 별도의 안전한 Hash Vault에 격리 보관한다.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from data_generator import generate_transactions, write_settlement_file
from hash_vault import HashVault
from hashchain import build_chain


@dataclass
class BatchResult:
    file_id: str
    file_path: str
    hash_value: str
    file_hash: str
    record_count: int
    generation_seconds: float  # 데이터 생성 + 파일 쓰기 소요 시간
    hashing_seconds: float     # 스트림 종료 직후 해시 체인 계산 소요 시간


class SettlementBatch:
    def __init__(self, vault: HashVault, staging_dir: str, algorithm: str = "sha256"):
        self.vault = vault
        self.staging_dir = staging_dir
        self.algorithm = algorithm

    def run(self, file_id: str, record_count: int, seed: int | None = None) -> BatchResult:
        os.makedirs(self.staging_dir, exist_ok=True)
        file_path = os.path.join(self.staging_dir, f"{file_id}.csv")

        t0 = time.perf_counter()
        df = generate_transactions(record_count, seed=seed)
        write_settlement_file(df, file_path)  # 이 호출이 반환되면 스트림은 이미 close() 된 상태
        t1 = time.perf_counter()

        # "파일 스트림이 닫히는 즉시 I/O 이벤트를 감지하여 해시 체인을 계산"
        chain = build_chain(file_path, file_id)
        t2 = time.perf_counter()

        self.vault.store(file_id, chain.root_hash, self.algorithm, record_count,
                          header_hash=chain.header_hash,
                          record_hashes=chain.record_hashes, trans_ids=chain.trans_ids,
                          file_hash=chain.file_hash)

        return BatchResult(
            file_id=file_id,
            file_path=file_path,
            hash_value=chain.root_hash,
            file_hash=chain.file_hash,
            record_count=record_count,
            generation_seconds=t1 - t0,
            hashing_seconds=t2 - t1,
        )
