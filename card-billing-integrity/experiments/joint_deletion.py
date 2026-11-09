"""③ 보완: 매출과 그 거래의 취소 레코드를 함께 삭제하는 공격(판정기 ref3, 데이터 sensitivity.build('orig') = seed 2024, 정상 1,000건).
공격: 정상 파일의 매출 레코드마다 하나씩, 그 매출과 같은 거래의 취소 레코드를 모두 지운 파일을 만든다(원장 불변).
  그 거래의 취소 레코드가 없으면 기존 '거래 삭제'와 같은 파일이므로 '취소 있음'과 '취소 없음'을 나누어 기록한다.
지표: Trej·Cdet(분자/분모), CR=2·c_c=3에서 c_s=0~4.
공식 후보(K가 L·D·B·X2 포함, 원본이 같은 K·A에서 수락):
  삭제 파일 수락 ⇔ S_def(F) + 1 ≤ c_s. S_def(F)는 미청구·반송 거래 중 F에 매출이 없는 건수이며 원장과 파일에서 직접 센다.
  근거: 상태가 고정되어 반송 비용은 그대로, 매출 이월은 1 증가, 그 거래의 미송신 취소는 A5에 따라 비용 0이 되어 취소 이월은 줄거나 같다.
  전제를 뺀 대조(L+D, L+D+B+Z+X1)는 원본이 X2에서 수락된 파일로 한정해 불일치 수만 기록한다."""
from collections import Counter
from ref3 import ref_accept
from sensitivity import build

LEVELS = [('L', 'L'), ('L+D', 'LD'), ('L+D+B+Z', 'LDBZ'), ('L+D+B+Z+X1', 'LDBZX'), ('L+D+B+Z+X2', 'LDBZY')]
FULL = [('X2', set('LDBZY')), ('X2(Z 미보유)', set('LDBY'))]
CONTRAST = [('B 없음 L+D', set('LD')), ('X1+Z', set('LDBZX'))]
CSS = range(5)


def s_def(F, led):
    sent = {r[1] for r in F[1] if r[0] == 10}
    return sum(v['m'] == F[0] and v['st'] in 'UR' and i not in sent for i, v in led.items())


def joint_attacks(F):
    for r in F[1]:
        if r[0] != 10: continue
        G = (F[0], [x for x in F[1] if x[1] != r[1]])
        yield ('취소 있음' if len(G[1]) < len(F[1]) - 1 else '취소 없음'), G


def pct(a, b):
    return f'{100 * a / b:5.1f}% ({a}/{b})' if b else '  -  '


def main():
    cases = [(led, F, list(joint_attacks(F))) for led, F, _ in build('orig')]
    n = Counter(k for *_, att in cases for k, _ in att)
    print(f'[joint_deletion] seed 2024, 정상 {len(cases)}, 공격 {sum(n.values())} (취소 있음 {n["취소 있음"]}, 취소 없음 {n["취소 없음"]}), CR=2, c_c=3, 판정기 ref3')
    chk = Counter(); bad = Counter(); lenient = Counter()
    for cs in CSS:
        A = (2, cs, 3)
        print(f'\n  c_s={cs}')
        for nm, k in LEVELS:
            K = set(k); s = {key: [0, 0, 0, 0] for key in ('전체', '취소 있음', '취소 없음')}
            for led, F, att in cases:
                ok = ref_accept(F, led, K, A)
                for kind, G in att:
                    rej = not ref_accept(G, led, K, A)
                    for key in ('전체', kind):
                        v = s[key]; v[0] += rej; v[1] += 1
                        if ok: v[2] += rej; v[3] += 1
            print(f'    K={nm:11s} ' + ' | '.join(f'{key} Trej {pct(a, b)} Cdet {pct(c, d)}' for key, (a, b, c, d) in s.items()))
        for led, F, att in cases:
            if not ref_accept(F, led, set('LDBZY'), A): continue
            want = s_def(F, led) + 1 <= cs
            for nm, K in FULL + CONTRAST:
                for _, G in att:
                    got = ref_accept(G, led, K, A)
                    chk[nm] += 1; bad[nm] += got != want; lenient[nm] += got and not want
    print('\n  공식 검사(원본이 X2에서 수락, c_s=0~4)')
    for nm, _ in FULL + CONTRAST:
        print(f'    {nm:14s} 검사 {chk[nm]:7,d} 불일치 {bad[nm]} (공식보다 더 수락 {lenient[nm]})')
    assert all(bad[nm] == 0 for nm, _ in FULL)
    print('OK')


if __name__ == '__main__': main()
