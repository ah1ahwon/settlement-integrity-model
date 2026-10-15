"""고정 설정: 정당 1000파일(seed 2024), p=10%, CR=2, 기준 c=3, 통일 판정 vs 기존 판정(같은 파일·같은 공격)."""
import random, statistics as st, collections, copy
from ref import ref_accept
from m4 import explainable4, attacks4
from run9 import make_case5
P=0.10; CR=2; CM=3
rng=random.Random(2024); CASES=[]
for _ in range(1000):
    led,F,ds,dc=make_case5(rng,P,P); CASES.append((led,F,attacks4(F,led,rng)))
print('고정:', len(CASES),'파일,', sum(len(a) for _,_,a in CASES),'공격, p=10%, CR=2, 기준 c=3')
SETS=[('V0 내부 규칙','' ),('V1 원장','L'),('원장+청구일자','LD'),('원장+D+B+Z','LDBZ'),('D+B+Z+X1','LDBZX'),('D+B+Z+X2','LDBZY'),('D+B (Z 없음)+X1','LDBX'),('D+B (Z 없음)+X2','LDBY')]
kinds=sorted({kd for _,_,A in CASES for kd,_ in A})
def tab(acc):
    R={}
    for nm,k in SETS:
        per={}; fr=0
        for l,F,A in CASES:
            fr+= not acc(F,l,set(k)); 
            for kd,G in A:
                d=per.setdefault(kd,[0,0]); d[0]+= not acc(G,l,set(k)); d[1]+=1
        R[k]=(per,100*fr/len(CASES))
    return R
new=tab(lambda G,l,k: ref_accept(G,l,k,(CR,CM,CM)))
old=tab(lambda G,l,k: explainable4(G,l,k,CM))
bal=lambda per: st.mean(100*v[0]/v[1] for v in per.values())
print('\n[표1] 조합별 유형균등 평균 차단% 및 오차단%  (기존 / 새 / 차이)')
for nm,k in SETS:
    o,n=bal(old[k][0]),bal(new[k][0])
    print(f'  {nm:18s} {o:5.1f} / {n:5.1f} / {n-o:+5.1f}   오차단 {old[k][1]:.1f} / {new[k][1]:.1f}')
print('\n[표1b] 유형별로 달라진 곳만 (기존 → 새, 차단율%)')
for kd in kinds:
    ch=[]
    for nm,k in SETS:
        o=100*old[k][0][kd][0]/old[k][0][kd][1]; n=100*new[k][0][kd][0]/new[k][0][kd][1]
        if abs(o-n)>=1: ch.append(f'{nm}:{o:.0f}→{n:.0f}')
    if ch: print(f'  {kd:22s}',' | '.join(ch))
print('\n[표1c] 새 판정 유형별 전체표 (V0, V1, +D, +D+B+Z, +X1, +X2, Z없이 X1, Z없이 X2)')
for kd in kinds: print(f'  {kd:22s}',*[f'{100*new[k][0][kd][0]/new[k][0][kd][1]:4.0f}' for _,k in SETS])
# 표3 격자 (새 vs 기존)
def grid(p,cs_list,acc):
    r=random.Random(77); C=[make_case5(r,p,p) for _ in range(600)]; out=[]
    for c in cs_list:
        f=0; d={'c':[0,0],'s':[0,0]}
        for led,F,_,_ in C:
            f+= not acc(F,led,c); rs=F[1]
            for j,x in enumerate(rs):
                G=(0,rs[:j]+rs[j+1:]); t='c' if x[0]==20 else 's'; d[t][1]+=1; d[t][0]+= not acc(G,led,c)
        out.append((100*f/len(C),100*d['c'][0]/max(1,d['c'][1]),100*d['s'][0]/max(1,d['s'][1])))
    return out
K5=set('LDBZY')
print('\n[표3] 실제 지연 p x 허용치 c: 오차단% / 취소삭제% / 거래삭제%   (기존 → 새)')
for p in (0.0,0.05,0.1,0.2):
    o=grid(p,range(5),lambda G,l,c: explainable4(G,l,K5,c)); n=grid(p,range(5),lambda G,l,c: ref_accept(G,l,K5,(CR,c,c)))
    print(f'  p={p:<5}', ' '.join(f'c{c}:{o[c][0]:.0f}/{o[c][1]:.0f}/{o[c][2]:.0f}→{n[c][0]:.0f}/{n[c][1]:.0f}/{n[c][2]:.0f}' for c in range(5)))
# 표4 분리 예산
import m2
from m4 import extra_ok
def go(ps,pc,cs,cc,acc,N=600,seed=17):
    r=random.Random(seed); f=0; n=dict(s=[0,0],c=[0,0])
    for _ in range(N):
        led,F,_,_=make_case5(r,ps,pc); rs=F[1]; f+= not acc(F,led,cs,cc)
        for typ,t in (('s',10),('c',20)):
            for j,x in enumerate(rs):
                if x[0]!=t: continue
                G=(0,rs[:j]+rs[j+1:]); n[typ][1]+=1; n[typ][0]+= not acc(G,led,cs,cc)
    return 100*f/N,100*n['s'][0]/max(1,n['s'][1]),100*n['c'][0]/max(1,n['c'][1])
oldacc=lambda G,l,cs,cc: m2.explainable.__call__(G,l,{'L','D','B','Z'},cs) and extra_ok(G,l,K5,cc)
newacc=lambda G,l,cs,cc: ref_accept(G,l,K5,(CR,cs,cc))
print('\n[표4] 분리 허용치: 오차단% / 판매삭제% / 취소삭제%  (기존 → 새)')
for ps,pc in ((0.1,0.0),(0.1,0.1),(0.0,0.1)):
    for cs,cc in ((3,3),(3,0),(0,3)):
        o=go(ps,pc,cs,cc,oldacc); n=go(ps,pc,cs,cc,newacc)
        print(f'  p_판매={ps} p_취소={pc} | c_판매={cs} c_취소={cc}: {o[0]:.1f}/{o[1]:.0f}/{o[2]:.0f} → {n[0]:.1f}/{n[1]:.0f}/{n[2]:.0f}')
# 표5 반영 상태 오류
def lag(led,p,r,mode):
    l2=copy.deepcopy(led)
    for i in l2:
        l2[i]['ev']=[((a,(False if (cl and mode=='old') else (True if (not cl and mode=='early') else cl))) if r.random()<p else (a,cl)) for a,cl in l2[i]['ev']]
    return l2
print('\n[표5] X2 반영상태 오류 (오차단% / 유형균등 차단%)  기존 → 새')
for mode,lab in (('old','청구완료→미반영 표시'),('early','미반영→반영 표시')):
    for p in (0,.05,.1,.2):
        res=[]
        for acc in (lambda G,l: explainable4(G,l,K5,CM), lambda G,l: ref_accept(G,l,K5,(CR,CM,CM))):
            r=random.Random(3); f=0; per={}
            for led,F,A in CASES:
                l2=lag(led,p,r,mode); f+= not acc(F,l2)
                for kd,G in A:
                    if kd=='취소 재전송(청구완료)': continue
                    d=per.setdefault(kd,[0,0]); d[0]+= not acc(G,l2); d[1]+=1
            res.append((100*f/len(CASES),bal(per)))
        print(f'  {lab:18s} {int(p*100):2d}%: {res[0][0]:.1f}/{res[0][1]:.1f} → {res[1][0]:.1f}/{res[1][1]:.1f}')
