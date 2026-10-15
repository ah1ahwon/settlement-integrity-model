import itertools, random, collections
from collections import Counter
from m4 import *
def world(amt, ev):  # ev: list of (amt, claimed)
    cum=sum(a for a,c in ev if c)
    return {1:dict(m=0,amt=amt,st='C',cum=cum,ev=list(ev))}
def files_from(ev):  # 모든 20-레코드 부분집합(중복 허용 아님) + 정당 외 재전송은 청구된 것 포함됨
    n=len(ev); out=set()
    for r in range(n+1):
        for S in itertools.combinations(range(n),r):
            out.add(tuple(sorted(ev[j][0] for j in S)))
    return out
print('[1] 전수: 승인 목록 A(최대 4건, 금액 1..V), 반영 상태 모든 조합')
for V,AMT in ((4,12),(6,20),(10,40)):
  for c in (0,2):
    worlds=0; amb_keys=set(); key2states=collections.defaultdict(set)
    dis=Counter(); fn=Counter(); tot_files=0; legit_rej=0; viol=0
    for n in range(1,5):
        for A in itertools.combinations_with_replacement(range(1,V+1),n):
            if sum(A)>AMT: continue
            for cl in itertools.product([0,1],repeat=n):
                ev=[(a,bool(x)) for a,x in zip(A,cl)]
                w=world(AMT,ev); worlds+=1
                key=(A,w[1]['cum']); key2states[key].add(tuple(sorted(a for a,x in ev if x)))
    ambK={k for k,v in key2states.items() if len(v)>1}
    # 판정 비교
    for n in range(1,5):
        for A in itertools.combinations_with_replacement(range(1,V+1),n):
            if sum(A)>AMT: continue
            for cl in itertools.product([0,1],repeat=n):
                ev=[(a,bool(x)) for a,x in zip(A,cl)]
                led=world(AMT,ev); amb=((A,led[1]['cum']) in ambK)
                for Fi in files_from(ev):
                    F=(0,[(20,1,a) for a in Fi]); tot_files+=1
                    y=explainable4(F,led,set('LDY'),c); xz=explainable4(F,led,set('LDZX'),c)
                    if y and not xz: viol+=1      # X2가 허용하는데 Z+X1이 거절: 건전성 위반
                    if xz and not y: dis['Z+X1만 허용(X2는 거절)']+=1; dis['  그중 모호 세계']+=amb
    amb_worlds=sum(1 for k,v in key2states.items() if len(v)>1)
    print(f' V={V} c={c}: (A,Z) 키 {len(key2states)}개 중 반영상태 복수 가능 {amb_worlds}개({100*amb_worlds/len(key2states):.1f}%) | 파일 {tot_files} 중 Z+X1이 X2보다 더 허용 {dis["Z+X1만 허용(X2는 거절)"]}건({100*dis["Z+X1만 허용(X2는 거절)"]/tot_files:.2f}%), 모호세계 아닌 경우 {dis["Z+X1만 허용(X2는 거절)"]-dis["  그중 모호 세계"]}건 | 건전성 위반 {viol}')
# 구체 반례 출력
print('\n[1b] 구체 반례 (c=0)')
shown=0
for A in itertools.combinations_with_replacement(range(1,7),3):
    if sum(A)>12: continue
    for cl in itertools.product([0,1],repeat=3):
        ev=[(a,bool(x)) for a,x in zip(A,cl)]; led=world(12,ev)
        for Fi in files_from(ev):
            F=(0,[(20,1,a) for a in Fi])
            if explainable4(F,led,set('LDZX'),0) and not explainable4(F,led,set('LDY'),0) and shown<3:
                print(f'  승인 취소 {list(A)}, 누계 Z={led[1]["cum"]}, 실제 반영된 건 {[a for a,c in ev if c]}, 파일 20레코드 {list(Fi)} → X2 거절(이미 반영된 건 재전송), Z+X1 허용(반영된 건이 {[a for a in A if a not in [a2 for a2,c2 in ev if c2]]} 쪽이었을 수도 있음)'); shown+=1
# ---- 2. 생성기 분포에서 모호성 비율 (금액 범위 의존)
print('\n[2] 금액 범위별: 한 거래의 (승인목록, 누계)에서 반영 상태 복수 가능 비율 (무작위 원장 20000건, 승인 3~4건)')
rng=random.Random(5)
for V in (5,10,50,200,1000):
    amb=0; tot=0
    for _ in range(20000):
        n=rng.choice([3,4]); A=[rng.randint(1,V) for _ in range(n)]; cl=[rng.random()<.5 for _ in range(n)]
        cum=sum(a for a,x in zip(A,cl) if x); st_=set()
        for m in itertools.product([0,1],repeat=n):
            if sum(a for a,x in zip(A,m) if x)==cum: st_.add(tuple(sorted(a for a,x in zip(A,m) if x)))
        tot+=1; amb+= len(st_)>1
    print(f'  금액 1..{V:<5d}: {100*amb/tot:5.1f}%')
# ---- 3. 본 실험 생성기에서 Z+X1 vs X2 판정 불일치
print('\n[3] 본 실험(m4.make_case4) 공격 전체에서 LDBZX vs LDBZY 판정 불일치')
rng=random.Random(41); dis=0; n=0; ev_amb=0; ev_tot=0
for _ in range(2000):
    led,F=make_case4(rng,2)
    for i,v in led.items():
        if len(v['ev'])>=2:
            ev_tot+=1
            A=[a for a,c in v['ev']]; cum=v['cum']; sts=set()
            for m in itertools.product([0,1],repeat=len(A)):
                if sum(a for a,x in zip(A,m) if x)==cum: sts.add(tuple(sorted(a for a,x in zip(A,m) if x)))
            ev_amb+= len(sts)>1
    for kd,G in attacks4(F,led,rng):
        n+=1; dis+= explainable4(G,led,set('LDBZX'),2)!=explainable4(G,led,set('LDBZY'),2)
print(f'  공격 {n}건 중 불일치 {dis}건 | 승인 취소 2건 이상인 거래 {ev_tot}개 중 상태 모호 {ev_amb}개')
