#!/usr/bin/env python3
import argparse, re, sys
from pathlib import Path
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning

URL="https://ipm.mospi.gov.in/Home/PublicDashboard"

def tx(el): return " ".join(el.stripped_strings) if el else ""

def parse(html):
    soup=BeautifulSoup(html,"lxml")
    modal=soup.select_one("#projectcount1")
    if not modal: raise RuntimeError("Project Overview modal not found")
    table=modal.find("table")
    hs=[tx(x) for x in table.select("thead th")]
    rows=[]
    for tr in table.select("tbody tr"):
        cells=[tx(td) for td in tr.find_all("td")]
        if len(cells)==len(hs): rows.append(cells)
    if not rows: raise RuntimeError("No project rows found")
    df=pd.DataFrame(rows,columns=hs)
    df.columns=["sr_no","sector_name","line_ministry","project_code","project_name",
                "original_cost_crore","revised_cost_crore","expenditure_crore",
                "original_end_date","revised_date"]
    df=df.replace(r"^\s*$",pd.NA,regex=True)
    for c in ["original_cost_crore","revised_cost_crore","expenditure_crore"]:
        df[c]=pd.to_numeric(df[c].astype("string").str.replace(",","",regex=False).str.replace("₹","",regex=False).str.strip(),errors="coerce")
    for c in ["original_end_date","revised_date"]:
        df[c]=pd.to_datetime(df[c],format="%d/%m/%Y",errors="coerce")
    df["delay_days"]=(df["revised_date"]-df["original_end_date"]).dt.days
    df["schedule_revised_later"]=pd.NA
    m=df["original_end_date"].notna() & df["revised_date"].notna()
    df.loc[m,"schedule_revised_later"]=(df.loc[m,"delay_days"]>0).astype("Int64")
    snap=soup.select_one("#refreshDateText")
    df["source_snapshot"]=tx(snap).strip("()") if snap else pd.NA
    df["source_url"]=URL
    return df

def session(insecure=False):
    s=requests.Session()
    s.headers["User-Agent"]="Mozilla/5.0"
    s.verify=not insecure
    if insecure:
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
    return s

def fetch(month=None,insecure=False):
    s=session(insecure)
    r=s.get(URL,timeout=90); r.raise_for_status()
    if not month: return r.text
    soup=BeautifulSoup(r.text,"lxml")
    tok=soup.select_one('input[name="__RequestVerificationToken"]')
    if not tok: raise RuntimeError("anti-forgery token not found")
    payload={"__RequestVerificationToken":tok.get("value",""),"SectorId":"","PROJ_MINISTRY_ID":"",
             "StateId":"","CostRange":"","MonthYear":month}
    r=s.post(URL,data=payload,headers={"Referer":URL},timeout=120)
    r.raise_for_status()
    return r.text

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--month")
    ap.add_argument("--output","-o")
    ap.add_argument("--html")
    ap.add_argument("--insecure",action="store_true")
    a=ap.parse_args()
    if a.month and not re.fullmatch(r"\d{4}-\d{2}",a.month): ap.error("--month must be YYYY-MM")
    try:
        html=Path(a.html).read_text(encoding="utf-8",errors="replace") if a.html else fetch(a.month,a.insecure)
        df=parse(html)
    except requests.exceptions.SSLError as e:
        print("TLS validation failed. Prefer saving the page HTML in Chrome and use --html; or for this public host only, use --insecure.",file=sys.stderr)
        return 3
    out=Path(a.output or f"data/raw/paimana/paimana_dashboard_{a.month or 'latest'}.csv")
    out.parent.mkdir(parents=True,exist_ok=True)
    x=df.copy()
    for c in ["original_end_date","revised_date"]: x[c]=x[c].dt.strftime("%Y-%m-%d")
    x.to_csv(out,index=False)
    print(f"Rows extracted: {len(x):,}")
    print(f"Unique project codes: {x.project_code.nunique():,}")
    print(f"Rows with revised dates: {x.revised_date.notna().sum():,}")
    print(f"Wrote: {out}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
