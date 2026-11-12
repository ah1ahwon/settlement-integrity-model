"""⑥ 보완(v6): 삭제 공격의 금액 규모. 판정기 ref3, 데이터 sensitivity.build('orig') = seed 2024, 정상 1,000건. 판정기·생성기 무수정.

E1 취소 삭제로 숨길 수 있는 최대 금액 (A=(2,3,c_c), c_c=0~5)
  대상: 같은 A에서 X2(L+D+B+Z+X2)가 원본을 수락하고 취소 레코드가 1~10건인 파일(삭제 조합 전수 탐색; 표 4-16과 같은 분모).
  X2 해석값: 따름정리 3.2에 따라 m = min(t, c_c − N_act)건까지 수락되므로 최대 금액 = 파일 취소 금액 중 큰 m건의 합.
    검증: (i) 큰 m건을 지운 파일을 판정기가 수락, (ii) 판정기가 수락한 모든 삭제 조합의 금액 ≤ 해석값. 위반 0이어야 한다.
  X1+Z: 판정기가 수락한 삭제 조합 중 금액 최대값(전수 탐색).
  비율: 숨긴 금액 / 해당 파일 취소 레코드 금액 합. 합성 금액(정수 10~200)은 통화 의미가 없으므로 비율을 주 지표로 쓴다.
  공격 전략 비교(X2): 상한을 아는 공격자가 큰 금액 m건을 지우는 경우와 같은 m건을 무작위로 지우는 경우의 기대 금액(m/t × 취소 합).
  취소 레코드가 10건을 넘는 파일은 X2 해석값만 따로 보고한다(X1+Z 탐색은 하지 않음).

E2 매출·연결 취소 동시 삭제의 순금액 (A=(2,c_s,3), c_s=0~4, K=X2; 표 4-17과 같은 공격)
  수락된 동시 삭제마다 순금액 = 지운 매출 금액 − 같이 지운 취소 금액. 이번 주기 정산에서 빠지는(이월되는) 금액이다.
  지표: 수락 공격 수(표 4-17의 분모 − 거절 수와 대조), 순금액 평균·중앙값, 파일 매출 합 대비 비율, 원본별 최대 순금액.
"""
import argparse, itertools, json, random, statistics as st
from collections import Counter
from ref3 import ref_accept
from sensitivity import build
from test_deletion_budget import n_act
from joint_deletion import s_def, joint_attacks

KY, KX = set('LDBZY'), set('LDBZX')
CCS, CSS = range(6), range(5)


def delete(F, S):
    return (F[0], [r for j, r in enumerate(F[1]) if j not in S])


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))] if xs else float('nan')


def e1(cases):
    out = {}; viol = Counter(); chk = Counter()
    for cc in CCS:
        A = (2, 3, cc)
        rows = []; big = []
        for led, F in cases:
            if not ref_accept(F, led, KY, A): continue
            idx = [j for j, r in enumerate(F[1]) if r[0] == 20]
            t = len(idx)
            if t == 0: continue
            amt = {j: F[1][j][2] for j in idx}; tot = sum(amt.values())
            m = min(t, cc - n_act(F, led))
            top = sorted(idx, key=lambda j: -amt[j])[:m]
            x2 = sum(amt[j] for j in top)
            chk['greedy'] += 1; viol['greedy'] += not ref_accept(delete(F, set(top)), led, KY, A)
            if t > 10:
                big.append(x2 / tot); continue
            x1 = x2_seen = 0
            for r in range(1, t + 1):
                for S in itertools.combinations(idx, r):
                    a = sum(amt[j] for j in S); G = delete(F, set(S))
                    if ref_accept(G, led, KY, A):
                        chk['subset'] += 1; viol['subset'] += a > x2; x2_seen = max(x2_seen, a)
                    if a > x1 and ref_accept(G, led, KX, A): x1 = a
            viol['exact'] += x2_seen != x2
            sales = sum(r[2] for r in F[1] if r[0] == 10)
            rows.append(dict(t=t, tot=tot, m=m, x2=x2, x1=x1, rnd=m / t * tot, sales=sales))
        n = len(rows); r2 = [r['x2'] / r['tot'] for r in rows]; r1 = [r['x1'] / r['tot'] for r in rows]
        hit = [r for r in rows if r['m'] >= 1]
        out[cc] = dict(
            files=n, files_gt10=len(big),
            x2_mean_ratio=100 * st.mean(r2), x2_median_ratio=100 * q(r2, .5), x2_full=100 * sum(x == 1 for x in r2) / n,
            x2_any=100 * len(hit) / n, x2_mean_amount=st.mean(r['x2'] for r in rows),
            x2_pooled_ratio=100 * sum(r['x2'] for r in rows) / sum(r['tot'] for r in rows),
            x1_mean_ratio=100 * st.mean(r1), x1_full=100 * sum(x == 1 for x in r1) / n,
            x1_gt_x2=sum(r['x1'] > r['x2'] for r in rows),
            greedy_over_random=(sum(r['x2'] for r in hit) / sum(r['rnd'] for r in hit)) if hit else None,
            random_mean_ratio=100 * st.mean(r['rnd'] / r['tot'] for r in rows),
            gt10_x2_mean_ratio=100 * st.mean(big) if big else None)
    return out, dict(chk), dict(viol)


