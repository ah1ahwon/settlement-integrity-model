"""명제 3.3(b) 분리 확인(단일 거래, 청구완료 C, Z 관측). 판정기 ref2는 금액 수준(파일 취소 레코드에 ID 없음).
  (b-1) 금액 수준: 모든 반영 후보 P(합 = Z)가 같은 미반영 금액 다중집합을 남기면
        X1+Z(금액) 판정 = X2(금액) 판정   -> ref2 K=LDBZX vs K=LDBZY
  (b-2) ID 수준: 반영 후보 색인 집합이 하나뿐이면 X1-ID+Z 판정 = X2-ID 판정
  반례 계수: (b-1) 전제를 만족해도 ID 수준에서는 판정이 갈리는 경우(예: A:1, B:1, Z=1, 실제 반영 {A}, 파일이 A 재송신)."""
import itertools
from collections import Counter
from ref2 import cancel_mc

def cands(ev, cum):
    n = len(ev)
    return [P for r in range(n + 1) for P in itertools.combinations(range(n), r) if sum(ev[j][0] for j in P) == cum]

def acc(m, cc): return m is not None and m <= cc

def main():
    c = Counter(); ex = None
    for k in range(1, 5):
        for amts in itertools.combinations_with_replacement(range(1, 4), k):
            for flags in itertools.product([False, True], repeat=k):
                ev = list(zip(amts, flags)); cum = sum(a for a, f in ev if f)
                Ps = cands(ev, cum)
                same_ms = len({tuple(sorted(ev[j][0] for j in range(k) if j not in P)) for P in Ps}) == 1
                uniq = len(Ps) == 1
                n_unref = sum(1 for _, f in ev if not f)
                for cc in range(3):
                    # (b-1) 금액 수준: 파일 취소 금액 다중집합 전부(크기 0..k)
                    for r in range(k + 1):
                        for T in itertools.combinations_with_replacement(range(1, 4), r):
                            a = acc(cancel_mc(list(T), ev, cum, set('LDBZX')), cc)
                            y = acc(cancel_mc(list(T), ev, cum, set('LDBZY')), cc)
                            if same_ms: c['(b-1) 전제 충족 금액 사례'] += 1; c['(b-1) 위반'] += a != y
                    # ID 수준: 보낸 ID 집합 S 전부
                    for r in range(k + 1):
                        for S in itertools.combinations(range(k), r):
                            xi = any(not set(P) & set(S) and k - len(P) - r <= cc for P in Ps)
                            yi = not any(ev[j][1] for j in S) and n_unref - r <= cc
                            if uniq: c['(b-2) 전제 충족 ID 사례'] += 1; c['(b-2) 위반'] += xi != yi
                            if same_ms and xi != yi:
                                c['(b-1) 전제 충족이나 ID 수준에서 갈림'] += 1
                                if ex is None: ex = (ev, cum, S, cc, xi, yi)
    print('명제 3.3(b) 분리 확인: 이벤트 1~4건, 금액 1..3, 이월 허용 0..2')
    for key in ['(b-1) 전제 충족 금액 사례', '(b-1) 위반', '(b-2) 전제 충족 ID 사례', '(b-2) 위반', '(b-1) 전제 충족이나 ID 수준에서 갈림']:
        print(f'  {key}: {c[key]}')
    if ex: print('  ID 수준 반례 예: 이벤트(금액,반영)', ex[0], '누계', ex[1], '보낸 ID 색인', ex[2], '허용', ex[3], 'X1-ID+Z', ex[4], 'X2-ID', ex[5])

if __name__ == '__main__': main()
