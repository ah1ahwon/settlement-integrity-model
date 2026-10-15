"""④ 가정 민감도(판정기 ref2). 모든 조건에 같은 7개 지표를 기록한다.
  지표: 정상 파일 수 / 취소 이벤트 수 / 모호 거래 수(반영 집합 후보 ≥2) / 판정 불일치 가능 거래 수(후보별 미반영 다중집합이 다름)
        / 실제 판정 불일치 공격 수(X1+Z 수락 & X2 거절) / 공격 탐지율(유형 균등 평균, 취소 삭제 별도) / 오차단율
  S1 취소 이월 허용 c_c ∈ {0,1,2,3}  (CR=2, c_s=3, 데이터 p=0.1 고정)
  S2 반송 상한 CR ∈ {1,2,3,∞}        (c_s=c_c=3; 생성기의 반송 거래는 최대 2건)
  S3 취소 생성 방식 기존/균등/단가 배수/동일 금액 (CR=2, c_s=c_c=3). 로그 제목은 '취소 금액 분포'이지만 금액만 바꾼 통제 실험이 아니다:
     균등·단가 배수·동일 금액은 make_dist로 기반영 이벤트 수를 누계와 독립적으로 뽑고 그 금액에서 누계를 계산하며(기존은 make_case5),
     난수 사용 순서도 달라 파일마다 거래·이벤트 구성이 달라진다. 비교는 생성 방식 전체의 민감도로 해석한다.
  취소 식별자 수준은 tests/test_id_equivalence.py(전수 대조)로 따로 확인한다."""
import random, itertools, statistics as st
from collections import Counter
from ref2 import ref_accept
from m4 import attacks4
from run9 import make_case5
from m2 import pick

SEED = 2024; N = 1000; P = 0.10
KX, KY = set('LDBZX'), set('LDBZY')

def cands(ev, cum):
    a = [x for x, _ in ev]
    return [P_ for r in range(len(a) + 1) for P_ in itertools.combinations(range(len(a)), r) if sum(a[j] for j in P_) == cum]

def data_metrics(cases):
    nev = amb = expl = 0
    for led, F, A in cases:
        for i in led:
            if led[i]['m'] != 0: continue
            ev = led[i]['ev']; nev += len(ev)
            Ps = cands(ev, led[i]['cum'])
            if len(Ps) > 1: amb += 1
            if len({tuple(sorted(ev[j][0] for j in range(len(ev)) if j not in P_)) for P_ in Ps}) > 1: expl += 1
    return len(cases), nev, amb, expl

def judge_metrics(cases, K, Aa):
    fr = 0; per = {}
    for led, F, A in cases:
        fr += not ref_accept(F, led, K, Aa)
        for kd, G in A:
            d = per.setdefault(kd, [0, 0]); d[0] += not ref_accept(G, led, K, Aa); d[1] += 1
    det = st.mean(100 * v[0] / v[1] for v in per.values())
    cd = per.get('취소 삭제', [0, 1]); return 100 * fr / len(cases), det, 100 * cd[0] / cd[1]

def disagree(cases, Aa):
    att = leg = 0
    for led, F, A in cases:
        leg += ref_accept(F, led, KX, Aa) != ref_accept(F, led, KY, Aa)
        for kd, G in A:
            att += ref_accept(G, led, KX, Aa) and not ref_accept(G, led, KY, Aa)
    return att, leg

