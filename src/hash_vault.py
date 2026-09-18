"""원자적 write-once Hash Vault 시뮬레이션.

신규 엔트리는 메타데이터와 레코드 체인 원장을 하나의 JSON 번들로 구성한 뒤,
동일 디렉터리의 임시 파일에 fsync하고 원자적 hard-link로 공개한다. 따라서
기록 도중 중단되어도 부분 기록을 관찰하지 않으며 동시 등록도 덮어쓸 수 없다.

이전 버전의 ``hash_vault.json`` 및 ``chains/<id>.json``은 읽기 호환성을
유지하지만, 신규 저장은 ``entries/<id>.json``만 사용한다.
"""

from __future__ import annotations

import json
import os
import re
import stat
import tempfile
import time
from dataclasses import asdict, dataclass, field


class VaultIntegrityError(Exception):
    """Vault의 write-once·형식·조회 무결성 규칙을 위반했을 때 발생한다."""


@dataclass
class VaultRecord:
    file_id: str
    hash_value: str
    algorithm: str
    record_count: int
    file_hash: str = ""
    stored_at: float = field(default_factory=time.time)


@dataclass
class ChainLedger:
    file_id: str
    header_hash: str
    record_hashes: list[str]
    trans_ids: list[str]


_SAFE_FILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class HashVault:
    def __init__(self, vault_path: str, chain_dir: str | None = None):
        self.vault_path = vault_path
        self.vault_dir = os.path.dirname(vault_path)
        self.chain_dir = chain_dir or os.path.join(self.vault_dir, "chains")
        self.entry_dir = os.path.join(self.vault_dir, "entries")
        os.makedirs(self.vault_dir, exist_ok=True)
        os.makedirs(self.chain_dir, exist_ok=True)
        os.makedirs(self.entry_dir, exist_ok=True)
        if not os.path.exists(vault_path):
            self._atomic_write_json(vault_path, {})
        os.chmod(vault_path, stat.S_IRUSR | stat.S_IWUSR)

    @staticmethod
    def _validate_file_id(file_id: str) -> None:
        if not isinstance(file_id, str) or not _SAFE_FILE_ID.fullmatch(file_id):
            raise VaultIntegrityError(
                "file_id는 영문·숫자로 시작하고 영문·숫자·점·밑줄·하이픈만 포함해야 합니다."
            )

    @staticmethod
    def _fsync_directory(directory: str) -> None:
        try:
            fd = os.open(directory, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _atomic_write_json(self, path: str, payload: dict, *, exclusive: bool = False) -> None:
        """완전 기록된 JSON만 원자적으로 공개한다."""
        directory = os.path.dirname(path)
        os.makedirs(directory, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix=".vault-tmp-", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
            if exclusive:
                os.link(temp_path, path)
                os.unlink(temp_path)
            else:
                os.replace(temp_path, path)
            self._fsync_directory(directory)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def _read_json(self, path: str) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as stream:
                payload = json.load(stream)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise VaultIntegrityError(f"Vault 엔트리를 안전하게 읽을 수 없습니다: {exc}") from exc
        if not isinstance(payload, dict):
            raise VaultIntegrityError("Vault 엔트리 형식이 객체가 아닙니다.")
        return payload

    def _read_legacy_index(self) -> dict:
        return self._read_json(self.vault_path)

    def _entry_path(self, file_id: str) -> str:
        self._validate_file_id(file_id)
        return os.path.join(self.entry_dir, f"{file_id}.json")

    def _chain_path(self, file_id: str) -> str:
        self._validate_file_id(file_id)
        return os.path.join(self.chain_dir, f"{file_id}.json")

    def store(self, file_id: str, hash_value: str, algorithm: str, record_count: int,
              header_hash: str | None = None, record_hashes: list[str] | None = None,
              trans_ids: list[str] | None = None, file_hash: str = "") -> VaultRecord:
        """메타데이터와 체인 원장을 하나의 원자적 write-once 번들로 저장한다."""
        entry_path = self._entry_path(file_id)
        legacy = self._read_legacy_index()
        if file_id in legacy or os.path.exists(entry_path):
            raise VaultIntegrityError(f"'{file_id}'는 이미 Vault에 등록되어 있습니다 (write-once 정책 위반).")

        record = VaultRecord(file_id=file_id, hash_value=hash_value, algorithm=algorithm,
                             record_count=record_count, file_hash=file_hash)
        ledger = None
        if record_hashes is not None:
            ledger = {"header_hash": header_hash or "", "record_hashes": list(record_hashes),
                      "trans_ids": list(trans_ids or [])}
        payload = {"schema_version": 2, "record": asdict(record), "chain": ledger}
        try:
            self._atomic_write_json(entry_path, payload, exclusive=True)
        except FileExistsError as exc:
            raise VaultIntegrityError(
                f"'{file_id}'는 동시에 다른 작업이 먼저 등록했습니다 (write-once 정책 위반)."
            ) from exc
        return record

    @staticmethod
    def _record_from_payload(file_id: str, payload: dict) -> VaultRecord:
        try:
            record = VaultRecord(**payload["record"])
        except (KeyError, TypeError, ValueError) as exc:
            raise VaultIntegrityError(f"'{file_id}'의 Vault 메타데이터 형식이 손상되었습니다.") from exc
        if record.file_id != file_id or record.record_count < 0:
            raise VaultIntegrityError(f"'{file_id}'의 Vault 메타데이터 값이 유효하지 않습니다.")
        return record

    def retrieve(self, file_id: str) -> VaultRecord:
        entry_path = self._entry_path(file_id)
        if os.path.exists(entry_path):
            return self._record_from_payload(file_id, self._read_json(entry_path))
        data = self._read_legacy_index()
        if file_id not in data:
            raise VaultIntegrityError(f"'{file_id}'에 해당하는 원본 해시가 Vault에 없습니다.")
        try:
            return VaultRecord(file_id=file_id, **data[file_id])
        except (TypeError, ValueError) as exc:
            raise VaultIntegrityError(f"'{file_id}'의 기존 Vault 메타데이터 형식이 손상되었습니다.") from exc

    def retrieve_chain(self, file_id: str) -> ChainLedger:
        """변조 탐지 시에만 원본 레코드별 해시 원장을 불러온다."""
        entry_path = self._entry_path(file_id)
        if os.path.exists(entry_path):
            chain = self._read_json(entry_path).get("chain")
            if not isinstance(chain, dict):
                raise VaultIntegrityError(f"'{file_id}'에 해당하는 체인 원장이 Vault에 없습니다.")
        else:
            chain_path = self._chain_path(file_id)
            if not os.path.exists(chain_path):
                raise VaultIntegrityError(f"'{file_id}'에 해당하는 체인 원장이 Vault에 없습니다.")
            chain = self._read_json(chain_path)
        try:
            return ChainLedger(file_id=file_id, header_hash=chain.get("header_hash", ""),
                               record_hashes=list(chain["record_hashes"]),
                               trans_ids=list(chain["trans_ids"]))
        except (KeyError, TypeError) as exc:
            raise VaultIntegrityError(f"'{file_id}'의 체인 원장 형식이 손상되었습니다.") from exc
