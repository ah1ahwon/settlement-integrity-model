"""예산 차이만으로 X1+Z와 X2의 판정이 갈리는 128건의 판정 경로를 재현하는 최소 테스트.
세 가지 서로 다른 절차를 대조한다: (1) 해석식(포함관계 + 이월 비용), (2) ref.py ref_accept(동적 계획), (3) refval.py 의 정당 세계 직접 열거(worlds_files; AST로 함수만 추출).
조건: 원장 대사/거래 유형/금액 정합성 제약은 사전에 만족(파일은 취소 레코드만, 한 거래, 상태 C, 반송 이력 B 관측)하며, 거절 원인은 포함관계 위반과 예산 초과로 한정된다."""
import ast, csv, itertools, os, sys
from collections import Counter
from ref import ref_accept, view_set
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'refval.py')).read()
fn = [n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == 'worlds_files'][0]
ns = {'itertools': itertools, 'Counter': Counter, 'view_set': view_set}
exec(compile(ast.Module([fn], []), 'worlds_files', 'exec'), ns)
worlds_files = ns['worlds_files']
KY, KXZ = set('LDBY'), set('LDBZX')
def analytic(E, Zs, Pstar, F, cc):
    amts = [a for a, _ in E]
    Ps = [P for r in range(len(E) + 1) for P in itertools.combinations(range(len(E)), r) if sum(amts[j] for j in P) == Zs]
    incl = lambda P: not (Counter(F) - Counter(amts[j] for j in range(len(E)) if j not in P))
    mc = lambda P: len(E) - len(P) - len(F)
    y = incl(Pstar) and mc(Pstar) <= cc
    xz = any(incl(P) and mc(P) <= cc for P in Ps)
    return y, xz, [incl(P) for P in Ps], [mc(P) for P in Ps]
def main():
    tot = 0; diff = []; bad_ana = 0; bad_enum = 0
    for n in range(2, 5):
        for A in itertools.combinations_with_replacement(range(1, 6), n):
            for fl in itertools.product([0, 1], repeat=n):
                E = [(a, bool(f)) for a, f in zip(A, fl)]; Zs = sum(a for a, f in E if f)
                Pst = tuple(j for j, (a, f) in enumerate(E) if f)
                led = {1: dict(m=0, amt=sum(A) + 2, st='C', cum=Zs, ev=E)}
                for k in range(4):
                    for F in itertools.combinations_with_replacement(range(1, 6), k):
                        for cc in (0, 1, 2):
                            tot += 1
                            y, xz, incs, mcs = analytic(E, Zs, Pst, list(F), cc)
                            rs = [(20, 1, a) for a in F]; Aa = (2, 9, cc)
                            ry = ref_accept((0, rs), led, KY, Aa); rx = ref_accept((0, rs), led, KXZ, Aa)
                            if (ry, rx) != (y, xz): bad_ana += 1
                            if ry != rx:
                                key = tuple(sorted(rs))
                                ey = key in worlds_files(led, KY, Aa); ex = key in worlds_files(led, KXZ, Aa)
                                if (ey, ex) != (ry, rx): bad_enum += 1
                                kind = 'budget_only' if all(incs) else 'inclusion'
                                diff.append((kind, A, Zs, [a for a, f in E if f], list(F), cc, ry, rx, incs, mcs))
    cnt = Counter(d[0] for d in diff)
    print('열거한 (원장, 파일, 이월허용) 조합:', tot)
    print('해석식 vs ref_accept 불일치:', bad_ana)
    print('판정이 갈린 파일:', len(diff), cnt)
    print('갈린 파일에 대한 정당 세계 직접 열거와의 불일치:', bad_enum)
    out = os.path.join(HERE, '..', 'results', 'budget_only_128.csv')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bo = sorted([d for d in diff if d[0] == 'budget_only'], key=lambda d: (len(d[1]), sum(d[1]), d[1], d[4], d[5]))
    with open(out, 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['승인취소', '누계Z', '실제반영', '파일취소', '취소이월허용', 'X2(Y)판정', 'X1+Z판정', '가능집합별포함관계', '가능집합별이월건수'])
        for d in bo: w.writerow([d[1], d[2], d[3], d[4], d[5], '수락' if d[6] else '거절', '수락' if d[7] else '거절', d[8], d[9]])
    print('예산만 차이 사례 수:', len(bo), '-> results/budget_only_128.csv')
    # 대표 최소 사례와 단위 테스트
    m = bo[0]; print('최소 사례:', dict(zip(['종류', '승인취소', '누계', '실제반영', '파일취소', '허용', 'X2', 'X1+Z'], m[:8])), '가능 집합별 포함/이월', m[8], m[9])
    E = [(1, False), (1, False), (2, True)]
    led = {1: dict(m=0, amt=6, st='C', cum=2, ev=E)}
    assert not ref_accept((0, []), led, KY, (2, 9, 1))      # X2: 미반영 {1,1} 두 건 > 1 -> 거절
    assert ref_accept((0, []), led, KXZ, (2, 9, 1))         # X1+Z: 반영 {1,1} 세계(미반영 {2} 한 건) 존재 -> 수락
    assert ref_accept((0, []), led, KY, (2, 9, 2))          # 허용 2이면 둘 다 수락
    print('단위 테스트(승인 {1,1,2}, Z=2, 실제 반영 {2}, 파일 취소 없음, 허용 1): 통과')
    ok = (tot == 245280 and bad_ana == 0 and bad_enum == 0 and len(diff) == 1183 and cnt['budget_only'] == 128 and cnt['inclusion'] == 1055)
    print('보고 수치 일치:', ok)
    sys.exit(0 if ok else 1)
if __name__ == '__main__': main()
