"""카드 청구 파일 모델 재실험. 매출(10)/취소(20) 레코드, 신뢰정보 L(승인원장) Z(취소누계) D(청구일자) B(반송이력)."""
import random, itertools, sys, statistics as st

# ---------- 모델 ----------
# ledger: id -> dict(m, amt, st in U/C/R, cum)   U=미청구 C=청구완료 R=반송(재청구 대상)
# file: (hdr_m, [(typ,id,amt)...])  typ 10 매출, 20 취소

def view_st(led, i, K):
    s = led[i]['st']
    if s == 'U': return 'U' if 'D' in K else None
    if 'D' not in K: return None
    return 'R' if ('B' in K and s == 'R') else 'C'

def atoms(F, led, K, c):
    """원자 규칙별 통과 여부 dict. 정보가 없으면 통과(True)."""
    hm, rs = F
    r10 = [(i, a) for (t, i, a) in rs if t == 10]
    r20 = [(i, a) for (t, i, a) in rs if t == 20]
    ids10 = [i for i, _ in r10]
    out = {}
    out['내부:10승인번호중복없음'] = len(ids10) == len(set(ids10))
    s20 = {}
    for i, a in r20: s20[i] = s20.get(i, 0) + a
    out['내부:20합≤같은파일10'] = all(s20[i] <= dict(r10)[i] for i in s20 if i in dict(r10))
    if 'L' not in K:
        for n in ['원장:승인번호존재', '원장:가맹점일치', '원장:10금액=승인금액', '원장:20누적≤한도',
                  '청구:20대상은청구됨', '청구:미청구누락≤c', '청구:재청구건수≤c', '반송:재청구는반송건만']:
            out[n] = True
        return out
    allids = ids10 + [i for i, _ in r20]
    out['원장:승인번호존재'] = all(i in led for i in allids)
    ok = out['원장:승인번호존재']
    out['원장:가맹점일치'] = ok and all(led[i]['m'] == hm for i in allids)
    out['원장:10금액=승인금액'] = ok and all(led[i]['amt'] == a for i, a in r10)
    lim = lambda i: led[i]['amt'] - (led[i]['cum'] if 'Z' in K else 0)
    out['원장:20누적≤한도'] = ok and all(s20[i] <= lim(i) for i in s20)
    if 'D' not in K:
        for n in ['청구:20대상은청구됨', '청구:미청구누락≤c', '청구:재청구건수≤c', '반송:재청구는반송건만']:
            out[n] = True
        return out
    S10 = set(ids10)
    out['청구:20대상은청구됨'] = ok and all(view_st(led, i, K) != 'U' or i in S10 for i in s20)
    mine = [i for i in led if led[i]['m'] == hm]
    miss = [i for i in mine if view_st(led, i, K) in ('U', 'R') and i not in S10]
    out['청구:미청구누락≤c'] = len(miss) <= c
    if 'B' in K:
        out['청구:재청구건수≤c'] = True
        out['반송:재청구는반송건만'] = ok and all(view_st(led, i, K) != 'C' for i in ids10)
    else:
        out['청구:재청구건수≤c'] = ok and sum(1 for i in ids10 if view_st(led, i, K) == 'C') <= c
        out['반송:재청구는반송건만'] = True
    return out

def explainable(F, led, K, c):
    return all(atoms(F, led, K, c).values())

# ---------- 정당 파일 생성 ----------
def wts(c): return {0: [1], 1: [5, 5], 2: [4, 4, 2], 3: [4, 3, 2, 1]}[c]
def pick(rng, c): return rng.choices(range(c + 1), weights=wts(c))[0]

def make_case(rng, c, small=False):
    ids = list(range(1, 100)); rng.shuffle(ids)
    led = {}
    A = (lambda: rng.randint(1, 3)) if small else (lambda: rng.randint(10, 200))
    nU = rng.randint(1, 2) if small else rng.randint(3, 6)
    nC = rng.randint(1, 2) if small else rng.randint(2, 4)
    nR = min(pick(rng, c), 1) if small else pick(rng, c)
    for k in range(nU): i = ids.pop(); led[i] = dict(m=0, amt=A(), st='U', cum=0)
    for k in range(nC):
        i = ids.pop(); a = A(); led[i] = dict(m=0, amt=a, st='C', cum=rng.choice([0, 0, rng.randint(0, a - 1)]))
    for k in range(nR): i = ids.pop(); led[i] = dict(m=0, amt=A(), st='R', cum=0)
    for k in range(1 if small else 2): i = ids.pop(); led[i] = dict(m=1, amt=A(), st=rng.choice('UC'), cum=0)
    U = [i for i in led if led[i]['m'] == 0 and led[i]['st'] in 'UR']
    rng.shuffle(U); d = min(pick(rng, c), len(U) - 1)
    defer = set(U[:d])
    rs = [(10, i, led[i]['amt']) for i in led if led[i]['m'] == 0 and led[i]['st'] in 'UR' and i not in defer]
    sent = {i for (_, i, _) in rs}
    rem = {i: led[i]['amt'] - led[i]['cum'] for i in led if led[i]['m'] == 0 and (led[i]['st'] == 'C' or i in sent)}
    for _ in range(rng.choice([0, 1, 1, 2])):
        cand = [i for i in rem if rem[i] > 0 and not (led[i]['st'] == 'R' and False)]
        if not cand: break
        i = rng.choice(cand); a = rng.randint(1, rem[i]); rem[i] -= a; rs.append((20, i, a))
    rng.shuffle(rs)
    return led, (0, rs)

