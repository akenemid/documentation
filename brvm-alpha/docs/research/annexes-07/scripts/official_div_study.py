# Étude (annexe 07) : ETUDE_DOSSIER désigne le dossier de travail de l'étude (pages/ et fichiers lus) ;
# les modules voisins (parse_views, names, evlib) sont lus dans le dossier de ce script.
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, evlib
S=os.path.join(os.environ.get('ETUDE_DOSSIER', '.'), '')
a=evlib.load()
bd=pd.read_csv(S+'brvm_dividends.csv',parse_dates=['pay','ex','avis_date'])
bd=bd[bd.symbol.notna()&bd.ex.notna()&bd.amount.notna()].drop_duplicates(['symbol','ex'])
bd=bd[bd.ex>='2017-02-01']
print('official events',len(bd), bd.ex.min().date(), bd.ex.max().date())
lag=(bd.ex-bd.avis_date).dt.days
print('avis->ex calendar days: n=%d mean %.1f med %.0f p10 %.0f p25 %.0f p75 %.0f p90 %.0f'%(lag.notna().sum(),lag.mean(),lag.median(),lag.quantile(.1),lag.quantile(.25),lag.quantile(.75),lag.quantile(.9)))
pl=(bd.pay-bd.ex).dt.days; print('ex->pay: med %.0f mean %.1f'%(pl.median(),pl.mean()), pl.value_counts().head(5).to_dict())
print('ex month distribution:', bd.ex.dt.month.value_counts().sort_index().to_dict())
print('ex weekday:', bd.ex.dt.dayofweek.value_counts().sort_index().to_dict())
# yield from close before ex (panel close)
cl=a.set_index(['symbol','date'])['close']
g={s:d for s,d in a.groupby('symbol')}
ys=[]; nsess=[]
for _,r in bd.iterrows():
    d=g.get(r.symbol)
    if d is None: ys.append(np.nan); nsess.append(np.nan); continue
    dates=d.date.values; k=np.searchsorted(dates,np.datetime64(r.ex),side='left')
    if k<1 or k>=len(d): ys.append(np.nan); nsess.append(np.nan); continue
    ys.append(r.amount/d.close.values[k-1])
    if pd.notna(r.avis_date):
        k0=np.searchsorted(dates,np.datetime64(r.avis_date),side='right')  # première séance APRÈS le jour de l'avis
        nsess.append(k-k0)
    else: nsess.append(np.nan)
bd['yield']=ys; bd['sess_avis_to_ex']=nsess
print('sessions from first session after avis to ex-day: med %.0f p10 %.0f p90 %.0f'%(bd.sess_avis_to_ex.median(),bd.sess_avis_to_ex.quantile(.1),bd.sess_avis_to_ex.quantile(.9)))
bd['event_date']=bd['ex']
w={'pre20':(-20,-1),'pre5':(-5,-1),'d0':(0,0),'d1':(1,1),'post5':(1,5),'post20':(1,20),'post60':(1,60)}
r=evlib.event_windows(a,bd,windows=w)
print(evlib.summarize(r,list(w)).round(3).to_string())
r['ym']=pd.to_datetime(r['ex']).dt.to_period('M')
rows=[]
for c in w:
    m=r.groupby('ym')[c].mean().dropna(); rows.append((c,len(m),100*m.mean(),m.mean()/(m.std(ddof=1)/np.sqrt(len(m)))))
print(pd.DataFrame(rows,columns=['w','n_clusters','mean_%','t_cluster']).round(2).to_string())
r['per']=np.where(pd.to_datetime(r['ex']).dt.year<=2021,'2017-2021','2022-2026')
for p,sub in r.groupby('per'): print('---',p); print(evlib.summarize(sub,list(w)).round(3).to_string())
# window from session after avis to ex-day close (tradable): sum AR over [k0, k]
res=[]
for _,ev in bd.iterrows():
    d=g.get(ev.symbol)
    if d is None or pd.isna(ev.avis_date): continue
    dates=d.date.values; k=np.searchsorted(dates,np.datetime64(ev.ex),side='left'); k0=np.searchsorted(dates,np.datetime64(ev.avis_date),side='right')
    if k>=len(d) or k0>k or k0<1: continue
    seg=d.ar.values[k0:k+1]; seg_pre=d.ar.values[k0:k]
    # announcement reaction: AR on first session after avis (k0) and [k0,k0+1]
    res.append(dict(symbol=ev.symbol,ex=ev.ex,n=k-k0+1,car_avis_to_ex=seg.sum() if np.isfinite(seg).all() else np.nan,
                    car_avis_to_preex=seg_pre.sum() if len(seg_pre) and np.isfinite(seg_pre).all() else np.nan,
                    ar_avis1=d.ar.values[k0] if k0<len(d) else np.nan, yld=ev['yield'],
                    raw_avis_to_ex=np.prod(1+d.tr_ret.values[k0:k+1])-1 if np.isfinite(d.tr_ret.values[k0:k+1]).all() else np.nan))
res=pd.DataFrame(res)
print('tradable: buy close of avis day, sell close ex-day')
print(evlib.summarize(res,['ar_avis1','car_avis_to_preex','car_avis_to_ex','raw_avis_to_ex']).round(3).to_string())
res['ybk']=pd.cut(res.yld,[0,.04,.07,1],labels=['<4%','4-7%','>7%'])
print(res.groupby('ybk',observed=True)['car_avis_to_ex'].agg(['count','mean','median']).round(4).to_string())
r.to_csv(S+'official_ex_events.csv',index=False); res.to_csv(S+'avis_to_ex.csv',index=False)
# PDR
pdr=[]
for _,ev in bd.iterrows():
    d=g.get(ev.symbol)
    if d is None: continue
    dates=d.date.values; k=np.searchsorted(dates,np.datetime64(ev.ex),side='left')
    if k<1 or k>=len(d) or not d.traded.values[k]: continue
    if (pd.Timestamp(dates[k])-ev.ex).days>3: continue
    pdr.append(((d.close.values[k-1]-d.close.values[k])/ev.amount,(d.close.values[k-1]-d.open.values[k])/ev.amount if d.open.values[k]>0 else np.nan, ev['yield']))
pdr=pd.DataFrame(pdr,columns=['pdr_close','pdr_open','y'])
print('PDR close n=%d mean %.2f med %.2f | open med %.2f'%(len(pdr),pdr.pdr_close.mean(),pdr.pdr_close.median(),pdr.pdr_open.median()))
print(pdr.groupby(pd.cut(pdr.y,[0,.04,.07,.075,1]),observed=True).pdr_close.agg(['count','median']).round(2).to_string())