def e2(cases):
    out = {}
    for cs in CSS:
        A = (2, cs, 3); acc = []; best = []; tot = rej = 0; chk = bad = 0; same_x1 = 0
        for led, F in cases:
            if not ref_accept(F, led, KY, A): continue
            sales = sum(r[2] for r in F[1] if r[0] == 10); b = 0
            want = s_def(F, led) + 1 <= cs
            for kind, G in joint_attacks(F):
                gone = [r for r in F[1] if r not in G[1]]
                sale = sum(r[2] for r in gone if r[0] == 10); canc = sum(r[2] for r in gone if r[0] == 20)
                ok = ref_accept(G, led, KY, A); tot += 1; rej += not ok
                chk += 1; bad += ok != want; same_x1 += ok == ref_accept(G, led, KX, A)
                if ok:
                    acc.append(dict(kind=kind, net=sale - canc, sale=sale, canc=canc, share=(sale - canc) / sales)); b = max(b, sale - canc)
            if any(True for _ in joint_attacks(F)) and want: best.append(b)
        nets = [a['net'] for a in acc]
        out[cs] = dict(attacks=tot, rejected=rej, accepted=len(acc), formula_checks=chk, formula_mismatch=bad, x1z_same=same_x1,
                       net_mean=st.mean(nets) if nets else None, net_median=q(nets, .5) if nets else None,
                       share_mean=100 * st.mean(a['share'] for a in acc) if acc else None,
                       with_cancel=sum(a['kind'] == '취소 있음' for a in acc),
                       canc_mean_with_cancel=st.mean(a['canc'] for a in acc if a['kind'] == '취소 있음') if acc else None,
                       best_net_mean=st.mean(best) if best else None, files_with_room=len(best))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--output'); args = ap.parse_args()
    cases = [(led, F) for led, F, _ in build('orig')]
    r1, chk, viol = e1(cases)
    print(f'[amount_deletion] seed 2024, 정상 {len(cases)}, 판정기 ref3, K=L+D+B+Z+X2 (대조 X1+Z)')
    print('\nE1 취소 삭제로 숨길 수 있는 최대 금액 (CR=2, c_s=3; 원본 X2 수락·취소 1~10건 파일)')
    print(f'  검증: 큰 m건 삭제 수락 {chk["greedy"]}건 중 위반 {viol.get("greedy", 0)}, 수락 조합 {chk["subset"]:,}건 중 해석값 초과 {viol.get("subset", 0)}, 해석값 미도달 파일 {viol.get("exact", 0)}')
    for cc, v in r1.items():
        g = f'{v["greedy_over_random"]:.2f}배' if v['greedy_over_random'] else '-'
        print(f'  c_c={cc} 파일 {v["files"]:4d} | X2 숨김 비율 평균 {v["x2_mean_ratio"]:5.1f}% 중앙 {v["x2_median_ratio"]:5.1f}% 합산 {v["x2_pooled_ratio"]:5.1f}%'
              f' 전액 {v["x2_full"]:5.1f}% 평균 금액 {v["x2_mean_amount"]:6.1f} | 무작위 m건 평균 {v["random_mean_ratio"]:5.1f}% 큰 금액 우선/무작위 {g}'
              f' | X1+Z 평균 {v["x1_mean_ratio"]:5.1f}% 전액 {v["x1_full"]:5.1f}% X1+Z>X2 {v["x1_gt_x2"]}'
              + (f' | 10건 초과 {v["files_gt10"]}개 X2 평균 {v["gt10_x2_mean_ratio"]:.1f}%' if v['files_gt10'] else ''))
    r2 = e2(cases)
    print('\nE2 매출·연결 취소 동시 삭제의 순금액 (CR=2, c_c=3, K=X2; 원본 X2 수락)')
    for cs, v in r2.items():
        if v['accepted']:
            print(f'  c_s={cs} 공격 {v["attacks"]} 거절 {v["rejected"]} 수락 {v["accepted"]} (취소 있음 {v["with_cancel"]}) | 순금액 평균 {v["net_mean"]:.1f} 중앙 {v["net_median"]}'
                  f' 파일 매출 대비 {v["share_mean"]:.1f}% | 연결 취소 평균 {v["canc_mean_with_cancel"]:.1f} | 여유 있는 원본 {v["files_with_room"]} 원본별 최대 순금액 평균 {v["best_net_mean"]:.1f}'
                  f' | 공식 불일치 {v["formula_mismatch"]}/{v["formula_checks"]} X1+Z 동일 {v["x1z_same"]}')
        else:
            print(f'  c_s={cs} 공격 {v["attacks"]} 거절 {v["rejected"]} 수락 0 | 공식 불일치 {v["formula_mismatch"]}/{v["formula_checks"]} X1+Z 동일 {v["x1z_same"]}')
    assert not any(viol.values()) and all(v['formula_mismatch'] == 0 for v in r2.values())
    if args.output:
        json.dump(dict(e1=r1, e1_checks=chk, e1_violations=viol, e2=r2), open(args.output, 'w'), ensure_ascii=False, indent=1)
    print('OK')


if __name__ == '__main__': main()
