"""가상 정산 트랜잭션 더미데이터 생성기.

정산 업무 필드를 단순화한
연구용 CSV 포맷을 사용한다. (거래ID, 거래일시, 가맹점번호, 카드번호,
승인번호, 상품코드, 거래구분, 정산금액, 수취계좌번호 등)
"""

from __future__ import annotations

import csv
import os

import numpy as np
import pandas as pd

COLUMNS = [
    "trans_id",        # 거래ID
    "trans_datetime",  # 거래일시 (YYYYMMDDHHMMSS)
    "merchant_id",      # 가맹점번호
    "card_no",           # 카드번호 (더미, 16자리)
    "approval_no",       # 승인번호
    "product_code",      # 상품코드
    "trans_type",        # 거래구분: 11=일반매출, 12=일반매출취소
    "installment",        # 할부개월 (00=일시불)
    "currency_code",       # 통화코드 (410=원화)
    "amount",               # 정산금액 (Amount)
    "settle_bank_code",      # 정산은행코드
    "settle_account_no",      # 수취계좌번호 (Acc_No)
]

_MERCHANT_POOL_SIZE = 50
_PRODUCT_POOL_SIZE = 200
_BANK_CODES = ["004", "011", "020", "088", "090", "003", "081"]


def generate_transactions(n: int = 100_000, seed: int | None = 42) -> pd.DataFrame:
    """n건의 가상 정산 트랜잭션을 생성한다."""
    rng = np.random.default_rng(seed)

    trans_id = np.array([f"TX{i:08d}" for i in range(1, n + 1)])

    # 하루(09:00~23:00) 범위 내에서 임의 초 단위 거래시각 생성
    base = pd.Timestamp("2026-05-01 09:00:00")
    offsets = rng.integers(0, 14 * 3600, size=n)
    trans_datetime = (base + pd.to_timedelta(offsets, unit="s")).strftime("%Y%m%d%H%M%S")

    # 가맹점 수를 제한해 동일 가맹점 반복 거래처럼 보이게 함
    merchant_pool = rng.integers(1_000_000_000, 1_099_999_999, size=_MERCHANT_POOL_SIZE, dtype=np.int64)
    merchant_id = merchant_pool[rng.integers(0, _MERCHANT_POOL_SIZE, size=n)].astype(str)

    card_no = np.array([
        "".join(str(d) for d in rng.integers(0, 10, size=16)) for _ in range(n)
    ])

    approval_no = rng.integers(10_000_000, 99_999_999, size=n).astype(str)

    product_pool = np.array([f"PRD-{i:04d}" for i in range(1, _PRODUCT_POOL_SIZE + 1)])
    product_code = product_pool[rng.integers(0, _PRODUCT_POOL_SIZE, size=n)]

    # 매출 90%, 취소 10%
    trans_type = np.where(rng.random(n) < 0.9, "11", "12")

    installment = np.where(rng.random(n) < 0.85, "00",
                            rng.choice(["03", "06", "12"], size=n))

    currency_code = np.full(n, "410")

    # 정산금액: 로그정규분포로 현실적인 결제금액 분포 모사 (1천 ~ 200만원대)
    amount = np.round(rng.lognormal(mean=10.0, sigma=1.0, size=n) / 100) * 100
    amount = np.clip(amount, 1_000, 3_000_000).astype(np.int64)
    # 취소 건은 원거래와의 대사를 위해 음수로 표기하지 않고 별도 trans_type으로만 구분

    settle_bank_code = np.array(_BANK_CODES)[rng.integers(0, len(_BANK_CODES), size=n)]
    settle_account_no = np.array([
        "".join(str(d) for d in rng.integers(0, 10, size=12)) for _ in range(n)
    ])

    df = pd.DataFrame({
        "trans_id": trans_id,
        "trans_datetime": trans_datetime,
        "merchant_id": merchant_id,
        "card_no": card_no,
        "approval_no": approval_no,
        "product_code": product_code,
        "trans_type": trans_type,
        "installment": installment,
        "currency_code": currency_code,
        "amount": amount,
        "settle_bank_code": settle_bank_code,
        "settle_account_no": settle_account_no,
    })
    return df[COLUMNS]


def write_settlement_file(df: pd.DataFrame, path: str) -> None:
    """정산 파일(CSV)을 생성하고 스트림을 명시적으로 닫는다.

    Phase 1의 '파일 스트림이 닫히는 즉시 해시를 계산' 이벤트를 재현하기
    위해, 이 함수가 반환된 시점에는 파일 디스크립터가 완전히 닫혀 있어야
    한다(os.fsync로 커널 버퍼까지 flush).
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        writer.writerows(df.itertuples(index=False, name=None))
        f.flush()
        os.fsync(f.fileno())
    # with 블록 종료 시점에 파일이 close() 됨 -> 이후 시점부터 해시 계산 가능
