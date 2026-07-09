# 정산 파일 무결성 검증 모델 (Settlement File Integrity Verification Model)

석사 논문 연구계획서 "대용량 트랜잭션 처리 시스템의 정산 데이터 무결성 보장 및
부정 방지 모델 연구"의 3단계 이중 해시 체이닝 검증 모델을 Python으로 구현한
시뮬레이션 코드와 더미데이터 생성기입니다.

## 3단계 검증 메커니즘과 코드 매핑

| 논문상 단계 | 설명 | 구현 모듈 |
|---|---|---|
| Phase 1: 생성 및 격리 | 정산 파일 생성 → 스트림 종료 즉시 레코드 단위 해시 체인 계산 → Hash Vault 격리 보관 | `data_generator.py`, `settlement_batch.py`, `hashchain.py`, `hash_vault.py` |
| Phase 2: 대기 및 전송 | 스케줄에 따라 전송 에이전트(FTP/SFTP 모사) 기동 | `transfer_agent.py` |
| Phase 3: 교차 검증 및 통제 | 전송 직전 체인 재계산 → Vault 원본 루트 해시와 대사 → 불일치 시 즉각 차단(Drop)+알람+변조 위치 특정 | `transfer_agent.py`, `hashchain.py` |
| Case B: 변조 공격 | Phase 1과 2 사이 시간차를 이용한 살라미 기법 변조 | `tamper.py` |
| 평가 지표 | 변조 탐지율, 변조 위치 특정 정확도, 처리 지연 시간(Latency Overhead) | `metrics.py` |
| 실험 오케스트레이션 | Case A/B 반복 실행, 데이터 규모별 지연시간 스윕 | `simulate.py` |

### 해시 체이닝(Hash Chaining) 구조

파일 전체를 한 번에 해싱하는 방식(단일 SHA-256) 대신, 정산 파일의 각
거래(DATA 레코드)를 순서대로 이전 체인값과 연결해 누적 해싱한다.

```
chain_0 = SHA256(genesis_seed)
chain_i = SHA256(chain_{i-1} || SHA256(record_i))   for i = 1..N
```

- **체인 루트(chain_N)** 는 파일 전체의 무결성을 대표하는 값으로 Hash
  Vault(`vault.json`)에 저장되며, 평소 전송 시점의 대사(Phase 3)는 이 루트
  값 하나만 비교하므로 기존 방식과 성능 차이가 크지 않다.
- **레코드별 해시 배열**은 별도의 격리된 원장(`data/hash_vault/chains/
  <file_id>.json`)에 함께 보관된다. 루트 해시가 불일치하는 **이상 상황에서만**
  이 원장을 불러와 위치별로 대조하여, 100,000건 중 단 1건만 살라미 기법으로
  변조되어도 **정확히 어느 거래(trans_id)가 변조되었는지 특정**한다
  (`TransferResult.tampered_trans_ids`).
- 정상 파일 흐름에서는 원장을 읽지 않으므로, 포렌식(위치 특정) 비용은 실제
  변조가 탐지된 예외 상황에만 발생한다.

## 설치

```bash
cd settlement-integrity-model
python3 -m pip install -r requirements.txt
```

## 실행

```bash
# 전체 시뮬레이션 (Case A, Case B, 지연시간 스윕) 기본 실행
python3 src/simulate.py --case all --records 100000 --trials 5

# 정상 시나리오만
python3 src/simulate.py --case a --records 100000 --trials 10

# 변조 시나리오만 (100,000건 중 1건만 변조하는 살라미 기법)
python3 src/simulate.py --case b --records 100000 --trials 10 --tamper-count 1 --tamper-mode amount

# 데이터 규모별 처리 지연 시간만 측정
python3 src/simulate.py --case latency --latency-sizes 1000 10000 50000 100000
```

실행 결과는 `results/` 아래에 저장됩니다.

- `case_a_results.csv`, `case_b_results.csv`: 시행별 상세 결과 (Case B는 실제
  변조한 trans_id와 체인 기반으로 특정한 trans_id를 나란히 기록)
- `latency_sweep.csv`, `latency_overhead.png`: 데이터 규모별 지연시간
- `report.md`: 변조 탐지율 / 변조 위치 특정 정확도 / 처리 지연 시간 요약 리포트

### 참고: 지연시간 측정치에 대한 해석

레코드 단위 체이닝은 파일 전체를 한 번에 훑는 단일 해시보다 Python
레벨의 함수 호출 오버헤드가 커서, 검증 없는 단순 전송(베이스라인) 대비
오버헤드 **비율**은 크게 보일 수 있다 (100,000건 기준 베이스라인 대비
약 10~13배). 다만 절대 시간으로는 100,000건에서도 해시 계산+검증 합산
약 150~200ms 수준으로, 실제 정산 배치가 분 단위로 소요되는 점을 고려하면
무시할 수 있는 수준이다. 또한 레코드 수에 비례해 선형(O(N))으로 증가하므로
대용량 환경에서도 예측 가능한 성능을 보인다(`results/latency_overhead.png`
참고).

## 테스트

```bash
python3 -m pytest tests/ -v
```

정상 파일은 전송 허용(TRANSMITTED), 변조 파일(금액/계좌번호, 1건 또는
여러 건을 동시에 변조하는 살라미 기법 포함)은 100% 차단(BLOCKED)되고 변조된
trans_id가 정확히 특정되는지, Hash Vault가 중복 등록·존재하지 않는 항목
조회를 거부하는지를 검증합니다.

## 디렉터리 구조

```
settlement-integrity-model/
├── src/
│   ├── config.py            # 경로/상수 설정
│   ├── data_generator.py     # 더미 정산 데이터 생성 (100,000건)
│   ├── hashchain.py           # 레코드 단위 해시 체이닝 + 변조 위치 특정
│   ├── hash_vault.py           # 격리된 해시 저장소 (write-once, 루트+체인원장)
│   ├── settlement_batch.py      # Phase 1: 생성 및 격리
│   ├── tamper.py                 # Case B: 변조 공격 시뮬레이션
│   ├── transfer_agent.py          # Phase 2&3: 전송 + 교차 검증 + 위치 특정
│   ├── metrics.py                  # 평가 지표
│   └── simulate.py                  # 실행 오케스트레이터 (CLI)
├── tests/
│   └── test_hash_chain.py
├── data/          # 실행 시 생성되는 정산 파일/Vault/전송함/격리함 (gitignore)
└── results/       # 실행 시 생성되는 결과 CSV/그래프/리포트 (gitignore)
```
