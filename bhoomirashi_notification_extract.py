
import argparse, csv, json, re, time
from urllib.parse import urljoin, urlparse, parse_qs
from datetime import datetime
import requests
from bs4 import BeautifulSoup

BASE="https://bhoomirashi.gov.in"
DATE_RE=re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
NUM_RE=re.compile(r"(?<!\d)(\d+(?:[/-]\d+)*(?:[A-Za-z])?)(?!\d)")

def clean(x):
    return re.sub(r"\s+"," ", x or "").strip()

def pid(url):
    return parse_qs(urlparse(url).query).get("project_id",[""])[0]

def get(url, timeout=45):
    r=requests.get(url,headers={"User-Agent":"Mozilla/5.0 (compatible; LandGuard-research/1.0)"},timeout=timeout)
    r.raise_for_status()
    return r.text

def project_name(soup):
    txt=soup.get_text("\n",strip=True)
    m=re.search(r"Project Name\s*(.*?)\s*Project Number",txt,re.S|re.I)
    return clean(m.group(1))[:1200] if m else ""

def project_number(txt):
    m=re.search(r"Project Number\s*\|\s*([A-Z]{1,4}/\d{4}/\d+)",txt,re.I)
    return m.group(1) if m else ""

def num_after(label, txt):
    m=re.search(re.escape(label)+r"\s*\|\s*([0-9.,]+)",txt,re.I)
    if not m: return None
    try: return float(m.group(1).replace(",",""))
    except: return None

def detect_stage(href):
    p=urlparse(href).path.lower()
    if p.endswith("/sdet.cshtml"): return "3A"
    if p.endswith("/sdet1.cshtml"): return "3D"
    return None

def nearest_row(a):
    tr=a.find_parent("tr")
    if tr:
        return clean(tr.get_text(" | ",strip=True))
    return clean(a.parent.get_text(" | ",strip=True)) if a.parent else ""

def parse_pubdate(row):
    m=DATE_RE.search(row)
    if not m: return ""
    try: return datetime.strptime(m.group(1),"%d/%m/%Y").date().isoformat()
    except: return ""

def parse_notification_number(row):
    # date usually first; number follows it in a table row.
    m=DATE_RE.search(row)
    tail=row[m.end():] if m else row
    tail=re.sub(r"\|\s*View Details.*$","",tail,flags=re.I)
    parts=[clean(p) for p in tail.split("|") if clean(p)]
    return parts[0][:120] if parts else ""

def generic_detail_features(html):
    soup=BeautifulSoup(html,"html.parser")
    text=clean(soup.get_text(" | ",strip=True))
    rows=[]
    for tr in soup.find_all("tr"):
        cells=[clean(td.get_text(" ",strip=True)) for td in tr.find_all(["th","td"])]
        if cells: rows.append(cells)

    # Keep structured text for audit and derive geography / survey-like tokens.
    joined_rows=[" | ".join(r) for r in rows]
    village_tokens=set()
    survey_tokens=set()

    headers=[c.lower() for r in rows[:5] for c in r]
    for r in rows:
        lower=" | ".join(r).lower()
        if "village" in lower:
            for c in r:
                if c and c.lower() not in {"village","villages","village name"}:
                    village_tokens.add(clean(c).lower())
        if "survey" in lower or "khasra" in lower or "plot" in lower:
            for c in r:
                for token in NUM_RE.findall(c):
                    if len(token) <= 30:
                        survey_tokens.add(token.lower())

    # Fallback: collect likely survey IDs from rows containing survey/khasra/plot.
    if not survey_tokens:
        for r in rows:
            line=" | ".join(r)
            if re.search(r"survey|khasra|plot",line,re.I):
                for token in NUM_RE.findall(line):
                    survey_tokens.add(token.lower())

    return {
        "detail_text": text[:20000],
        "table_json": json.dumps(rows,ensure_ascii=False)[:50000],
        "villages": ";".join(sorted(village_tokens)),
        "survey_numbers": ";".join(sorted(survey_tokens)),
        "n_surveys": len(survey_tokens),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",default="seed_urls.csv")
    ap.add_argument("--projects-out",default="bhoomirashi_projects.csv")
    ap.add_argument("--notifications-out",default="bhoomirashi_notifications.csv")
    ap.add_argument("--delay",type=float,default=1.5)
    ap.add_argument("--detail-delay",type=float,default=1.0)
    args=ap.parse_args()

    urls=[]
    with open(args.input,encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            u=(r.get("url") or "").strip()
            if u: urls.append(u)

    proj_rows=[]; notif_rows=[]
    seen_detail=set()

    for i,u in enumerate(urls,1):
        print(f"[project {i}/{len(urls)}] {u}")
        try:
            html=get(u)
            soup=BeautifulSoup(html,"html.parser")
            txt=clean(soup.get_text(" | ",strip=True))
            p={
                "project_id":pid(u),"project_number":project_number(txt),
                "project_name":project_name(soup),"url":u,
                "land_required_ha":num_after("Land Required",txt),
                "land_available_ha":num_after("Land Available",txt),
                "land_to_be_acquired_ha":num_after("Land to be acquired",txt),
                "land_acquired_ha":num_after("Land Acquired till now",txt),
            }
            proj_rows.append(p)

            links=[]
            for a in soup.find_all("a",href=True):
                href=urljoin(u,a["href"])
                stage=detect_stage(href)
                if stage:
                    links.append((stage,href,a))
            # dedupe because same href may appear twice on bilingual/duplicate rows
            ded={}
            for stage,href,a in links:
                ded[(stage,href)]=a

            for j,((stage,href),a) in enumerate(ded.items(),1):
                row=nearest_row(a)
                n={
                    "project_id":p["project_id"],"project_number":p["project_number"],
                    "stage":stage,"publish_date":parse_pubdate(row),
                    "notification_number":parse_notification_number(row),
                    "detail_url":href,"row_text":row,
                    "villages":"","survey_numbers":"","n_surveys":0,
                    "detail_ok":0,"detail_error":""
                }
                if href not in seen_detail:
                    try:
                        dh=get(href)
                        feat=generic_detail_features(dh)
                        n.update(feat); n["detail_ok"]=1
                        seen_detail.add(href)
                        time.sleep(args.detail_delay)
                    except Exception as e:
                        n["detail_error"]=repr(e)
                notif_rows.append(n)
            print(f"  found {len(ded)} unique 3A/3D detail links")
        except Exception as e:
            print("  PROJECT ERROR:",e)
        time.sleep(args.delay)

    pfields=["project_id","project_number","project_name","url","land_required_ha","land_available_ha","land_to_be_acquired_ha","land_acquired_ha"]
    with open(args.projects_out,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=pfields); w.writeheader(); w.writerows(proj_rows)

    nfields=["project_id","project_number","stage","publish_date","notification_number","detail_url","row_text","villages","survey_numbers","n_surveys","detail_ok","detail_error","detail_text","table_json"]
    with open(args.notifications_out,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=nfields); w.writeheader()
        for r in notif_rows:
            for k in nfields: r.setdefault(k,"")
            w.writerow({k:r.get(k,"") for k in nfields})

    print(f"[done] projects={len(proj_rows)} notifications={len(notif_rows)}")

if __name__=="__main__":
    main()
