"""
Hyperscaler cloud dataset (AWS, Azure, Google Cloud) by CALENDAR quarter, 2022Q1-2026Q2.
Values were transcribed from primary documents (SEC filings / company IR releases); this script
(1) stores them with per-datapoint URLs, (2) aligns Microsoft fiscal quarters to calendar quarters,
(3) computes YoY for AWS and Google Cloud from reported revenue, (4) runs integrity checks, (5) writes CSVs.
"""
import pandas as pd, numpy as np

OUT = "outputs/"          # change for local use
AMZ = "https://www.sec.gov/Archives/edgar/data/1018724/"
AMZ0 = "https://www.sec.gov/Archives/edgar/data/0001018724/"
GOOG = "https://www.sec.gov/Archives/edgar/data/1652044/"
GOOG0 = "https://www.sec.gov/Archives/edgar/data/0001652044/"
MSFT = "https://www.sec.gov/Archives/edgar/data/789019/"
MSIR = "https://www.microsoft.com/en-us/investor/earnings/"

# ---------------- AWS segment net sales, USD millions (as reported; Q4 = FY - 9M where noted) ----------------
aws = {'2021Q1':13503,'2021Q2':14809,'2021Q3':16110,'2021Q4':17780,
       '2022Q1':18441,'2022Q2':19739,'2022Q3':20538,'2022Q4':21378,
       '2023Q1':21354,'2023Q2':22140,'2023Q3':23059,'2023Q4':24204,
       '2024Q1':25037,'2024Q2':26281,'2024Q3':27452,'2024Q4':28786,
       '2025Q1':29267,'2025Q2':30873,'2025Q3':33006,'2025Q4':35579,
       '2026Q1':37587,'2026Q2':42232}
aws_derived_q4 = {'2021Q4':(62202,44422),'2022Q4':(80096,58718),'2023Q4':(90757,66553),
                  '2024Q4':(107556,78770),'2025Q4':(128725,93146)}          # (FY total, 9M total)
aws_src = {
 '2021Q1':AMZ+'000101872421000010/amzn-20210331.htm','2021Q2':AMZ+'000101872421000020/amzn-20210630.htm',
 '2021Q3':AMZ+'000101872421000028/R23.htm',
 '2021Q4':'DERIVED FY21 62,202 ('+AMZ+'000101872424000008/Financial_Report.xlsx) minus 9M21 44,422 ('+AMZ+'000101872421000028/R23.htm)',
 '2022Q1':AMZ+'000101872422000013/amzn-20220331.htm','2022Q2':AMZ+'000101872422000019/amzn-20220630.htm',
 '2022Q3':AMZ+'000101872422000023/R23.htm',
 '2022Q4':'DERIVED FY22 80,096 ('+AMZ+'000101872424000008/amzn-20231231.htm) minus 9M22 58,718 ('+AMZ+'000101872422000023/R23.htm); release: '+AMZ+'000101872423000002/amzn-20221231xex991.htm',
 '2023Q1':AMZ+'000101872423000008/amzn-20230331.htm','2023Q2':AMZ+'000101872423000012/amzn-20230630.htm',
 '2023Q3':AMZ+'000101872423000018/R23.htm',
 '2023Q4':'DERIVED FY23 90,757 ('+AMZ+'000101872424000008/amzn-20231231.htm) minus 9M23 66,553 ('+AMZ+'000101872423000018/R23.htm); release: '+AMZ+'000101872424000006/amzn-20231231xex991.htm',
 '2024Q1':AMZ+'000101872424000083/amzn-20240331.htm',
 '2024Q2':'Comparative column in 10-Q 2Q25: '+AMZ+'000101872425000086/amzn-20250630.htm (original 2Q24 10-Q: '+AMZ+'000101872424000130/amzn-20240630.htm)',
 '2024Q3':AMZ+'000101872424000161/amzn-20240930.htm',
 '2024Q4':'DERIVED FY24 107,556 ('+AMZ+'000101872426000004/amzn-20251231.htm) minus 9M24 78,770 ('+AMZ+'000101872424000161/amzn-20240930.htm); release: '+AMZ+'000101872425000002/amzn-20241231xex991.htm',
 '2025Q1':AMZ+'000101872425000036/amzn-20250331.htm','2025Q2':AMZ+'000101872425000086/amzn-20250630.htm',
 '2025Q3':AMZ+'000101872425000123/amzn-20250930.htm',
 '2025Q4':'DERIVED FY25 128,725 ('+AMZ+'000101872426000004/amzn-20251231.htm) minus 9M25 93,146 ('+AMZ+'000101872425000123/amzn-20250930.htm)',
 '2026Q1':AMZ0+'000101872426000014/amzn-20260331.htm','2026Q2':AMZ0+'000101872426000026/amzn-20260630.htm'}

