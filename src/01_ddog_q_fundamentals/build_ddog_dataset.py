import pandas as pd, numpy as np

# ---------- RAW DATA (revenue in USD thousands, as reported) ----------
rev_k = {
 '2021Q1':198549,'2021Q2':233549,'2021Q3':270488,'2021Q4':326198,
 '2022Q1':363030,'2022Q2':406138,'2022Q3':436533,'2022Q4':469399,
 '2023Q1':481714,'2023Q2':509460,'2023Q3':547536,'2023Q4':589649,
 '2024Q1':611253,'2024Q2':645279,'2024Q3':690016,'2024Q4':737727,
 '2025Q1':761553,'2025Q2':826760,'2025Q3':885651,'2025Q4':953194,
 '2026Q1':1006426,'2026Q2':1121454}
c100 = {
 '2021Q1':1406,'2021Q2':1570,'2021Q3':1800,'2021Q4':2010,
 '2022Q1':2250,'2022Q2':2420,'2022Q3':2600,'2022Q4':2780,
 '2023Q1':2910,'2023Q2':2990,'2023Q3':3130,'2023Q4':3190,
 '2024Q1':3340,'2024Q2':3390,'2024Q3':3490,'2024Q4':3610,
 '2025Q1':3770,'2025Q2':3850,'2025Q3':4060,'2025Q4':4310,
 '2026Q1':4550,'2026Q2':4720}
tot = {
 '2022Q1':19800,'2022Q2':21200,'2022Q3':22200,'2022Q4':23200,
 '2023Q1':25500,'2023Q2':26100,'2023Q3':26800,'2023Q4':27300,
 '2024Q1':28000,'2024Q2':28700,'2024Q3':29200,'2024Q4':30000,
 '2025Q1':30500,'2025Q2':31400,'2025Q3':32000,'2025Q4':32700,
 '2026Q1':33200,'2026Q2':33400}
rpo = {  # USD millions
 '2021Q4':815.0,
 '2022Q1':857.9,'2022Q2':881.4,'2022Q3':941.0,'2022Q4':1057.2,
 '2023Q1':1138.3,'2023Q2':1252.5,'2023Q3':1446.2,'2023Q4':1839.4,
 '2024Q1':1731.5,'2024Q2':1792.4,'2024Q3':1821.8,'2024Q4':2273.1,
 '2025Q1':2309.0,'2025Q2':2430.0,'2025Q3':2787.6,'2025Q4':3461.2,
 '2026Q1':3480.0,'2026Q2':3470.0}
rpo_basis = {q:'10-Q/10-K exact' for q in rpo}
for q in ['2025Q2','2026Q1','2026Q2']: rpo_basis[q]='CFO call, rounded to $10M (10-Q exact not retrieved)'
nrr = {
 '2022Q1':'>130%','2022Q2':'>130%','2022Q3':'>130%','2022Q4':'>130%','2023Q1':'>130%',
 '2023Q2':'<130% and >120%','2023Q3':'slightly below 120%','2023Q4':'mid-110s',
 '2024Q1':'mid-110s','2024Q2':'mid-110s','2024Q3':'mid-110s','2024Q4':'high-110s',
 '2025Q1':'high-110s','2025Q2':'about 120%','2025Q3':'about 120%','2025Q4':'about 120%',
 '2026Q1':'low-120s','2026Q2':'low-120s'}
nrr_conf = {q:'high' for q in nrr}
nrr_conf.update({'2022Q1':'medium (call transcript, 3rd-party host)','2022Q2':'medium (implied by "Nth consecutive quarter" statements)',
 '2023Q1':'LOW (implied by Q2-23 commentary; not directly verified)','2023Q2':'LOW-MEDIUM (secondary summary of call; exact wording not verified)',
 '2023Q3':'medium (call transcript, 3rd-party host)'})

qend = {'Q1':'03-31','Q2':'06-30','Q3':'09-30','Q4':'12-31'}
def qe(q): return f"{q[:4]}-{qend[q[4:]]}"
def lab(q): return f"{q[:4]} {q[4:]}"
quarters = [f"{y}Q{i}" for y in range(2022,2027) for i in range(1,5)][:18]
def prev_year(q): return f"{int(q[:4])-1}{q[4:]}"
def prev_q(q):
    y,i = int(q[:4]),int(q[5]); return f"{y-1}Q4" if i==1 else f"{y}Q{i-1}"

