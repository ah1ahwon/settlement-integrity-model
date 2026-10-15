"""명제(취소 ID 포함관계)의 거래별 비용 수준 전수 확인. 청구완료 거래 하나, 관측 Z 포함.
  mc_amt : X1-금액+Z  -> ref2.cancel_mc(K=LDBZX)
  mc_id  : X1-ID+Z    -> min_{P: a(P)=Z, P∩S=∅} |E\\P| - |S|
  mc_yamt: X2-금액    -> ref2.cancel_mc(K=LDBZY)
  mc_yid : X2-ID      -> |E\\R*| - |S| (S∩R*=∅일 때)
  None(불가능)은 무한대로 본다. 전역 판정은 거래별 최소 비용의 합을 예산과 비교하므로(ref2의 DP),
  거래별 최소 비용이 같으면 판정이 같고, 크거나 같으면 수락 집합이 포함된다.
확인: (1) mc_amt == mc_id   (2) mc_yid ≥ mc_id   (3) mc_yid ≥ mc_yamt ≥ mc_amt"""
import itertools
from collections import Counter
from ref2 import cancel_mc

INF = float('inf')
def v(x): return INF if x is None else x

def mc_id(S, ev, cum):
    n = len(ev); best = INF
    for r in range(n + 1):
        for P in itertools.combinations(range(n), r):
            if sum(ev[j][0] for j in P) == cum and not set(P) & set(S):
                best = min(best, n - r - len(S))
    return best

def main():
    n = 0; bad = Counter(); strict = Counter()
    for k in range(1, 6):
        for amts in itertools.combinations_with_replacement(range(1, 4), k):
            for flags in itertools.product([False, True], repeat=k):
                ev = list(zip(amts, flags)); cum = sum(a for a, f in ev if f)
                for r in range(k + 1):
                    for S in itertools.combinations(range(k), r):
                        Fi = [ev[j][0] for j in S]
                        a = v(cancel_mc(Fi, ev, cum, set('LDBZX')))
                        i = mc_id(S, ev, cum)
                        ya = v(cancel_mc(Fi, ev, cum, set('LDBZY')))
                        yi = INF if any(ev[j][1] for j in S) else sum(1 for _, f in ev if not f) - len(S)
                        n += 1
                        bad['(1) X1-금액 ≠ X1-ID'] += a != i
                        bad['(2) X2-ID < X1-ID'] += yi < i
                        bad['(3) X2-ID < X2-금액 또는 X2-금액 < X1-금액'] += yi < ya or ya < a
                        strict['X2-ID > X1-ID (정보 차이가 비용을 바꿈)'] += yi > i
                        strict['X2-ID > X2-금액 (같은 금액 미반영 건이 있는 반영 건 재전송)'] += yi > ya
    print('취소 ID 포함관계: 이벤트 1~5건, 금액 1..3, 반영 여부 전부, 보낸 ID 집합 전부 =', n, '건')
    for k_, c in bad.items(): print('  위반', k_, c)
    for k_, c in strict.items(): print('  엄격한 차이', k_, c)

if __name__ == '__main__': main()
