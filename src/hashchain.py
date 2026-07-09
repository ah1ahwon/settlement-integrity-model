"""레코드 단위 해시 체이닝(Hash Chaining).

파일 전체를 한 번에 해싱하는 대신, 정산 파일의 각 DATA 레코드(거래 1건)를
순서대로 이전 체인값과 연결하여 다음과 같이 누적 해싱한다.

    chain_0 = SHA256(genesis_seed)
    chain_i = SHA256(chain_{i-1} || SHA256(record_i))   for i = 1..N

최종 chain_N을 '체인 루트 해시'로 삼아 Hash Vault에 저장한다. 체인 루트가
원본과 다르면 파일이 변조된 것이며, 레코드별 해시(SHA256(record_i))를
원본과 위치별로 대조하면 변조된 정확한 거래(trans_id)를 특정(Localize)할
수 있다 — 파일 전체 해시 방식으로는 "변조 여부"만 알 수 있었던 것에서
한 걸음 더 나아간 포렌식 기능이다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass
class ChainResult:
    root_hash: str
    record_hashes: list[str]
    trans_ids: list[str]


def genesis_seed(file_id: str) -> str:
    return f"SETTLEMENT-CHAIN-GENESIS:{file_id}"


def build_chain(file_path: str, file_id: str) -> ChainResult:
    """정산 CSV 파일을 레코드(행) 단위로 읽어 해시 체인을 구성한다.

    바이트 단위 원본 라인을 그대로 해싱하므로 필드 값의 공백 하나, 자릿수
    하나가 바뀌어도 해당 레코드 해시와 이후 체인 전체가 달라진다.
    """
    record_hashes: list[str] = []
    trans_ids: list[str] = []
    chain = hashlib.sha256(genesis_seed(file_id).encode("utf-8")).hexdigest()

    with open(file_path, "rb") as f:
        f.readline()  # 헤더 라인은 레코드가 아니므로 체인에서 제외
        for raw_line in f:
            line = raw_line.rstrip(b"\r\n")
            if not line:
                continue
            record_hash = hashlib.sha256(line).hexdigest()
            record_hashes.append(record_hash)
            trans_ids.append(line.split(b",", 1)[0].decode("utf-8"))
            chain = hashlib.sha256((chain + record_hash).encode("utf-8")).hexdigest()

    return ChainResult(root_hash=chain, record_hashes=record_hashes, trans_ids=trans_ids)


def localize_tampering(original: ChainResult, recomputed: ChainResult) -> list[str]:
    """체인 루트 불일치 시, 위치별 레코드 해시를 대조해 변조된 trans_id를 특정한다."""
    tampered: list[str] = []
    n = min(len(original.record_hashes), len(recomputed.record_hashes))
    for i in range(n):
        if original.record_hashes[i] != recomputed.record_hashes[i]:
            tampered.append(recomputed.trans_ids[i])

    if len(original.record_hashes) != len(recomputed.record_hashes):
        tampered.append(
            f"RECORD_COUNT_MISMATCH(original={len(original.record_hashes)},"
            f"recomputed={len(recomputed.record_hashes)})"
        )
    return tampered
