"""c(검증기 허용치) x p(실제 지연 확률) 분리. 기본 거래와 실제 지연을 먼저 고정하고 c만 사후에 변경."""
import random, itertools, statistics as st, collections, sys
from m4 import *
import m2
CS = [0, 1, 2, 3, 4, 5]
K = set('LDBZY')

def make_case5(rng, ps, pc):
    ids = list(range(1, 100)); rng.shuffle(ids)
    led = {}; A = lambda: rng.randint(10, 200)
    for _ in range(rng.randint(3, 6)): i = ids.pop(); led[i] = dict(m=0, amt=A(), st='U', cum=0, ev=[])
    for _ in range(rng.randint(2, 4)):
        i = ids.pop(); a = A(); led[i] = dict(m=0, amt=a, st='C', cum=rng.choice([0, 0, rng.randint(0, a - 1)]), ev=[])
    for _ in range(pick(rng, 2)): i = ids.pop(); led[i] = dict(m=0, amt=A(), st='R', cum=0, ev=[])
    for _ in range(2): i = ids.pop(); led[i] = dict(m=1, amt=A(), st=rng.choice('UC'), cum=0, ev=[])
    US = [i for i in led if led[i]['m'] == 0 and led[i]['st'] in 'UR']
    defer = {i for i in US if rng.random() < ps}
    sent = [i for i in US if i not in defer]
    rs = [(10, i, led[i]['amt']) for i in sent]; sset = set(sent)
    dc = 0
    for i in led:
        if led[i]['m'] != 0: continue
        cum = led[i]['cum']
        if led[i]['st'] == 'C' and cum > 0:
            if cum >= 2 and rng.random() < .4:
                a = rng.randint(1, cum - 1); led[i]['ev'] += [(a, True), (cum - a, True)]
            else: led[i]['ev'] += [(cum, True)]
        if led[i]['st'] == 'C' or i in sset:
            rem = led[i]['amt'] - cum; k = rng.choice([0, 0, 1, 1, 2])
            if k == 1 and rem >= 1: evs = [rng.randint(1, rem)]
            elif k == 2 and rem >= 2:
                a = rng.randint(1, rem - 1); evs = [a, rng.randint(1, rem - a)]
            else: evs = []
            for a in evs:
                led[i]['ev'].append((a, False))
                if rng.random() < pc: dc += 1
                else: rs.append((20, i, a))
    rng.shuffle(rs)
    return led, (0, rs), len(defer), dc

def run(ps, pc, N, seed):
    rng = random.Random(seed); rows = []
    for _ in range(N):
        led, F, ds, dc = make_case5(rng, ps, pc)
        rs = F[1]; i10 = [j for j, r in enumerate(rs) if r[0] == 10]; i20 = [j for j, r in enumerate(rs) if r[0] == 20]
        att = {}
        for typ, idx in (('거래삭제', i10), ('취소삭제', i20)):
            for k in (1, 2, 3):
                if len(idx) < k: continue
                combos = list(itertools.combinations(idx, k))
                if len(combos) > 12: combos = rng.sample(combos, 12)
                att[(typ, k)] = [(0, [r for j, r in enumerate(rs) if j not in S]) for S in combos]
        r = dict(ds=ds, dc=dc, n10=len(i10), n20=len(i20))
        for c in CS:
            r[('fr', c)] = not explainable4(F, led, K, c)
            for key, L in att.items():
                r[(key, c)] = [explainable4(G, led, K, c) for G in L]   # True = 미탐
        rows.append(r)
    return rows

def summarize(rows, name):
    print(f'\n== 지연 패턴 {name}')
    print('  c:            ' + ' '.join(f'{c:6d}' for c in CS))
    print('  정당 오차단%   ' + ' '.join(f'{100*sum(r[("fr", c)] for r in rows)/len(rows):6.1f}' for c in CS))
    for typ in ('거래삭제', '취소삭제'):
        for k in (1, 2, 3):
            vals = []
            for c in CS:
                tot = miss = 0
                for r in rows:
                    L = r.get(((typ, k), c))
                    if L: tot += len(L); miss += sum(L)
                vals.append(100 * (tot - miss) / tot if tot else float('nan'))
            print(f'  {typ} {k}건 탐지% ' + ' '.join(f'{v:6.1f}' for v in vals))
    # 실제 지연 건수별 (1건 삭제, 두 유형 합)
    print('  [실제 지연 건수(판매+취소)별 1건 삭제 탐지%]  c=' + ' / '.join(str(c) for c in (1, 2, 3)))
    for d in range(0, 5):
        sel = [r for r in rows if r['ds'] + r['dc'] == d]
        if len(sel) < 20: continue
        out = []
        for c in (1, 2, 3):
            tot = miss = 0
            for r in sel:
                for typ in ('거래삭제', '취소삭제'):
                    L = r.get(((typ, 1), c))
                    if L: tot += len(L); miss += sum(L)
            out.append(f'{100*(tot-miss)/tot:5.1f}' if tot else '  -  ')
        fr = [f'{100*sum(r[("fr", c)] for r in sel)/len(sel):4.0f}' for c in (1, 2, 3)]
        print(f'    지연 {d}건 (n={len(sel):4d}): 탐지 ' + ' / '.join(out) + '  | 오차단% ' + ' / '.join(fr))
    # 적응형: 최대 미탐 삭제 건수
    print('  [적응형] 공격자가 들키지 않고 지울 수 있는 최대 건수 평균 (거래+취소 각 최대 3건 탐색)')
    out = []
    for c in CS:
        ms = []
        for r in rows:
            m = 0
            for k in (1, 2, 3):
                ok = False
                for typ in ('거래삭제', '취소삭제'):
                    L = r.get(((typ, k), c))
                    if L and any(L): ok = True
                if ok: m = k
            ms.append(m)
        out.append(st.mean(ms))
    print('     ' + ' '.join(f'{v:6.2f}' for v in out))
    # 동일 오차단 허용치에서 최대 탐지율
    pts = []
    for c in CS:
        fr = sum(r[('fr', c)] for r in rows) / len(rows)
        tot = miss = 0
        for r in rows:
            for typ in ('거래삭제', '취소삭제'):
                L = r.get(((typ, 1), c))
                if L: tot += len(L); miss += sum(L)
        pts.append((c, fr * 100, 100 * (tot - miss) / tot))
    for lim in (1, 5, 10):
        ok = [p for p in pts if p[1] <= lim]
        b = max(ok, key=lambda p: p[2]) if ok else None
        print(f'  오차단 ≤{lim}%에서 최대 1건삭제 탐지: ' + (f'{b[2]:.1f}% (c={b[0]}, 오차단 {b[1]:.1f}%)' if b else '해당 c 없음'))

if __name__ == '__main__':
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    for p in (0.0, 0.05, 0.1, 0.2):
        print(f'\n######## 실제 지연 확률 p={p}')
        for name, ps, pc in (('균등(판매·취소 모두)', p, p), ('취소만', 0, p), ('판매만', p, 0)):
            if p == 0 and name != '균등(판매·취소 모두)': continue
            summarize(run(ps, pc, N, 17), name)
