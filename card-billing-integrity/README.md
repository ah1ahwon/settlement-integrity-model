# card-billing-integrity — 재현성 패키지

학위논문 「카드 청구 데이터의 변조 식별 가능성 분석: 신뢰정보와 정상 청구 지연 조건을 중심으로」의 합성 실험·검증 코드와 결과 로그.
외부 라이브러리 없음. Python 3.11.1 (표준 라이브러리만), `PYTHONHASHSEED=0`.

이 패키지의 청구 파일은 특정 카드사, VAN 사업자 또는 기업의 전자문서 명세를 구현한 것이 아니다. 변조 식별 문제를 분석하려고 연구자가 독립적으로 정의한 합성 모델이며, 모든 데이터는 난수로 생성한다(실제 거래·회사 정보 없음).

**공개판 안내.** 공개판은 레코드 구분값만 바꾼 판이며(매출 레코드 10, 취소 레코드 20), 연구용 판과 모든 로그가 구분값을 제외하면 동일함을 확인하였다. 단, `indep_check_ref.log`의 불일치 예시 5줄은 집합 순회 순서에 따라 다른 사례가 뽑혀 달라지며, 불일치 사례 전체 집합(2,667건)은 두 판이 같음을 별도로 확인하였다.

## 연구 모델 (논문 제3장)
- **파일.** F = (가맹점 m, 레코드 목록). 레코드는 (유형 t ∈ {매출, 취소}, 거래 식별자 k, 금액 a)이고, ID 관측 수준에서만 취소 레코드에 취소 이벤트 식별자 e를 붙인다. 코드 표기는 `(10, k, a)`, `(20, k, a[, e])`.
- **범위.** 한 레코드는 한 거래 이벤트에 대응한다. 여러 거래를 한 레코드로 묶는 다대일 집계와 파일 단위 집계·종료 레코드의 검증 효과는 다루지 않는다.
- **거래 상태와 취소.** 거래마다 숨은 상태 U(미청구)·C(청구완료)·R(반송)과 승인 취소 이벤트 (금액, 반영 여부)가 있다. 업무 제약: 반영된 취소는 청구완료(C) 거래에만 있다.
- **신뢰정보 K** ⊆ {L(매출 승인 원장), D(청구일자), B(반송 이력), Z(거래별 기반영 취소 누계), X(취소 승인 목록), Y(X + 건별 반영 상태)}.
- **관측 수준.** X1-금액 = L+D+B+Z+X, X2-금액 = L+D+B+Z+Y. X1-ID·X2-ID는 같은 정보에 취소 이벤트 식별자를 더한 수준이다.
- **업무 가정** A = (CR, c_s, c_c): 반송 거래 수 ≤ CR, 매출 이월 ≤ c_s, 취소 이월 ≤ c_c. 모든 K가 같은 A를 공유하고 관측만 달라진다. A와 지연 확률 p는 모델 매개변수이고, Z는 연구 설정이다. 어느 값도 실제 운영값으로 확인한 것이 아니다.
- **판정.** 관측과 일치하는 정당 세계가 존재하면 수락한다(가능 세계 존재 판정). 기준 판정기 `src/ref2.py`의 `ref_accept(F, led, K, A)`는 거래별 숨은 상태와 취소 반영 부분집합을 고르고, (반송, 매출 이월, 취소 이월) 비용 삼중쌍의 합이 A 이내인 선택이 있는지를 동적 계획(도달 가능 비용 집합)으로 판정한다. ID 수준 판정기는 `src/ref2id.py`.
- **사전 검사.** 파일 자체 정합성 검사(같은 파일 안 매출 거래 식별자 중복 없음, 같은 파일 취소 합 ≤ 매출 금액; 코드 라벨 `내부:`)와 원장 검사(거래 식별자 존재, 가맹점 일치, 매출 금액 = 승인 금액, 취소 누적 ≤ 한도)는 `m2.atoms`에서 가져온다.

## 논문 수치와 재현 위치
로그는 별도 표시가 없으면 `results/baseline_v2/`. 수치 대조: `tests/check_reported_numbers_v2.py`(32항목).

