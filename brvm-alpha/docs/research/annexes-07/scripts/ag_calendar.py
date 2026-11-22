import gzip, re, sys, pandas as pd
from pathlib import Path
BOC=Path('/home/user/documentation/brvm-alpha/data/boc_text')
files={2017:'boc_20171229',2018:'boc_20181231',2019:'boc_20191231',2020:'boc_20201231',2021:'boc_20211231',
       2022:'boc_20221230',2023:'boc_20231229',2024:'boc_20241231',2025:'boc_20251231',2026:'boc_20261120'}
pat=re.compile(r"^\s*(?P<name>\S.*?)\s{2,}(?P<nature>Ordinaire|Extraordinaire|Mixte|Spéciale|Speciale|Constitutive)\s+(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<heure>\d{1,2}[:h]\d{2}(?::\d{2})?)?\s*(?P<lieu>.*)$")
rows=[]
for y,f in files.items():
    txt=gzip.open(BOC/f'{f}.txt.gz','rt',encoding='utf-8',errors='replace').read().splitlines()
    for ln in txt:
        m=pat.match(ln)
        if m:
            d=m.groupdict(); d['year_file']=y; d['annule']=bool(re.search(r'annul',ln,re.I)); d['report']=bool(re.search(r'report',ln,re.I))
            rows.append(d)
df=pd.DataFrame(rows); df['date']=pd.to_datetime(df['date'],format='%d/%m/%Y',errors='coerce')
df.to_csv(sys.argv[1],index=False)
print(len(df)); print(df.groupby('year_file').size()); print(df['name'].value_counts().head(80).to_string())
