
import argparse, json, joblib, pandas as pd, numpy as np
from pathlib import Path
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score,balanced_accuracy_score,precision_score,recall_score,f1_score,roc_auc_score

def metric(y,p,pr):
    x={"accuracy":accuracy_score(y,p),"balanced_accuracy":balanced_accuracy_score(y,p),
       "precision":precision_score(y,p,zero_division=0),"recall":recall_score(y,p,zero_division=0),
       "f1":f1_score(y,p,zero_division=0)}
    if len(set(y))==2: x["roc_auc"]=roc_auc_score(y,pr)
    return x

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",default="bhoomirashi_notification_pairs.csv")
    ap.add_argument("--outdir",default="bhoomirashi_notification_model")
    args=ap.parse_args()
    df=pd.read_csv(args.input)
    if len(df)<100:
        raise SystemExit(f"Only {len(df)} matched notification pairs. Collect more data before training (100 hard minimum; 500+ preferred).")
    if df.delay_over_365d.nunique()<2:
        raise SystemExit("Only one target class present. Need both <=365 and >365 day matched examples.")

    # Use only features known before the 3D outcome.
    features=["land_required_ha","land_available_ha","land_to_be_acquired_ha"]
    X=df[features]; y=df.delay_over_365d.astype(int); groups=df.project_id.astype(str)

    splitter=GroupShuffleSplit(n_splits=1,test_size=.25,random_state=42)
    tr,te=next(splitter.split(X,y,groups))
    Xtr,Xte=X.iloc[tr],X.iloc[te]; ytr,yte=y.iloc[tr],y.iloc[te]

    models={
      "logistic_regression":Pipeline([("imp",SimpleImputer(strategy="median")),("scale",StandardScaler()),("m",LogisticRegression(max_iter=3000,class_weight="balanced"))]),
      "random_forest":Pipeline([("imp",SimpleImputer(strategy="median")),("m",RandomForestClassifier(n_estimators=500,random_state=42,class_weight="balanced",min_samples_leaf=3))]),
      "gradient_boosting":Pipeline([("imp",SimpleImputer(strategy="median")),("m",GradientBoostingClassifier(random_state=42))])
    }
    results={}; best=None; bestf=-1
    for name,m in models.items():
        m.fit(Xtr,ytr); pred=m.predict(Xte); prob=m.predict_proba(Xte)[:,1]
        res=metric(yte,pred,prob); results[name]=res; print(name,res)
        if res["f1"]>bestf: bestf=res["f1"]; best=(name,m)
    Path(args.outdir).mkdir(exist_ok=True)
    joblib.dump({"model":best[1],"features":features,"target":"delay_over_365d"},Path(args.outdir)/"model.joblib")
    (Path(args.outdir)/"metrics.json").write_text(json.dumps({"selected":best[0],"results":results},indent=2))
    print("[selected]",best[0])

if __name__=="__main__":
    main()
