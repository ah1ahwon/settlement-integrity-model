"""X 규칙(extra_ok)의 독립 전수 검증: 정당 과정을 직접 열거(이벤트 식별자 e0,e1.. 유지)해서 규칙 판정과 대조.
정당 과정: 거래별로 (반영 상태 할당: 수신측 관측과 일치하는 모든 것) x (미반영 승인 취소 중 일부를 송신, 나머지는 이월) ; 이월 총합 <= c."""
import itertools, random, collections
from collections import Counter
from m4 import extra_ok

def legit_Fi(events, K):
    """한 거래의 events=[(eid,amt,claimed_true)] 에 대해, 관측 K에서 가능한 {송신 금액 다중집합: 최소 이월 건수}."""
    n = len(events); cum = sum(a for _, a, c in events if c)
    res = {}
    for claim in itertools.product([0, 1], repeat=n):
        if 'Y' in K:
            if any(bool(cl) != ev[2] for cl, ev in zip(claim, events)): continue
        elif 'Z' in K:
            if sum(ev[1] for cl, ev in zip(claim, events) if cl) != cum: continue
        unc = [ev for cl, ev in zip(claim, events) if not cl]
        for r in range(len(unc) + 1):
            for T in itertools.combinations(unc, r):
                key = tuple(sorted(ev[1] for ev in T)); miss = len(unc) - r
                if key not in res or miss < res[key]: res[key] = miss
    return res

def brute(files, events_by_txn, K, c):
    tabs = [legit_Fi(events_by_txn[i], K) for i in sorted(events_by_txn)]
    ids = sorted(events_by_txn)
    # 파일을 거래별 다중집합으로 분해
    f_i = {i: tuple(sorted(a for t, j, a in files if t == 20 and j == i)) for i in ids}
    tot = 0
    for i, tab in zip(ids, tabs):
        if f_i[i] not in tab: return False
        tot += tab[f_i[i]]
    return tot <= c

def main():
    rng = random.Random(1); bad = 0; n = 0; stat = Counter()
    for trial in range(300):
        ntx = rng.choice([1, 2]); led = {}; evs = {}
        for i in range(1, ntx + 1):
            ev = []
            for k in range(rng.randint(1, 4)):
                ev.append((f'e{i}_{k}', rng.randint(1, 5), rng.random() < .5))
            cum = sum(a for _, a, c in ev if c)
            led[i] = dict(m=0, amt=sum(a for _, a, c in ev) + rng.randint(0, 3), st='C', cum=cum, ev=[(a, c) for _, a, c in ev])
            evs[i] = ev
        led[99] = dict(m=1, amt=5, st='C', cum=0, ev=[])
        # 후보 파일: 각 거래 20-레코드 다중집합(금액 1..5, 최대 4건) 전수의 무작위 표본 + 실제 부분집합
        cands = []
        for _ in range(60):
            rs = []
            for i in led:
                if led[i]['m'] != 0: continue
                k = rng.randint(0, 4)
                rs += [(20, i, rng.randint(1, 5)) for _ in range(k)]
            cands.append(rs)
        for i in led:
            if led[i]['m'] != 0: continue
        for rs in cands:
            for K in ({'L', 'D', 'Y'}, {'L', 'D', 'Z', 'X'}, {'L', 'D', 'X'}):
                for c in (0, 1, 2):
                    e = extra_ok((0, rs), led, K, c)
                    # 거래별 동일 금액 이벤트는 식별자만 다름: brute는 식별자 유지
                    b = brute(rs, {i: evs[i] for i in evs}, K, c)
                    n += 1; stat[(''.join(sorted(K)), e)] += 1
                    if e != b:
                        bad += 1
                        if bad <= 5: print('MISMATCH', K, c, rs, led, 'rule', e, 'brute', b)
    print('검증 건수', n, '불일치', bad)
    for k, v in sorted(stat.items()): print(' ', k, v)
main()