# ---------------- Google Cloud segment revenues, USD millions (as reported) ----------------
gcp = {'2021Q1':4047,'2021Q2':4628,'2021Q3':4990,'2021Q4':5541,
       '2022Q1':5821,'2022Q2':6276,'2022Q3':6868,'2022Q4':7315,
       '2023Q1':7454,'2023Q2':8031,'2023Q3':8411,'2023Q4':9192,
       '2024Q1':9574,'2024Q2':10347,'2024Q3':11353,'2024Q4':11955,
       '2025Q1':12260,'2025Q2':13624,'2025Q3':15157,'2025Q4':17664,
       '2026Q1':20028,'2026Q2':24768}
gcp_src = {
 '2021Q1':'Comparative in 10-Q 1Q22: '+GOOG+'000165204422000029/goog-20220331.htm','2021Q2':'Comparative in 10-Q 2Q22: '+GOOG+'000165204422000071/goog-20220630.htm',
 '2021Q3':GOOG+'000165204421000054/googexhibit991q32021.htm','2021Q4':'Comparative in 8-K 4Q22: '+GOOG+'000165204423000013/googexhibit991q42022.htm',
 '2022Q1':GOOG+'000165204422000029/goog-20220331.htm','2022Q2':GOOG+'000165204422000071/goog-20220630.htm',
 '2022Q3':GOOG+'000165204422000085/googexhibit991q32022.htm','2022Q4':GOOG+'000165204423000013/googexhibit991q42022.htm',
 '2023Q1':GOOG+'000165204423000041/googexhibit991q12023.htm','2023Q2':GOOG+'000165204423000067/googexhibit991q22023.htm',
 '2023Q3':GOOG+'000165204423000088/googexhibit991q32023.htm','2023Q4':GOOG+'000165204424000014/googexhibit991q42023.htm',
 '2024Q1':GOOG+'000165204424000047/googexhibit991q12024.htm','2024Q2':GOOG+'000165204424000076/googexhibit991q22024.htm',
 '2024Q3':GOOG+'000165204424000115/googexhibit991q32024.htm','2024Q4':GOOG+'000165204425000010/googexhibit991q42024.htm',
 '2025Q1':GOOG+'000165204425000040/googexhibit991q12025.htm','2025Q2':GOOG+'000165204425000056/googexhibit991q22025.htm',
 '2025Q3':GOOG+'000165204425000087/googexhibit991q32025.htm',
 '2025Q4':'https://s206.q4cdn.com/479360582/files/doc_financials/2025/q4/2025q4-alphabet-earnings-release.pdf',
 '2026Q1':GOOG0+'000165204426000043/googexhibit991q12026.htm','2026Q2':GOOG0+'000165204426000066/googexhibit991q22026.htm'}