# ---------- 공격 ----------
def attacks(F, led, rng, small=False):
    """유형별 단일 변조 목록 [(유형, 새파일)]"""
    hm, rs = F
    A = (lambda: rng.randint(1, 3)) if small else (lambda: rng.randint(1, 200))
    out = []
    mine = [i for i in led if led[i]['m'] == 0]
    other = [i for i in led if led[i]['m'] != 0]
    free = [x for x in range(1, 100) if x not in led]
    sent = {i for (t, i, a) in rs if t == 10}
    def add(k, nrs, nh=None): out.append((k, (hm if nh is None else nh, nrs)))
    for j, (t, i, a) in enumerate(rs):
        add('거래 삭제' if t == 10 else '취소 삭제', rs[:j] + rs[j + 1:])
        v = rng.choice([x for x in (range(1, 4) if small else range(1, 201)) if x != a])
        add('금액 변경(10)' if t == 10 else '금액 변경(20)', rs[:j] + [(t, i, v)] + rs[j + 1:])
        add('구분 변경(10↔20)', rs[:j] + [(30 - t, i, a)] + rs[j + 1:])
        if t == 10 and a >= 2 and free:
            a1 = rng.randint(1, a - 1); add('거래 분할(새 승인번호)', rs[:j] + [(10, i, a1), (10, rng.choice(free), a - a1)] + rs[j + 1:])
    paid = [i for i in mine if led[i]['st'] == 'C']
    if paid:
        i = rng.choice(paid); add('중복 청구 삽입(10)', rs + [(10, i, led[i]['amt'])])
    rem = {i: led[i]['amt'] - led[i]['cum'] - sum(a for (t, j, a) in rs if t == 20 and j == i) for i in mine}
    ok20 = [i for i in mine if rem[i] >= 1 and (led[i]['st'] == 'C' or i in sent)]
    if ok20:
        i = rng.choice(ok20); add('위조 취소 삽입(한도 이내)', rs + [(20, i, rng.randint(1, rem[i]))])
    if mine:
        i = rng.choice(mine); add('위조 취소 삽입(한도 초과)', rs + [(20, i, max(rem[i], 0) + rng.randint(1, 3 if small else 50))])
    if free: add('유령 거래 삽입', rs + [(10, rng.choice(free), A())])
    if other:
        i = rng.choice(other); add('타 가맹점 거래 삽입', rs + [(10, i, led[i]['amt'])])
    add('가맹점번호 치환', rs, nh=1)
    return [(k, f) for k, f in out if f != F or k == '가맹점번호 치환']

def norm(F): return (F[0], tuple(sorted(F[1])))

# ---------- 본 실험 ----------
KSETS = [('', ''), ('L', 'L'), ('LZ', 'LZ'), ('LD', 'LD'), ('LDZ', 'LDZ'), ('LDB', 'LDB'), ('LDBZ', 'LDBZ')]
KNAME = {'': '없음(내부 규칙만)', 'L': '승인 원장', 'LZ': '원장+취소누계', 'LD': '원장+청구일자', 'LDZ': '원장+청구일자+취소누계',
         'LDB': '원장+청구일자+반송이력', 'LDBZ': '원장+청구일자+반송이력+취소누계'}
def sim(seed, c, ncase=300):
    rng = random.Random(seed)
    res = {}; fr = {k: 0 for k, _ in KSETS}; tot = 0; nexc = 0
    for _ in range(ncase):
        led, F = make_case(rng, c)
        nexc += sum(1 for i in led if led[i]['m'] == 0 and led[i]['st'] == 'R')
        for k, _ in KSETS:
            if not explainable(F, led, set(k), c): fr[k] += 1
        for kind, G in attacks(F, led, rng):
            tot += 1
            for k, _ in KSETS:
                b = not explainable(G, led, set(k), c)
                d = res.setdefault((k, kind), [0, 0]); d[0] += b; d[1] += 1
    return res, fr, tot

if __name__ == '__main__':
    pass
