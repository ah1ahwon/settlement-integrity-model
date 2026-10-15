# card-billing-integrity — 재현성 패키지

카드 청구 데이터 변조 식별 가능성 분석(학위논문)의 합성 실험·검증 코드와 결과 로그.

**공개판 안내.** 이 패키지는 공개판이다. 공개판은 레코드 구분값만 바꾼 판이며(매출 레코드 10, 취소 레코드 20), 연구용 판과 모든 로그가 구분값을 제외하면 동일함을 확인하였다. 단, `indep_check_ref.log`의 불일치 예시 5줄은 집합 순회 순서에 따라 다른 사례가 뽑혀 달라지며, 불일치 사례 전체 집합(2,667건)은 두 판이 같음을 별도로 확인하였다. 아래 기록 중 2026-10-14의 재실행·diff 파일명은 연구용 판의 기록이며 공개판에는 포함하지 않는다. 공개판 baseline은 `results/baseline`, `results/baseline_v2`이고 재실행 차이 0이다.
외부 라이브러리 없음. Python 3.11.1 (표준 라이브러리만), `PYTHONHASHSEED=0`.

## 구성
| 위치 | 내용 |
|---|---|
| `src/` | 모델·생성기·판정기. `m2.py`(구 규칙, 레코드 단위), `m2b.py`(구 규칙+반송 상한 CR 고정), `m4.py`(취소 승인 이력 X/Y 규칙, 13개 공격 생성), `ref.py`(**통일 기준 판정기**), `run9.py`(정상 파일 생성기 `make_case5`) |
| `tests/` | 열거 대조, 단조성, 반례, 판정 경로 검증 |
| `experiments/` | 고정 실험 표 재계산, 모호성, 독립 생성기(일별 배치), `legacy/final.py`(구 판정 원본 표) |
| `config/experiment_config.json` | 시드, 사례 수, 업무 가정 기록 |
| `results/baseline/` | 기준 로그(첫 실행). **덮어쓰지 않는다** |
| `results/rerun_*/`, `results/diff_*.txt` | 재실행 로그와 baseline 대비 차이 기록 |
| `results/budget_only_128.csv` | 예산 차이만으로 X1+Z와 X2 판정이 갈리는 128건 목록 |

## 실행
```
python3 run_all.py                 # baseline 이 없을 때만 실행(있으면 거부)
python3 run_all.py --rerun         # 새 디렉터리에 재실행하고 baseline 과의 diff 를 results/diff_*.txt 에 기록
python3 tests/check_reported_numbers.py [baseline|rerun_<시각>]   # 보고 수치와 로그 대조(23항목)
python3 tests/check_reported_numbers_v2.py [baseline_v2|rerun_v2_<시각>]   # 2차 세트 보고 수치 대조(32항목)
```
각 검증은 독립 스크립트이며 `python3 <스크립트>`에 `PYTHONPATH=src:tests:experiments:experiments/legacy`를 주면 개별 실행된다.

## 모델 요약
- 신뢰정보 K ⊆ {L(판매 승인 원장), D(청구일자), B(반송 이력), Z(기반영 취소 누계), X(취소 승인 목록), Y(X+건별 반영 상태)}.
- 업무 가정 A=(CR, c_s, c_c): 반송 거래 수 ≤ CR, 판매 이월 ≤ c_s, 취소 이월 ≤ c_c. 모든 K가 같은 A를 공유하고 관측만 달라진다.
- 기준 판정 `ref.ref_accept(F, led, K, (CR, c_s, c_c))`: 관측과 일치하는 정당 세계가 존재하면 수락. 거래별 숨은 상태(U/C/R)와 취소 반영 부분집합을 선택하고 (반송, 판매 이월, 취소 이월) 비용의 합이 예산 이내인 선택이 있는지를 동적 계획(도달 가능 비용 집합)으로 판정한다.
- 레코드 단위 정합성(승인번호 존재, 가맹점 일치, 매출 금액, 취소 한도, 매출 승인번호 중복 없음, 같은 파일 취소 합 ≤ 매출 금액)은 `m2.atoms`에서 가져와 사전 조건으로 적용한다.

