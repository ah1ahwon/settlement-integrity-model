"""파일 전체 해시와 레코드 단위 해시 체이닝(Hash Chaining).

파일 전체를 한 번에 해싱하는 대신, 정산 파일의 각 DATA 레코드(거래 1건)를
순서대로 이전 체인값과 연결하여 다음과 같이 누적 해싱한다.

    chain_0 = SHA256(genesis_seed)
    chain_i = SHA256(chain_{i-1} || SHA256(record_i))   for i = 1..N

원본 파일의 모든 바이트에 대한 SHA-256도 같은 읽기 과정에서 계산한다.
파일 전체 해시는 바이트 단위 변경을 빠짐없이 탐지하고, 최종 chain_N과
레코드별 해시 원장은 업무 레코드의 구조적 변조와 위치를 특정한다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass
class ChainResult:
    file_hash: str
    root_hash: str
    header_hash: str
    record_hashes: list[str]
    trans_ids: list[str]


def genesis_seed(file_id: str) -> str:
    return f"SETTLEMENT-CHAIN-GENESIS:{file_id}"


def build_chain(file_path: str, file_id: str) -> ChainResult:
    """한 번의 파일 읽기로 전체 바이트 해시와 레코드 해시 체인을 구성한다.

    file_hash는 개행·빈 줄·인코딩을 포함한 파일의 모든 원본 바이트를
    SHA-256으로 계산한다. 레코드 체인은 CSV의 헤더와 비어 있지 않은 각
    레코드 내용을 연결해 구조적 변조를 탐지하고 위치를 특정하는 데 쓴다.
    """
    record_hashes: list[str] = []
    trans_ids: list[str] = []
    file_hasher = hashlib.sha256()
    chain = hashlib.sha256(genesis_seed(file_id).encode("utf-8")).hexdigest()

    with open(file_path, "rb") as f:
        raw_header = f.readline()
        file_hasher.update(raw_header)
        header = raw_header.rstrip(b"\r\n")
        header_hash = hashlib.sha256(header).hexdigest()
        chain = hashlib.sha256((chain + header_hash).encode("utf-8")).hexdigest()
        for raw_line in f:
            file_hasher.update(raw_line)
            line = raw_line.rstrip(b"\r\n")
            if not line:
                continue
            record_hash = hashlib.sha256(line).hexdigest()
            record_hashes.append(record_hash)
            trans_ids.append(line.split(b",", 1)[0].decode("utf-8"))
            chain = hashlib.sha256((chain + record_hash).encode("utf-8")).hexdigest()

    return ChainResult(
        file_hash=file_hasher.hexdigest(),
        root_hash=chain,
        header_hash=header_hash,
        record_hashes=record_hashes,
        trans_ids=trans_ids,
    )


def localize_tampering(original: ChainResult, recomputed: ChainResult) -> list[str]:
    """체인 루트 불일치 시, 변조된 trans_id를 특정한다.

    레코드 수가 같으면(값 변조) 위치별 해시를 그대로 비교한다. 레코드 수가
    다르면(삭제/삽입) 삭제·삽입 지점 이후 모든 레코드가 한 칸씩 밀리므로
    위치 비교는 무의미해진다 — 대신 해시 집합의 차이를 이용해 실제로
    없어졌거나 새로 생긴 레코드만 정확히 골라낸다.
    """
    tampered: list[str] = []
    if original.header_hash != recomputed.header_hash:
        tampered.append("HEADER_MISMATCH")

    if len(original.record_hashes) == len(recomputed.record_hashes):
        for i in range(len(original.record_hashes)):
            if original.record_hashes[i] != recomputed.record_hashes[i]:
                tampered.append(recomputed.trans_ids[i])
    else:
        recomputed_set = set(recomputed.record_hashes)
        original_set = set(original.record_hashes)
        deleted = [
            original.trans_ids[i]
            for i, h in enumerate(original.record_hashes)
            if h not in recomputed_set
        ]
        inserted = [
            recomputed.trans_ids[i]
            for i, h in enumerate(recomputed.record_hashes)
            if h not in original_set
        ]
        tampered.extend(deleted)
        tampered.extend(inserted)
        tampered.append(
            f"RECORD_COUNT_MISMATCH(original={len(original.record_hashes)},"
            f"recomputed={len(recomputed.record_hashes)})"
        )
    return tampered
