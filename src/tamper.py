"""Case B: 변조 공격 시나리오 (Tampering Attack Simulation).

Phase 1(파일 생성 및 해시 격리 보관)과 Phase 2(전송) 사이의 시간차
(Time Gap)를 악용해, 내부자 또는 악성코드가 정산 파일 내 일부 거래의
금액 또는 수취계좌번호를 변조하는 상황을 재현한다.

다수의 거래 중 극소수만 교묘히 수정하는 '살라미 기법(Salami Slicing)'을
모사하기 위해 기본적으로 변조 건수를 소수(1~5건)로 제한한다. 금액/계좌
수정 외에도 헤더 변조, 레코드 삭제, 레코드 삽입처럼 파일 구조를 바꾸는
공격을 함께 재현할 수 있다.
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


def tamper_file(file_path: str, tamper_count: int = 1, mode: str = "amount",
                 seed: int | None = None) -> TamperReport:
    """정산 파일 내 일부 거래를 변조하고 같은 경로에 덮어쓴다 (파일 재작성을 통한 변조 모사)."""
    if mode not in ("amount", "account", "both", "header", "delete", "insert"):
        raise ValueError("mode는 'amount', 'account', 'both', 'header', 'delete', 'insert' 중 하나여야 합니다.")

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

    if mode == "insert":
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

    target_idx = rng.sample(range(len(df)), tamper_count)
    tampered_ids: list[str] = []

    for idx in target_idx:
        if mode in ("amount", "both"):
            original = int(df.at[idx, "amount"])
            # 금액 부풀리기: 원 금액의 1.5~5배 사이로 변조
            df.at[idx, "amount"] = str(int(original * rng.uniform(1.5, 5.0)))
        if mode in ("account", "both"):
            # 수취계좌번호 임의 변경 (동일 자리수의 다른 난수로 교체)
            digits = len(df.at[idx, "settle_account_no"])
            df.at[idx, "settle_account_no"] = "".join(str(rng.randint(0, 9)) for _ in range(digits))
        tampered_ids.append(df.at[idx, "trans_id"])

    df[COLUMNS].to_csv(file_path, index=False)
    return TamperReport(file_path=file_path, mode=mode, tampered_rows=tampered_ids)
