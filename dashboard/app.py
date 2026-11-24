"""Streamlit client for the local analytics API."""
import os
import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="E-Commerce Intelligence",page_icon="📊",layout="wide")
API=os.getenv("ANALYTICS_API_URL","http://127.0.0.1:8000")
def get(endpoint,params=None,raw=False):
    try:
        response=httpx.get(API+endpoint,params=params,timeout=20)
        response.raise_for_status()
        return response.content if raw else response.json()
    except httpx.HTTPError as exc:
        st.error(f"Analytics service unavailable: {exc}")
        st.stop()

def dollars(cents):
    return f"${cents/100:,.2f}"

def chart(data,label,title):
    frame=pd.DataFrame(data)
    if frame.empty:
        st.info("No matching sales records.")
        return
    frame["Gross USD"]=frame.gross_cents/100
    frame["Paid USD"]=frame.paid_cents/100
    fig=px.bar(frame,x="label",y=["Gross USD","Paid USD"],barmode="group",labels={"label":label,"value":"USD","variable":"Value"},title=title,color_discrete_sequence=["#64748b","#0d9488"])
    fig.update_layout(legend_title_text="",margin=dict(l=10,r=10,t=45,b=10))
    st.plotly_chart(fig,use_container_width=True)

st.title("E-Commerce Intelligence")
st.caption("Local lakehouse • Synthetic commerce data • Read-only analytics")
opts=get("/api/filters")
q=get("/api/quality")
latest=q.get("latest")
if latest is None:
    st.warning("Latest pipeline quality status unavailable.")
elif latest["success"]:
    st.success("Latest quality gate passed · "+str(sum(x["passed"] for x in latest["checks"]))+" checks passed")
else:
    st.warning("Latest quality gate failed. Showing the last published, validated snapshot.")
st.sidebar.header("Sales filters")
params={}
if opts["start"] and opts["end"]:
    from datetime import date
    bounds=(date.fromisoformat(opts["start"]),date.fromisoformat(opts["end"]))
    selection=st.sidebar.date_input("Order dates",value=bounds,min_value=bounds[0],max_value=bounds[1])
    if len(selection)!=2:
        st.info("Select both date boundaries.")
        st.stop()
    params.update(start=str(selection[0]),end=str(selection[1]))
for name,key in (("Region","regions"),("Category","categories"),("Status","statuses")):
    value=st.sidebar.selectbox(name,["All"]+opts[key])
    if value!="All":
        params[name.lower()]=value
k=get("/api/kpis",params)
for col,label,value in zip(st.columns(5),["Gross order value","Paid order value","Orders","Purchasing customers*","Units"],[dollars(k["gross_cents"]),dollars(k["paid_cents"]),f'{k["orders"]:,}',f'{k["customers"]:,}',f'{k["units"]:,}']):
    col.metric(label,value)
st.caption("*Customers with matching order lines, including unpaid/cancelled orders. Gross includes all statuses; paid includes paid/shipped before returns. Category filters select line values, not whole-order totals.")
sales_tab,customer_tab,event_tab,health_tab=st.tabs(["Sales","Customers & payments","Streaming events","Data health"])
with sales_tab:
    left,right=st.columns(2)
    with left:
        chart(get("/api/sales",{**params,"group":"region"}),"Region","Regional sales")
    with right:
        chart(get("/api/sales",{**params,"group":"category"}),"Category","Product categories")
    chart(get("/api/sales",{**params,"group":"date"}),"Order date","Daily sales")
    statuses=pd.DataFrame(get("/api/sales",{**params,"group":"status"}))
    if not statuses.empty:
        st.plotly_chart(px.pie(statuses,names="label",values="orders",hole=.5,title="Order status"),use_container_width=True)
    group=st.selectbox("Export breakdown",["region","category","status","date","product"])
    st.download_button("Download filtered sales CSV",get("/api/export/sales.csv",{**params,"group":group},True),"sales.csv","text/csv")
with customer_tab:
    st.subheader("Top customers by paid value")
    customers=pd.DataFrame(get("/api/customers",params))
    if not customers.empty:
        customers["paid_usd"]=customers.paid_cents/100
        st.dataframe(customers,use_container_width=True,hide_index=True)
    st.subheader("All-time payments (unfiltered)")
    p=get("/api/payments")
    a,b=st.columns(2)
    a.metric("Payments",p["payments"])
    b.metric("Payment value",dollars(p["amount_cents"]))
with event_tab:
    st.caption("Independent clickstream data; sales filters do not apply.")
    from datetime import date
    event_dates=st.date_input("Event dates (optional)",value=(),key="event_dates")
    ep={}
    if len(event_dates)==2:
        ep=dict(start=str(event_dates[0]),end=str(event_dates[1]))
    e=get("/api/events",ep)
    a,b=st.columns(2)
    a.metric("Events",e["summary"]["events"])
    b.metric("Distinct sessions",e["summary"]["sessions"])
    if e["types"]:
        st.plotly_chart(px.bar(pd.DataFrame(e["types"]),x="event_type",y="events",color_discrete_sequence=["#0d9488"]),use_container_width=True)
        st.plotly_chart(px.line(pd.DataFrame(e["timeline"]),x="window",y="events",markers=True,title="Five-minute event windows"),use_container_width=True)
    else:
        st.info("No matching events.")
    st.caption("Purchase events are synthetic and not linked to batch orders; event counts are not conversion rates.")
with health_tab:
    st.subheader("Published snapshot quality")
    st.dataframe(pd.DataFrame(q["published"]["checks"]),hide_index=True,use_container_width=True)
    if latest:
        st.subheader("Latest quality report")
        st.dataframe(pd.DataFrame(latest["checks"]),hide_index=True,use_container_width=True)
    st.write("Operational tools: [Dagster](http://localhost:3000) · [Grafana](http://localhost:3001) · [Prometheus](http://localhost:9090) · [API docs](http://localhost:8000/docs)")
