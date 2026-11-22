import sys; sys.path.insert(0,'/tmp/claude-0/-home-user-documentation/b095b722-74b3-5e89-8589-8e6133bd6c39/scratchpad/scripts')
import numpy as np, pandas as pd, evlib
a=evlib.load()
dv=pd.read_parquet(evlib.P+'dividends.parquet')
print(dv['evidence'].value_counts())
dv=dv[dv['evidence']!='first_seen'].copy()
dv['event_date']=dv['ex_date']
r=evlib.event_windows(a,dv)
# ex-day price drop ratio using close (and open)
g={s:d.set_index('date') for s,d in a.groupby('symbol')}
pdr=[];
for i,ev in r.iterrows():
    d=g[ev['symbol']]; t=ev['k_date']
    if t not in d.index: pdr.append((np.nan,np.nan,np.nan)); continue
    row=d.loc[t]; pc=ev['close_before']; D=ev['amount']
    trd=row['traded']
    pdr.append(((pc-row['close'])/D if trd else np.nan, (pc-row['open'])/D if (trd and row['open']>0) else np.nan, trd))
r[['pdr_close','pdr_open','traded_ex']]=pd.DataFrame(pdr,index=r.index)
r['ret_px_d0']=np.nan
r.to_csv('div_ex_events.csv',index=False)
print('N events',len(r), 'gap!=0:',(r['gap_days']!=0).sum())
cols=['pre20','pre5','d0','post5','post20','post60']
print(evlib.summarize(r,cols).round(3).to_string())
r['ybk']=pd.cut(r['yield_pct'],[0,4,7,100],labels=['<4%','4-7%','>7%'])
for b,sub in r.groupby('ybk',observed=True):
    print('--- yield',b,len(sub)); print(evlib.summarize(sub,cols).round(3).to_string())
r['liq']=np.where(r['traded_share_base']>=0.8,'liquide','peu liquide')
for b,sub in r.groupby('liq'):
    print('--- ',b,len(sub)); print(evlib.summarize(sub,cols).round(3).to_string())
x=r['pdr_close'].dropna(); xo=r['pdr_open'].dropna()
print('PDR close n=%d mean=%.3f median=%.3f p25=%.3f p75=%.3f'%(len(x),x.mean(),x.median(),x.quantile(.25),x.quantile(.75)))
print('PDR open n=%d mean=%.3f median=%.3f p25=%.3f p75=%.3f'%(len(xo),xo.mean(),xo.median(),xo.quantile(.25),xo.quantile(.75)))
r['year']=r['ex_date'].dt.year; r['month']=r['ex_date'].dt.month
print(r.groupby('month').size().to_string())
print(r.groupby('year').agg(n=('symbol','size'),pre20=('pre20','mean'),post20=('post20','mean')).round(4).to_string())
# Pre-ex run-up by year
