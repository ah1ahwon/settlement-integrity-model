import itertools, random, collections
from collections import Counter
from ref import ref_accept
# ---- (1) 단일 거래: 판정 차이의 원인 분류. 해석식으로 계산 후 ref_accept와 대조
def subsets(E):
    return [P for r in range(len(E)+1) for P in itertools.combinations(range(len(E)),r)]
def analyze(E,Zs,P_star,F,cc):
    amts=[a for a,_ in E]
    Ps=[P for P in subsets(E) if sum(amts[j] for j in P)==Zs]
    def incl(P):
        rest=Counter(amts[j] for j in range(len(E)) if j not in P); return not (Counter(F)-rest)
    def mc(P): return len(E)-len(P)-len(F)
    y=incl(P_star) and mc(P_star)<=cc
    xz=any(incl(P) and mc(P)<=cc for P in Ps)
    return y,xz,Ps,[incl(P) for P in Ps],[mc(P) for P in Ps]
cnt=collections.Counter(); chk=0; badchk=0; ex={}
for n in range(2,5):
  for A in itertools.combinations_with_replacement(range(1,6),n):
    for fl in itertools.product([0,1],repeat=n):
        E=[(a,bool(f)) for a,f in zip(A,fl)]; Zs=sum(a for a,f in E if f); Pst=tuple(j for j,(a,f) in enumerate(E) if f)
        led={1:dict(m=0,amt=sum(A)+2,st='C',cum=Zs,ev=E)}
        for k in range(0,4):
            for F in itertools.combinations_with_replacement(range(1,6),k):
                for cc in (0,1,2):
                    y,xz,Ps,inc,mcs=analyze(E,Zs,Pst,list(F),cc)
                    # 대조
                    r_y=ref_accept((0,[(20,1,a) for a in F]),led,set('LDY'),(2,9,cc)); r_x=ref_accept((0,[(20,1,a) for a in F]),led,set('LDZX'),(2,9,cc))
                    chk+=1
                    if (r_y,r_x)!=(y,xz): badchk+=1
                    if y!=xz:
                        ctype='포함관계 차이' if len(set(inc))>1 else '비용(예산)만 차이'
                        cnt[ctype]+=1
                        ex.setdefault(ctype,(A,Zs,[a for a,f in E if f],list(F),cc,list(zip(Ps,inc,mcs))))
print('[단일 거래] 해석식과 ref_accept 대조',chk,'건 중 불일치',badchk)
print('판정이 갈린 파일 원인 분류:',dict(cnt))
for k,v in ex.items(): print(' 예(',k,'): 승인취소',v[0],'누계',v[1],'실제 반영',v[2],'파일 취소',v[3],'취소 이월 허용',v[4],'\n    가능한 반영 집합(색인), 포함 여부, 이월 건수:',v[5])
# ---- (2) 두 거래 전역 예산 결합: 거래별로는 어느 한쪽도 단독으로는 갈리지 않지만 합산 예산에서 갈리는 사례
rng=random.Random(3); coup=0; tot=0; exs=None
def single_diff(E,Zs,Pst,F,cc):
    y,xz,*_=analyze(E,Zs,Pst,F,cc); return y!=xz
for _ in range(20000):
    leds={}; parts=[]
    for i in (1,2):
        n=rng.randint(2,4); A=[rng.randint(1,4) for _ in range(n)]; fl=[rng.random()<.5 for _ in range(n)]
        E=[(a,bool(f)) for a,f in zip(A,fl)]; Zs=sum(a for a,f in E if f); Pst=tuple(j for j,(a,f) in enumerate(E) if f)
        leds[i]=dict(m=0,amt=sum(A)+2,st='C',cum=Zs,ev=E); parts.append((E,Zs,Pst))
    Fs={i:[rng.randint(1,4) for _ in range(rng.randint(0,2))] for i in (1,2)}
    F=(0,[(20,i,a) for i in (1,2) for a in Fs[i]])
    for cc in (1,2,3):
        y=ref_accept(F,leds,set('LDY'),(2,9,cc)); xz=ref_accept(F,leds,set('LDZX'),(2,9,cc)); tot+=1
        if y!=xz:
            # 거래별로 (예산 무제한=9)에서는 판정이 같은가?
            y9=ref_accept(F,leds,set('LDY'),(2,9,9)); x9=ref_accept(F,leds,set('LDZX'),(2,9,9))
            if y9==x9 and exs is None:
                exs=(parts,Fs,cc)
            if y9==x9: coup+=1
print(f'\n[두 거래] 무작위 {tot}건 중, 개별 판정(예산 충분)은 같은데 공통 취소 예산에서만 갈린 경우 {coup}건')
if exs: 
    for i,(E,Zs,Pst) in enumerate(exs[0],1): print(f'  거래{i}: 승인취소 {[a for a,f in E]}, 누계 {Zs}, 실제 반영 {[a for a,f in E if f]}, 파일 취소 {exs[1][i]}')
    print('  취소 이월 허용 합계',exs[2])
