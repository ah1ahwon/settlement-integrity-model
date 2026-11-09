"""② 공격자의 취소 삭제 여유(따름정리 후보)의 유한 검사. 판정기 ref3, 데이터 sensitivity.build('orig')와 S4의 build_id(seed 2024, 정상 1,000건).
전제: K가 L·D·B와 X2를 포함(관측이 모든 거래의 상태와 반영 집합을 고정), 원본 F가 같은 K·A에서 수락, 공격은 취소 레코드만 d건 삭제.
주장: 삭제 파일 수락 ⇔ N_act(F) + d ≤ c_c. N_act(F)는 송신 자격이 있는 거래(청구완료이거나 이번에 매출을 보낸 거래)의
      미반영 취소 중 F에 없는 건수이며, 판정기와 별개로 원장과 파일에서 직접 센다. 따라서 들키지 않는 최대 삭제 건수는 c_c − N_act(F)이고,
      어떤 취소를 지우는지와 무관하다.
검사: 취소 레코드가 10건 이하이면 모든 삭제 부분집합, 초과하면 고정 시드 표본 512개. A=(2,3,c_c), c_c=0~5.
전제를 뺀 대조(단정하지 않고 불일치 수만 기록): B 없음(L+D+Z+X2), 반영 이력 없음(X1+Z). 원본은 X2에서 수락된 파일로 한정한다.
X1+Z는 명제 3.1에 따라 X2보다 삭제 여유가 작을 수 없으며, 실제로 더 큰 파일 수를 센다."""
import itertools, random
from collections import Counter
from ref3 import ref_accept, ref_accept_id
from sensitivity import build
from sensitivity_s4 import build_id

CCS = range(6)
FULL = [('X2 금액', set('LDBZY'), False), ('X2 금액(Z 미보유)', set('LDBY'), False), ('X2-ID', set('LDBZY'), True)]
CONTRAST = [('B 없음 L+D+Z+X2', set('LDZY')), ('X1+Z', set('LDBZX'))]


def n_act(F, led):
    sent = {r[1] for r in F[1] if r[0] == 10}
    fc = Counter(r[1] for r in F[1] if r[0] == 20)
    return sum(sum(not f for _, f in v['ev']) - fc[i] for i, v in led.items()
               if v['m'] == F[0] and (v['st'] == 'C' or i in sent))


def subsets(idx, rng):
    if len(idx) <= 10:
        for r in range(len(idx) + 1): yield from itertools.combinations(idx, r)
    else:
        yield ()
        for _ in range(512): yield tuple(sorted(rng.sample(idx, rng.randint(1, len(idx)))))


def delete(F, S):
    return (F[0], [r for j, r in enumerate(F[1]) if j not in S])


def main():
    rng = random.Random(20261026)
    amount = [(led, F) for led, F, _ in build('orig')]
    ids = [(led, F) for led, F, _, _ in build_id()[0]]
    chk = Counter(); bad = Counter(); lenient = Counter(); big = 0
    budget = {cc: Counter() for cc in CCS}
    for (led, F), (led_i, F_i) in zip(amount, ids):
        assert led == led_i
        idx = [j for j, r in enumerate(F[1]) if r[0] == 20]
        big += len(idx) > 10
        subs = list(subsets(idx, rng))
        na = n_act(F, led); assert na == n_act(F_i, led)
        for cc in CCS:
            A = (2, 3, cc)
            for nm, K, use_id in FULL:
                G0, acc = (F_i, ref_accept_id) if use_id else (F, ref_accept)
                if not acc(G0, led, K, A): continue
                assert na <= cc
                for S in subs:
                    chk[nm] += 1
                    bad[nm] += acc(delete(G0, S), led, K, A) != (na + len(S) <= cc)
            # 대조는 X2 전제의 원본(같은 A에서 X2 수락)으로 한정해 삭제 효과만 비교한다.
            if ref_accept(F, led, set('LDBZY'), A):
                for nm, K in CONTRAST:
                    for S in subs:
                        chk[nm] += 1
                        got, want = ref_accept(delete(F, S), led, K, A), na + len(S) <= cc
                        bad[nm] += got != want; lenient[nm] += got and not want
            # 공격자 관점의 요약: 원본이 X2에서 수락되고 취소 레코드가 1~10건인 파일(X1+Z 최대값은 전수 탐색이 필요)
            if 0 < len(idx) <= 10 and ref_accept(F, led, set('LDBZY'), A):
                b = budget[cc]; b['files'] += 1
                x2 = min(cc - na, len(idx))
                x1 = max(len(S) for S in subs if ref_accept(delete(F, S), led, set('LDBZX'), A))
                assert x1 >= x2
                b['X2 1건 이상'] += x2 >= 1; b['X2 전부'] += x2 == len(idx); b['X2 합'] += x2
                b['X1+Z 1건 이상'] += x1 >= 1; b['X1+Z 전부'] += x1 == len(idx); b['X1+Z 합'] += x1
                b['X1+Z > X2'] += x1 > x2
    print(f'[deletion_budget] 정상 {len(amount)}, c_c=0~5, CR=2, c_s=3. 취소 레코드 10건 초과로 표본 검사한 파일 {big}개')
    print('  전제를 만족하는 관측 수준(불일치 0이어야 함)')
    for nm, *_ in FULL: print(f'    {nm:20s} 검사 {chk[nm]:9,d} 불일치 {bad[nm]}')
    print('  전제를 뺀 대조(불일치는 공식이 성립하지 않는 사례 수)')
    for nm, _ in CONTRAST: print(f'    {nm:20s} 검사 {chk[nm]:9,d} 불일치 {bad[nm]} (공식보다 더 수락 {lenient[nm]})')
    print('  원본이 X2에서 수락되고 취소 레코드가 1~10건인 파일에서 들키지 않는 최대 취소 삭제 건수')
    for cc in CCS:
        b = budget[cc]; n = b['files']
        print(f'    c_c={cc} 파일 {n:4d} | X2: 1건 이상 {100*b["X2 1건 이상"]/n:5.1f}% 전부 {100*b["X2 전부"]/n:5.1f}% 평균 {b["X2 합"]/n:4.2f}'
              f' | X1+Z: 1건 이상 {100*b["X1+Z 1건 이상"]/n:5.1f}% 전부 {100*b["X1+Z 전부"]/n:5.1f}% 평균 {b["X1+Z 합"]/n:4.2f}'
              f' | X1+Z가 더 큰 파일 {b["X1+Z > X2"]}')
    assert all(bad[nm] == 0 for nm, *_ in FULL)
    print('OK')


if __name__ == '__main__': main()
