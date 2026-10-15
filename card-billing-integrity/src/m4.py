"""m2 확장: 취소 승인 이력 X1(승인사실만) / X2(승인+반영상태). 정당 20레코드는 승인된 미반영 취소에서만 나온다."""
import random, itertools, collections, copy
from collections import Counter
from m2 import *
import m2

def make_case4(rng, c):
    led, F = make_case(rng, c)
    rs10 = [r for r in F[1] if r[0] == 10]; sent = {i for _, i, _ in rs10}
    for i in led: led[i]['ev'] = []
    unc = []
    for i in led:
        if led[i]['m'] != 0: continue
        cum = led[i]['cum']
        if led[i]['st'] == 'C' and cum > 0:
            if cum >= 2 and rng.random() < .4:
                a = rng.randint(1, cum - 1); led[i]['ev'] += [(a, True), (cum - a, True)]
            else: led[i]['ev'] += [(cum, True)]
        if led[i]['st'] == 'C' or i in sent:
            rem = led[i]['amt'] - cum; k = rng.choice([0, 0, 1, 1, 2])
            if k == 1 and rem >= 1: evs = [rng.randint(1, rem)]
            elif k == 2 and rem >= 2:
                a = rng.randint(1, rem - 1); evs = [a, rng.randint(1, rem - a)]
            else: evs = []
            for a in evs: led[i]['ev'].append((a, False)); unc.append((i, a))
    rng.shuffle(unc); d = min(pick(rng, c), len(unc))
    sentc = unc[d:]
    rs = rs10 + [(20, i, a) for i, a in sentc]; rng.shuffle(rs)
    return led, (0, rs)

def extra_ok(F, led, K, c):
    """X1/X2 규칙. K에 'X'(승인만) 또는 'Y'(승인+반영상태)."""
    hm, rs = F
    if 'L' not in K or not ('X' in K or 'Y' in K): return True
    mine = [i for i in led if led[i]['m'] == hm]
    f20 = collections.defaultdict(list)
    for t, i, a in rs:
        if t == 20:
            if i not in led: return True   # 원장 규칙이 처리
            f20[i].append(a)
    S10 = {i for t, i, a in rs if t == 10}
    D = 'D' in K; miss = 0
    for i in set(mine) | set(f20):
        if i not in led or led[i]['m'] != hm: continue
        Fi = Counter(f20.get(i, [])); ev = led[i]['ev']
        elig = D and (view_st(led, i, K) == 'C' or (i in S10) ) if True else False
        if 'Y' in K:
            U = Counter(a for a, cl in ev if not cl)
            if Fi - U: return False
            if D and (view_st(led, i, K) == 'C' or i in S10): miss += sum((U - Fi).values())
        else:
            A = Counter(a for a, cl in ev)
            if Fi - A: return False
            if 'Z' in K:
                cum = led[i]['cum']; evl = [a for a, cl in ev]; best = None
                for r in range(len(evl) + 1):
                    for P in itertools.combinations(range(len(evl)), r):
                        if sum(evl[j] for j in P) != cum: continue
                        rest = Counter(evl[j] for j in range(len(evl)) if j not in P)
                        if Fi - rest: continue
                        m_ = sum((rest - Fi).values()); best = m_ if best is None else min(best, m_)
                if best is None: return False
                if D and (view_st(led, i, K) == 'C' or i in S10): miss += best
    return miss <= c

def explainable4(F, led, K, c):
    Kb = {k for k in K if k not in 'XY'}
    return explainable(F, led, Kb, c) and extra_ok(F, led, K, c)

def attacks4(F, led, rng):
    out = attacks(F, led, rng)
    hm, rs = F
    # 추가 유형: 청구 완료 취소 재전송(리플레이)
    for i in led:
        if led[i]['m'] != 0: continue
        cl = [a for a, c_ in led[i]['ev'] if c_]
        if cl:
            rem = led[i]['amt'] - led[i]['cum'] - sum(a for t, j, a in rs if t == 20 and j == i)
            if cl[0] <= rem: out.append(('취소 재전송(청구완료)', (hm, rs + [(20, i, cl[0])]))); break
    return out
