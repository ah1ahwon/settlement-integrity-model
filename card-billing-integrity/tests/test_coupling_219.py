"""두 거래 전역 예산 결합의 분리(thm2.py 두 번째 부분과 같은 시드 3, 같은 생성 순서, 판정기 ref2).
  예산 의존 차이: 이월 허용 cc에서 X1+Z와 X2 판정이 다르고, 허용을 9로 풀면 같아지는 경우
  그중 순수 결합: 각 거래만 남긴 원장·파일에서 같은 허용 cc로 판정하면 두 판정이 같은 경우
  나머지: 한 거래만으로도 같은 허용에서 판정이 갈리는 경우(거래별 비용 차이)"""
import random
from ref2 import ref_accept

KY, KX = set('LDBY'), set('LDBZX')

def main():
    rng = random.Random(3); tot = dep = pure = 0; ex = None
    for _ in range(20000):
        leds = {}
        for i in (1, 2):
            n = rng.randint(2, 4); A = [rng.randint(1, 4) for _ in range(n)]; fl = [rng.random() < .5 for _ in range(n)]
            E = [(a, bool(f)) for a, f in zip(A, fl)]
            leds[i] = dict(m=0, amt=sum(A) + 2, st='C', cum=sum(a for a, f in E if f), ev=E)
        Fs = {i: [rng.randint(1, 4) for _ in range(rng.randint(0, 2))] for i in (1, 2)}
        F = (0, [(20, i, a) for i in (1, 2) for a in Fs[i]])
        for cc in (1, 2, 3):
            tot += 1
            if ref_accept(F, leds, KY, (2, 9, cc)) == ref_accept(F, leds, KX, (2, 9, cc)): continue
            if ref_accept(F, leds, KY, (2, 9, 9)) != ref_accept(F, leds, KX, (2, 9, 9)): continue
            dep += 1
            single = any(ref_accept((0, [(20, i, a) for a in Fs[i]]), {i: leds[i]}, KY, (2, 9, cc)) !=
                         ref_accept((0, [(20, i, a) for a in Fs[i]]), {i: leds[i]}, KX, (2, 9, cc)) for i in (1, 2))
            if not single:
                pure += 1
                if ex is None: ex = ({i: ([a for a, _ in leds[i]['ev']], leds[i]['cum'], [a for a, f in leds[i]['ev'] if f], Fs[i]) for i in (1, 2)}, cc)
    print(f'두 거래 무작위 {tot}건(시드 3): 예산 의존 판정 차이 {dep}, 한 거래만으로도 갈림 {dep - pure}, 공통 예산에서만 갈림(순수 결합) {pure}')
    if ex:
        for i, (a, z, r, f) in ex[0].items(): print(f'  거래{i}: 승인취소 {a}, 누계 {z}, 실제 반영 {r}, 파일 취소 {f}')
        print('  취소 이월 허용 합계', ex[1])

if __name__ == '__main__': main()
