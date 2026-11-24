"""Human-readable assistant result table; raw API evidence stays unchanged."""
def assistant_frame(result):
    import pandas as pd
    frame=pd.DataFrame(result["rows"])
    plan=result["plan"]
    metric=plan["metric"]
    groups={"customer":"Customer ID","region":"Region","category":"Category","status":"Status","date":"Date","product":"Product ID","event_type":"Event type"}
    names={"gross_cents":"Gross order value ($)","paid_cents":"Paid order value ($)","amount_cents":"Payment value ($)"}
    if "value" in frame and metric in names:
        frame["value"]=frame["value"]/100
    return frame.rename(columns={"label":groups.get(plan["group"],"Group"),"value":names.get(metric,metric.capitalize()),"check":"Check","passed":"Passed","severity":"Severity"})
