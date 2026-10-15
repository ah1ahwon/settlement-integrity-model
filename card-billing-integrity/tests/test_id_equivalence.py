"""취소 식별자 수준 전수 대조(단일 거래, 청구완료 거래, 관측 X+Z).
  X1-금액: 파일 취소 레코드는 금액만 가진다 -> ref2.cancel_mc
  X1-ID : 파일 취소 레코드가 승인 취소 이벤트 ID를 가진다(금액 일치, ID 중복 없음).
          수락 <=> 합이 누계 Z인 반영 집합 P가 있어 보낸 ID가 P 밖에 있고, 보내지 않은 미반영 건수 ≤ 취소 이월 허용
  X2    : 이벤트별 반영 여부가 관측된다
예상(명제): 누계가 합계만 주면 같은 금액 이벤트의 ID를 서로 바꿔도 관측이 같으므로 X1-ID 판정 = X1-금액 판정."""
import itertools
from collections import Counter
from ref2 import cancel_mc

def id_accept(sent_ids, ev, cum, cc):
    n = len(ev); best = None
    for r in range(n + 1):
        for P in itertools.combinations(range(n), r):
            if sum(ev[j][0] for j in P) != cum or set(P) & set(sent_ids): continue
            m = n - r - len(sent_ids); best = m if best is None else min(best, m)
    return best is not None and best <= cc

def main():
    n = diff_id = diff_y = 0; amb = 0
    for k in range(1, 5):
        for amts in itertools.combinations_with_replacement(range(1, 4), k):
            for flags in itertools.product([False, True], repeat=k):
                ev = list(zip(amts, flags)); cum = sum(a for a, f in ev if f)
                for r in range(k + 1):
                    for S in itertools.combinations(range(k), r):   # 보낸 ID 집합(중복 없음, 반영된 이벤트 재전송 포함)
                        Fi = [ev[j][0] for j in S]
                        for cc in range(3):
                            a_amt = cancel_mc(Fi, ev, cum, {'L', 'D', 'B', 'Z', 'X'})
                            a_amt = a_amt is not None and a_amt <= cc
                            a_id = id_accept(S, ev, cum, cc)
                            m_y = cancel_mc(Fi, ev, cum, {'L', 'D', 'B', 'Z', 'Y'})
                            a_y = m_y is not None and m_y <= cc
                            n += 1; diff_id += a_amt != a_id; diff_y += a_id != a_y
    print('취소 ID 수준 전수 대조(이벤트 1~4건, 금액 1..3, 이월 허용 0..2):', n, '건')
    print('  X1-금액 vs X1-ID 불일치', diff_id)
    print('  X1-ID vs X2 불일치', diff_y)

if __name__ == '__main__': main()
