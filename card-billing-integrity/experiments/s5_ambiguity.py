"""① S5: 같은 누계를 서로 다른 건수로 만들 수 있는 거래(모호 거래)의 비중과 취소 이월 상한에 따른 X1+Z·X2 판정 차이(판정기 ref3).
생성(make_amb): make_case5와 같은 원장·매출 송신 절차에서, 청구완료(C) 거래마다 확률 π로 취소 이벤트를 다음 구조로 바꾼다.
  작은 취소 q를 m건(m = 2 또는 3), 큰 취소 m·q를 1건 두고 누계 Z = m·q. 2·m·q ≤ 승인 금액이 되도록 q를 고른다.
  방향은 확률 1/2로 정한다. '큰 건 반영'이면 실제로 남은 취소는 작은 m건, '작은 건 반영'이면 큰 1건이다.
  두 경우 모두 누계만으로는 어느 쪽이 반영됐는지 알 수 없고, 남은 건수가 m과 1로 달라 명제 3.3(b-1)의 전제가 깨진다.
  남은 미반영 취소는 각각 확률 p로 이월하고 나머지는 송신한다. 나머지 거래는 make_case5와 같다.
  π = 0이면 난수 소비까지 make_case5와 같으므로 기준 데이터를 그대로 재현한다(실행 중 확인).
공격: attacks4(기준 13유형), 원본 생성 직후 같은 난수 생성기로 만든다(기준 실험과 같은 순서).
지표(A = (2, 3, c_c)):
  무변조 거절: 정상 파일 거절 수(X1+Z / X2)
  Cdet: 관측 수준별 정의(바탕 파일이 그 수준에서 수락된 공격만)의 유형 균등 평균
  공통 분모 Cdet: 바탕 파일이 X2에서 수락된 공격만(명제 3.1에 따라 X1+Z에서도 수락)으로 두 수준을 같은 분모에서 비교
  판정 차이: 공통 분모 공격 중 X1+Z 수락·X2 거절 수와 비율. 유형별로 취소 삭제·취소 재전송을 따로 적는다.
선택한 π·p는 차이가 생기는 조건을 보이기 위한 합성 설정이며 현실 발생률이 아니다."""
import argparse, json, random, statistics as st
from collections import Counter
from pathlib import Path
from ref3 import ref_accept
from m4 import attacks4
from run9 import make_case5
from m2 import pick

SEED = 2024; N = 1000
KX, KY = set('LDBZX'), set('LDBZY')
PIS = (0.0, 0.25, 0.5, 1.0); PS = (0.1, 0.3); CCS = (1, 2, 3, 4)


