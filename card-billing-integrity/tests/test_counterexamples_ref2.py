"""반례 표의 ref2 정식 판(원 tests/cex.py는 구 판정기 explainable4로 실행되며 수정하지 않는다).
  [1] cex.py의 11개 사례를 ref2로 판정한 표와, 같은 사례·관측·허용치에서 explainable4와의 판정 차이
  [2] 반례 3.1(예산형)과 반례 3.2(포함관계형): 청구완료 거래 하나, 승인 취소 {a:1, b:1, c:2}, Z = 2.
      반영 후보 P(금액 합 = Z)별 미반영 다중집합과 최소 취소 이월 비용, 허용치 c_c별 X1+Z·X2 판정."""
import io, contextlib, runpy, os, itertools
from collections import Counter
from ref2 import ref_accept
from m4 import explainable4

KX, KY = set('LDBZX'), set('LDBZY')
w = lambda b: '수락' if b else '거절'

def part1():
    with contextlib.redirect_stdout(io.StringIO()):
        g = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cex.py'))
    print('[1] cex.py 사례의 ref2 판정 (A=(2, c, c), c는 사례별 허용치)')
    print(f'  {"사례":26s}' + ''.join(f'{n:>9s}' for n, _ in g['KSET']))
    diff = 0
    for nm, desc, led, rs, c in g['I']:
        row = []
        for _, k in g['KSET']:
            b = ref_accept((0, rs), led, set(k), (2, c, c)); row.append(w(b))
            diff += b != explainable4((0, rs), led, set(k), c)
        print(f'  {nm:26s}' + ''.join(f'{r:>10s}' for r in row))
    print(f'  explainable4와의 판정 차이: {diff}/{len(g["I"]) * len(g["KSET"])}')

def tx(reflected, amt=10):
    names = ['a', 'b', 'c']; amts = [1, 1, 2]
    ev = [(x, n in reflected) for n, x in zip(names, amts)]
    return {1: dict(m=0, amt=amt, st='C', cum=sum(x for x, f in ev if f), ev=ev)}, names, amts

def detail(title, reflected, sent):
    led, names, amts = tx(reflected); F = (0, [(20, 1, amts[names.index(n)]) for n in sent])
    print(f'  {title}: 실제 반영 {{{",".join(reflected)}}}, 파일 취소 {[amts[names.index(n)] for n in sent]} (금액), Z = {led[1]["cum"]}')
    Fc = Counter(amts[names.index(n)] for n in sent)
    for r in range(4):
        for P in itertools.combinations(range(3), r):
            if sum(amts[j] for j in P) != led[1]['cum']: continue
            rest = Counter(amts[j] for j in range(3) if j not in P)
            ok = not (Fc - rest)
            print(f'    후보 P = {{{",".join(names[j] for j in P)}}}: 미반영 {sorted(rest.elements())}, 파일 취소 송신 ' + (f'가능, 이월 {sum((rest - Fc).values())}건' if ok else '불가(반영된 취소 재송신)')
                  + ('  ← 실제 반영' if set(names[j] for j in P) == set(reflected) else ''))
    for cc in (0, 1, 2):
        print(f'    c_c={cc}: X1+Z {w(ref_accept(F, led, KX, (2, 3, cc)))}, X2 {w(ref_accept(F, led, KY, (2, 3, cc)))}')

def main():
    part1()
    print('\n[2] 반례 (청구완료 거래 하나, 승인 취소 a:1, b:1, c:2, 승인 금액 10, A=(2, 3, c_c))')
    detail('반례 3.1 예산형', ['c'], [])
    detail('반례 3.2 포함관계형', ['c'], ['c'])
    detail('참고: 반영 {a,b}에서 a 재송신', ['a', 'b'], ['a'])

if __name__ == '__main__': main()
