"""Petite bibliothèque d'étude d'événements sur le panel BOC (market-adjusted)."""
import numpy as np, pandas as pd
P='/home/user/documentation/brvm-alpha/data/panel/'
def load():
    a=pd.read_parquet(P+'adjusted_prices.parquet')
    e=pd.read_parquet(P+'equities.parquet',columns=['date','symbol','volume','value','open','close','prev_close','status'])
    a=a.merge(e,on=['date','symbol'],how='left',suffixes=('','_e'))
    ix=pd.read_parquet(P+'indices.parquet')
    m=ix[ix['index']=='BRVM COMPOSITE'].set_index('date')['level'].sort_index()
    rm=m.pct_change().rename('rm')
    a=a.merge(rm,left_on='date',right_index=True,how='left')
    a=a.sort_values(['symbol','date']).reset_index(drop=True)
    a['ar']=a['tr_ret']-a['rm']
    a['ar_px']=a['ret']-a['rm']
    a['traded']=(a['volume'].fillna(0)>0)
    gap=a.groupby('symbol')['date'].diff().dt.days
    bad=(gap>7)|a['ar'].isna()|(a['ar'].abs()>0.5)
    a.loc[bad,['ar','ar_px']]=np.nan
    return a
def event_windows(a, events, date_col='event_date', windows=None, ar_col='ar', align='on_or_after'):
    """events: DataFrame avec symbol + date_col. Renvoie une ligne par événement avec les CAR."""
    windows=windows or {'pre20':(-20,-1),'pre5':(-5,-1),'d0':(0,0),'d01':(0,1),'post5':(1,5),'post20':(1,20),'post60':(1,60)}
    g={s:d for s,d in a.groupby('symbol')}
    out=[]
    for _,ev in events.iterrows():
        d=g.get(ev['symbol'])
        if d is None: continue
        dates=d['date'].values
        t=np.datetime64(pd.Timestamp(ev[date_col]))
        k=np.searchsorted(dates,t,side='left')  # première séance >= date
        if align=='before' : k=np.searchsorted(dates,t,side='right')-1
        if k<0 or k>=len(d): continue
        row=dict(ev); row['k_date']=pd.Timestamp(dates[k]); row['gap_days']=(pd.Timestamp(dates[k])-pd.Timestamp(ev[date_col])).days
        arr=d[ar_col].values; vol=d['value'].fillna(0).values; trd=d['traded'].values
        ok=True
        for name,(lo,hi) in windows.items():
            i0,i1=k+lo,k+hi
            if i0<1 or i1>=len(d): row[name]=np.nan; continue
            seg=arr[i0:i1+1]
            row[name]=seg.sum() if np.isfinite(seg).all() else np.nan
        # volume anormal : valeur moyenne [0,+1] / médiane [-60,-11]
        if k-60>=0 and k+1<len(d):
            base=np.median(vol[k-60:k-10]); row['abn_value']=(vol[k:k+2].mean()/base) if base>0 else np.nan
            row['traded_share_base']=trd[k-60:k-10].mean()
        out.append(row)
    return pd.DataFrame(out)
def summarize(df, cols):
    rows=[]
    for c in cols:
        x=df[c].dropna()
        if len(x)<3: rows.append((c,len(x),np.nan,np.nan,np.nan,np.nan)); continue
        t=x.mean()/(x.std(ddof=1)/np.sqrt(len(x)))
        rows.append((c,len(x),100*x.mean(),100*x.median(),t,100*(x>0).mean()))
    return pd.DataFrame(rows,columns=['fenetre','n','moy_%','med_%','t','pct_pos'])
