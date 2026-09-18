# 정산 파일 무결성 검증 모델 (Settlement File Integrity Verification Model)

석사 논문 연구계획서 "대용량 트랜잭션 처리 시스템의 정산 데이터 무결성 보장 및
부정 방지 모델 연구"의 3단계 이중 해시 체이닝 검증 모델을 Python으로 구현한
시뮬레이션 코드와 더미데이터 생성기입니다.

## 3단계 검증 메커니즘과 코드 매핑

| 논문상 단계 | 설명 | 구현 모듈 |
|---|---|---|
| Phase 1: 생성 및 격리 | 정산 파일 생성 → 파일 전체 SHA-256과 레코드 체인 계산 → 메타데이터와 체인 원장을 하나의 번들로 원자적 write-once 저장 | `data_generator.py`, `settlement_batch.py`, `hashchain.py`, `hash_vault.py` |
| Phase 2: 대기 및 전송 | 스케줄에 따라 전송 에이전트(FTP/SFTP 모사) 기동 | `transfer_agent.py` |
| Phase 3: 교차 검증 및 통제 | 보호된 스냅샷 생성 → 이중 대사 → 모두 일치할 때만 원자적 승격. 불일치·Vault 오류·검증 예외·목적지 충돌은 사유 코드와 함께 fail-closed 차단 | `transfer_agent.py`, `hashchain.py` |
| Case B: 변조 공격 | Phase 1과 2 사이 시간차를 이용한 금액/계좌/헤더/레코드 구조/비트 단위 변조 | `tamper.py` |
| 평가 지표 | 변조 탐지율, 변조 위치 특정 정확도, 처리 지연 시간(Latency Overhead) | `metrics.py` |
| RQ4 비교 | 동일한 mtime 위조 공격에 기존 방식과 제안 모델을 모두 직접 실행 | `naive_baseline.py`, `simulate.py` |
| 네트워크 지연 추정 | 대역폭 가정 기반 종단간(end-to-end) 전송 지연 추정 | `network.py` |
| 실험 오케스트레이션 | Case A/B 반복 실행, 데이터 규모별 지연시간 스윕, RQ4 비교 | `simulate.py` |

### 해시 체이닝(Hash Chaining) 구조

제안 모델은 역할이 다른 두 무결성 값을 한 번의 파일 읽기에서 함께 계산한다.

- **파일 전체 해시(file hash)**: 개행 방식, 빈 줄, 인코딩, 파일 끝 데이터까지
  포함한 원본 바이트 전체의 SHA-256이다. 파일 바이트가 하나라도 달라지면
  전송을 차단한다.
- **레코드 해시 체인(chain root)**: CSV 헤더와 각 업무 레코드의 내용·순서를
  누적 해싱한다. 체인이 불일치하면 레코드별 해시 원장을 대조해 변조된
  거래 ID를 특정한다.

파일 전체 해시가 불일치하지만 레코드 체인이 일치하는 경우에는 개행 변경이나
빈 줄 삽입처럼 업무 레코드 외부의 바이트 수준 변경으로 분류하고
`FILE_BYTES_MISMATCH`로 차단한다. 두 값이 모두 일치해야만 전송이 허용된다.

파일 전체 SHA-256만으로는 변조 위치를 알 수 없으므로, 정산 파일의 각
거래(DATA 레코드)를 이전 체인값과 연결해 누적 해싱한다. 컬럼명과 순서를
바꾸는 헤더 변조도 탐지하기 위해 헤더 해시를 체인에 먼저 반영한다.

```
file_hash = SHA256(file_raw_bytes)
chain_0 = SHA256(genesis_seed)
chain_header = SHA256(chain_0 || SHA256(header))
chain_i = SHA256(chain_{i-1} || SHA256(record_i))   for i = 1..N
```

- **체인 루트와 레코드별 원장**은 `data/runs/<run-id>/hash_vault/entries/
  <file_id>.json` 하나에 저장된다. 임시 파일을 완전히 기록하고 `fsync`한 뒤
  hard-link로 공개하므로 메타데이터만 저장되거나 원장만 저장되는 부분 상태가
  외부에 보이지 않는다. 이미 존재하는 파일은 링크 단계에서 원자적으로 거부된다.
- 체인 루트가 불일치한 **이상 상황에서만** 같은 번들의 레코드 원장을 읽어
  100,000건 중 단 1건의 변조도 거래 ID 단위로 특정한다.
- 정상 파일 흐름에서는 원장을 읽지 않으므로, 포렌식(위치 특정) 비용은 실제
  변조가 탐지된 예외 상황에만 발생한다.

