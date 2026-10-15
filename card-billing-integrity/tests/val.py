import random, itertools, sys
from m2 import *
def legit_set(led, K, c):
    mine = [i for i in led if led[i]['m'] == 0]
    D, B, Z = 'D' in K, 'B' in K, 'Z' in K
    opts = []
    for i in mine:
        s = led[i]['st']
        if not D: o = ['absent', 'send']
        elif s == 'U': o = ['send', 'absent']
        elif s == 'R' and B: o = ['send', 'absent']
        elif s == 'R' or s == 'C': o = ['absent'] if B else ['absent', 'send']
        opts.append(o)
    out = set()
    for ch in itertools.product(*opts):
        sent = {i for i, o in zip(mine, ch) if o == 'send'}
        if D:
            vs = {i: view_st(led, i, K) for i in mine}
            miss = sum(1 for i in mine if vs[i] in ('U', 'R') and i not in sent)
            rec = sum(1 for i in sent if vs[i] == 'C')
            if miss > c: continue
            if not B and rec > c: continue
        elig = [i for i in mine if (not D) or vs[i] != 'U' or i in sent]
        lim = {i: led[i]['amt'] - (led[i]['cum'] if Z else 0) for i in elig}
        m20 = []
        for i in elig:
            L = [()]
            for n_ in (1, 2, 3):
                for t_ in itertools.combinations_with_replacement(range(1, lim[i] + 1), n_):
                    if sum(t_) <= lim[i]: L.append(t_)
            m20.append(L)
        base = [(10, i, led[i]['amt']) for i in sent]
        for ch2 in itertools.product(*m20):
            r20 = [(20, i, a) for i, t in zip(elig, ch2) for a in t]
            if len(r20) > 6: continue
            out.add(norm((0, base + r20)))
    return out
if __name__ == '__main__':
    rng = random.Random(5); bad = 0; n = 0; stat = {}
    for t in range(40):
        c = rng.choice([1, 2]); led, F = make_case(rng, c, small=True)
        for k, _ in KSETS[1:]:
            K = set(k); LS = legit_set(led, K, c)
            assert norm(F) in LS, ('legit not in set', k)
            assert explainable(F, led, K, c), ('false reject', k)
            cand = [(kind, G) for kind, G in attacks(F, led, rng, small=True) if kind != '가맹점번호 치환']
            cand += [(a + '+' + b, G2) for a, G in cand[:6] for b, G2 in attacks(G, led, rng, small=True) if b != '가맹점번호 치환'][:30]
            for kind, G in cand:
                n += 1
                e = explainable(G, led, K, c); m = norm(G) in LS
                if e != m: bad += 1; print('MISMATCH', k, kind, G, 'explain', e, 'brute', m, led) if bad < 8 else None
    print('검증 건수', n, '불일치', bad)