# ---------------- Microsoft: Azure and other cloud services growth (%), keyed by CALENDAR quarter ----------------
# calendar quarter -> (MSFT fiscal label, reported YoY, constant-currency YoY or None, cc note, source)
azure = {
 '2022Q1':('FY22 Q3',46,49,'',"https://microsoft.gcs-web.com/static-files/7bcc3532-5541-4d7a-bf21-699077fb5ff4 (8-K: "+MSFT+"000119312522120207/d328712dex991.htm)"),
 '2022Q2':('FY22 Q4',40,46,'',MSIR+'FY-2022-Q4/press-release-webcast'),
 '2022Q3':('FY23 Q1',35,42,'',MSIR+'FY-2023-Q1/press-release-webcast'),
 '2022Q4':('FY23 Q2',31,38,'',MSIR+'FY-2023-Q2/press-release-webcast'),
 '2023Q1':('FY23 Q3',27,31,'',MSIR+'FY-2023-Q3/press-release-webcast (8-K: '+MSFT+'000119312523115280/d321368dex991.htm)'),
 '2023Q2':('FY23 Q4',26,27,'',MSFT+'000095017023034400/msft-ex99_1.htm'),
 '2023Q3':('FY24 Q1',29,28,'',MSIR+'FY-2024-Q1/press-release-webcast (8-K: '+MSFT+'000095017023054848/msft-ex99_1.htm)'),
 '2023Q4':('FY24 Q2',30,28,'',MSFT+'000095017024008809/msft-ex99_1.htm'),
 '2024Q1':('FY24 Q3',31,None,'cc not stated in release',MSFT+'000095017024048268/msft-ex99_1.htm'),
 '2024Q2':('FY24 Q4',29,30,'',MSFT+'000095017024087835/msft-ex99_1.htm'),
 '2024Q3':('FY25 Q1',33,None,'cc not retrieved (release excerpt truncated)',MSIR+'fy-2025-q1/intelligent-cloud-performance (8-K: '+MSFT+'000095017024118955/msft-ex99_1.htm)'),
 '2024Q4':('FY25 Q2',31,None,'cc not stated in release','https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/PressReleaseFY25Q2 ('+MSIR+'fy-2025-q2/intelligent-cloud-performance)'),
 '2025Q1':('FY25 Q3',33,None,'cc not retrieved (release excerpt truncated)',MSIR+'FY-2025-Q3/intelligent-cloud-performance (8-K: '+MSFT+'000095017025061032/msft-ex99_1.htm)'),
 '2025Q2':('FY25 Q4',39,None,'cc not stated in release',MSIR+'FY-2025-Q4/press-release-webcast (8-K: '+MSFT+'000095017025100226/msft-ex99_1.htm)'),
 '2025Q3':('FY26 Q1',40,39,'cc taken from a third-party reproduction of the release (benzinga.com/node/48510921); IR release page not retrieved',MSIR+'fy-2026-q1/intelligent-cloud-performance'),
 '2025Q4':('FY26 Q2',39,38,'',MSFT+'000119312526027198/msft-ex99_1.htm ('+MSIR+'FY-2026-Q2/press-release-webcast)'),
 '2026Q1':('FY26 Q3',40,39,'',MSFT+'000119312526191457/msft-ex99_1.htm ('+MSIR+'FY-2026-Q3/press-release-webcast)'),
 '2026Q2':('FY26 Q4',43,None,'cc not stated in release',MSFT+'000119312526323632/msft-ex99_1.htm ('+MSIR+'fy-2026-q4/press-release-webcast)')}
# Microsoft's own restatement of FY24 to the FY25 (new) Azure definition: (reported, cc)
azure_restated = {'2023Q3':(31,30),'2023Q4':(33,31),'2024Q1':(35,None),'2024Q2':(34,35)}
AZ_RESTATE_SRC = MSFT+'000119312524204403/d846847dex991.htm'

# ---------------- helpers ----------------
qend = {'1':'03-31','2':'06-30','3':'09-30','4':'12-31'}
cal = [f"{y}Q{q}" for y in range(2022,2027) for q in range(1,5)][:18]
py = lambda q: f"{int(q[:4])-1}{q[4:]}"
lab = lambda q: f"{q[:4]} Q{q[5]}"

# ---------------- integrity checks ----------------
print("== AWS: derived Q4 and YTD ties ==")
for q,(fy,ninem) in aws_derived_q4.items():
    print(q, fy-ninem, aws[q], 'OK' if fy-ninem==aws[q] else 'MISMATCH')
for y,ytd in {2021:44422,2022:58718,2023:66553,2024:78770,2025:93146}.items():
    s = sum(aws[f'{y}Q{i}'] for i in (1,2,3)); print(y,'9M',s,ytd,'OK' if s==ytd else 'MISMATCH')
