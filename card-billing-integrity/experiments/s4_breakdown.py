"""S4 보조: ID 3유형 공격에서 금액 수준과 ID 수준의 판정 불일치를 공격 유형별로 나눈다(sensitivity_s4.py와 같은 데이터·판정기).
sensitivity_s4.log의 'X1-금액≠X1-ID 998 / 868'이 어떤 유형에서 나왔는지 기록한다."""
from collections import Counter
from sensitivity_s4 import build_id, judge, KX, KY

def main():
    cases, _ = build_id()
    for Aa in ((2, 3, 3), (2, 3, 1)):
        c = Counter(); n = Counter()
        for led, F, _, aid in cases:
            for k, G in aid:
                n[k] += 1
                c[(k, 'X1-금액≠X1-ID')] += judge(G, led, KX, False, Aa) != judge(G, led, KX, True, Aa)
                c[(k, 'X2-금액≠X2-ID')] += judge(G, led, KY, False, Aa) != judge(G, led, KY, True, Aa)
                c[(k, 'X1-ID 수락·X2-ID 거절')] += judge(G, led, KX, True, Aa) and not judge(G, led, KY, True, Aa)
        print(f'A=(CR,c_s,c_c)={Aa}')
        for k in n:
            print(f'  {k} ({n[k]}건): ' + ', '.join(f'{m} {c[(k, m)]}' for m in ('X1-금액≠X1-ID', 'X2-금액≠X2-ID', 'X1-ID 수락·X2-ID 거절')))

if __name__ == '__main__': main()
