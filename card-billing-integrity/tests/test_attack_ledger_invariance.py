"""위협 모델 T1(공격자는 청구 파일만 바꾸고 원장·처리 결과 기록은 바꾸지 못한다)이 공격 생성기에서 지켜지는지 확인.
  고정 실험·S1~S3의 attacks4(4개 금액 분포), S4의 label_attack·id_attacks가 원장을 바꾸지 않는지 seed 2024, 1,000파일씩 확인."""
import copy, random
from m4 import attacks4
from sensitivity import make_dist, SEED, N
from sensitivity_s4 import make_case5_id, strip, label_attack, id_attacks, P

def main():
    for mode in ('orig', 'uniform', 'unit', 'same'):
        rng = random.Random(SEED); mut = 0
        for _ in range(N):
            led, F, _, _ = make_dist(rng, mode); before = copy.deepcopy(led); attacks4(F, led, rng); mut += led != before
        print(f'attacks4 ({mode}): 원장이 바뀐 파일 {mut}/{N}')
    rng = random.Random(SEED); mut = 0
    for _ in range(N):
        led, Fid = make_case5_id(rng, P, P); before = copy.deepcopy(led)
        A13 = attacks4(strip(Fid), led, rng); [label_attack(G, Fid, led) for _, G in A13]; id_attacks(Fid, led)
        mut += led != before
    print(f'S4 attacks4·label_attack·id_attacks: 원장이 바뀐 파일 {mut}/{N}')

if __name__ == '__main__': main()