print('6M24',aws['2024Q1']+aws['2024Q2'],51318,'| 6M25',aws['2025Q1']+aws['2025Q2'],60140,'| 6M26',aws['2026Q1']+aws['2026Q2'],79819)
print("== Google Cloud: YTD / FY ties ==")
for y,ytd in {2021:13665,2022:18965,2023:23896,2024:31274}.items():
    s = sum(gcp[f'{y}Q{i}'] for i in (1,2,3)); print(y,'9M',s,ytd,'OK' if s==ytd else 'MISMATCH')
for y,fy in {2021:19206,2022:26280,2023:33088,2024:43229,2025:58705}.items():
    s = sum(gcp[f'{y}Q{i}'] for i in (1,2,3,4)); print(y,'FY',s,fy,'OK' if s==fy else 'MISMATCH')
print('6M25',gcp['2025Q1']+gcp['2025Q2'],25884)
# company-stated YoY (rounded, as printed in releases/10-Qs where retrieved)
aws_stated = {'2022Q3':27,'2022Q4':20,'2023Q3':12,'2023Q4':13,'2024Q1':17,'2024Q2':19,'2024Q3':19,'2024Q4':19,
              '2025Q1':17,'2025Q2':17,'2025Q3':20,'2025Q4':24,'2026Q1':28,'2026Q2':37}
gcp_stated = {'2024Q3':35,'2024Q4':30,'2025Q3':34,'2025Q4':48}
for name,d,stated in (('AWS',aws,aws_stated),('GCP',gcp,gcp_stated)):
    bad=[(q,s,round((d[q]/d[py(q)]-1)*100,2)) for q,s in stated.items() if round((d[q]/d[py(q)]-1)*100)!=s]
    print(name,'stated-vs-computed rounding mismatches:',bad)
print('AWS 2026Q2 computed YoY %.3f (CEO quote: 36.7%%)' % ((aws['2026Q2']/aws['2025Q2']-1)*100))

# ---------------- OUTPUT 1: raw ----------------
def fisc_map(q):  # Microsoft fiscal label from calendar quarter
    y,n = int(q[:4]),int(q[5]); return f"FY{str(y if n<=2 else y+1)[2:]} Q{n+2 if n<=2 else n-2}"
raw = []
for q in cal:
    fl,rep,cc,ccnote,src = azure[q]
    assert fl==fisc_map(q), (q,fl,fisc_map(q))            # calendar alignment self-check
    rest = azure_restated.get(q)
    raw.append({'Calendar_Quarter':lab(q),'Quarter_End':f"{q[:4]}-{qend[q[5]]}",
      'AWS_Revenue_USDm':aws[q],'Azure_Reported_YoY_pct':rep,'GoogleCloud_Revenue_USDm':gcp[q],
      'Azure_ConstCurrency_YoY_pct':cc if cc is not None else np.nan,
      'Azure_Restated_NewDef_YoY_pct':rest[0] if rest else np.nan,
      'Azure_Restated_NewDef_CC_pct':(rest[1] if rest and rest[1] is not None else np.nan),
      'MSFT_Fiscal_Quarter':fl,'Azure_CC_Note':ccnote,
      'AWS_Source':aws_src[q],'Azure_Source':src,'GoogleCloud_Source':gcp_src[q]})
raw = pd.DataFrame(raw)
raw.to_csv(OUT+'cloud_raw_data.csv',index=False)

# ---------------- OUTPUT 2: calculated ----------------
calc = []
for q in cal:
    calc.append({'Calendar_Quarter':lab(q),
      'AWS_YoY_pct':round((aws[q]/aws[py(q)]-1)*100,2),
      'Azure_YoY_pct':azure[q][1],                        # reported, as printed by Microsoft (primary series)
      'GoogleCloud_YoY_pct':round((gcp[q]/gcp[py(q)]-1)*100,2)})
calc = pd.DataFrame(calc)
calc.to_csv(OUT+'cloud_calculated_data.csv',index=False)
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
print(raw.drop(columns=['AWS_Source','Azure_Source','GoogleCloud_Source','Azure_CC_Note']).to_string(index=False))
print(calc.to_string(index=False))
print(calc.to_csv(index=False))
