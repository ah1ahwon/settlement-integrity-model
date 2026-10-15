"""④ 민감도 S4: 취소 이벤트 식별자 및 반영 상태 관측 수준(판정기 ref2 / ref2id). S1~S3과 같은 데이터와 같은 7개 지표.
관측 수준: X1-금액(K=LDBZX, ID 제거), X1-ID(LDBZX + ID), X2-금액(LDBZY, ID 제거), X2-ID(LDBZY + ID). 업무 가정 A=(CR,c_s,c_c).
데이터: sensitivity.py의 build('orig')와 같은 seed 2024, 정상 1,000건, p=0.1. 생성 단계에서 이벤트 ID를 추적하기 위해
  make_case5를 그대로 옮긴 make_case5_id를 쓰고, 원 make_case5와 원장·파일이 같은지 전 사례에서 확인한다(rng 소비 순서 동일).
공격:
  (가) 기존 13유형(attacks4, 금액 수준 파일). ID 부여 규칙: 정상 파일에 있던 취소 레코드는 원래 ID를 유지한다.
       새로 생긴 취소 레코드는 공격자에게 가장 유리하게 ID를 고른다: 같은 거래의 아직 보내지 않은 미반영 동일 금액 이벤트
       → 없으면 아직 보내지 않은 반영 동일 금액 이벤트(재전송) → 없으면 존재하지 않는 ID.
  (나) ID 전용 3유형(정상 파일 기준): 유령 ID(취소 레코드 하나의 ID를 없는 ID로), 중복 ID(취소 레코드 하나를 같은 ID로 한 번 더),
       기반영 취소 ID 재전송(반영된 이벤트를 그 ID와 금액으로 추가; 한도 이내인 첫 거래).
지표(관측 수준별 정의):
  정상 파일 수, 취소 이벤트 수
  모호 거래 수: 합이 누계인 반영 후보(색인 집합)가 2개 이상인 가맹점 0 거래. X1-ID 수준의 판정 불일치 가능 조건(명제 3.3(b-2)의 부정)과 같다
  판정 불일치 가능 거래 수(금액 수준): 후보별 미반영 금액 다중집합이 서로 다른 거래(명제 3.3(b-1)의 부정, S1~S3과 같은 정의)
  실제 판정 불일치 공격 수: 쌍별로 X1-금액≠X1-ID, X2-금액≠X2-ID, X1-ID 수락·X2-ID 거절
  탐지율(유형 균등 평균; 13유형 / ID 3유형 / 16유형 따로), 오차단율(정상 파일 거절 비율)"""
import random, itertools, statistics as st
from collections import Counter
from ref2 import ref_accept
from ref2id import ref_accept_id, strip
from m4 import attacks4
from run9 import make_case5
from m2 import pick
from sensitivity import SEED, N, P, cands, data_metrics

KX, KY = set('LDBZX'), set('LDBZY')
LEVELS = [('X1-금액', KX, False), ('X1-ID', KX, True), ('X2-금액', KY, False), ('X2-ID', KY, True)]
GHOST = 999

def make_case5_id(rng, ps, pc):
    """run9.make_case5와 같은 절차·같은 rng 소비. 취소 레코드에 이벤트 색인 j를 붙여 (20, i, a, j)로 만든다."""
    ids = list(range(1, 100)); rng.shuffle(ids)
    led = {}; A = lambda: rng.randint(10, 200)
    for _ in range(rng.randint(3, 6)): i = ids.pop(); led[i] = dict(m=0, amt=A(), st='U', cum=0, ev=[])
    for _ in range(rng.randint(2, 4)):
        i = ids.pop(); a = A(); led[i] = dict(m=0, amt=a, st='C', cum=rng.choice([0, 0, rng.randint(0, a - 1)]), ev=[])
    for _ in range(pick(rng, 2)): i = ids.pop(); led[i] = dict(m=0, amt=A(), st='R', cum=0, ev=[])
    for _ in range(2): i = ids.pop(); led[i] = dict(m=1, amt=A(), st=rng.choice('UC'), cum=0, ev=[])
    US = [i for i in led if led[i]['m'] == 0 and led[i]['st'] in 'UR']
    defer = {i for i in US if rng.random() < ps}
    sent = [i for i in US if i not in defer]
    rs = [(10, i, led[i]['amt']) for i in sent]; sset = set(sent)
    for i in led:
        if led[i]['m'] != 0: continue
        cum = led[i]['cum']
        if led[i]['st'] == 'C' and cum > 0:
            if cum >= 2 and rng.random() < .4:
                a = rng.randint(1, cum - 1); led[i]['ev'] += [(a, True), (cum - a, True)]
            else: led[i]['ev'] += [(cum, True)]
        if led[i]['st'] == 'C' or i in sset:
            rem = led[i]['amt'] - cum; k = rng.choice([0, 0, 1, 1, 2])
            if k == 1 and rem >= 1: evs = [rng.randint(1, rem)]
            elif k == 2 and rem >= 2:
                a = rng.randint(1, rem - 1); evs = [a, rng.randint(1, rem - a)]
            else: evs = []
            for a in evs:
                led[i]['ev'].append((a, False))
                if rng.random() < pc: pass
                else: rs.append((20, i, a, len(led[i]['ev']) - 1))
    rng.shuffle(rs)
    return led, (0, rs)

