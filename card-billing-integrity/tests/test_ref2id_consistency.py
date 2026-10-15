"""S4 판정기 ref2id와 별도로 작성한 ID 수준 판정식(test_id_equivalence.id_accept, X2-ID 식)의 단일 거래 전수 대조.
범위: 청구완료 거래 1건, 이벤트 1~4건, 금액 1..3, 반영 여부 전부, 보낸 ID 집합 전부(유효 ID), 이월 허용 0..2, K=LDBZX / LDBZY."""
import itertools
from ref2id import ref_accept_id
from test_id_equivalence import id_accept

def main():
    n = bad = 0
    for k in range(1, 5):
        for amts in itertools.combinations_with_replacement(range(1, 4), k):
            for flags in itertools.product([False, True], repeat=k):
                ev = list(zip(amts, flags)); cum = sum(a for a, f in ev if f)
                led = {1: dict(m=0, amt=sum(amts) + 2, st='C', cum=cum, ev=ev)}
                for r in range(k + 1):
                    for S in itertools.combinations(range(k), r):
                        F = (0, [(20, 1, ev[j][0], j) for j in S])
                        for cc in range(3):
                            x = ref_accept_id(F, led, set('LDBZX'), (2, 9, cc))
                            y = ref_accept_id(F, led, set('LDBZY'), (2, 9, cc))
                            ex = id_accept(S, ev, cum, cc)
                            ey = not any(ev[j][1] for j in S) and sum(1 for _, f in ev if not f) - r <= cc
                            n += 1; bad += (x != ex) + (y != ey)
    print('ref2id vs 별도 ID 판정식(X1-ID+Z, X2-ID) 단일 거래 전수 대조:', n, '건, 불일치', bad)

if __name__ == '__main__': main()
