"""독립 열거기(indep_world, 판정기 비의존)와 통일 판정기(ref_accept)의 전수 대조.
검증 범위: 가맹점 0의 거래 1~2건 + 타 가맹점 거래 1건, 승인금액 1..3, 관측 K 18종(L 포함), 업무 가정 A 5종.
후보 파일: 거래별 (매출 없음/정상 금액/틀린 금액) x (취소 금액 다중집합 크기 0..2) 전수 + 정당 파일 전부
          + 표본 파일에 유령 승인번호, 타 가맹점 거래, 매출 중복, 가맹점번호 치환을 더한 변형."""
import random, itertools
from collections import Counter
from indep_world import legit_files, event_lists, AMT_MAX
import os, importlib
ref_accept = importlib.import_module(os.environ.get("JUDGE", "ref2")).ref_accept

SEED = 11; LEDGERS = 60
KS = [set('L') | set(d) | set(z) | set(x) for d in ('', 'D', 'DB') for z in ('', 'Z') for x in ('', 'X', 'Y')]
AS = [(0, 0, 0), (1, 0, 1), (1, 1, 0), (2, 1, 1), (1, 2, 2)]
GHOST = 9

def make_ledger(rng):
    led = {}
    for i in range(1, rng.choice([1, 2]) + 1):
        amt = rng.randint(1, AMT_MAX); st = rng.choice('UCR')
        evs = [e for e in event_lists(amt) if st == 'C' or not any(f for _, f in e)]
        ev = list(rng.choice(evs)) if rng.random() < .8 else []
        led[i] = dict(m=0, amt=amt, st=st, cum=sum(a for a, f in ev if f), ev=ev)
    led[5] = dict(m=1, amt=rng.randint(1, AMT_MAX), st=rng.choice('UC'), cum=0, ev=[])
    return led

def candidates(led, rng, W):
    mine = sorted(i for i in led if led[i]['m'] == 0)
    ms20 = [()] + [(a,) for a in range(1, 4)] + [tuple(sorted(p)) for p in itertools.combinations_with_replacement(range(1, 4), 2)]
    per = []
    for i in mine:
        a = led[i]['amt']
        per.append([(s10, T) for s10 in (None, a, a % AMT_MAX + 1) for T in ms20])
    base = []
    for combo in itertools.product(*per):
        rec = []
        for i, (s10, T) in zip(mine, combo):
            if s10 is not None: rec.append((10, i, s10))
            rec += [(20, i, x) for x in T]
        base.append(tuple(sorted(rec)))
    C = {(0, f) for f in base} | set(W)
    for f in rng.sample(base, min(40, len(base))) + [f for _, f in W]:
        C.add((0, tuple(sorted(f + ((10, GHOST, 1),)))))
        C.add((0, tuple(sorted(f + ((10, 5, led[5]['amt']),)))))
        C.add((1, f))
        s = [r for r in f if r[0] == 10]
        if s: C.add((0, tuple(sorted(f + (s[0],)))))
    return C

def main():
    rng = random.Random(SEED); n = bad = 0; acc = Counter(); kinds = Counter(); ex = []
    for _ in range(LEDGERS):
        led = make_ledger(rng)
        for K in KS:
            for A in AS:
                W = legit_files(led, 0, K, A); W1 = legit_files(led, 1, K, A)
                for F in candidates(led, rng, W) | W1:
                    e = F in (W if F[0] == 0 else W1)
                    r = ref_accept((F[0], list(F[1])), led, K, A)
                    n += 1; acc[e] += 1
                    if e != r:
                        bad += 1; kinds[(''.join(sorted(K)), 'ref만 수락' if r else '열거만 수락')] += 1
                        if len(ex) < 5: ex.append((sorted(K), A, F, led))
    print('독립 열거기(판정기 비의존) vs ref_accept: 대조', n, '건, 불일치', bad)
    print('  열거기 기준 정당 파일', acc[True], '/ 비정당 파일', acc[False])
    for k, v in sorted(kinds.items()): print('  불일치 유형', k, v)
    for e in ex: print('  예', e)

if __name__ == '__main__': main()
