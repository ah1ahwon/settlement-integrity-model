"""반례 3.1·3.2와 ID 식별력 사례를 네 관측 수준(X1-금액, X1-ID, X2-금액, X2-ID)에서 판정한다(판정기 ref2, ref2id).
청구완료 거래 하나, 승인 금액 10, A=(2, 3, c_c), c_c ∈ {0, 1, 2}. 이벤트 ID는 승인 취소 목록의 색인이다.
  반례 3.1 예산형     : 승인 취소 a:1, b:1, c:2, 실제 반영 {c}, Z = 2, 파일에 취소 없음
  반례 3.2 포함관계형 : 같은 원장, 파일이 c(2)를 ID와 함께 재송신
  ID 식별력 사례      : 승인 취소 a:1, b:1, 실제 반영 {b}, Z = 1, 파일이 b(1)를 ID와 함께 재송신"""
from ref2 import ref_accept
from ref2id import ref_accept_id, strip

LV = [('X1-금액', 'LDBZX', False), ('X1-ID', 'LDBZX', True), ('X2-금액', 'LDBZY', False), ('X2-ID', 'LDBZY', True)]
w = lambda b: '수락' if b else '거절'

def case(title, names, amts, reflected, sent):
    ev = [(a, n in reflected) for n, a in zip(names, amts)]
    led = {1: dict(m=0, amt=10, st='C', cum=sum(a for a, f in ev if f), ev=ev)}
    F = (0, [(20, 1, amts[names.index(n)], names.index(n)) for n in sent])
    print(f'{title}: 승인 취소 {dict(zip(names, amts))}, 실제 반영 {{{",".join(reflected)}}}, Z = {led[1]["cum"]}, 파일 취소 ID {sent}')
    for cc in (0, 1, 2):
        A = (2, 3, cc)
        r = [ref_accept_id(F, led, set(k), A) if u else ref_accept(strip(F), led, set(k), A) for _, k, u in LV]
        print(f'  c_c={cc}: ' + ', '.join(f'{nm} {w(x)}' for (nm, *_), x in zip(LV, r)))

def main():
    case('반례 3.1 예산형', ['a', 'b', 'c'], [1, 1, 2], ['c'], [])
    case('반례 3.2 포함관계형', ['a', 'b', 'c'], [1, 1, 2], ['c'], ['c'])
    case('ID 식별력 사례', ['a', 'b'], [1, 1], ['b'], ['b'])

if __name__ == '__main__': main()