# ---------- CALCULATED ----------
rows=[]
for q in quarters:
    r = rev_k[q]/1000
    yoy = rev_k[q]/rev_k[prev_year(q)]-1
    qoq = rev_k[q]/rev_k[prev_q(q)]-1
    c = c100[q]; cy = c/c100[prev_year(q)]-1
    rp = rpo[q]; py = prev_year(q)
    ry = rp/rpo[py]-1 if py in rpo else np.nan
    rows.append(dict(Quarter=lab(q),Quarter_End=qe(q),Revenue_USDm=round(r,3),
        Revenue_YoY=round(yoy*100,2),Revenue_QoQ=round(qoq*100,2),
        Customers_100k=c,Customers_100k_YoY=round(cy*100,2),
        RPO_USDm=rp,RPO_YoY=round(ry*100,2) if not np.isnan(ry) else np.nan,
        RPO_basis=rpo_basis[q]))
calc = pd.DataFrame(rows)
calc.to_csv('outputs/ddog_calculated_dataset.csv',index=False)

# ---------- SOURCES ----------
IR="https://investors.datadoghq.com/static-files/"; SEC="https://www.sec.gov/Archives/edgar/data/1561550/"
SUPP4Q25=IR+"94241e00-9de8-4081-b62f-214d051d083b"; SUPP2Q26=IR+"477a4084-42e7-4468-af1d-1bf9ae99d9ab"
PR={'2022Q1':IR+'23d358e0-eba2-4fb9-993a-98179120f56b','2022Q2':IR+'9e82d3c5-00bc-44af-abfe-ebbc486e71fa',
 '2022Q3':IR+'5dfafb8f-c6bb-415d-80b2-da508e48122b','2022Q4':IR+'d0afe925-a0eb-4124-9971-749762415612',
 '2023Q1':IR+'6ca01f63-80f5-4ce0-b5a2-683ff3378f05','2023Q2':IR+'2ec01832-668b-4e43-9075-bf96baf7d38b',
 '2023Q3':IR+'27c898b8-fb12-48b8-af68-5958f226a2fc','2023Q4':IR+'a8ba8d41-5a66-41fd-a8b5-b2408a393b02',
 '2024Q1':SUPP4Q25,'2024Q2':SUPP4Q25,'2024Q3':SUPP4Q25,
 '2024Q4':SEC+'000156155025000017/ex-991x20241231x8k.htm',
 '2025Q1':IR+'2d291f15-a1e1-402b-88a0-6e83a8fad901','2025Q2':SUPP4Q25,'2025Q3':SUPP4Q25,
 '2025Q4':'https://www.sec.gov/Archives/edgar/data/1561550/000162828026006645/ex-991x20251231x8k.htm',
 '2026Q1':'https://www.sec.gov/Archives/edgar/data/0001561550/000162828026031677/ex-991x20260331x8k.htm',
 '2026Q2':'https://investors.datadoghq.com/news-releases/news-release-details/datadog-announces-second-quarter-2026-financial-results'}
XREV={'2022Q1':'PR 1Q23 comparative: '+PR['2023Q1'],'2022Q2':'PR 2Q23 comparative: '+PR['2023Q2'],
 '2022Q3':'PR 3Q23 comparative: '+PR['2023Q3'],'2022Q4':'PR 4Q23 comparative: '+PR['2023Q4'],
 '2023Q1':'10-Q 1Q24: '+SEC+'000156155024000051/ddog-20240331.htm','2023Q2':'10-Q 2Q24 XBRL: '+SEC+'000156155024000112/Financial_Report.xlsx',
 '2023Q3':'10-Q 3Q24: '+SEC+'000156155024000175/ddog-20240930.htm','2023Q4':'FY2023 (2,128,359) minus 9M (1,538,710) per PR 4Q23/3Q23',
 '2024Q1':'10-Q 1Q24: '+SEC+'000156155024000051/ddog-20240331.htm','2024Q2':'10-Q 2Q24 XBRL: '+SEC+'000156155024000112/Financial_Report.xlsx',
 '2024Q3':'10-Q 3Q24: '+SEC+'000156155024000175/ddog-20240930.htm','2024Q4':'FY2024 10-K (2,684,275) minus 9M (1,946,548): '+SEC+'000156155025000025/ddog-20241231.htm',
 '2025Q1':'10-Q 1Q26: https://www.sec.gov/Archives/edgar/data/0001561550/000162828026032328/ddog-20260331.htm',
 '2025Q2':'10-Q 2Q26: https://www.sec.gov/Archives/edgar/data/0001561550/000162828026054458/ddog-20260630.htm',
 '2025Q3':'10-Q 3Q25: '+SEC+'000156155025000313/ddog-20250930.htm','2025Q4':'FY2025 10-K (3,427,158) minus 9M (2,473,964): https://www.sec.gov/Archives/edgar/data/1561550/000162828026008819/ddog-20251231.htm',
 '2026Q1':'10-Q 1Q26 + '+SUPP2Q26,'2026Q2':'10-Q 2Q26 + '+SUPP2Q26}