### Fail-closed 오류 사유 코드

`TransferResult.reason_code`는 정상 시 `OK`, 차단 시
`FILE_HASH_MISMATCH`, `CHAIN_HASH_MISMATCH`, `FILE_AND_CHAIN_MISMATCH`,
`VAULT_LOOKUP_FAILED`, `VERIFICATION_ERROR`, `SNAPSHOT_CREATION_FAILED`,
`DESTINATION_CONFLICT`, `PROMOTION_FAILED` 중 하나를 반환한다. 알 수 없는 검증
예외나 격리 I/O 오류가 발생해도 전송 허용으로 되돌아가지 않는다.

## 설치

```bash
cd settlement-integrity-model
python3 -m pip install -r requirements.txt
```

## 실행

```bash
# 전체 재실험. run-id별 새 폴더를 만들며 기존 결과는 덮어쓰지 않음
python3 src/simulate.py --case all --records 100000 --trials 5 \
  --latency-repeats 5 --run-id v2_atomic_failclosed_100k

# 정상 시나리오만
python3 src/simulate.py --case a --records 100000 --trials 10

# 변조 시나리오만 (100,000건 중 1건만 변조하는 살라미 기법)
python3 src/simulate.py --case b --records 100000 --trials 10 --tamper-count 1 --tamper-mode amount

# 구조적 변조 시나리오 (헤더 변경, 레코드 삭제/삽입)
python3 src/simulate.py --case b --records 100000 --trials 5 --tamper-mode header
python3 src/simulate.py --case b --records 100000 --trials 5 --tamper-count 1 --tamper-mode delete
python3 src/simulate.py --case b --records 100000 --trials 5 --tamper-count 1 --tamper-mode insert

# 비트 단위 변조 (필드 전체가 아니라 파일 원본 바이트 중 1비트만 변경)
python3 src/simulate.py --case b --records 100000 --trials 10 --tamper-mode bitflip

# 변조 건수 스윕 (1/5/10/50/100건으로 늘려가며 탐지율·위치 특정 정확도가
# 변조 규모와 무관하게 100%인지 검증)
python3 src/simulate.py --case sweep --records 100000 --sweep-counts 1 5 10 50 100 --sweep-trials 5

# RQ4: 기존 방식과 제안 모델을 동일 공격에 직접 실행
python3 src/simulate.py --case naive --records 100000 --trials 10

# 데이터 규모별 처리 지연 시간만 측정 (네트워크 전송 구간 추정 포함)
python3 src/simulate.py --case latency --latency-sizes 1000 10000 50000 100000
```

실행 결과는 `results/runs/<run-id>/`에, 해당 실행의 Vault·전송·격리 데이터는
`data/runs/<run-id>/`에 저장됩니다. 동일한 `run-id`가 이미 존재하면 실행을
거부하므로 이전 결과가 실수로 덮어써지지 않습니다.

- `case_a_results.csv`, `case_b_results.csv`: 시행별 상세 결과 (Case B는 실제
  변조한 trans_id와 체인 기반으로 특정한 trans_id를 나란히 기록)
- `rq4_comparison.csv`: 동일 공격에서 기존 방식과 제안 모델의 직접 실행 탐지율
- `tamper_count_sweep.csv`: 변조 건수(1~100건 등)별 탐지율·위치 특정 정확도
- `latency_sweep.csv`, `latency_overhead.png`: 데이터 규모별 지연시간(네트워크 추정 포함)
- `report.md`: 탐지율 / 위치 특정 / RQ4 / 공격 규모 / 수정된 지연 측정 요약
- `manifest.json`: 실행 인자, Git commit, Python·OS, 시작·종료 시각과 결과 경로

### 검증된 v2 재실험 결과

`v2_20260918_atomic_failclosed_100k` 실행은 100,000건, 기본 시행 5회,
공격 규모별 5회, 성능 구간별 5회 조건으로 수행했다.

- 정상 파일 오탐률 0%, 금액 변조 탐지율·위치 특정 정확도 100%
- 1·5·10·50·100건 변조 모두 탐지율·위치 특정 정확도 100%
- RQ4 제안 모델은 mtime 위조 후 amount/account/delete/bitflip을 모두 5/5 차단
- 100,000건 중앙값: Phase 1 167.92ms, Phase 3 gate 132.97ms,
  제안 모델 전체 299.54ms, 무검증 복사 베이스라인 12.22ms

수치는 `results/runs/v2_20260918_atomic_failclosed_100k/`의 CSV와
`manifest.json`을 근거로 하며, 이전 `results/` 결과는 수정하지 않았다.

