# 정산 파일 무결성 검증 모델 (Settlement File Integrity Verification Model)

석사 논문 연구계획서 "대용량 트랜잭션 처리 시스템의 정산 데이터 무결성 보장 및
부정 방지 모델 연구"의 3단계 이중 해시 체이닝 검증 모델을 Python으로 구현한
시뮬레이션 코드와 더미데이터 생성기입니다.

## 3단계 검증 메커니즘과 코드 매핑

| 논문상 단계 | 설명 | 구현 모듈 |
|---|---|---|
| Phase 1: 생성 및 격리 | 정산 파일 생성 → 스트림 종료 즉시 파일 전체 SHA-256과 레코드 단위 해시 체인 계산 → Hash Vault 격리 보관 | `data_generator.py`, `settlement_batch.py`, `hashchain.py`, `hash_vault.py` |
| Phase 2: 대기 및 전송 | 스케줄에 따라 전송 에이전트(FTP/SFTP 모사) 기동 | `transfer_agent.py` |
| Phase 3: 교차 검증 및 통제 | 보호된 임시 스냅샷 생성 → 파일 전체 해시와 레코드 체인 재계산 → Vault 원본값과 이중 대사 → 모두 일치할 때만 검증한 스냅샷을 전송함으로 원자적 승격, 불일치 시 동일 스냅샷 격리+알람+변조 위치 특정 | `transfer_agent.py`, `hashchain.py` |
| Case B: 변조 공격 | Phase 1과 2 사이 시간차를 이용한 금액/계좌/헤더/레코드 구조/비트 단위 변조 | `tamper.py` |
| 평가 지표 | 변조 탐지율, 변조 위치 특정 정확도, 처리 지연 시간(Latency Overhead) | `metrics.py` |
| RQ4 비교 | 파일 크기·수정시각 비교 방식(기존 단순 방식)과의 정량 비교 | `naive_baseline.py` |
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

# 구조적 변조 시나리오 (헤더 변경, 레코드 삭제/삽입)
python3 src/simulate.py --case b --records 100000 --trials 5 --tamper-mode header
python3 src/simulate.py --case b --records 100000 --trials 5 --tamper-count 1 --tamper-mode delete
python3 src/simulate.py --case b --records 100000 --trials 5 --tamper-count 1 --tamper-mode insert

# 비트 단위 변조 (필드 전체가 아니라 파일 원본 바이트 중 1비트만 변경)
python3 src/simulate.py --case b --records 100000 --trials 10 --tamper-mode bitflip

# 변조 건수 스윕 (1/5/10/50/100건으로 늘려가며 탐지율·위치 특정 정확도가
# 변조 규모와 무관하게 100%인지 검증)
python3 src/simulate.py --case sweep --records 100000 --sweep-counts 1 5 10 50 100 --sweep-trials 5

# RQ4: 제안 모델 vs 파일 크기·수정시각 비교 방식(기존 단순 방식)
python3 src/simulate.py --case naive --records 100000 --trials 10

