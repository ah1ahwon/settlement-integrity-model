"""공통 설정값 모음."""

from __future__ import annotations

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data")
STAGING_DIR = os.path.join(DATA_DIR, "staging")        # Phase 1: 생성 직후 파일이 격리 대기하는 로컬 서버 영역
VAULT_DIR = os.path.join(DATA_DIR, "hash_vault")        # Phase 1: 접근통제된 별도의 안전한 해시 저장소
CHAIN_LEDGER_DIR = os.path.join(VAULT_DIR, "chains")     # 레코드별 해시 체인 원장 (변조 위치 특정용, 격리 보관)
TRANSMITTED_DIR = os.path.join(DATA_DIR, "transmitted")  # Phase 3: 검증 통과 후 외부 기관 전송함(모사)
QUARANTINE_DIR = os.path.join(DATA_DIR, "quarantine")    # Phase 3: 검증 실패 시 격리(Drop)함
RESULTS_DIR = os.path.join(BASE_DIR, "results")

VAULT_PATH = os.path.join(VAULT_DIR, "hash_vault.json")

HASH_ALGORITHM = "sha256"
DEFAULT_RECORD_COUNT = 100_000
DEFAULT_SEED = 42


def ensure_dirs() -> None:
    for d in (STAGING_DIR, VAULT_DIR, CHAIN_LEDGER_DIR, TRANSMITTED_DIR, QUARANTINE_DIR, RESULTS_DIR):
        os.makedirs(d, exist_ok=True)
