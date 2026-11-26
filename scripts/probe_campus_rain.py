"""Bounded, read-only diagnostics of public campus rainfall/quality telemetry."""
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from observatorio.campus_station import request_json, PUBLIC_ID, TELEMETRY, DASHBOARD_CONFIG, SourceError

def main():
    auth=request_json("/api/auth/login/public",body={"publicId":PUBLIC_ID})
    token=auth.get("token")
    if not isinstance(token,str) or not token: raise SourceError("invalid_public_session")
    keys=["rain_total","rain_increment","rain_daily","rain_event","rain_suspects_total","rain_rate_instant","temperature","humidity","pressure","humidity_valid","bme_cal_ok","bme_stale","bme_consec_fails","dew_point","dew_point_valid","thermal_sensation","thermal_sensation_valid","wind_std","wind_min"]
    now=datetime.now(timezone.utc)
    end=int(now.timestamp()//300*300*1000)
    def query(fields, hours, agg, limit=300):
        return request_json(TELEMETRY+"?"+urlencode({"keys":",".join(fields),"startTs":end-hours*3600000,"endTs":end,"agg":agg,"limit":limit,"interval":300000,"orderBy":"DESC"}),token=token)
    try:
        config=request_json(DASHBOARD_CONFIG,token=token)
        for widget in config.get("configuration",{}).get("widgets",{}).values():
            for source in widget.get("config",{}).get("datasources",[]):
                for field in source.get("dataKeys",[]):
                    if field.get("name") in keys:
                        print("FIELD",field.get("name"),{k:field[k] for k in ("label","units","decimals") if k in field and isinstance(field[k],(str,int,float))})
    except (SourceError,ValueError,TypeError,AttributeError):
        print("Widget metadata unavailable")
    raw=query(keys,6,"NONE")
    for key in keys:
        rows=sorted(raw.get(key,[]),key=lambda r:r["ts"])
        delta=Counter(round((b["ts"]-a["ts"])/1000,1) for a,b in zip(rows,rows[1:]))
        values=Counter(str(r["value"]) for r in rows)
        print("RAW",key,"n",len(rows),"cadence",delta.most_common(4),"first",rows[:2],"last",rows[-4:],"frequent",values.most_common(4))
    for agg,fields in [("MAX",["rain_total","rain_daily","rain_suspects_total"]),("MIN",["rain_total","rain_suspects_total"]),("SUM",["rain_increment"]),("COUNT",["rain_increment","rain_total","rain_suspects_total"])]:
        data=query(fields,6,agg,74)
        for key,points in data.items():
            rows=sorted(points,key=lambda r:r["ts"])
            try: v=[float(r["value"]) for r in rows]; changes=[(r["ts"],round(b-a,5)) for r,a,b in zip(rows[1:],v,v[1:]) if b!=a]
            except (ValueError,TypeError): continue
            print("AGG",agg,key,"n",len(rows),"range",(min(v),max(v)) if v else None,"first",rows[:2],"last",rows[-3:],"changes",changes[-15:],"sum",round(sum(v),5) if agg=="SUM" else None)
    return 0

if __name__=="__main__":
    try: raise SystemExit(main())
    except (SourceError,OSError,ValueError,TypeError,KeyError) as exc:
        print("Campus diagnostic unavailable:",type(exc).__name__)
        raise SystemExit(0)
