"""Projection only: schedule_model.py generalised from the benchmark's 5 bodies to N bodies.

Same per-pair op graph, unit latencies and greedy in-order issue as docs/schedule_model.py (which
the RTL matches: model 123, RTL 124 cycles/step at N = 5). The RTL itself is fixed at N = 5 /
10 pairs with body state in flops, so nothing here is an RTL or timing result: it answers "how
would this datapath scale" and is quoted as a model projection in report_nbody section 5.

    python3 hw/grape_pipeline/docs/schedule_model_n.py
"""
import sys
ADD_L, MUL_L, SQRT_L, SQRT_II, RCP_L, RCP_II, COMMIT, FSM = 3,3,30,2,22,2,2,4
def build(N):
    ops=[]; 
    def op(u,d,c=None): ops.append((u,list(d),c)); return len(ops)-1
    vch={}
    for bi in range(N-1):
        for bj in range(bi+1,N):
            sub=[op("ADD",[]) for _ in range(3)]; sq=[op("MUL",[sub[c]]) for c in range(3)]
            a1=op("ADD",[sq[0],sq[1]]); dsq=op("ADD",[a1,sq[2]]); s=op("SQRT",[dsq]); d3=op("MUL",[dsq,s])
            r=op("RCP",[d3]); mag=op("MUL",[r]); b1=op("MUL",[mag]); b2=op("MUL",[mag])
            fi=[op("MUL",[sub[c],b2]) for c in range(3)]; fj=[op("MUL",[sub[c],b1]) for c in range(3)]
            for b,f in ((bi,fi),(bj,fj)):
                for c in range(3):
                    p=vch.get((b,c)); vch[(b,c)]=op("ADD",[f[c]]+([p] if p is not None else []),(b,c))
    for b in range(N):
        for c in range(3):
            m=op("MUL",[vch[(b,c)]]); op("ADD",[m])
    return ops
def schedule(N,n_add,n_mul,n_sqrt=1,n_rcp=1,sq_ii=SQRT_II,rc_ii=RCP_II,WIN=4096):
    ops=build(N); lat={"ADD":ADD_L,"MUL":MUL_L,"SQRT":SQRT_L,"RCP":RCP_L}
    cap={"ADD":n_add,"MUL":n_mul,"SQRT":n_sqrt,"RCP":n_rcp}
    q={u:[i for i,o in enumerate(ops) if o[0]==u] for u in cap}
    done=[None]*len(ops); t=0; left=len(ops)
    nextfree={"SQRT":[0]*n_sqrt,"RCP":[0]*n_rcp}
    # chain order is implied by deps (each chain op depends on the previous one)
    while left:
        for u in cap:
            used=0; lst=q[u]; k=0; scanned=0
            while k<len(lst) and used<cap[u] and scanned<WIN:
                i=lst[k]; scanned+=1
                if all(done[d] is not None and done[d]<=t for d in ops[i][1]):
                    if u in nextfree:
                        slot=min(range(len(nextfree[u])),key=lambda s:nextfree[u][s])
                        if nextfree[u][slot]>t: break
                        nextfree[u][slot]=t+(sq_ii if u=="SQRT" else rc_ii)
                    done[i]=t+lat[u]; used+=1; lst.pop(k); left-=1
                else: k+=1
        t+=1
    return max(done)+COMMIT+FSM, len(ops)
if __name__=="__main__":
    F=19.46e6
    print("check N=5 (3 add,3 mul):",schedule(5,3,3))
    print(f"{'N':>5} {'pairs':>7} {'ops':>8} {'cyc/step':>9} {'cyc/pair':>8} {'us/pair@19.46':>13} {'vs Rust 0.045us':>15}")
    for N in (5,10,20,50,100):
        c,n=schedule(N,3,3); P=N*(N-1)//2
        print(f"{N:>5} {P:>7} {n:>8} {c:>9} {c/P:>8.2f} {c/P/F*1e6:>13.3f} {c/P/F*1e6/0.045:>14.1f}x")
    print("wider inventories at N=100 (add,mul,sqrt,rcp, II=1 for sqrt/rcp):")
    for a,m,s,r in ((6,6,1,1),(12,12,1,1),(12,12,2,2),(24,24,2,2)):
        c,n=schedule(100,a,m,s,r,1,1); P=4950
        print(f"   {a:>2} add {m:>2} mul {s} sqrt {r} rcp: {c:>7} cyc/step  {c/P:5.2f} cyc/pair  {c/P/F*1e6:6.3f} us/pair @19.46  {c/P/50e6*1e6:6.3f} @50")