# 데이터 규모별 처리 지연 시간만 측정 (네트워크 전송 구간 추정 포함)
python3 src/simulate.py --case latency --latency-sizes 1000 10000 50000 100000
```

실행 결과는 `results/` 아래에 저장됩니다.

- `case_a_results.csv`, `case_b_results.csv`: 시행별 상세 결과 (Case B는 실제
  변조한 trans_id와 체인 기반으로 특정한 trans_id를 나란히 기록)
- `naive_baseline_results.csv`: 변조 방식별 기존(파일 속성 비교) 방식의 탐지율
- `tamper_count_sweep.csv`: 변조 건수(1~100건 등)별 탐지율·위치 특정 정확도
- `latency_sweep.csv`, `latency_overhead.png`: 데이터 규모별 지연시간(네트워크 추정 포함)
- `report.md`: 변조 탐지율 / 변조 위치 특정 정확도 / RQ4 비교 / 변조 건수 스윕 / 처리 지연 시간 요약 리포트

### RQ4: 기존 방식(파일 크기·수정시각 비교) 대비 개선 효과

`--case naive`는 정산 파일 인터페이스 구간에서 실무적으로 흔히 쓰이는 가장
단순한 무결성 점검(파일 크기·수정시각 비교)을 재현해, 제안 모델과 정량적으로
대조한다. 각 변조 방식에 대해 두 가지 공격자를 가정한다 — (1) 변조 후
수정시각을 그대로 두는 as-is 공격자, (2) `os.utime()`으로 수정시각까지
원본과 동일하게 위조하는, 기초적인 안티포렌식 지식을 가진 공격자.

100,000건 기준 실행 결과(예시, 시드에 따라 소폭 달라질 수 있음):

| 변조 방식 | 기존 방식(as-is) | 기존 방식(mtime 위조 후) | 제안 모델 |
|---|---|---|---|
| amount(금액 변조) | 100% | 자릿수가 우연히 바뀔 때만 검출 | 100% |
| account(계좌 변조, 자릿수 불변) | 100% | 0% | 100% |
| delete(레코드 삭제) | 100% | 100%(크기 자체가 줄어듦) | 100% |
| bitflip(1비트 변조) | 100% | 0% | 100% |

즉 기존 방식은 파일 크기가 눈에 띄게 바뀌는 변조(레코드 삭제)만 안정적으로
잡아내고, 자릿수를 유지한 채 값만 바꾸는 살라미 기법이나 1비트 변조처럼
크기가 그대로인 공격에는 수정시각 위조 한 번으로 완전히 무력화된다. 제안
모델은 내용을 직접 해시로 검증하므로 이런 메타데이터 위조와 무관하게
항상 탐지한다.

### 참고: 지연시간 측정치에 대한 해석

레코드 단위 체이닝은 파일 전체를 한 번에 훑는 단일 해시보다 Python
레벨의 함수 호출 오버헤드가 커서, 검증 없는 단순 전송(베이스라인) 대비
오버헤드 **비율**은 크게 보일 수 있다 (100,000건 기준 베이스라인 대비
약 10~13배). 다만 절대 시간으로는 100,000건에서도 해시 계산+검증 합산
약 150~200ms 수준으로, 실제 정산 배치가 분 단위로 소요되는 점을 고려하면
무시할 수 있는 수준이다. 또한 레코드 수에 비례해 선형(O(N))으로 증가하므로
대용량 환경에서도 예측 가능한 성능을 보인다(`results/latency_overhead.png`
참고).

이 로컬 I/O 측정치는 실제 네트워크 전송 구간(SFTP 등)을 포함하지 않는다는
한계가 있다. 이를 보완하기 위해 `src/network.py`가 회선 대역폭 가정(전용회선
100Mbps/10Mbps, 인터넷 VPN 평균)에 기반한 종단간(end-to-end) 전송 시간을
분석적으로 추정하며, `--case latency` 실행 시 `report.md`에 함께 기록된다.
실측치가 아니라 추정치이므로 논문에 인용할 때는 반드시 "대역폭 가정 기반
추정"이라고 명시해야 한다. 100,000건 기준으로 보면 해시 검증 오버헤드는
전용회선 100Mbps 환경 종단간 지연의 약 18~19% 수준에 그쳐, 실제 전송
구간까지 포함해도 검증 비용이 지배적이지 않음을 보여준다.

## 테스트

```bash
python3 -m pytest tests/ -v
```

정상 파일은 전송 허용(TRANSMITTED), 변조 파일(금액/계좌번호, 헤더 변경,
레코드 삭제/삽입, 1건 또는 여러 건을 동시에 변조하는 살라미 기법 포함)은
100% 차단(BLOCKED)되는지 검증합니다. 금액/계좌번호 수정은 변조된 trans_id가
정확히 특정되는지, 레코드 삭제/삽입은 건수 불일치가 탐지되는지, Hash Vault가
중복 등록·존재하지 않는 항목 조회를 거부하는지도 함께 확인합니다.

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
│   ├── network.py                   # 네트워크 전송 구간 지연 추정 (대역폭 기반 분석 모델)
│   └── simulate.py                   # 실행 오케스트레이터 (CLI)
├── tests/
│   ├── test_hash_chain.py
│   └── test_network.py
├── data/          # 실행 시 생성되는 정산 파일/Vault/전송함/격리함 (gitignore)
└── results/       # 실행 시 생성되는 결과 CSV/그래프/리포트 (gitignore)
```
