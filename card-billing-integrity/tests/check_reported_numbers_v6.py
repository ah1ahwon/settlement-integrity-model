"""v6 금액 실험(amount_deletion.json)이 논문 4.5.9절·표 4-18·4-19·부록 B에 보고한 수치와 일치하는지 대조한다.
원고를 직접 읽거나 실험을 재실행하지 않는다. 비율은 원고와 같은 자릿수로 반올림해 비교한다.
사용: python3 tests/check_reported_numbers_v6.py [amount_deletion.json 경로]  (기본: results/review_v6/amount_deletion.json)"""
import json, os, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'results', 'review_v6', 'amount_deletion.json')
R = json.load(open(PATH))
E1, E2 = R['e1'], R['e2']
r1 = lambda x: round(x + 1e-12, 1)

# 표 4-18: cc -> (대상 원본, 최대 삭제 비율 평균, 중앙값, 무작위 기대 비율 평균, 전액 삭제 가능 원본 %)
T418 = {0: (526, 0.0, 0.0, 0.0, 0.0), 1: (847, 28.3, 31.9, 13.6, 0.9), 2: (946, 55.2, 57.8, 31.4, 4.9),
        3: (975, 74.0, 76.8, 49.0, 12.1), 4: (977, 86.2, 90.2, 65.2, 24.9), 5: (977, 93.1, 97.5, 77.9, 40.7)}
# 표 4-19: cs -> (수락 공격, 원본 수락 공격, 순금액 평균, 중앙값, 파일 매출 대비 %), 표 4-17 거절 수
T419 = {0: (0, 3089, None, None, None), 1: (3089, 4482, 72.0, 58, 13.1), 2: (4482, 4778, 71.9, 59, 13.7),
        3: (4778, 4809, 71.7, 58, 13.9), 4: (4809, 4809, 71.7, 58, 14.0)}
T417_REJ = {0: 3089, 1: 1393, 2: 296, 3: 31, 4: 0}

CHK = []
def check(desc, ok): CHK.append((desc, bool(ok)))

for cc, (n, mean, med, rnd, full) in T418.items():
    v = E1[str(cc)]
    check(f'표 4-18 cc={cc} 대상 {n}', v['files'] == n)
    check(f'표 4-18 cc={cc} 평균 {mean}', r1(v['x2_mean_ratio']) == mean)
    check(f'표 4-18 cc={cc} 중앙값 {med}', r1(v['x2_median_ratio']) == med)
    check(f'표 4-18 cc={cc} 무작위 기대 {rnd}', r1(v['random_mean_ratio']) == rnd)
    check(f'표 4-18 cc={cc} 전액 {full}', r1(v['x2_full']) == full)
check('4.5.9 큰 금액 우선/무작위 1.64배(cc=3)', round(E1['3']['greedy_over_random'], 2) == 1.64)
check('4.5.9 X1+Z 최대 금액이 더 큰 파일 조건별 0~4개', {E1[str(c)]['x1_gt_x2'] for c in range(6)} <= set(range(5))
      and min(E1[str(c)]['x1_gt_x2'] for c in range(6)) == 0 and max(E1[str(c)]['x1_gt_x2'] for c in range(6)) == 4)
check('4.5.9 cc=2 X2 55.2 · X1+Z 55.3', r1(E1['2']['x2_mean_ratio']) == 55.2 and r1(E1['2']['x1_mean_ratio']) == 55.3)
check('부록 B 큰 금액 우선 삭제 5,360건 위반 0', R['e1_checks']['greedy'] == 5360 and R['e1_violations'].get('greedy', 0) == 0)
check('부록 B 수락 삭제 조합 194,045건 공식 초과 0', R['e1_checks']['subset'] == 194045 and R['e1_violations'].get('subset', 0) == 0)
check('부록 B 최대값 미도달 파일 0', R['e1_violations'].get('exact', 0) == 0)
check('부록 B 10건 초과 cc=3 20개 평균 57.0%', E1['3']['files_gt10'] == 20 and r1(E1['3']['gt10_x2_mean_ratio']) == 57.0)
check('6.1 RQ3 cc=3 대상 975개 평균 74.0%', E1['3']['files'] == 975 and r1(E1['3']['x2_mean_ratio']) == 74.0)

for cs, (acc, den, mean, med, share) in T419.items():
    v = E2[str(cs)]
    check(f'표 4-19 cs={cs} {acc}/{den}', v['accepted'] == acc and v['attacks'] == den)
    check(f'표 4-17 cs={cs} 거절 {T417_REJ[cs]}', v['rejected'] == T417_REJ[cs])
    if mean is not None:
        check(f'표 4-19 cs={cs} 순금액 평균 {mean} 중앙 {med} 비율 {share}',
              r1(v['net_mean']) == mean and v['net_median'] == med and r1(v['share_mean']) == share)
    check(f'부록 B cs={cs} 따름정리 3.3 불일치 0·X1+Z 동일', v['formula_mismatch'] == 0 and v['x1z_same'] == v['formula_checks'])

fail = [d for d, ok in CHK if not ok]
for d, ok in CHK: print(('PASS ' if ok else 'FAIL ') + d)
print(f'\n{os.path.relpath(PATH, ROOT)}\n{len(CHK)}항목, FAIL {len(fail)}')
sys.exit(1 if fail else 0)
