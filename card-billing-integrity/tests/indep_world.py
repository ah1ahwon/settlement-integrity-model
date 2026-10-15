"""판정기(ref.py)와 구 규칙(m2.py, m4.py)을 import하지 않는 독립 열거기.

판정기는 '관측에서 허용되는 숨은 상태 후보(view_set)'와 '취소 규칙(cancel_mc)'을 규칙으로 계산한다.
이 열거기는 그 규칙을 쓰지 않고, 업무 가정 A의 정당 세계를 문장 정의 그대로 전부 만든 다음
관측 함수 observe()로 실제 세계와 관측이 같은 세계만 남긴다. 남은 세계가 만들 수 있는 파일 전체가 정당 파일 집합이다.

정당 세계(거래 하나):
  - 실제 상태 s ∈ {U(미청구), C(청구완료), R(반송)}
  - 승인 취소 이벤트 다중집합 ev = [(금액, 반영여부)], 금액 합 ≤ 승인금액
  - 업무 제약: 반영된 취소는 청구완료(C) 거래에만 있다
정당 파일(가맹점 하나): 거래마다
  - s ∈ {U,R}: 매출(10)을 보내거나 이월(판매 이월 1)
  - s = C: 매출을 다시 보내지 않는다
  - 이번 파일에 매출을 보냈거나 s = C이면, 미반영 취소 중 일부를 20로 보내고 나머지는 이월(취소 이월 건수)
  - 그 외에는 취소를 보내지 않는다
  전역 예산: 반송 거래 수 ≤ CR, 판매 이월 ≤ cs, 취소 이월 ≤ cc
관측 K ⊆ {L,D,B,Z,X,Y}: L 승인원장(가맹점, 금액), D 미청구 여부, B 상태(C/R), Z 반영 누계, X 승인 취소 금액 목록, Y 이벤트별 반영 여부.
제한 모델: 승인금액 1..AMT_MAX. 이벤트 금액은 1 이상이고 합이 승인금액 이하이므로 이벤트 공간이 유한하고 빠짐없이 열거된다."""
import itertools

AMT_MAX = 3

def event_lists(amt):
    """금액 합 ≤ amt인 (금액, 반영) 다중집합 전부(정렬된 튜플)."""
    kinds = [(a, f) for a in range(1, amt + 1) for f in (False, True)]
    out = []
    def rec(start, cur, s):
        out.append(tuple(cur))
        for k in range(start, len(kinds)):
            if s + kinds[k][0] <= amt:
                rec(k, cur + [kinds[k]], s + kinds[k][0])
    rec(0, [], 0)
    return out

def tx_worlds(amt):
    for s in 'UCR':
        for ev in event_lists(amt):
            if s != 'C' and any(f for _, f in ev):
                continue
            yield s, ev

def observe(K, m, amt, s, ev):
    o = [('L', m, amt)]
    if 'D' in K: o.append(('D', s == 'U'))
    if 'B' in K: o.append(('B', s))
    if 'Z' in K: o.append(('Z', sum(a for a, f in ev if f)))
    if 'Y' in K: o.append(('Y', tuple(sorted(ev))))
    elif 'X' in K: o.append(('X', tuple(sorted(a for a, _ in ev))))
    return tuple(o)

def local_outputs(s, ev):
    """한 거래 세계가 낼 수 있는 (매출 송신, 취소 금액 다중집합, 반송, 판매 이월, 취소 이월)."""
    unref = [a for a, f in ev if not f]
    res = set()
    for sent in ((True, False) if s in 'UR' else (False,)):
        r = 1 if s == 'R' else 0
        ms = 1 if (s in 'UR' and not sent) else 0
        if sent or s == 'C':
            for k in range(len(unref) + 1):
                for T in itertools.combinations(range(len(unref)), k):
                    res.add((sent, tuple(sorted(unref[j] for j in T)), r, ms, len(unref) - k))
        else:
            res.add((sent, (), r, ms, 0))
    return res

def legit_files(led, hm, K, A):
    """관측 K에서 실제 원장 led와 구별되지 않는 모든 정당 세계가 만들 수 있는 가맹점 hm의 파일 집합."""
    CR, cs, cc = A
    mine = sorted(i for i in led if led[i]['m'] == hm)
    per = []
    for i in mine:
        t = led[i]
        true_obs = observe(K, t['m'], t['amt'], t['st'], tuple(sorted(t['ev'])))
        outs = set()
        for s, ev in tx_worlds(t['amt']):
            if observe(K, t['m'], t['amt'], s, ev) == true_obs:
                outs |= local_outputs(s, ev)
        per.append(outs)
    files = set()
    for combo in itertools.product(*per):
        if sum(c[2] for c in combo) > CR or sum(c[3] for c in combo) > cs or sum(c[4] for c in combo) > cc:
            continue
        rec = []
        for i, (sent, T, *_) in zip(mine, combo):
            if sent: rec.append((10, i, led[i]['amt']))
            rec += [(20, i, a) for a in T]
        files.add((hm, tuple(sorted(rec))))
    return files