FOOL22="https://www.fool.com/earnings/call-transcripts/2022/"
TOT={'2022Q1':'1Q23 call (year-ago comparative): https://www.fool.com/earnings/call-transcripts/2023/05/04/datadog-ddog-q1-2023-earnings-call-transcript/',
 '2022Q2':'2Q23 call (year-ago comparative): https://www.marketbeat.com/earnings/reports/2023-8-8-datadog-inc-stock',
 '2022Q3':'3Q22 call: '+FOOL22+'11/03/datadog-ddog-q3-2022-earnings-call-transcript/',
 '2022Q4':'4Q23 call, IR-hosted (year-ago comparative): '+IR+'8a1b21f1-c008-4b97-afca-b11b0e0cbec5',
 '2023Q1':'1Q23 call: https://www.fool.com/earnings/call-transcripts/2023/05/04/datadog-ddog-q1-2023-earnings-call-transcript/',
 '2023Q2':'2Q23 call: https://www.marketbeat.com/earnings/reports/2023-8-8-datadog-inc-stock',
 '2023Q3':'3Q23 call: https://www.fool.com/earnings/call-transcripts/2023/11/07/datadog-ddog-q3-2023-earnings-call-transcript/',
 '2023Q4':'4Q23 call, IR-hosted: '+IR+'8a1b21f1-c008-4b97-afca-b11b0e0cbec5'}
for q in ['2024Q1','2024Q2','2024Q3','2024Q4','2025Q1','2025Q2','2025Q3','2025Q4']: TOT[q]='Supplemental 4Q25: '+SUPP4Q25
for q in ['2026Q1','2026Q2']: TOT[q]='Supplemental 2Q26: '+SUPP2Q26
FR=lambda acc: SEC+acc+'/Financial_Report.xlsx'
RPO_SRC={'2022Q1':SEC+'000156155022000026/ddog-20220331.htm','2022Q2':FR('000156155022000038'),'2022Q3':FR('000156155022000045'),
 '2022Q4':FR('000156155024000009')+' (prior-year column of FY2023 10-K)','2023Q1':FR('000156155023000023'),'2023Q2':FR('000156155023000039'),
 '2023Q3':FR('000156155023000055'),'2023Q4':FR('000156155024000009'),'2024Q1':FR('000156155024000051'),'2024Q2':FR('000156155024000112'),
 '2024Q3':FR('000156155024000175'),'2024Q4':FR('000156155025000025'),'2025Q1':FR('000156155025000123'),
 '2025Q2':'2Q25 call, IR-hosted: '+IR+'4b5b9407-c0e8-4333-b035-ca5b894e8904 (10-Q: '+SEC+'000156155025000220/ddog-20250630.htm)',
 '2025Q3':SEC+'000156155025000313/ddog-20250930.htm','2025Q4':'1Q26 10-Q Dec-31-2025 comparative: '+SEC+'000162828026032328/ddog-20260331.htm',
 '2026Q1':'1Q26 call: https://www.fool.com/earnings/call-transcripts/2026/05/07/datadog-ddog-q1-2026-earnings-transcript/ (IR transcript: '+IR+'b162f4b4-ae66-4fd2-bc41-92b4f9a877c9+)',
 '2026Q2':'2Q26 call: https://www.investing.com/news/transcripts/earnings-call-transcript-datadog-beats-q2-2026-estimates-but-shares-fall-156-93CH-4842560 (IR transcript: '+IR+'2360a5cc-f17a-4731-b74a-fb6f4617baf5)'}
