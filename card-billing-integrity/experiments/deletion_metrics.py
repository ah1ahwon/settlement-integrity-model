"""③ 매출 삭제와 취소 삭제를 같은 지표로 비교한다(판정기 ref3, 데이터 sensitivity.build('orig') = seed 2024, 정상 1,000건, 기준 공격).
  Trej = 해당 유형에서 거절된 공격 / 해당 유형 공격.
  Cdet = 바탕 정상 파일이 같은 K·A에서 수락된 공격 중 거절된 비율.
  두 지표 모두 분자/분모를 함께 출력한다. 본문 4.4절의 '매출 삭제 약 57%'(Trej)와 '취소 삭제 2.9%'(Cdet)를 같은 지표로 다시 맞추기 위한 집계이다.
  매출 삭제는 지운 매출에 연결된 취소 레코드가 파일에 남는지로 나눈다. 남으면 그 취소는 A5의 송신 자격을 잃으므로,
  거절이 '매출 누락' 자체가 아니라 '남은 취소의 자격 상실' 때문일 수 있다."""
from collections import Counter
from ref3 import ref_accept
from sensitivity import build

LEVELS = [('L', 'L'), ('L+D', 'LD'), ('L+D+B+Z', 'LDBZ'), ('L+D+B+Z+X1', 'LDBZX'), ('L+D+B+Z+X2', 'LDBZY')]
A = (2, 3, 3)


def deleted_sale(F, G):
    gone = Counter(F[1]) - Counter(G[1])
    (rec, n), = gone.items()
    assert n == 1 and rec[0] == 10
    return rec[1]


def pct(a, b):
    return f'{100 * a / b:5.1f}% ({a}/{b})' if b else '  -  '


def main():
    cases = build('orig')
    print(f'[deletion_metrics] seed 2024, 정상 {len(cases)}, A=(CR,c_s,c_c)={A}, 판정기 ref3')
    for nm, k in LEVELS:
        K = set(k)
        s = {key: [0, 0, 0, 0] for key in ('거래 삭제', '취소 삭제', '거래 삭제·취소 남음', '거래 삭제·취소 없음')}
        for led, F, att in cases:
            ok = ref_accept(F, led, K, A)
            for kind, G in att:
                if kind not in ('거래 삭제', '취소 삭제'): continue
                rej = not ref_accept(G, led, K, A)
                keys = [kind]
                if kind == '거래 삭제':
                    i = deleted_sale(F, G)
                    orphan = any(r[0] == 20 and r[1] == i for r in G[1])
                    keys.append('거래 삭제·취소 남음' if orphan else '거래 삭제·취소 없음')
                for key in keys:
                    v = s[key]; v[0] += rej; v[1] += 1
                    if ok: v[2] += rej; v[3] += 1
        print(f'\n  K={nm}')
        for key, (tr, tn, cr, cn) in s.items():
            print(f'    {key:14s} Trej {pct(tr, tn)} | Cdet {pct(cr, cn)}')


if __name__ == '__main__': main()
