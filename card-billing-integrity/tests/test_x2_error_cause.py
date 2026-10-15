"""표5(X2 반영 표시 기록 오류) 조건에서 정상 파일이 거절되는 원인을 분해한다(final_ref.py 표5와 같은 데이터·난수·판정기 ref2, K = L+D+B+Z+X2, A = (2, 3, 3)).
기록 오류는 반영 표시만 뒤집고 누계 Z는 바꾸지 않으므로, 관측된 반영 표시의 금액 합이 Z와 다를 수 있다(정의 3.3 위반).
판정기는 반영 표시 합과 Z의 일치를 직접 검사하지 않는다. 거절된 정상 파일마다 다음 순서로 첫 원인을 기록한다.
  A4  : 미청구·반송 거래에 반영 표시가 생겨 가능한 매출 상태가 없음(업무 가정 A4)
  송신 : 청구완료 거래에서 파일이 송신한 취소가 관측상 미반영 이벤트에 포함되지 않음
  예산 : 위에 해당하지 않으며 비용 합이 예산을 넘음(반영 표시 변경으로 미반영 이벤트 수가 달라짐)
또 반영 표시 합이 Z와 다른 거래가 있는 정상 파일 수(모순 관측 파일)와 그중 수락된 파일 수를 센다."""
import copy, random
from collections import Counter
from ref2 import ref_accept
from m4 import attacks4
from run9 import make_case5

K5 = set('LDBZY'); A = (2, 3, 3)

def lag(led, p, r, mode):
    l2 = copy.deepcopy(led)
    for i in l2:
        l2[i]['ev'] = [((a, (False if (cl and mode == 'old') else (True if (not cl and mode == 'early') else cl))) if r.random() < p else (a, cl)) for a, cl in l2[i]['ev']]
    return l2

def cause(F, l2):
    hm, rs = F
    for i in l2:
        if l2[i]['m'] != hm: continue
        if l2[i]['st'] in 'UR' and any(f for _, f in l2[i]['ev']): return 'A4'
    for i in l2:
        if l2[i]['m'] != hm or l2[i]['st'] != 'C': continue
        unref = Counter(a for a, f in l2[i]['ev'] if not f); sent = Counter(a for t, j, a in rs if t == 20 and j == i)
        if sent - unref: return '송신'
    return '예산'

def main():
    rng = random.Random(2024); cases = []
    for _ in range(1000):
        led, F, _, _ = make_case5(rng, 0.1, 0.1); cases.append((led, F, attacks4(F, led, rng)))
    for mode, lab in (('old', '반영 → 미반영 기록'), ('early', '미반영 → 반영 기록')):
        for p in (0.05, 0.1, 0.2):
            r = random.Random(3); rej = 0; why = Counter(); contra = 0; contra_acc = 0
            for led, F, _ in cases:
                l2 = lag(led, p, r, mode)
                bad = any(l2[i]['m'] == 0 and sum(a for a, f in l2[i]['ev'] if f) != l2[i]['cum'] for i in l2)
                acc = ref_accept(F, l2, K5, A)
                contra += bad; contra_acc += bad and acc
                if not acc: rej += 1; why[cause(F, l2)] += 1
            print(f'{lab} {int(p * 100):2d}%: 정상 파일 거절 {rej}/1000 원인 {dict(sorted(why.items()))} | 반영 표시 합과 Z가 다른 파일 {contra}, 그중 수락 {contra_acc}')

if __name__ == '__main__': main()