## 검증 항목과 재현 스크립트
| 보고 수치 | 스크립트 | 내용 | 절차 |
|---|---|---|---|
| 85,624 / 불일치 0 | `tests/refval.py` | 정당 세계 직접 열거(`worlds_files`) vs `ref_accept` | 열거 vs 동적 계획 |
| 162,000 / 0 | `tests/val_x.py` | 취소 규칙(`m4.extra_ok`) vs 이벤트 식별자 유지 열거 | 열거 vs 규칙 |
| 10,428 / 0 | `tests/val.py` | 구 규칙(m2) vs 열거(`legit_set`) | 열거 vs 규칙(구 모델) |
| 245,280 / 0 | `tests/thm2.py`, `tests/test_budget_only_minimal.py` | 단일 거래 해석식 vs `ref_accept` (반송 이력 포함 조합) | 해석식 vs 동적 계획 |
| 1,183건 갈림 = 포함관계 1,055 + 예산만 128 | `tests/test_budget_only_minimal.py` | 갈린 파일을 정당 세계 직접 열거로 재확인 | 3중 대조 |
| 두 거래 결합 290건 | `tests/thm2.py` | 개별(예산 충분)은 같고 공통 예산에서만 갈림 | `ref_accept` |
| 114,426 / 0 | `experiments/refeval.py` | 허용치 c 단조성 | `ref_accept` |
| 1,155,690 / 0 (c=1,2,3) | `experiments/refeval.py` | 정보 단조성(통일 판정) | `ref_accept` |
| 5,352 → 10 → 5 → 0 | `tests/props.py`, `tests/cls.py`, `tests/cls2.py` | 구 규칙의 정보 단조성 위반과 CR 고정 후 잔여 | 구 규칙 vs 보정 |
| 43,668 / 판정 불일치 0 | `tests/casecmp.py` | D+B+Z+X1 vs D+B+Z+X2 사례별 판정 | `ref_accept` |
| 42,668 공격, 표1~5 | `experiments/final_ref.py` | 고정 실험(기존/새) | `explainable4` vs `ref_accept` |
| 모호성 비율 | `experiments/run8.py` | (승인목록, 누계)의 복수 반영 상태 | 열거 |
| 독립 생성기 | `experiments/sim_batch.py` | 일별 배치 시뮬레이터에서 c 효과 | `explainable4` |

## 고정 실험 조건
정상 1,000파일(시드 2024), 공격 42,668건(13유형), 실제 지연 p=10%, CR=2, 기준 c=3, 합성 데이터만 사용(실제 거래·회사 정보 없음).

## 한계 (반드시 함께 읽을 것)
1. **독립성의 범위.** 기준 판정기와 열거 검증기는 서로 다른 절차(동적 계획 vs 세계 직접 열거)이지만, 업무 가정 A와 관측의 정의는 같은 저자가 같은 명세로 작성했다. 또한 열거 검증기가 `ref.view_set`(K별 숨은 상태 허용 집합)을 공유하므로 이 함수의 오류는 열거 대조로 잡히지 않는다. 열거 대상은 레코드 단위 정합성을 검사하지 않고 파일 수준(송신·취소 레코드)만 비교한다.
2. **규모.** 열거 검증은 작은 모델(거래 1~3건, 취소 이벤트 최대 3~4건)에서 수행했다. 일반 동치는 증명하지 않았다. 취소 승인 목록이 없는 정보 집합은 열거 대상에서 제외했다.
3. **합성 데이터.** 정상·공격 생성기는 저자가 정의했다. 업무 가정(지연, 취소 이월, 이력 보유)의 값은 실제 시스템으로 확인되지 않았다.
4. **구 판정 스크립트 보존.** `m2`, `m2b`, `m4.explainable4`, `props*`, `cls*`, `legacy/final.py`는 통일 판정으로 대체되기 전의 결과를 보여주기 위해 남겼다. 논문 수치는 `ref.py` 기반 결과를 사용한다.
5. **미포함.** 문헌 조사, 템플릿 문법 기반 규칙 생성 실험(구 모델), 문서 수치(연구계획서)는 이 패키지에 없다.
6. 일부 스크립트는 import 시 실행되는 구조라(`props.py` 등) `props2/cls/cls2`가 `props`를 다시 실행한다. 원본 보존을 위해 수정하지 않았다.

## 재실행 결과가 다를 때
`results/baseline`은 덮어쓰지 않는다. `--rerun`은 새 디렉터리에 저장하고 차이를 `results/diff_*.txt`에 줄 단위로 기록한다. 현재 baseline 대비 재실행 차이는 0개 로그(`results/diff_20261014_174200.txt`).

