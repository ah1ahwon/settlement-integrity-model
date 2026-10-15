"""[ref2] ref.py에 업무 제약 하나를 추가한 판(원본 ref.py는 보존): 반영된 취소는 청구완료(C) 거래에만 존재한다.
따라서 숨은 상태 s가 U 또는 R이면 반영 집합은 공집합이어야 한다(Z>0 또는 Y의 반영 표시가 있으면 그 상태는 불가능,
X만 있으면 승인 취소 전부가 미반영). 독립 열거기(tests/indep_world.py) 대조에서 발견(2026-10-14).
통일 기준 판정: 하나의 업무 가정 A=(CR,cs,cc)에서 모든 K가 같은 정당 세계 정의를 공유하고, 관측만 달라진다.
숨은 변수: 거래별 실제 상태 s in {U,C,R}, 취소 이벤트의 반영 여부. 판정 = 관측과 일치하는 정당 세계 존재 여부."""
import itertools
from collections import Counter
from m2 import atoms
REC=['원장:승인번호존재','원장:가맹점일치','원장:10금액=승인금액','원장:20누적≤한도']
INT=['내부:10승인번호중복없음','내부:20합≤같은파일10']
def view_set(K,st):
    if 'D' not in K: return ['U','C','R']
    if st=='U': return ['U']
    if 'B' not in K: return ['C','R']
    return [st]
def cancel_mc(Fi,ev,cum,K,s="C"):
    """취소 규칙. 반환: 최소 이월 취소 건수 또는 None(불가)."""
    Fc=Counter(Fi)
    if 'Y' in K:
        U=Counter(a for a,cl in ev if not cl)
        if Fc-U: return None
        return sum((U-Fc).values())
    if 'X' in K:
        A=Counter(a for a,cl in ev)
        if Fc-A: return None
        if 'Z' not in K: return 0 if s=='C' else sum((A-Fc).values())
        evl=[a for a,cl in ev]; best=None
        for r in range(len(evl)+1):
            for P in itertools.combinations(range(len(evl)),r):
                if sum(evl[j] for j in P)!=cum: continue
                rest=Counter(evl[j] for j in range(len(evl)) if j not in P)
                if Fc-rest: continue
                m=sum((rest-Fc).values()); best=m if best is None else min(best,m)
        return best
    return 0
def ref_accept(F,led,K,Aa):
    CR,cs,cc=Aa; hm,rs=F
    a=atoms(F,led,{'L'}|({'Z'} if 'Z' in K else set()) if 'L' in K else set(),0)
    if not all(a[k] for k in INT): return False
    if 'L' not in K: return True
    if not all(a[k] for k in REC): return False
    sent={i for t,i,x in rs if t==10}; f20={}
    for t,i,x in rs:
        if t==20: f20.setdefault(i,[]).append(x)
    mine=[i for i in led if led[i]['m']==hm]
    reach={(0,0,0)}
    for i in mine:
        opts=set()
        for s in view_set(K,led[i]['st']):
            if s!='C' and (('Z' in K and led[i]['cum']>0) or ('Y' in K and any(cl for _,cl in led[i]['ev']))): continue
            if i in sent:
                if s=='C': continue
                r,ms,el=(1 if s=='R' else 0),0,True
            elif s=='C': r,ms,el=0,0,True
            else: r,ms,el=(1 if s=='R' else 0),1,False
            Fi=f20.get(i,[])
            if not el:
                if Fi: continue
                mc=0
            else:
                mc=cancel_mc(Fi,led[i]['ev'],led[i]['cum'],K,s)
                if mc is None: continue
            opts.add((r,ms,mc))
        new=set()
        for (r0,m0,c0) in reach:
            for (r,ms,mc) in opts:
                t=(r0+r,m0+ms,c0+mc)
                if t[0]<=CR and t[1]<=cs and t[2]<=cc: new.add(t)
        reach=new
        if not reach: return False
    return True