def make_dist(rng, mode):
    """make_case5와 같은 원장 구성에서 취소 이벤트를 방식별로 만든다. mode='orig'는 make_case5 그대로.
    그 외 방식은 기반영 이벤트 수(C 거래 0~2건)를 누계와 독립적으로 뽑고 누계를 그 금액의 합으로 정한다. 금액만 바꾼 통제 비교가 아니다."""
    if mode == 'orig': return make_case5(rng, P, P)
    ids = list(range(1, 100)); rng.shuffle(ids); led = {}; A = lambda: rng.randint(10, 200)
    for _ in range(rng.randint(3, 6)): i = ids.pop(); led[i] = dict(m=0, amt=A(), st='U', cum=0, ev=[])
    for _ in range(rng.randint(2, 4)): i = ids.pop(); led[i] = dict(m=0, amt=A(), st='C', cum=0, ev=[])
    for _ in range(pick(rng, 2)): i = ids.pop(); led[i] = dict(m=0, amt=A(), st='R', cum=0, ev=[])
    for _ in range(2): i = ids.pop(); led[i] = dict(m=1, amt=A(), st=rng.choice('UC'), cum=0, ev=[])
    US = [i for i in led if led[i]['m'] == 0 and led[i]['st'] in 'UR']
    defer = {i for i in US if rng.random() < P}; sent = [i for i in US if i not in defer]
    rs = [(10, i, led[i]['amt']) for i in sent]; sset = set(sent)
    def draw(amt, k):
        if k == 0: return []
        cap = max(1, amt // (2 * k))
        if mode == 'uniform': return [rng.randint(1, cap) for _ in range(k)]
        if mode == 'unit': u = rng.randint(1, max(1, cap // 2)); return [u * rng.randint(1, 2) for _ in range(k)]
        if mode == 'same': u = rng.randint(1, cap); return [u] * k
    for i in led:
        if led[i]['m'] != 0: continue
        kr = rng.choice([0, 0, 1, 2]) if led[i]['st'] == 'C' else 0
        ku = rng.choice([0, 0, 1, 1, 2]) if (led[i]['st'] == 'C' or i in sset) else 0
        vals = draw(led[i]['amt'], kr + ku)
        led[i]['ev'] = [(v, True) for v in vals[:kr]] + [(v, False) for v in vals[kr:]]
        led[i]['cum'] = sum(vals[:kr])
        for v in vals[kr:]:
            if rng.random() >= P: rs.append((20, i, v))
    rng.shuffle(rs)
    return led, (0, rs), len(defer), 0

def build(mode):
    rng = random.Random(SEED); out = []
    for _ in range(N):
        led, F, _, _ = make_dist(rng, mode); out.append((led, F, attacks4(F, led, rng)))
    return out

def row(label, cases, dm, Aa, Ks):
    att, leg = disagree(cases, Aa)
    js = ' | '.join(f'{nm} 오차단 {j[0]:5.1f} 탐지 {j[1]:5.1f} 취소삭제 {j[2]:5.1f}' for nm, K in Ks for j in [judge_metrics(cases, K, Aa)])
    print(f'  {label:14s} 파일 {dm[0]} 이벤트 {dm[1]} 모호 {dm[2]} 불일치가능 {dm[3]} | 불일치 공격 {att}/{sum(len(a) for *_, a in cases)} 정당파일 판정차 {leg} | {js}')

def main():
    base = build('orig'); dm = data_metrics(base)
    print(f'[고정] seed {SEED}, 정상 파일 {N}, 지연 p={P}, 공격 {sum(len(a) for *_, a in base)}건 (attacks4 13유형), 판정기 ref2')
    print('\n[S1] 취소 이월 허용 c_c (CR=2, c_s=3)')
    for cc in range(4): row(f'c_c={cc}', base, dm, (2, 3, cc), [('X1+Z', KX), ('X2', KY)])
    print('\n[S2] 반송 상한 CR (c_s=c_c=3). B 없는 조합에서만 숨은 반송 상태가 생긴다')
    for CR in (1, 2, 3, 99):
        row(f'CR={"∞" if CR == 99 else CR}', base, dm, (CR, 3, 3), [('L+D', set('LD')), ('L+D+Z', set('LDZ')), ('L+D+B+Z+X2', KY)])
    print('\n[S3] 취소 금액 분포 (CR=2, c_s=c_c=3)')
    for mode, lab in (('orig', '기존'), ('uniform', '균등'), ('unit', '단가 배수'), ('same', '동일 금액')):
        cs = base if mode == 'orig' else build(mode)
        row(lab, cs, data_metrics(cs), (2, 3, 3), [('X1+Z', KX), ('X2', KY)])

if __name__ == '__main__': main()
