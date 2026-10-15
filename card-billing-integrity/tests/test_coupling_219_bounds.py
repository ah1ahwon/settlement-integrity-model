"""test_coupling_219.py(시드 3, 표본 20,000 × 취소 이월 허용 c_c 3종 = 60,000 조합)의 경계조건 점검.
  (a) 시험의 X2(L+D+B+Y, Z 없음)와 L+D+B+Z+Y의 판정이 같은지(Y가 반영 상태를 주므로 Z가 정보를 더하지 않음)
  (b) 290·219가 조합 수인지 서로 다른 표본 수인지
  (c) 순수 결합 219의 판정 패턴과 허용치 분포
  기준 '예산 무제한'은 c_c=9: 거래당 취소 이벤트 최대 4건, 두 거래 합 최대 8건."""
import random
from collections import Counter
from ref2 import ref_accept

KY, KYZ, KX = set('LDBY'), set('LDBZY'), set('LDBZX')

def main():
    rng = random.Random(3); dyz = dep = pure = 0; dep_s = set(); pure_s = set(); pat = Counter(); ccd = Counter(); mx = 0
    for s in range(20000):
        leds = {}
        for i in (1, 2):
            n = rng.randint(2, 4); A = [rng.randint(1, 4) for _ in range(n)]; fl = [rng.random() < .5 for _ in range(n)]
            E = [(a, bool(f)) for a, f in zip(A, fl)]
            leds[i] = dict(m=0, amt=sum(A) + 2, st='C', cum=sum(a for a, f in E if f), ev=E)
        mx = max(mx, len(leds[1]['ev']) + len(leds[2]['ev']))
        Fs = {i: [rng.randint(1, 4) for _ in range(rng.randint(0, 2))] for i in (1, 2)}
        F = (0, [(20, i, a) for i in (1, 2) for a in Fs[i]])
        for cc in (1, 2, 3):
            y = ref_accept(F, leds, KY, (2, 9, cc)); dyz += y != ref_accept(F, leds, KYZ, (2, 9, cc))
            x = ref_accept(F, leds, KX, (2, 9, cc))
            if y == x or ref_accept(F, leds, KY, (2, 9, 9)) != ref_accept(F, leds, KX, (2, 9, 9)): continue
            dep += 1; dep_s.add(s)
            sing = tuple((ref_accept((0, [(20, i, a) for a in Fs[i]]), {i: leds[i]}, KX, (2, 9, cc)),
                          ref_accept((0, [(20, i, a) for a in Fs[i]]), {i: leds[i]}, KY, (2, 9, cc))) for i in (1, 2))
            if all(a == b for a, b in sing):
                pure += 1; pure_s.add(s); ccd[cc] += 1
                pat[f"전체 X1={'수락' if x else '거절'}·X2={'수락' if y else '거절'}, 거래별 " + ' / '.join(f"X1={'수락' if a else '거절'}·X2={'수락' if b else '거절'}" for a, b in sing)] += 1
    print(f'(a) X2를 L+D+B+Y로 둔 판정과 L+D+B+Z+Y 판정의 차이: {dyz}/60000')
    print(f'(b) 예산 의존 차이 {dep}조합(서로 다른 표본 {len(dep_s)}), 순수 결합 {pure}조합(서로 다른 표본 {len(pure_s)})')
    print(f'(c) 순수 결합 허용치 분포 {dict(sorted(ccd.items()))}, 판정 패턴 {dict(pat)}')
    print(f'    두 거래 취소 이벤트 수 최대 {mx} (무제한 기준 c_c=9)')

if __name__ == '__main__': main()
