# Étude (annexe 07) : ETUDE_DOSSIER désigne le dossier de travail de l'étude (pages/ et fichiers lus) ;
# les modules voisins (parse_views, names, evlib) sont lus dans le dossier de ce script.
import os, sys, glob, re, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_views, names
B=os.path.join(os.environ.get('ETUDE_DOSSIER', '.'), 'pages', '')
def load(kind):
    files=[B+f'{kind}.html']+sorted(glob.glob(B+f'p/{kind}_*.html'),key=lambda f:int(re.search(r'_(\d+)\.html',f).group(1)))
    rows=[]
    for f in files:
        m,rs=parse_views.parse(f)
        for r in rs:
            c={x['cls']:x for x in r}
            dcell=c.get('views-field-field-date-annonce') or c.get('views-field-field-date-avis')
            link=None
            for x in r:
                if x['links']: link=x['links'][0]
            fd=None
            if link:
                mm=re.search(r'/files/(\d{8})',link)
                if mm:
                    try: fd=pd.Timestamp(mm.group(1))
                    except Exception: fd=None
            rows.append(dict(date_iso=dcell['iso'] if dcell else None, societe=(c.get('views-field-og-group-ref') or {}).get('text'),
                             titre=(c.get('views-field-title') or {}).get('text'), file=link, file_date=fd))
    df=pd.DataFrame(rows)
    df['ts']=pd.to_datetime(df['date_iso'].str[:19],errors='coerce')
    df['date']=df['ts'].dt.normalize()
    df['symbol']=df['societe'].map(names.to_symbol)
    df['lag_file_to_post']=(df['date']-df['file_date']).dt.days
    return df
if __name__=='__main__':
    for k in sys.argv[1:]:
        d=load(k); d.to_csv(B+f'../list_{k}.csv',index=False)
        x=d['lag_file_to_post'].dropna(); x=x[(x>=-5)&(x<=60)]
        print(k,len(d),d.date.min(),d.date.max(),'unmapped',d[d.symbol.isna()].societe.dropna().unique()[:10])
        print('   lag file->post: n=%d mean %.2f med %.1f p75 %.1f p90 %.1f share<=1d %.2f'%(len(x),x.mean(),x.median(),x.quantile(.75),x.quantile(.9),(x<=1).mean()))