RPO_SRC['2026Q1']=RPO_SRC['2026Q1'].replace('+)',')')
NRR_SRC={'2022Q1':'1Q22 call: '+FOOL22+'05/05/datadog-ddog-q1-2022-earnings-call-transcript/','2022Q2':'Implied: 1Q22=19th and 4Q22=22nd consecutive quarter >130%',
 '2022Q3':'10-Q 3Q23 (Sep-30-2022 comparative): '+SEC+'000156155023000055/ddog-20230930.htm','2022Q4':'FY2022 annual report/10-K: '+SEC+'000156155023000015/datadogannualreport2022.pdf',
 '2023Q1':'Implied by 2Q23 commentary (secondary): https://www.thewolfofharcourtstreet.com/p/datadog-are-the-dog-days-over ; SEC CORRESP: '+SEC+'000119312523265193/filename1.htm',
 '2023Q2':'Secondary: https://www.thewolfofharcourtstreet.com/p/datadog-are-the-dog-days-over ; SEC CORRESP: '+SEC+'000119312523265193/filename1.htm',
 '2023Q3':'3Q23 call: https://www.fool.com/earnings/call-transcripts/2023/11/07/datadog-ddog-q3-2023-earnings-call-transcript/',
 '2023Q4':'4Q23 call, IR-hosted: '+IR+'8a1b21f1-c008-4b97-afca-b11b0e0cbec5'}
for q in ['2024Q1','2024Q2']: NRR_SRC[q]='Supplemental 4Q25: '+SUPP4Q25
for q in ['2024Q3','2024Q4','2025Q1','2025Q2','2025Q3','2025Q4','2026Q1','2026Q2']: NRR_SRC[q]='Supplemental 2Q26: '+SUPP2Q26

raw=[]
for q in quarters:
    raw.append(dict(Quarter=lab(q),Quarter_End=qe(q),Revenue_USDm=round(rev_k[q]/1000,3),Total_Customers=tot[q],
      Customers_100k=c100[q],RPO_USDm=rpo[q],RPO_basis=rpo_basis[q],NRR=nrr[q],NRR_confidence=nrr_conf[q],
      Src_Revenue_and_100k=PR[q],Src_Revenue_XCheck=XREV[q],Src_TotalCustomers=TOT[q],Src_RPO=RPO_SRC[q],Src_NRR=NRR_SRC[q]))
rawdf=pd.DataFrame(raw); rawdf.to_csv('outputs/ddog_raw_data_with_sources.csv',index=False)

# ---------- INTEGRITY CHECKS ----------
fy = {2022:1675100,2023:2128359,2024:2684275,2025:3427158}
print("FY sum checks (quarters vs reported FY):")
for y,v in fy.items():
    s=sum(rev_k[f'{y}Q{i}'] for i in range(1,5)); print(y,s,v,'OK' if s==v else 'MISMATCH')
print('FY2021 check', sum(rev_k[f'2021Q{i}'] for i in range(1,5)), 1028784)
print('6M26', rev_k['2026Q1']+rev_k['2026Q2'], 2127880)
# company-stated YoY revenue growth vs computed (rounded)
stated={'2022Q1':83,'2022Q2':74,'2022Q3':61,'2022Q4':44,'2023Q1':33,'2023Q2':25,'2023Q3':25,'2023Q4':26,'2024Q1':27,'2024Q3':26,'2024Q4':25,'2025Q1':25,'2025Q2':28,'2025Q3':28,'2025Q4':29,'2026Q1':32,'2026Q2':36}
bad=[(q,s,round((rev_k[q]/rev_k[prev_year(q)]-1)*100,1)) for q,s in stated.items() if round((rev_k[q]/rev_k[prev_year(q)]-1)*100)!=s]
print('Stated vs computed rev YoY mismatches:',bad)
stated100={'2022Q1':60,'2022Q2':54,'2022Q3':44,'2022Q4':38,'2023Q1':29,'2023Q2':24,'2023Q3':20,'2023Q4':15,'2024Q3':12,'2024Q4':13,'2025Q4':19,'2026Q1':21,'2026Q2':23}
bad2=[(q,s,round((c100[q]/c100[prev_year(q)]-1)*100,1)) for q,s in stated100.items() if round((c100[q]/c100[prev_year(q)]-1)*100)!=s]
print('Stated vs computed $100k YoY mismatches:',bad2)
# stated RPO YoY
sr={'2022Q4':30,'2023Q4':74,'2024Q3':26,'2024Q4':24,'2025Q2':35,'2025Q3':53,'2025Q4':52,'2026Q1':51,'2026Q2':43}
print('RPO YoY stated vs computed:',[(q,s,round((rpo[q]/rpo[prev_year(q)]-1)*100,1)) for q,s in sr.items()])
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
print(calc.drop(columns=['RPO_basis']).to_string(index=False))
print(calc.drop(columns=['RPO_basis']).to_csv(index=False))