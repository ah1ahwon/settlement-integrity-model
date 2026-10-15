"""독립 열거: 세계(실제 상태, 반영 플래그)를 직접 열거해 생성 가능한 파일 집합을 만들고 ref_accept와 대조."""
import random, itertools
from collections import Counter
from ref import *
def worlds_files(led,K,Aa):
    CR,cs,cc=Aa; mine=[i for i in led if led[i]['m']==0]; out=set()
    Ss=[view_set(K,led[i]['st']) for i in mine]
    for ss in itertools.product(*Ss):
        if sum(s=='R' for s in ss)>CR: continue
        flagopts=[]
        for i,s in zip(mine,ss):
            ev=led[i]['ev']; n=len(ev); o=[]
            for fl in itertools.product([False,True],repeat=n):
                if 'Y' in K and any(f!=e[1] for f,e in zip(fl,ev)): continue
                if 'X' in K and 'Y' not in K and 'Z' in K and sum(e[0] for f,e in zip(fl,ev) if f)!=led[i]['cum']: continue
                o.append(fl)
            flagopts.append(o)
        for fls in itertools.product(*flagopts):
            ids=[i for i,s in zip(mine,ss) if s in 'UR']
            for r in range(len(ids)+1):
                for sent in itertools.combinations(ids,r):
                    if len(ids)-r>cs: continue
                    elig=[i for i,s in zip(mine,ss) if s=='C' or i in sent]
                    unc={i:[e[0] for f,e in zip(fl,led[i]['ev']) if not f] for i,fl in zip(mine,fls)}
                    tot_un=sum(len(unc[i]) for i in elig)
                    choices=[]
                    for i in elig:
                        cs_=[]
                        for k in range(len(unc[i])+1):
                            for T in itertools.combinations(range(len(unc[i])),k):
                                cs_.append((tuple(sorted(unc[i][j] for j in T)),len(unc[i])-k))
                        choices.append(cs_)
                    for ch in itertools.product(*choices):
                        if sum(m for _,m in ch)>cc: continue
                        rec=[(10,i,led[i]['amt']) for i in sent]+[(20,i,a) for i,(T,_) in zip(elig,ch) for a in T]
                        out.add(tuple(sorted(rec)))
    return out
rng=random.Random(4); n=0; bad=0; legit_rej=0
for trial in range(400):
    led={}; nm=rng.choice([1,2,3])
    for i in range(1,nm+1):
        amt=rng.randint(3,8); st_=rng.choice('UCR')
        if st_=='C':
            ev=[]; rem=amt
            for _ in range(rng.randint(0,3)):
                if rem<1: break
                x=rng.randint(1,min(rem,4)); rem-=x; ev.append((x,rng.random()<.5))
            cum=sum(x for x,f in ev if f)
        else: ev=[(rng.randint(1,2),False)] if rng.random()<.4 else []; cum=0
        led[i]=dict(m=0,amt=amt,st=st_,cum=cum,ev=ev)
    for K in (set('LD'),set('LDB'),set('LDBZ'),set('LDX'),set('LDBX'),set('LDZX'),set('LDBZX'),set('LDY'),set('LDBY'),set('LDBZY'),set('LX'),set('LY')):
        if not (('X' in K) or ('Y' in K)):
            continue  # 취소 목록을 모르는 K는 기록 단위 한도 규칙으로 처리(열거 대상에서 제외)
        Aa=(rng.choice([1,2]),rng.choice([0,1,2]),rng.choice([0,1,2]))
        W=worlds_files(led,K,Aa)
        cands=set(rng.sample(sorted(W),min(len(W),15))) if W else set()
        for _ in range(25):
            rs=[(10,i,led[i]['amt']) for i in led if rng.random()<.4]+[(20,rng.randint(1,nm),rng.randint(1,4)) for _ in range(rng.randint(0,3))]
            cands.add(tuple(sorted(rs)))
        for G in cands:
            ra=ref_accept((0,list(G)),led,K,Aa); br=G in W; n+=1
            if ra!=br:
                bad+=1
                if bad<=3: print('MISMATCH',sorted(K),Aa,G,led,'ref',ra,'brute',br)
print('독립 열거 대조(관측 K에 취소 목록 포함 조합 포함):',n,'건, 불일치',bad)
