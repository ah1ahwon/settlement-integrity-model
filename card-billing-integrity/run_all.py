"""전체 재현 실행기. 기존 스크립트는 수정하지 않고 PYTHONPATH로 import 경로만 맞춘다.
  python3 run_all.py            # results/baseline 이 없을 때만 기준 로그 생성(있으면 거부)
  python3 run_all.py --rerun    # results/rerun_<시각>/ 에 새로 실행, baseline 은 덮어쓰지 않고 diff 를 results/diff_<시각>.txt 에 기록
  python3 run_all.py --set v2 [--rerun]   # 2차 세트(독립 열거기, 판정기 ref2, 민감도). 기준 로그는 results/baseline_v2"""
import os, sys, subprocess, time, platform, difflib, concurrent.futures as cf
ROOT = os.path.dirname(os.path.abspath(__file__))
JOBS = [  # (로그 이름, 스크립트 상대경로) -- 각 항목은 독립적으로 재현 가능
 ('refval',     'tests/refval.py'),        # 85,624 독립 열거 대조
 ('val_x',      'tests/val_x.py'),         # 162,000 취소 규칙 열거 대조
 ('val',        'tests/val.py'),           # 10,428 구 규칙 열거 대조
 ('thm2',       'tests/thm2.py'),          # 245,280 단일 거래 + 두 거래 결합
 ('thm',        'tests/thm.py'),           # 반송 이력 없는 조합(불일치 2,650의 원인 확인용)
 ('props',      'tests/props.py'),         # 구 규칙 단조성 위반 5,352
 ('cls',        'tests/cls.py'),           # 위반 원인 분해, CR 고정 후 10/5/0
 ('cls2',       'tests/cls2.py'),          # 잔여 위반 유형
 ('casecmp',    'tests/casecmp.py'),       # X1+Z vs X2 사례별 일치 43,668
 ('cex',        'tests/cex.py'),           # 최소 반례 판정표
 ('refeval',    'experiments/refeval.py'), # 통일 판정 단조성 114,426 / 1,155,690 + 표 재계산
 ('final_ref',  'experiments/final_ref.py'),# 고정 실험 42,668 공격, 표1~5 (기존/새)
 ('run8',       'experiments/run8.py'),    # 누계 모호성
 ('sim_batch',  'experiments/sim_batch.py'),# 독립 생성기(일별 배치)
 ('legacy_final','experiments/legacy/final.py'), # 구 판정 고정 결과(표1~5 원본)
 ('budget_only','tests/test_budget_only_minimal.py'), # 예산 차이 128건 최소 테스트
]
SHIM = 'variants/ref2_shim'   # 기존 스크립트를 수정하지 않고 판정기만 ref2로 바꾸는 대체 모듈 경로
JOBS_V2 = [  # (로그 이름, 스크립트, 추가 환경)
 ('indep_check_ref2', 'tests/indep_check.py', {'JUDGE': 'ref2'}),   # 판정기 비의존 열거기 vs ref2: 3,063,413건
 ('indep_check_ref',  'tests/indep_check.py', {'JUDGE': 'ref'}),    # 같은 대조를 원 판정기로: 불일치 2,667(발견 기록)
 ('id_equivalence',   'tests/test_id_equivalence.py', {}),          # 취소 ID 수준 전수 대조
 ('id_chain',         'tests/test_id_chain.py', {}),                # 명제: X2-ID ⊆ X1-ID+Z = X1-금액+Z (거래별 비용 26,092건)
 ('sensitivity',      'experiments/sensitivity.py', {}),            # ④ 민감도 S1~S3
 ('ref2_final_ref',   'experiments/final_ref.py', {'SHIM': 1}),     # 고정 실험을 ref2로 재실행
 ('ref2_refeval',     'experiments/refeval.py', {'SHIM': 1}),       # 단조성을 ref2로 재확인
 ('ref2_thm2',        'tests/thm2.py', {'SHIM': 1}),
 ('ref2_casecmp',     'tests/casecmp.py', {'SHIM': 1}),
 ('ref2_budget_only', 'tests/test_budget_only_minimal.py', {'SHIM': 1}),
 ('ref2_refval',      'tests/refval.py', {'SHIM': 1}),              # 구 열거기(view_set 공유)와 ref2의 차이 기록
 ('prop33b',          'tests/test_prop33b.py', {}),                 # 명제 3.3(b) 금액 수준(b-1)/ID 수준(b-2) 분리
 ('coupling_219',     'tests/test_coupling_219.py', {}),            # 290건 = 거래별 71 + 순수 결합 219
 ('ref2id_consistency', 'tests/test_ref2id_consistency.py', {}),   # S4 ID 판정기 vs 별도 ID 판정식 13,764건
 ('sensitivity_s4',   'experiments/sensitivity_s4.py', {}),         # ④ 민감도 S4: 식별자·반영 상태 관측 수준
 ('s4_breakdown',     'experiments/s4_breakdown.py', {}),           # S4 ID 공격 불일치의 유형별 분해
 ('falseblock_cause', 'tests/test_falseblock_cause.py', {}),        # 정상 파일 거절 원인(가정 초과) 분해, 취소 단독 레코드 확인
 ('coupling_219_bounds', 'tests/test_coupling_219_bounds.py', {}),  # 219 분류 경계조건: 조합/표본 수, X2 정의, 판정 패턴
 ('s4_conditional',   'experiments/s4_conditional.py', {}),         # S4 ID 공격: 바탕 파일 수락 조건부 탐지율
 ('conditional_detection', 'experiments/conditional_detection.py', {}), # 모든 표의 탐지율: 전체 거절률 T와 조건부 탐지율 C
 ('coupling_219_multiplicity', 'tests/test_coupling_219_multiplicity.py', {}), # 290/219의 표본 중복, 판정 방향, 71조합 패턴
 ('ref2_cex',         'tests/test_counterexamples_ref2.py', {}),    # 반례 표 ref2 판, 반례 3.1 예산형·3.2 포함관계형
 ('ledger_invariance', 'tests/test_attack_ledger_invariance.py', {}), # 위협 모델 T1: 공격 생성기가 원장을 바꾸지 않음
 ('ref2id_cex',       'tests/test_counterexamples_id.py', {}),     # 반례 3.1·3.2와 ID 식별력 사례의 네 관측 수준 판정
]
def run(job, outdir):
    name, path = job[:2]; extra = dict(job[2]) if len(job) > 2 else {}
    dirs = ([SHIM] if extra.pop('SHIM', None) else []) + ['src','tests','experiments','experiments/legacy']
    env = dict(os.environ, PYTHONHASHSEED='0', PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONPATH=os.pathsep.join(os.path.join(ROOT, d) for d in dirs), **extra)
    t = time.time()
    p = subprocess.run([sys.executable, os.path.join(ROOT, path)], cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8')
    with open(os.path.join(outdir, name + '.log'), 'w', encoding='utf-8') as f:
        f.write(p.stdout)
        if p.stderr: f.write('\n[stderr]\n' + p.stderr)
    return name, p.returncode, time.time() - t
def main():
    rerun = '--rerun' in sys.argv
    v2 = '--set' in sys.argv and sys.argv[sys.argv.index('--set') + 1] == 'v2'
    jobs = JOBS_V2 if v2 else JOBS; tag = '_v2' if v2 else ''
    res = os.path.join(ROOT, 'results'); base = os.path.join(res, 'baseline' + tag)
    ts = time.strftime('%Y%m%d_%H%M%S')
    if rerun:
        out = os.path.join(res, 'rerun' + tag + '_' + ts)
    else:
        out = base
        if os.path.isdir(base) and any(n.endswith('.log') for n in os.listdir(base)):
            sys.exit('baseline 이 이미 있다. 덮어쓰지 않는다. 다시 실행하려면 --rerun')
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'environment.txt'), 'w', encoding='utf-8') as f:
        f.write(f'python {platform.python_version()}\nplatform {platform.platform()}\nPYTHONHASHSEED 0\ndate {ts}\n')
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        rcs = {}
        for name, rc, sec in ex.map(lambda j: run(j, out), jobs):
            rcs[name] = rc; print(f'{name:14s} exit={rc} {sec:6.1f}s')
    if rerun:  # baseline 과 비교해 차이를 기록
        rep = os.path.join(res, 'diff' + tag + '_' + ts + '.txt'); nd = 0
        with open(rep, 'w', encoding='utf-8') as f:
            for name, *_ in jobs:
                a = os.path.join(base, name + '.log'); b = os.path.join(out, name + '.log')
                if not os.path.exists(a): f.write(f'[{name}] baseline 없음\n'); nd += 1; continue
                da = open(a, encoding='utf-8').read().splitlines(); db = open(b, encoding='utf-8').read().splitlines()
                d = list(difflib.unified_diff(da, db, 'baseline' + tag + '/' + name, 'rerun/' + name, lineterm=''))
                if d: nd += 1; f.write('\n'.join(d) + '\n')
            bad = [n for n, rc in rcs.items() if rc != 0]
            f.write(f'\n차이가 있는 로그 {nd}개\n비정상 종료 {len(bad)}개 {bad}\n')
        print('diff 보고서:', rep, '| 차이 있는 로그', nd)
if __name__ == '__main__': main()