| 논문 내용 | 수치 | 스크립트 | 로그 |
|---|---|---|---|
| 판정기 독립 검증(판정기를 import하지 않는 열거기) | 3,063,413건 불일치 0 | `tests/indep_check.py` + `tests/indep_world.py` | `indep_check_ref2` |
| 판정기 결함 기록: 원 판정기 `ref.py`에 업무 제약 누락 | 불일치 2,667 | 같은 대조를 `ref`로 | `indep_check_ref` |
| 결함 기록: 구 열거기 `refval.py`도 같은 정의를 공유해 누락을 못 잡음 | 3,036(구 열거기 쪽 결함) | `tests/refval.py` | `ref2_refval` |
| 단일 거래 해석식 대조 | 245,280건 불일치 0 | `tests/thm2.py` | `ref2_thm2` |
| X1+Z와 X2 판정이 갈린 파일 | 1,183 = 포함관계 1,055 + 예산만 128 | `tests/test_budget_only_minimal.py` | `ref2_budget_only`, `results/budget_only_128.csv` |
| 명제 3.3(b-1) 금액 수준 | 위반 0/26,352 | `tests/test_prop33b.py` | `prop33b` |
| 명제 3.3(b-2) ID 수준(반영 후보 유일) | 위반 0/3,372, (b-1) 전제만으로는 ID 수준에서 갈리는 경우 1,824 | `tests/test_prop33b.py` | `prop33b` |
| 공통 예산 결합(두 거래 표본, 시드 3, 60,000건) | 290 = 한 거래만으로 갈림 71 + 순수 결합 219 | `tests/test_coupling_219.py` | `coupling_219` |
| 취소 ID 포함관계(X2-ID ⊆ X1-ID+Z = X1-금액+Z) | 26,092건 위반 0 | `tests/test_id_chain.py` | `id_chain` |
| 취소 ID 수준 전수 대조 | 13,764건: X1-금액 vs X1-ID 0, X1-ID vs X2 355 | `tests/test_id_equivalence.py` | `id_equivalence` |
| 단조성 | 정보 0/1,155,690 (c=1,2,3), 허용치 0/114,426 | `experiments/refeval.py` | `ref2_refeval` |
| 사례별 X1+Z vs X2(명제 3.4(c)와 일치) | 43,668건 판정 불일치 0 | `tests/casecmp.py` | `ref2_casecmp` |
| 고정 실험 표1~5(공격 42,668건, 13유형) | 표1 X1·X2 89.2, Z 없는 X1 81.3, 표5 26.1/45.4/68.5 | `experiments/final_ref.py` | `ref2_final_ref` |
| 민감도 S1 취소 이월, S2 반송 상한, S3 금액 분포 | 7개 지표 | `experiments/sensitivity.py` | `sensitivity` |
| 민감도 S4 취소 ID 관측 | 16유형 X1·X2-금액 85.0, X1·X2-ID 91.2, X1-ID 수락·X2-ID 거절 0 | `experiments/sensitivity_s4.py`, `src/ref2id.py` | `sensitivity_s4` |
| S4 불일치 분해 | 유령 ID 995/865, 중복 ID 3/3, 기반영 취소 ID 재전송 0 | `experiments/s4_breakdown.py` | `s4_breakdown` |
| S4 ID 판정기 검증 | 13,764건 불일치 0 | `tests/test_ref2id_consistency.py` | `ref2id_consistency` |
| 누계 모호성 | (승인 목록, 누계)의 복수 반영 상태 | `experiments/run8.py` | `results/baseline/run8` |

## 실행
```
python3 run_all.py --rerun                 # 1차 세트 재실행, baseline 과의 diff 를 results/diff_*.txt 에 기록
python3 run_all.py --set v2 --rerun        # 2차 세트(논문 수치) 재실행, results/diff_v2_*.txt
python3 tests/check_reported_numbers_v2.py [baseline_v2|rerun_v2_<시각>]   # 논문 수치 대조(32항목)
python3 tests/check_reported_numbers.py [baseline|rerun_<시각>]           # 1차 세트 수치 대조(23항목)
```
`python3 run_all.py`(옵션 없음)는 baseline이 없을 때만 실행된다. 각 검증은 독립 스크립트이며 `PYTHONPATH=src:tests:experiments:experiments/legacy`를 주면 개별 실행된다. `results/baseline*`은 덮어쓰지 않는다.

## 고정 실험 조건
정상 1,000파일(시드 2024), 공격 42,668건(13유형), 지연 p=10%, A=(CR, c_s, c_c)=(2, 3, 3), 판정기 ref2.