def make_amb(rng, pi, p):
    """make_case5와 같은 절차. C 거래의 취소 생성 단계에서만 확률 pi로 모호 구조를 쓴다. 반환 마지막 값은 모호 거래의 방향."""
    ids = list(range(1, 100)); rng.shuffle(ids)
    led = {}; A = lambda: rng.randint(10, 200)
    for _ in range(rng.randint(3, 6)): i = ids.pop(); led[i] = dict(m=0, amt=A(), st='U', cum=0, ev=[])
    for _ in range(rng.randint(2, 4)):
        i = ids.pop(); a = A(); led[i] = dict(m=0, amt=a, st='C', cum=rng.choice([0, 0, rng.randint(0, a - 1)]), ev=[])
    for _ in range(pick(rng, 2)): i = ids.pop(); led[i] = dict(m=0, amt=A(), st='R', cum=0, ev=[])
    for _ in range(2): i = ids.pop(); led[i] = dict(m=1, amt=A(), st=rng.choice('UC'), cum=0, ev=[])
    US = [i for i in led if led[i]['m'] == 0 and led[i]['st'] in 'UR']
    defer = {i for i in US if rng.random() < p}
    sent = [i for i in US if i not in defer]
    rs = [(10, i, led[i]['amt']) for i in sent]; sset = set(sent)
    dc = 0; amb = {}
    for i in led:
        if led[i]['m'] != 0: continue
        # pi = 0이면 난수를 쓰지 않아 make_case5와 같은 순서가 된다.
        if led[i]['st'] == 'C' and pi and rng.random() < pi:
            m = rng.choice((2, 3)); q = rng.randint(1, led[i]['amt'] // (2 * m))
            big = rng.random() < .5
            led[i]['ev'] = [(q, not big)] * m + [(m * q, big)]
            led[i]['cum'] = m * q; amb[i] = 'big' if big else 'small'
            for a, f in led[i]['ev']:
                if f: continue
                if rng.random() < p: dc += 1
                else: rs.append((20, i, a))
            continue
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
                if rng.random() < p: dc += 1
                else: rs.append((20, i, a))
    rng.shuffle(rs)
    return led, (0, rs), len(defer), dc, amb


def build(pi, p, seed=SEED):
    rng = random.Random(seed); out = []
    for _ in range(N):
        led, F, _, _, amb = make_amb(rng, pi, p)
        out.append((led, F, attacks4(F, led, rng), amb))
    return out


def same_as_baseline(cases, p, seed=SEED):
    rng = random.Random(seed); same = 0
    for led, F, att, _ in cases:
        led0, F0, _, _ = make_case5(rng, p, p)
        same += led == led0 and F == F0 and att == attacks4(F0, led0, rng)
    return same


def evaluate(cases, A):
    r = Counter(); T = {}; C = {}; common = {}; diff = Counter()
    for led, F, att, _ in cases:
        ox, oy = ref_accept(F, led, KX, A), ref_accept(F, led, KY, A)
        assert ox or not oy
        r['무변조 거절 X1+Z'] += not ox; r['무변조 거절 X2'] += not oy
        for kind, G in att:
            x, y = ref_accept(G, led, KX, A), ref_accept(G, led, KY, A)
            assert x or not y
            for nm, o, v in (('X1+Z', ox, x), ('X2', oy, y)):
                if o: c = C.setdefault(nm, {}).setdefault(kind, [0, 0]); c[0] += not v; c[1] += 1
            if oy:
                for nm, v in (('X1+Z', x), ('X2', y)):
                    c = common.setdefault(nm, {}).setdefault(kind, [0, 0]); c[0] += not v; c[1] += 1
                r['공통 분모 공격'] += 1
                if x and not y: r['판정 차이'] += 1; diff[kind] += 1
    macro = lambda d: st.mean(100 * a / b for a, b in d.values())
    out = dict(counts=dict(r), diff_by_type=dict(diff),
               Cdet={nm: macro(d) for nm, d in C.items()},
               common_Cdet={nm: macro(d) for nm, d in common.items()},
               common_by_type={nm: {k: v for k, v in d.items()} for nm, d in common.items()})
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--output'); args = ap.parse_args()
    print(f'[S5] seed {SEED}, 정상 {N}, CR=2, c_s=3, 판정기 ref3. π=모호 구조를 쓰는 C 거래 비율, p=이월 확률')
    result = []
    for p in PS:
        for pi in PIS:
            cases = build(pi, p)
            if pi == 0:
                same = same_as_baseline(cases, p)
                print(f'\n  p={p} π=0: make_case5·attacks4와 원장·파일·공격 일치 {same}/{N}')
                assert same == N
            namb = Counter(d for *_, amb in cases for d in amb.values())
            natt = sum(len(a) for _, _, a, _ in cases)
            print(f'  p={p} π={pi}: 모호 거래 {sum(namb.values())} (큰 건 반영 {namb["big"]}, 작은 건 반영 {namb["small"]}), 공격 {natt}')
            for cc in CCS:
                e = evaluate(cases, (2, 3, cc)); c = e['counts']
                rate = 100 * c.get('판정 차이', 0) / c['공통 분모 공격']
                cd = e['diff_by_type']
                ct = e['common_by_type']
                def typ(nm, k):
                    a, b = ct[nm].get(k, (0, 0)); return f'{100*a/b:5.1f}' if b else '  -  '
                print(f'    c_c={cc} 무변조 거절 {c["무변조 거절 X1+Z"]:3d}/{c["무변조 거절 X2"]:3d}'
                      f' | Cdet {e["Cdet"]["X1+Z"]:5.1f}/{e["Cdet"]["X2"]:5.1f}'
                      f' | 공통 분모 Cdet {e["common_Cdet"]["X1+Z"]:5.1f}/{e["common_Cdet"]["X2"]:5.1f}'
                      f' | 판정 차이 {c.get("판정 차이", 0):4d}/{c["공통 분모 공격"]} ({rate:4.2f}%)'
                      f' 취소 삭제 {cd.get("취소 삭제", 0)} 재전송 {cd.get("취소 재전송(청구완료)", 0)}'
                      f' | 공통 분모 취소 삭제 {typ("X1+Z", "취소 삭제")}/{typ("X2", "취소 삭제")}'
                      f' 재전송 {typ("X1+Z", "취소 재전송(청구완료)")}/{typ("X2", "취소 재전송(청구완료)")}')
                result.append(dict(p=p, pi=pi, cc=cc, ambiguous=dict(namb), attacks=natt, **e))
    print('\n  표기: 앞/뒤 = X1+Z/X2. 판정 차이는 바탕 파일이 X2에서 수락된 공격 중 X1+Z 수락·X2 거절.')
    if args.output:
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print('Saved', args.output)


if __name__ == '__main__': main()
