"""탐지율 정의 통일: 모든 표의 공격 탐지율을 두 가지로 함께 계산한다(판정기 ref2, 데이터는 각 원 실험과 같음).
  전체 거절률 T  = 유형별 (거절된 공격 수 / 공격 수)의 유형 균등 평균. 기존 표의 '탐지'와 같은 값이다.
  조건부 탐지율 C = 유형별 (바탕 정상 파일이 같은 관측 수준·업무 가정에서 수락된 공격 중 거절된 수 / 그 공격 수)의 유형 균등 평균.
바탕 정상 파일이 이미 거절되면(업무 가정 초과) 그 위의 공격 거절은 공격 때문이라고 볼 수 없으므로 C에서 뺀다.
대상: 표1(final_ref, A=(2,3,3)), S1~S3(sensitivity.py), S4(sensitivity_s4.py: 13유형, ID 3유형, 16유형)."""
import statistics as st
from ref2 import ref_accept
from sensitivity import build, SEED
from sensitivity_s4 import build_id, judge, LEVELS

def line(label, cases, K, Aa):
    ok = [ref_accept(F, led, K, Aa) for led, F, _ in cases]
    T, C, tcd, ccd, _ = rates_led(cases, ok, K, Aa)
    print(f'  {label:26s} 바탕 수락 {sum(ok):4d}/{len(cases)} | 전체 거절률 {T:5.1f} 조건부 탐지율 {C:5.1f} | 취소 삭제 {tcd:5.1f} / {ccd:5.1f}')

def rates_led(cases, ok, K, Aa):
    T, C = {}, {}
    for o, (led, F, A) in zip(ok, cases):
        for kd, G in A:
            r = not ref_accept(G, led, K, Aa)
            t = T.setdefault(kd, [0, 0]); t[0] += r; t[1] += 1
            if o: c = C.setdefault(kd, [0, 0]); c[0] += r; c[1] += 1
    m = lambda d: st.mean(100 * v[0] / v[1] for v in d.values())
    cd = lambda d: 100 * d['취소 삭제'][0] / d['취소 삭제'][1]
    return m(T), m(C), cd(T), cd(C), None

def main():
    base = build('orig')
    print(f'[고정] seed {SEED}, 정상 1000, 공격 13유형 {sum(len(a) for *_, a in base)}건. 값은 T(전체 거절률) / C(조건부 탐지율), 유형 균등 평균')
    print('\n[표1] A=(CR,c_s,c_c)=(2,3,3)')
    for nm, k in [('V0 내부 규칙', ''), ('V1 원장', 'L'), ('원장+청구일자', 'LD'), ('원장+D+B+Z', 'LDBZ'), ('D+B+Z+X1', 'LDBZX'), ('D+B+Z+X2', 'LDBZY'), ('D+B (Z 없음)+X1', 'LDBX'), ('D+B (Z 없음)+X2', 'LDBY')]:
        line(nm, base, set(k), (2, 3, 3))
    print('\n[S1] 취소 이월 허용 c_c (CR=2, c_s=3)')
    for cc in range(4):
        for nm, k in (('X1+Z', 'LDBZX'), ('X2', 'LDBZY')): line(f'c_c={cc} {nm}', base, set(k), (2, 3, cc))
    print('\n[S2] 반송 상한 CR (c_s=c_c=3)')
    for CR in (1, 2, 3, 99):
        for nm, k in (('L+D', 'LD'), ('L+D+Z', 'LDZ'), ('L+D+B+Z+X2', 'LDBZY')): line(f'CR={"∞" if CR == 99 else CR} {nm}', base, set(k), (CR, 3, 3))
    print('\n[S3] 취소 금액 분포 (CR=2, c_s=c_c=3)')
    for mode, lab in (('orig', '기존'), ('uniform', '균등'), ('unit', '단가 배수'), ('same', '동일 금액')):
        cs = base if mode == 'orig' else build(mode)
        for nm, k in (('X1+Z', 'LDBZX'), ('X2', 'LDBZY')): line(f'{lab} {nm}', cs, set(k), (2, 3, 3))
    print('\n[S4] 관측 수준별 13유형 / ID 3유형 / 16유형')
    cases, _ = build_id()
    for Aa in ((2, 3, 3), (2, 3, 1)):
        print(f'  A=(CR,c_s,c_c)={Aa}')
        for nm, K, u in LEVELS:
            ok = [judge(F, led, K, u, Aa) for led, F, _, _ in cases]
            res = {}
            for grp, sel in (('13유형', lambda a13, aid: a13), ('ID 3유형', lambda a13, aid: aid), ('16유형', lambda a13, aid: a13 + aid)):
                items = [(o, sel(a13, aid)) for o, (led, F, a13, aid) in zip(ok, cases)]
                led_of = [led for led, *_ in cases]
                T, C = {}, {}
                for o, led, (_, att) in zip(ok, led_of, items):
                    for kd, G in att:
                        r = not judge(G, led, K, u, Aa)
                        t = T.setdefault(kd, [0, 0]); t[0] += r; t[1] += 1
                        if o: c = C.setdefault(kd, [0, 0]); c[0] += r; c[1] += 1
                m = lambda d: st.mean(100 * v[0] / v[1] for v in d.values())
                res[grp] = (m(T), m(C))
            print(f'    {nm:6s} 바탕 수락 {sum(ok):4d}/{len(cases)} | ' + ' | '.join(f'{g} {t:5.1f} / {c:5.1f}' for g, (t, c) in res.items()))

if __name__ == '__main__': main()
