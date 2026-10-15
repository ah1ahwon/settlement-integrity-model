"""S4 보조: ID 3유형 공격의 관측 수준별 탐지율을, 공격의 바탕이 된 정상 파일이 같은 수준에서 수락된 경우로 한정해 다시 계산한다
(sensitivity_s4.py와 같은 데이터·판정기). 바탕 파일이 이미 거절되면 공격 탐지로 셀 수 없기 때문이다.
또 ID를 떼면 바탕 정상 파일과 같아지는 공격(금액 수준에서 관측상 정상 파일과 동일)의 수를 센다."""
from collections import Counter
from sensitivity_s4 import build_id, judge, strip, LEVELS

def main():
    cases, _ = build_id()
    for Aa in ((2, 3, 3), (2, 3, 1)):
        print(f'A=(CR,c_s,c_c)={Aa}')
        n = Counter(); same = Counter(); base_ok = Counter(); det = Counter(); det_all = Counter()
        for led, F, _, aid in cases:
            ok = {nm: judge(F, led, K, u, Aa) for nm, K, u in LEVELS}
            for k, G in aid:
                n[k] += 1; same[k] += strip(G) == strip(F)
                for nm, K, u in LEVELS:
                    rej = not judge(G, led, K, u, Aa); det_all[(k, nm)] += rej
                    if ok[nm]: base_ok[(k, nm)] += 1; det[(k, nm)] += rej
        for k in n:
            print(f'  {k} ({n[k]}건, ID를 떼면 바탕 정상 파일과 같음 {same[k]}건)')
            for nm, *_ in LEVELS:
                b = base_ok[(k, nm)]
                print(f'    {nm:6s} 전체 탐지 {det_all[(k, nm)]}/{n[k]} | 바탕 파일 수락 {b}건 중 탐지 {det[(k, nm)]} ({100 * det[(k, nm)] / b:5.1f}%)')
        for nm, *_ in LEVELS:
            print(f'  {nm:6s} ID 3유형 조건부 평균 {sum(100 * det[(k, nm)] / base_ok[(k, nm)] for k in n) / len(n):5.1f}%')

if __name__ == '__main__': main()