## 구성
| 위치 | 내용 |
|---|---|
| `src/` | `ref2.py`(기준 판정기), `ref2id.py`(ID 수준 판정기), `run9.py`(정상 파일 생성기 `make_case5`), `m4.py`(13개 공격 생성), `m2.py`(파일·원장 검사 `atoms`). `ref.py`, `m2b.py`는 1차 세트 기록용 |
| `tests/` | 독립 열거기와 대조, 명제 검증, 단조성, 반례, 수치 대조 |
| `experiments/` | 고정 실험, 민감도 S1~S4, 모호성, 독립 생성기, `legacy/final.py`(구 판정 원본 표) |
| `variants/ref2_shim/` | 1차 세트 스크립트를 수정 없이 ref2로 다시 돌리기 위한 대체 모듈 |
| `config/experiment_config.json` | 시드, 사례 수, 업무 가정 기록 |
| `results/baseline/`, `results/baseline_v2/` | 1차·2차 세트 기준 로그 |
| `results/rerun_*/`, `results/diff_*.txt` | 재실행 로그와 baseline 대비 차이 |

## 1차 세트(이력)
`run_all.py`의 기본 세트는 원 판정기 `ref.py`와 구 규칙(`m2`, `m2b`, `m4.explainable4`, `props*`, `cls*`, `legacy/final.py`)의 결과다. 구 규칙의 정보 단조성 위반(5,352 → CR 고정 후 10 → 5 → 0)과, 독립 열거기로 드러난 `ref.py`의 업무 제약 누락을 기록으로 남기려고 보존했다. **논문 수치는 2차 세트(ref2)를 사용한다.** 원 스크립트는 수정하지 않았고, ref2 재실행은 `variants/ref2_shim/`으로 판정기만 바꿔 수행했다. ref2로 바꿔도 표1 주요 행, 245,280/43,668/128건, 단조성은 같고, Z 없는 X1(81.2 → 81.3)과 표5 '미반영→반영 표시' 오차단(24.8 → 26.1, 43.3 → 45.4, 66.2 → 68.5)만 달라진다. `experiments/sim_batch.py`(일별 배치 독립 생성기)는 1차 세트의 구 판정 결과다.

## 한계 (반드시 함께 읽을 것)
1. **독립성의 범위.** 독립 열거기는 판정기와 구 규칙을 import하지 않고 정당 세계를 정의대로 만든다. 그러나 업무 가정과 관측의 정의는 같은 저자가 같은 명세로 작성했으므로, 정의 자체의 오류는 이 대조로 잡히지 않는다.
2. **규모.** 열거 검증은 작은 모델(가맹점 하나의 거래 1~2건 + 타 가맹점 거래 1건, 승인 금액 1..3, 관측 K 18종, 업무 가정 5종; 명제·ID 검증은 취소 이벤트 1~4건, 금액 1..3, 포함관계 확인만 1~5건)에서 수행했다. 일반 성립은 논문의 증명에 의존하며, 스크립트는 유한 사례 확인이다.
3. **표본 결과.** 290 = 71 + 219는 무작위 표본(시드 3, 60,000건)의 결과다.
4. **합성 모델.** 파일 구조, 정상·공격 생성기, 업무 가정은 저자가 정의했다. 결과는 이 모델과 합성 데이터 조건에서 해석하며, 특정 상용 정산 시스템의 탐지 성능으로 일반화하지 않는다.
5. **재현 환경.** 같은 기계의 Python 3.11.1과 3.14.8에서 두 세트 모두 baseline과 차이 0이다. 다른 기계에서의 실행은 아직 없다.
6. **미포함.** 문헌 조사와 연구계획서 단계의 수치는 이 패키지에 없다.
7. 일부 1차 세트 스크립트는 import 시 실행되는 구조라(`props.py` 등) `props2/cls/cls2`가 `props`를 다시 실행한다. 원본 보존을 위해 수정하지 않았다.

## 재현성 기록
- 공개판 재실행 차이 0: `results/diff_20261014_235603.txt`(1차), `results/diff_v2_20261014_235802.txt`(2차). 논문 수치 대조 FAIL 0(baseline_v2와 재실행 모두).
- 이식성: `run_all.py`는 자식 프로세스에 `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`을 주고 로그를 UTF-8로 읽고 쓴다(Windows 기본 인코딩에서 한글 로그가 달라지는 문제 방지). diff 보고서에 비정상 종료 작업 목록을 함께 적는다.
- 해시 시드 독립성: 모든 작업을 `PYTHONHASHSEED=777`로 실행해도 baseline과 같았다(실행기는 0으로 고정).
- 실행은 이 폴더 안에서 한다. 경로는 모두 `run_all.py` 위치 기준 상대 경로다. `conftest.py`는 저장소 루트에서 pytest를 실행할 때 이 폴더를 수집하지 않게 한다.
- `private/`(git 제외): 공개하지 않는 참고 자료와 연구용 판 기록.
