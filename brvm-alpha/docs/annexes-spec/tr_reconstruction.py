# Reconstruction du nombre de titres et du BRVM Composite Total Return (spec BRVM Alpha, 22/11/2026).
# Usage : python3 -I tr_reconstruction.py /home/user/documentation/brvm-alpha
import pandas as pd, numpy as np, re, sys
root = sys.argv[1]
md = open(root + '/docs/research/01-structure-marche.md', encoding='utf-8').read().splitlines()
sh = {}
for l in md:
    if l.startswith('| ') and l.count('|') >= 12:
        c = [x.strip() for x in l.strip('|').split('|')]
        if re.fullmatch(r'[A-Z]{3,6}', c[0]) and re.fullmatch(r'[\d ]+', c[7].replace(' ',' ')):
            sh[c[0]] = int(c[7].replace(' ', '').replace(' ',''))
print(len(sh))
e = pd.read_parquet(root + '/data/panel/equities.parquet')
m = pd.read_parquet(root + '/data/panel/market.parquet').set_index('date')
ca = pd.read_parquet(root + '/data/panel/corporate_actions.parquet')
ca = ca[(ca.kind.isin(['split','capital_adjustment'])) & (ca.confidence != 'low')]
px = e.pivot_table(index='date', columns='symbol', values='close', aggfunc='last')
N = pd.DataFrame(index=px.index, columns=sorted(sh), dtype=float)
for s, n in sh.items():
    f = pd.Series(1.0, index=px.index)
    for _, r in ca[ca.symbol == s].iterrows():
        if s == 'SAFC' and r.kind == 'capital_adjustment':
            continue
        f[f.index < r.date] /= r.ratio
    N[s] = n * f
# SAFC : 8 119 750 titres avant le 11/08/2026
N.loc[N.index < '2026-08-11', 'SAFC'] = 8_119_750 * (N.loc[N.index < '2026-08-11', 'SAFC'] / 11_869_750)
cap = (N * px[N.columns]).sum(axis=1, min_count=1)
r = (cap / m['market_cap']).dropna()
for d in ['2017-03-01','2017-12-29','2018-12-31','2019-12-31','2020-12-31','2021-12-31','2022-06-30','2022-12-30','2023-12-29','2024-12-31','2025-12-31','2026-11-20']:
    x = r[r.index <= d]
    print(d, round(x.iloc[-1], 4) if len(x) else None)
# --- reconstruction du Composite TR ---
i = pd.read_parquet(root + '/data/panel/indices.parquet')
comp = i[i['index'] == 'BRVM COMPOSITE'].set_index('date')['level'].sort_index()
tr_off = i[i['index'] == 'BRVM COMPOSITE TOTAL RETURN'].set_index('date')['level'].sort_index()
dv = pd.read_parquet(root + '/data/panel/dividends.parquet')
dates = comp.index
mc = m['market_cap'].reindex(dates)
divcash = pd.Series(0.0, index=dates)
for _, r in dv.iterrows():
    if r.symbol in N.columns and r.ex_date in dates:
        n = N.loc[r.ex_date, r.symbol] if r.ex_date in N.index else np.nan
        if np.isfinite(n):
            divcash[r.ex_date] += n * r.amount
rc = comp.pct_change()
add = divcash / mc.shift(1)
trr = (rc + add.fillna(0)).loc['2025-01-03':]
tr = 100 * (1 + trr).cumprod()
cmp_ = pd.concat([tr.rename('rec'), tr_off.rename('off')], axis=1).dropna()
d = (cmp_['rec'].pct_change() - cmp_['off'].pct_change()).dropna() * 1e4
print('jours compares', len(d), 'ecart quotidien median |pb|', round(d.abs().median(), 2), 'moyenne |pb|', round(d.abs().mean(), 2), 'max', round(d.abs().max(), 1))
print('niveau rec 2025-12-31', round(tr.loc[:'2025-12-31'].iloc[-1], 2), 'rec 2026-11-20', round(tr.iloc[-1], 2), 'off', tr_off.iloc[-1])
print('ratio fin/fin', round(cmp_['rec'].iloc[-1] / cmp_['rec'].iloc[0] / (cmp_['off'].iloc[-1] / cmp_['off'].iloc[0]), 4))
# annual TR rec back to 2017
trr_all = (rc + add.fillna(0)).dropna()
yr = (1 + trr_all).groupby(trr_all.index.year).prod() - 1
pr = (1 + rc.dropna()).groupby(rc.dropna().index.year).prod() - 1
print(pd.DataFrame({'prix': pr.round(4), 'TR_rec': yr.round(4)}).to_string())
lvl = (1 + trr_all).cumprod()
yrs = (lvl.index[-1] - lvl.index[0]).days / 365.25
print('TR cumul', round(lvl.iloc[-1] - 1, 4), 'TCAC', round(lvl.iloc[-1] ** (1 / yrs) - 1, 4), 'annees', round(yrs, 2))
dd = lvl / lvl.cummax() - 1
print('maxDD TR', round(dd.min(), 4), dd.idxmin().date(), 'pic', lvl.loc[:dd.idxmin()].idxmax().date())
rec = lvl.loc[dd.idxmin():]; peak = lvl.loc[:dd.idxmin()].max()
print('retour au pic TR', rec[rec >= peak].index[0].date() if (rec >= peak).any() else None)
pl = (1 + rc.dropna()).cumprod(); print('prix cumul', round(pl.iloc[-1] - 1, 4), 'TCAC', round(pl.iloc[-1] ** (1 / yrs) - 1, 4))
w = (1 + trr_all).resample('W-FRI').prod() - 1
print('vol hebdo ann TR', round(w.std() * 52 ** .5, 4), 'mens', round(((1 + trr_all).resample('ME').prod() - 1).std() * 12 ** .5, 4))
