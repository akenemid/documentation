# Largeur de l univers eligible par annee (spec BRVM Alpha, 22/11/2026).
# Usage : python3 -I univ_breadth.py data/panel/equities.parquet 0,250000,500000,1000000,2000000
import pandas as pd, numpy as np, sys
e = pd.read_parquet(sys.argv[1])
e = e.sort_values(['date','symbol'])
val = e.pivot_table(index='date', columns='symbol', values='value', aggfunc='last')
st = e.pivot_table(index='date', columns='symbol', values='status', aggfunc='last')
vol = e.pivot_table(index='date', columns='symbol', values='volume', aggfunc='last')
listed = st.notna()
traded = (vol.fillna(0) > 0) & listed
susp = st.eq('suspended')
v = val.where(listed)
med63 = v.where(traded, 0.0).where(listed).rolling(63, min_periods=40).median()
frac120 = traded.astype(float).where(listed).rolling(120, min_periods=60).mean()
me = e.date.drop_duplicates().groupby(e.date.dt.to_period('M')).max().values
rows=[]
for thr in [float(x) for x in sys.argv[2].split(",")]:
    elig = (med63 >= thr) & (frac120 >= 0.5) & ~susp
    n = elig.loc[elig.index.isin(me)].sum(axis=1)
    rows.append(n.groupby(n.index.year).median().rename(f'{thr/1e6:g}M'))
print(pd.concat(rows, axis=1).to_string())
n_listed = listed.loc[listed.index.isin(me)].sum(axis=1)
print(n_listed.groupby(n_listed.index.year).median().to_string())
