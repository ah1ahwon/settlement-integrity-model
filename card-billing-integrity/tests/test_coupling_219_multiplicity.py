"""test_coupling_219.py와 같은 표본(시드 3, 표본 20,000 × 취소 이월 허용 c_c ∈ {1,2,3})에서
  (a) 290조합·219조합이 서로 다른 표본 몇 개에서 나왔는지(표본당 허용치 개수, 허용치 묶음)
  (b) 290조합 전체의 판정 방향(X1+Z, X2)
  (c) 순수 결합이 아닌 71조합에서 거래별 판정 패턴"""
import random
from collections import Counter, defaultdict
from ref2 import ref_accept

KY, KX = set('LDBY'), set('LDBZX')
w = lambda b: '수락' if b else '거절'

def main():
    rng = random.Random(3); D = defaultdict(list); P = defaultdict(list); dirD = Counter(); pat71 = Counter()
    for s in range(20000):
        leds = {}
        for i in (1, 2):
            n = rng.randint(2, 4); A = [rng.randint(1, 4) for _ in range(n)]; fl = [rng.random() < .5 for _ in range(n)]
            E = [(a, bool(f)) for a, f in zip(A, fl)]
            leds[i] = dict(m=0, amt=sum(A) + 2, st='C', cum=sum(a for a, f in E if f), ev=E)
        Fs = {i: [rng.randint(1, 4) for _ in range(rng.randint(0, 2))] for i in (1, 2)}
        F = (0, [(20, i, a) for i in (1, 2) for a in Fs[i]])
        for cc in (1, 2, 3):
            y = ref_accept(F, leds, KY, (2, 9, cc)); x = ref_accept(F, leds, KX, (2, 9, cc))
            if y == x or ref_accept(F, leds, KY, (2, 9, 9)) != ref_accept(F, leds, KX, (2, 9, 9)): continue
            D[s].append(cc); dirD[f'X1+Z {w(x)}·X2 {w(y)}'] += 1
            sing = [(ref_accept((0, [(20, i, a) for a in Fs[i]]), {i: leds[i]}, KX, (2, 9, cc)),
                     ref_accept((0, [(20, i, a) for a in Fs[i]]), {i: leds[i]}, KY, (2, 9, cc))) for i in (1, 2)]
            if all(a == b for a, b in sing): P[s].append(cc)
            else: pat71[' / '.join(f'거래{i} X1 {w(a)}·X2 {w(b)}' for i, (a, b) in zip((1, 2), sing))] += 1
    for nm, S in (('예산 의존 차이', D), ('순수 결합', P)):
        mult = Counter(len(v) for v in S.values()); grp = Counter(tuple(v) for v in S.values() if len(v) > 1)
        print(f'(a) {nm}: 조합 {sum(len(v) for v in S.values())}, 서로 다른 표본 {len(S)}, 표본당 허용치 개수 {dict(sorted(mult.items()))}, 둘 이상에 걸친 허용치 묶음 {dict(sorted(grp.items()))}')
    print(f'(b) 예산 의존 차이의 판정 방향: {dict(dirD)}')
    print(f'(c) 순수 결합이 아닌 {sum(pat71.values())}조합의 거래별 판정: {dict(sorted(pat71.items()))}')

if __name__ == '__main__': main()
