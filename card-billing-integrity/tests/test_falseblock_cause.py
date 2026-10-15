"""정상 파일 수락·거절의 원인 분해와 취소 단독 레코드 확인(판정기 ref2, sensitivity.py와 같은 데이터: seed 2024, 1,000파일, p=0.1).
  (1) 청구완료(C) 거래의 취소 레코드가 같은 파일의 매출 레코드 없이 단독으로 올 때 파일 자체 정합성 검사와 충돌하는지
  (2) 생성기의 실제 반송 거래 수·매출 이월·취소 이월이 업무 가정 A 이내인지와 판정(수락/거절)의 관계"""
import random
from collections import Counter
from ref2 import ref_accept, INT
from m2 import atoms
from m4 import attacks4
from run9 import make_case5

SEED = 2024; N = 1000; P = 0.10

def main():
    rng = random.Random(SEED); cases = []
    for _ in range(N):
        led, F, ns, nc = make_case5(rng, P, P); attacks4(F, led, rng)
        nR = sum(1 for i in led if led[i]['m'] == 0 and led[i]['st'] == 'R')
        cases.append((led, F, ns, nc, nR))
    intfail = sum(1 for led, F, *_ in cases if not all(atoms(F, led, set(), 0)[k] for k in INT))
    def solo(led, F):
        sold = {i for t, i, _ in F[1] if t == 10}
        return [i for t, i, _ in F[1] if t == 20 and led[i]['st'] == 'C' and i not in sold]
    ns_rec = sum(len(solo(led, F)) for led, F, *_ in cases); ns_file = sum(1 for led, F, *_ in cases if solo(led, F))
    print(f'[1] 정상 파일 {N}: 청구완료 거래의 취소 단독 레코드 {ns_rec}건(파일 {ns_file}개), 파일 자체 정합성 위반 파일 {intfail}')
    led = {1: dict(m=0, amt=100, st='C', cum=0, ev=[(30, False)])}
    print('    최소 사례(청구완료 거래, 미반영 취소 30 단독) 수락:',
          ', '.join(f"{K}={ref_accept((0, [(20, 1, 30)]), led, set(K), (2, 3, 3))}" for K in ('L', 'LD', 'LDBZ', 'LDBZX', 'LDBZY')))
    for A in ((2, 3, 3), (2, 3, 1)):
        for K in ('LDBZX', 'LDBZY'):
            c = Counter(); why = Counter()
            for led, F, ns, nc, nR in cases:
                within = nR <= A[0] and ns <= A[1] and nc <= A[2]; acc = ref_accept(F, led, set(K), A)
                c[(within, acc)] += 1
                if not acc:
                    why['+'.join(n for n, v in (('반송', nR > A[0]), ('매출 이월', ns > A[1]), ('취소 이월', nc > A[2])) if v) or '없음'] += 1
            print(f'[2] A=(CR,c_s,c_c)={A} K={K}: 가정 이내 {c[(True, True)] + c[(True, False)]}(거절 {c[(True, False)]}) | '
                  f'가정 초과 {c[(False, True)] + c[(False, False)]}(거절 {c[(False, False)]}, 수락 {c[(False, True)]}) | 거절 원인 {dict(sorted(why.items()))}')

if __name__ == '__main__': main()
