"""Hash Vault: 접근이 엄격히 통제되는 별도의 안전한 해시 저장소(시뮬레이션).

연구계획서 Phase 1의 "이 값은 기존 서버가 아닌, 접근이 엄격히 통제되는
별도의 안전한 Hash Vault에 전송되어 격리 보관됩니다" 를 재현한다.

실제 운영 환경이라면 별도 네트워크 세그먼트의 HSM/KMS나 write-once
스토리지가 되겠지만, 본 시뮬레이션에서는 다음 두 가지로 '격리 및 통제'
성격을 모사한다.
  1. 파일시스템 권한을 0600으로 제한 (소유자만 접근 가능)
  2. 동일 file_id에 대한 재기록(덮어쓰기)을 금지하는 write-once 저장소

저장 구조는 두 층으로 나뉜다.
  - vault.json      : file_id -> 체인 루트 해시(+메타데이터). 매 전송마다
                       빠르게 대사(matching)하는 상시 경로에서 사용된다.
  - chains/<id>.json: file_id -> 레코드별 해시 배열 + trans_id 목록(체인
                       원장). 루트 해시가 불일치한 '이상 상황'에서만 불러와
                       변조된 거래를 특정(localize)하는 데 사용한다.
"""

from __future__ import annotations

import json
import os
import stat
import time
from dataclasses import dataclass, field


class VaultIntegrityError(Exception):
    """Vault에 이미 등록된 해시를 다시 등록하려 하거나, 존재하지 않는 항목을 조회할 때 발생."""


@dataclass
class VaultRecord:
    file_id: str
    hash_value: str
    algorithm: str
    record_count: int
    stored_at: float = field(default_factory=time.time)


@dataclass
class ChainLedger:
    file_id: str
    record_hashes: list[str]
    trans_ids: list[str]


class HashVault:
    def __init__(self, vault_path: str, chain_dir: str | None = None):
        self.vault_path = vault_path
        self.chain_dir = chain_dir or os.path.join(os.path.dirname(vault_path), "chains")
        os.makedirs(os.path.dirname(vault_path), exist_ok=True)
        os.makedirs(self.chain_dir, exist_ok=True)
        if not os.path.exists(vault_path):
            self._write_all({})
        os.chmod(vault_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600: 소유자만 읽기/쓰기

    def _read_all(self) -> dict:
        with open(self.vault_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_all(self, data: dict) -> None:
        with open(self.vault_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.chmod(self.vault_path, stat.S_IRUSR | stat.S_IWUSR)

    def _chain_path(self, file_id: str) -> str:
        return os.path.join(self.chain_dir, f"{file_id}.json")

    def store(self, file_id: str, hash_value: str, algorithm: str, record_count: int,
              record_hashes: list[str] | None = None, trans_ids: list[str] | None = None) -> VaultRecord:
        """체인 루트 해시를 격리 보관한다. 동일 file_id 재등록은 변조 시도로 간주하여 거부한다."""
        data = self._read_all()
        if file_id in data:
            raise VaultIntegrityError(f"'{file_id}'는 이미 Vault에 등록되어 있습니다 (write-once 정책 위반).")
        record = VaultRecord(file_id=file_id, hash_value=hash_value, algorithm=algorithm, record_count=record_count)
        data[file_id] = {
            "hash_value": record.hash_value,
            "algorithm": record.algorithm,
            "record_count": record.record_count,
            "stored_at": record.stored_at,
        }
        self._write_all(data)

        if record_hashes is not None:
            chain_path = self._chain_path(file_id)
            if os.path.exists(chain_path):
                raise VaultIntegrityError(f"'{file_id}'의 체인 원장이 이미 존재합니다 (write-once 정책 위반).")
            with open(chain_path, "w", encoding="utf-8") as f:
                json.dump({"record_hashes": record_hashes, "trans_ids": trans_ids or []}, f)
            os.chmod(chain_path, stat.S_IRUSR | stat.S_IWUSR)

        return record

    def retrieve(self, file_id: str) -> VaultRecord:
        data = self._read_all()
        if file_id not in data:
            raise VaultIntegrityError(f"'{file_id}'에 해당하는 원본 해시가 Vault에 없습니다.")
        entry = data[file_id]
        return VaultRecord(file_id=file_id, **entry)

    def retrieve_chain(self, file_id: str) -> ChainLedger:
        """변조 탐지 시에만 호출되는 포렌식 경로: 원본 레코드별 해시 원장을 불러온다."""
        chain_path = self._chain_path(file_id)
        if not os.path.exists(chain_path):
            raise VaultIntegrityError(f"'{file_id}'에 해당하는 체인 원장이 Vault에 없습니다.")
        with open(chain_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return ChainLedger(file_id=file_id, record_hashes=payload["record_hashes"], trans_ids=payload["trans_ids"])