def label_attack(G, Fid, led):
    """금액 수준 공격 파일 G에 ID를 붙인다(위 규칙)."""
    hm, rs = G
    pool = Counter(r[:3] for r in Fid[1] if r[0] == 20); idq = {}
    for r in Fid[1]:
        if r[0] == 20: idq.setdefault(r[:3], []).append(r[3])
    used = {(r[1], r[3]) for r in Fid[1] if r[0] == 20}
    out = []; new = []
    for r in rs:
        if r[0] == 20 and pool[r[:3]] > 0: pool[r[:3]] -= 1; out.append(r[:3] + (idq[r[:3]].pop(0),))
        elif r[0] == 20: new.append(r)
        else: out.append(r)
    kept = {(r[1], r[3]) for r in out if r[0] == 20}
    for _, i, a in new:
        ev = led[i]['ev'] if i in led else []
        cand = [j for j in range(len(ev)) if ev[j][0] == a and (i, j) not in kept]
        pickj = ([j for j in cand if not ev[j][1]] + [j for j in cand if ev[j][1]] + [GHOST])[0]
        if pickj != GHOST: kept.add((i, pickj))
        out.append((20, i, a, pickj))
    return hm, out

def id_attacks(Fid, led):
    hm, rs = Fid; out = []
    c20 = [k for k, r in enumerate(rs) if r[0] == 20]
    if c20:
        k = c20[0]; r = rs[k]
        out.append(('유령 ID', (hm, rs[:k] + [r[:3] + (GHOST,)] + rs[k + 1:])))
        out.append(('중복 ID', (hm, rs + [r])))
    for i in led:
        if led[i]['m'] != 0: continue
        refl = [j for j, (a, c_) in enumerate(led[i]['ev']) if c_]
        if refl:
            j = refl[0]; a = led[i]['ev'][j][0]
            rem = led[i]['amt'] - led[i]['cum'] - sum(r[2] for r in rs if r[0] == 20 and r[1] == i)
            if a <= rem: out.append(('기반영 취소 ID 재전송', (hm, rs + [(20, i, a, j)]))); break
    return out

def build_id():
    rng = random.Random(SEED); out = []; same = 0
    rng2 = random.Random(SEED)
    for _ in range(N):
        led, Fid = make_case5_id(rng, P, P)
        led0, F0, _, _ = make_case5(rng2, P, P)
        Fs = strip(Fid); same += (led == led0 and Fs == F0)
        A13 = attacks4(Fs, led, rng); attacks4(F0, led0, rng2)
        out.append((led, Fid, [(k, label_attack(G, Fid, led)) for k, G in A13], id_attacks(Fid, led)))
    return out, same

def judge(F, led, K, use_id, Aa):
    return ref_accept_id(F, led, K, Aa) if use_id else ref_accept(strip(F), led, K, Aa)

def main(Aa_list=((2, 3, 3), (2, 3, 1))):
    cases, same = build_id()
    print(f'[S4] seed {SEED}, 정상 {N}, p={P}. make_case5_id와 make_case5의 원장·파일 일치 {same}/{N}')
    bad_valid = sum(not __import__("ref2id").id_valid(F, led) for led, F, _, _ in cases)
    print(f'  정상 파일 ID 유효성 위반 {bad_valid}/{N}')
    dm = data_metrics([(led, strip(F), None) for led, F, _, _ in cases])
    n13 = sum(len(a) for _, _, a, _ in cases); nid = sum(len(b) for *_, b in cases)
    print(f'  파일 {dm[0]}, 취소 이벤트 {dm[1]}, 모호 거래(색인 후보 ≥2) {dm[2]}, 판정 불일치 가능(금액 수준) {dm[3]}, 공격 13유형 {n13}건, ID 3유형 {nid}건')
    print('  ID 3유형 건수', dict(Counter(k for *_, b in cases for k, _ in b)))
    for Aa in Aa_list:
        print(f'\n  업무 가정 A=(CR,c_s,c_c)={Aa}')
        R = {}
        for nm, K, u in LEVELS:
            fr = sum(not judge(F, led, K, u, Aa) for led, F, _, _ in cases)
            per13, perid = {}, {}
            for led, F, a13, aid in cases:
                for d, lst in ((per13, a13), (perid, aid)):
                    for kd, G in lst:
                        v = d.setdefault(kd, [0, 0]); v[0] += not judge(G, led, K, u, Aa); v[1] += 1
            R[nm] = (fr, per13, perid)
            allp = {**per13, **perid}
            m = lambda d: st.mean(100 * v[0] / v[1] for v in d.values())
            cd = per13.get('취소 삭제', [0, 1])
            print(f'   {nm:7s} 오차단 {100*fr/N:5.1f} | 탐지 13유형 {m(per13):5.1f} ID3유형 {m(perid):5.1f} 16유형 {m(allp):5.1f} | 취소삭제 {100*cd[0]/cd[1]:5.1f} | '
                  + ' '.join(f'{k} {100*v[0]/v[1]:5.1f}' for k, v in perid.items()))
        # 쌍별 실제 판정 불일치
        for grp, idx in (('13유형', 2), ('ID 3유형', 3), ('정상 파일', None)):
            c = Counter()
            for led, F, a13, aid in cases:
                files = [F] if idx is None else [G for _, G in (a13 if idx == 2 else aid)]
                for G in files:
                    j = {nm: judge(G, led, K, u, Aa) for nm, K, u in LEVELS}
                    c['X1-금액≠X1-ID'] += j['X1-금액'] != j['X1-ID']
                    c['X1-금액 수락·X1-ID 거절'] += j['X1-금액'] and not j['X1-ID']
                    c['X2-금액≠X2-ID'] += j['X2-금액'] != j['X2-ID']
                    c['X1-ID 수락·X2-ID 거절'] += j['X1-ID'] and not j['X2-ID']
                    c['X1-금액 수락·X2-금액 거절'] += j['X1-금액'] and not j['X2-금액']
            print(f'   실제 판정 불일치({grp}):', dict(c))

if __name__ == '__main__': main()
