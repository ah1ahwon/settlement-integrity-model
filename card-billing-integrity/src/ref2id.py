"""[ref2id] 취소 레코드가 승인 취소 이벤트 ID를 갖는 파일의 판정기(S4 전용, ref2.py는 수정하지 않음).
파일 레코드: 매출 (10, i, 금액), 취소 (20, i, 금액, j)  — j는 원장 led[i]['ev']의 색인(이벤트 ID).
판정 = ref2와 같은 정당 세계 정의(업무 가정, 상태 U/C/R, 반영 취소는 C 거래에만)에 ID 관측을 더한 것.
  1) ID를 뗀 파일로 ref2와 같은 내부·원장 검사
  2) ID 유효성 V(F): 같은 거래의 ID 중복 없음, 이벤트 존재, 금액 일치. 위반이면 거절
  3) 거래별 취소 비용: 반영 집합 P는 K=Y이면 실제 반영 집합, K=Z이면 합이 누계인 모든 집합,
     둘 다 없으면 임의 집합. 상태가 C가 아니면 P=∅. P와 보낸 ID 집합 S는 서로소여야 하며 비용 = n-|P|-|S| 의 최소
  4) ref2와 같은 방식으로 (반송, 판매 이월, 취소 이월) 삼중항을 합산해 예산 비교
판정기 내부 반복문은 ref2.ref_accept와 같은 구조를 그대로 옮겼다."""
import itertools
from m2 import atoms
from ref2 import view_set, REC, INT

def strip(F):
    hm, rs = F
    return hm, [r[:3] for r in rs]

def id_valid(F, led):
    hm, rs = F; seen = set()
    for r in rs:
        if r[0] != 20: continue
        _, i, a, j = r
        if i not in led or led[i]['m'] != hm: continue        # 원장 검사가 처리
        ev = led[i]['ev']
        if (i, j) in seen or not (0 <= j < len(ev)) or ev[j][0] != a: return False
        seen.add((i, j))
    return True

def cancel_mc_id(S, ev, cum, K, s):
    n = len(ev); S = set(S)
    if s != 'C': Ps = [()]
    elif 'Y' in K: Ps = [tuple(j for j in range(n) if ev[j][1])]
    elif 'Z' in K: Ps = [P for r in range(n + 1) for P in itertools.combinations(range(n), r) if sum(ev[j][0] for j in P) == cum]
    else: Ps = [P for r in range(n + 1) for P in itertools.combinations(range(n), r)]
    best = None
    for P in Ps:
        if S & set(P): continue
        m = n - len(P) - len(S); best = m if best is None else min(best, m)
    return best

def ref_accept_id(F, led, K, Aa):
    CR, cs, cc = Aa; hm, rs = F; Fs = strip(F)
    a = atoms(Fs, led, {'L'} | ({'Z'} if 'Z' in K else set()) if 'L' in K else set(), 0)
    if not all(a[k] for k in INT): return False
    if 'L' not in K: return True
    if not all(a[k] for k in REC): return False
    if not id_valid(F, led): return False
    sent = {i for t, i, *_ in rs if t == 10}; f20 = {}
    for r in rs:
        if r[0] == 20: f20.setdefault(r[1], []).append(r[3])
    mine = [i for i in led if led[i]['m'] == hm]
    reach = {(0, 0, 0)}
    for i in mine:
        opts = set()
        for s in view_set(K, led[i]['st']):
            if s != 'C' and (('Z' in K and led[i]['cum'] > 0) or ('Y' in K and any(cl for _, cl in led[i]['ev']))): continue
            if i in sent:
                if s == 'C': continue
                r, ms, el = (1 if s == 'R' else 0), 0, True
            elif s == 'C': r, ms, el = 0, 0, True
            else: r, ms, el = (1 if s == 'R' else 0), 1, False
            Si = f20.get(i, [])
            if not el:
                if Si: continue
                mc = 0
            else:
                mc = cancel_mc_id(Si, led[i]['ev'], led[i]['cum'], K, s)
                if mc is None: continue
            opts.add((r, ms, mc))
        new = set()
        for (r0, m0, c0) in reach:
            for (r, ms, mc) in opts:
                t = (r0 + r, m0 + ms, c0 + mc)
                if t[0] <= CR and t[1] <= cs and t[2] <= cc: new.add(t)
        reach = new
        if not reach: return False
    return True
