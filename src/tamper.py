"""Case B: 변조 공격 시나리오 (Tampering Attack Simulation).

Phase 1(파일 생성 및 해시 격리 보관)과 Phase 2(전송) 사이의 시간차
(Time Gap)를 악용해, 내부자 또는 악성코드가 정산 파일 내 일부 거래의
금액 또는 수취계좌번호를 변조하는 상황을 재현한다.

다수의 거래 중 극소수만 교묘히 수정하는 '살라미 기법(Salami Slicing)'을
모사하기 위해 기본적으로 변조 건수를 소수(1~5건)로 제한한다. 금액/계좌
수정 외에도 헤더 변조, 레코드 삭제, 레코드 삽입처럼 파일 구조를 바꾸는
공격을 함께 재현할 수 있다. bitflip 모드는 필드 단위 의미 변경이 아니라
파일의 원본 바이트 중 정확히 1비트만 뒤집어, "단 1비트 변조도 탐지한다"는
주장을 문자 그대로 검증하기 위한 모드다.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import pandas as pd

from data_generator import COLUMNS


@dataclass
class TamperReport:
    file_path: str
    mode: str
    tampered_rows: list[str]  # 변조된 trans_id 목록


def _bitflip_file(file_path: str, seed: int | None) -> TamperReport:
    """파일 원본 바이트 중 정확히 1비트만 뒤집는다 (필드 단위가 아닌 순수 비트 단위 변조).

    콤마(,)와 개행문자는 CSV 구조 자체를 깨뜨려 대상 거래를 특정하기
    어려워지므로 대상에서 제외하고, 필드 값 내부의 바이트만 뒤집는다.
    """
    rng = random.Random(seed)
    with open(file_path, "rb") as f:
        data = bytearray(f.read())

    header_end = data.index(b"\n") + 1
    excluded = (ord(","), ord("\n"), ord("\r"))
    while True:
        byte_pos = rng.randrange(header_end, len(data))
        if data[byte_pos] not in excluded:
            break
    bit_pos = rng.randrange(8)
    data[byte_pos] ^= (1 << bit_pos)

    line_start = data.rfind(b"\n", 0, byte_pos) + 1
    line_end = data.find(b"\n", byte_pos)
    if line_end == -1:
        line_end = len(data)
    trans_id = bytes(data[line_start:line_end]).split(b",", 1)[0].decode("utf-8", errors="replace")

    with open(file_path, "wb") as f:
        f.write(data)
    return TamperReport(file_path=file_path, mode="bitflip", tampered_rows=[trans_id])


def _surgical_field_tamper(file_path: str, tamper_count: int, mode: str, seed: int | None) -> TamperReport:
    """금액/계좌번호를 필드 단위로 변조하되, 대상이 아닌 레코드는 원본 바이트를
    그대로 보존한다.

    pandas로 파일 전체를 다시 직렬화(read_csv -> to_csv)하면 개행 문자 등
    직렬화 방식이 미세하게 달라져(예: \\r\\n -> \\n) 변조 대상이 아닌 레코드의
    바이트까지 전부 바뀌어버린다. 이렇게 되면 "계좌번호처럼 자릿수가 그대로인
    변조는 파일 크기를 바꾸지 않는다"는 살라미 공격의 전제가 구현상 오염되어,
    파일 크기 비교 같은 기존 방식과의 비교 실험이 왜곡된다. 따라서 변조 대상
    레코드의 해당 라인만 바이트 단위로 치환하고 나머지는 원본 그대로 둔다.
    """
    rng = random.Random(seed)
    with open(file_path, "rb") as f:
        raw_lines = f.readlines()

    header, body = raw_lines[0], raw_lines[1:]
    if tamper_count > len(body):
        raise ValueError("tamper_count가 전체 거래 건수를 초과합니다.")

    col_index = {name: i for i, name in enumerate(COLUMNS)}
    target_idx = rng.sample(range(len(body)), tamper_count)
    tampered_ids: list[str] = []

    for idx in target_idx:
        line = body[idx]
        ending = b""
        content = line
        if content.endswith(b"\r\n"):
            ending, content = b"\r\n", content[:-2]
        elif content.endswith(b"\n"):
            ending, content = b"\n", content[:-1]
        fields = content.split(b",")

        if mode in ("amount", "both"):
            i = col_index["amount"]
            original = int(fields[i])
            # 금액 부풀리기: 원 금액의 1.5~5배 사이로 변조
            fields[i] = str(int(original * rng.uniform(1.5, 5.0))).encode()
        if mode in ("account", "both"):
            # 수취계좌번호 임의 변경 (동일 자리수의 다른 난수로 교체 -> 파일 크기 불변)
            i = col_index["settle_account_no"]
            digits = len(fields[i])
            fields[i] = "".join(str(rng.randint(0, 9)) for _ in range(digits)).encode()

        body[idx] = b",".join(fields) + ending
        tampered_ids.append(fields[col_index["trans_id"]].decode("utf-8"))

    with open(file_path, "wb") as f:
        f.write(header)
        f.writelines(body)

    return TamperReport(file_path=file_path, mode=mode, tampered_rows=tampered_ids)


def tamper_file(file_path: str, tamper_count: int = 1, mode: str = "amount",
                 seed: int | None = None) -> TamperReport:
    """정산 파일 내 일부 거래를 변조하고 같은 경로에 덮어쓴다 (파일 재작성을 통한 변조 모사)."""
    if mode not in ("amount", "account", "both", "header", "delete", "insert", "bitflip"):
        raise ValueError(
            "mode는 'amount', 'account', 'both', 'header', 'delete', 'insert', 'bitflip' 중 하나여야 합니다."
        )

    if mode == "bitflip":
        return _bitflip_file(file_path, seed)

    if mode in ("amount", "account", "both"):
        return _surgical_field_tamper(file_path, tamper_count, mode, seed)

    rng = random.Random(seed)
    df = pd.read_csv(file_path, dtype=str)
    if tamper_count > len(df):
        raise ValueError("tamper_count가 전체 거래 건수를 초과합니다.")

    if mode == "header":
        df = df.rename(columns={"amount": "amount_modified"})
        df.to_csv(file_path, index=False)
        return TamperReport(file_path=file_path, mode=mode, tampered_rows=["HEADER_MISMATCH"])

    if mode == "delete":
        target_idx = rng.sample(range(len(df)), tamper_count)
        tampered_ids = df.iloc[target_idx]["trans_id"].tolist()
        df = df.drop(index=target_idx)
        df[COLUMNS].to_csv(file_path, index=False)
        return TamperReport(file_path=file_path, mode=mode, tampered_rows=tampered_ids)

    # mode == "insert"
    rows = []
    for i in range(tamper_count):
        row = df.iloc[rng.randrange(len(df))].copy()
        row["trans_id"] = f"TX_FAKE_{seed or 0}_{i:04d}"
        row["amount"] = str(int(row["amount"]) + rng.randint(1000, 50000))
        rows.append(row)
    insert_df = pd.DataFrame(rows, columns=COLUMNS)
    df = pd.concat([df, insert_df], ignore_index=True)
    df[COLUMNS].to_csv(file_path, index=False)
    return TamperReport(file_path=file_path, mode=mode, tampered_rows=insert_df["trans_id"].tolist())