### RQ4: 기존 방식(파일 크기·수정시각 비교) 대비 개선 효과

`--case naive`는 정산 파일 인터페이스 구간에서 실무적으로 흔히 쓰이는 가장
단순한 무결성 점검(파일 크기·수정시각 비교)을 재현해, 제안 모델과 정량적으로
대조한다. 각 변조 방식에 대해 두 가지 공격자를 가정한다 — (1) 변조 후
수정시각을 그대로 두는 as-is 공격자, (2) `os.utime()`으로 수정시각까지
원본과 동일하게 위조하는, 기초적인 안티포렌식 지식을 가진 공격자.

제안 모델의 결과를 별도 Case B 측정치로 대신하지 않는다. 각 시행에서 mtime을
원본으로 위조한 동일 파일을 `TransferAgent.transmit()`에 직접 넣어 두 방식의
판정을 함께 기록한다. `rq4_comparison.csv`에는 제안 모델의 오류 사유 코드
분포도 저장되므로 결과를 사후 검증할 수 있다.

### 성능 측정 구간

해시 함수 내부 시간만 합산하지 않고 보호 모델의 실제 처리 경계를 측정한다.

- `phase1_integrity_ms`: 파일 생성 완료 후 해시 계산 + 원자적 Vault 저장
- `phase3_gate_ms`: 스냅샷 생성 시작부터 해시 재계산·Vault 조회·허용 결정까지
- `proposed_total_ms`: Phase 1 무결성 처리 + 전송 에이전트 전체 처리
- `baseline_transfer_ms`: 동일 파일을 검증 없이 한 번 복사하는 시간

파일 생성 시간은 두 방식의 공통 비용이라 제외하며, 제안 모델에 필요한 Vault
영속화와 검증 스냅샷 복사는 포함한다. 각 값은 반복 실행의 중앙값이다.

이 로컬 I/O 측정치는 실제 네트워크 전송 구간(SFTP 등)을 포함하지 않는다는
한계가 있다. 이를 보완하기 위해 `src/network.py`가 회선 대역폭 가정(전용회선
100Mbps/10Mbps, 인터넷 VPN 평균)에 기반한 종단간(end-to-end) 전송 시간을
분석적으로 추정하며, `--case latency` 실행 시 `report.md`에 함께 기록된다.
실측치가 아니라 추정치이므로 논문에 인용할 때는 반드시 "대역폭 가정 기반
추정"이라고 명시해야 한다. 수치 결론은 특정 실행의 `manifest.json`과
`latency_sweep.csv`를 함께 제시해야 한다.

## 테스트

```bash
python3 -m pytest tests/ -v
```

정상 파일은 전송 허용(TRANSMITTED), 변조 파일(금액/계좌번호, 헤더 변경,
레코드 삭제/삽입, 1건 또는 여러 건을 동시에 변조하는 살라미 기법 포함)은
100% 차단(BLOCKED)되는지 검증합니다. 금액/계좌번호 수정은 변조된 trans_id가
정확히 특정되는지, 레코드 삭제/삽입은 건수 불일치가 탐지되는지 확인합니다.
또한 Vault 저장 중단 시 부분 엔트리가 남지 않는지, 경로 탈출형 ID·미등록
파일·검증기 예외·전송 목적지 충돌에서 항상 차단되는지까지 검사합니다.

## 디렉터리 구조

```
settlement-integrity-model/
├── src/
│   ├── config.py            # 경로/상수 설정
│   ├── data_generator.py     # 더미 정산 데이터 생성 (100,000건)
│   ├── hashchain.py           # 레코드 단위 해시 체이닝 + 변조 위치 특정
│   ├── hash_vault.py           # 원자적 write-once 엔트리(메타데이터+체인원장)
│   ├── settlement_batch.py      # Phase 1: 생성 및 격리
│   ├── tamper.py                 # Case B: 변조 공격 시뮬레이션
│   ├── transfer_agent.py          # Phase 2&3: 전송 + 교차 검증 + 위치 특정
│   ├── metrics.py                  # 평가 지표
│   ├── network.py                   # 네트워크 전송 구간 지연 추정 (대역폭 기반 분석 모델)
│   └── simulate.py                   # 실행 오케스트레이터 (CLI)
├── tests/
│   ├── test_hash_chain.py
│   └── test_network.py
├── data/runs/<run-id>/       # 실행별 Vault/전송/격리 데이터
└── results/runs/<run-id>/    # 실행별 CSV/그래프/리포트/manifest
```