## 2차 세트 (2026-10-14 추가): 독립 열거기, 판정기 ref2, 민감도
실행: `python3 run_all.py --set v2` (기준 `results/baseline_v2`), `--set v2 --rerun`으로 재실행·비교. 보고 수치 대조는 `tests/check_reported_numbers_v2.py`(baseline_v2와 재실행 모두 FAIL 0).
- `tests/indep_world.py`: 판정기(`ref`, `m2`, `m4`)를 import하지 않는 열거기. 정당 세계를 정의대로 전부 만들고 관측 함수로 거른다.
- 발견: 원 판정기 `ref.py`에는 업무 제약 "반영된 취소는 청구완료 거래에만 존재"가 빠져 있었다(불일치 2,667건, `indep_check_ref.log`). 구 열거기 `refval.py`도 같은 정의를 공유해 이를 잡지 못했다(`ref2_refval.log`의 3,036건은 구 열거기 쪽 결함).
- `src/ref2.py`: 위 제약을 추가한 판정기. 독립 열거기와 3,063,413건 불일치 0. 원본 `ref.py`는 수정하지 않았다.
- ref2 재실행 영향: 표1 주요 행(13.8~89.2), 245,280/43,668/128건, 단조성은 동일. Z 없는 X1 81.2→81.3, 표5 '미반영→반영 표시' 오차단 24.8→26.1(5%), 43.3→45.4(10%), 66.2→68.5(20%).
- `tests/test_id_equivalence.py`: 취소 ID 수준 전수 대조. X1-금액과 X1-ID 판정 불일치 0, X1-ID와 X2 불일치 355.
- `experiments/sensitivity.py`: 취소 이월 허용, 반송 상한, 금액 분포 민감도(7개 지표).
- 재실행 환경: Python 3.11.1과 3.14.8(같은 기계)에서 두 세트 모두 baseline과 차이 0. 다른 기계에서의 실행은 아직 없다.
- `tests/test_prop33b.py` (2026-10-14 추가): 명제 3.3(b) 분리. 금액 수준(b-1) 위반 0/26,352, ID 수준(b-2, 반영 후보 유일) 위반 0/3,372. (b-1) 전제를 만족해도 ID 수준에서 갈리는 경우 1,824건(예: A:1 미반영, B:1 반영, Z=1, B 재송신).
- `tests/test_coupling_219.py` (2026-10-14 추가): `thm2.py` 두 거래 표본(시드 3, 60,000건)의 예산 의존 차이 290건 = 한 거래만으로 갈림 71 + 공통 예산에서만 갈림(순수 결합) 219. 두 로그는 기존 baseline_v2 로그를 덮어쓰지 않고 새 파일로 추가했으며, v2 재실행 차이 0(`diff_v2_20261014_224340.txt`).
- S4 (2026-10-14 추가): `experiments/sensitivity_s4.py`, 판정기 `src/ref2id.py`(취소 레코드에 이벤트 ID, ref2는 수정하지 않음). 관측 수준 X1-금액·X1-ID·X2-금액·X2-ID, S1~S3과 같은 데이터(seed 2024, 1,000건)와 7개 지표. ID 추적 생성기 `make_case5_id`는 원 `make_case5`와 원장·파일 1,000/1,000 일치. 공격은 기존 13유형(42,668건)과 ID 3유형(유령 ID 998, 중복 ID 998, 기반영 취소 ID 재전송 379)을 따로 보고. `tests/test_ref2id_consistency.py`: ref2id와 별도 ID 판정식 13,764건 불일치 0.

## 저장소 배치와 이식성 (2026-10-14)
- 이 폴더는 `settlement-integrity-model` 저장소의 하위 폴더 `card-billing-integrity/`로 옮겼다. 실행은 이 폴더 안에서 한다(`python3 run_all.py ...`). 경로는 모두 `run_all.py` 위치 기준 상대 경로다.
- `run_all.py` 이식성 보완: 자식 프로세스에 `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`을 주고 로그를 UTF-8로 읽고 쓴다(Windows 기본 인코딩 cp949에서 한글 로그가 달라지는 문제 방지). diff 보고서에 비정상 종료(exit≠0) 작업 목록을 함께 적는다. 수정 후 두 세트 재실행 차이 0(`diff_20261014_233843.txt`, `diff_v2_20261014_234003.txt`).
- 해시 시드 독립성: 31개 작업 전부를 `PYTHONHASHSEED=777`로 실행해도 baseline과 같았다(실행기는 0으로 고정).
- `experiments/s4_breakdown.py`: S4 ID 공격 불일치의 유형별 분해(유령 ID 995/865, 중복 ID 3/3, 기반영 취소 ID 재전송 0).
- 논문 수치는 `run_all.py` 작업의 로그에서만 인용한다. 초기 탐색 스크립트는 공개판에 포함하지 않는다.
- `private/` (git 제외): 공개하지 않는 참고 자료와 연구용 판 기록. 공개·커밋하지 않는다.
- `conftest.py`: 저장소 루트에서 pytest를 실행할 때 이 폴더를 수집하지 않게 한다.
