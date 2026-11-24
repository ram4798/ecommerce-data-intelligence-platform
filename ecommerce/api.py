"""Read-only business intelligence endpoints; money is expressed in integer cents."""
import csv
import io
import json
from datetime import date
from typing import Literal
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from ecommerce.serving import serving_path
from ecommerce.observability import directory

app = FastAPI(title="E-Commerce Intelligence API", version="1.0.0", description="Synthetic data. Gross order value includes all statuses; paid value is before returns.")

def connection():
    import duckdb
    try:
        con = duckdb.connect(str(serving_path()), read_only=True, config={"threads":2,"memory_limit":"1GB"})
    except duckdb.Error as exc:
        raise HTTPException(503, "Serving snapshot unavailable; publish after a successful quality run.") from exc
    try:
        yield con
    finally:
        con.close()

def rows(con, sql, params=()):
    result = con.execute(sql, list(params))
    names = [x[0] for x in result.description]
    return [dict(zip(names, row)) for row in result.fetchall()]

def filters(start: date | None = None, end: date | None = None,
            region: str | None = Query(None, max_length=100),
            category: str | None = Query(None, max_length=100),
            status: Literal["placed","paid","shipped","cancelled"] | None = None):
    if start and end and start > end:
        raise HTTPException(422, "start must not be after end")
    clauses, params = [], []
    for field, op, value in (("s.order_date",">=",start),("s.order_date","<=",end),("c.region","=",region),("p.category","=",category),("s.status","=",status)):
        if value is not None:
            clauses.append(f"{field} {op} ?")
            params.append(value)
    return (" WHERE " + " AND ".join(clauses) if clauses else "", params)

BASE = " FROM analytics.fct_sales s JOIN analytics.dim_customers c USING(customer_id) JOIN analytics.dim_products p USING(product_id)"
AGG = "count(distinct s.order_id) AS orders, coalesce(sum(s.line_value_cents),0) AS gross_cents, coalesce(sum(s.paid_value_cents),0) AS paid_cents"
GROUPS = {"region":"c.region","category":"p.category","status":"s.status","date":"s.order_date","product":"s.product_id"}

@app.get("/health")
def health(con=Depends(connection)):
    return {"status":"ok","published_at":con.execute("SELECT published_at FROM analytics.publication").fetchone()[0]}

@app.get("/api/quality")
def quality(con=Depends(connection)):
    published = json.loads(con.execute("SELECT quality_report FROM analytics.publication").fetchone()[0])
    try:
        latest = json.loads((directory() / "quality_report.json").read_text())
    except (OSError, ValueError):
        latest = None
    return {"published":published,"latest":latest}

@app.get("/api/filters")
def options(con=Depends(connection)):
    bounds = con.execute("SELECT min(order_date),max(order_date) FROM analytics.fct_sales").fetchone()
    return {"regions":[x[0] for x in con.execute("SELECT DISTINCT region FROM analytics.dim_customers ORDER BY 1").fetchall()],
            "categories":[x[0] for x in con.execute("SELECT DISTINCT category FROM analytics.dim_products ORDER BY 1").fetchall()],
            "statuses":["placed","paid","shipped","cancelled"],"start":bounds[0],"end":bounds[1]}

@app.get("/api/kpis")
def kpis(f=Depends(filters), con=Depends(connection)):
    where, params = f
    return rows(con, "SELECT "+AGG+", count(distinct s.customer_id) AS customers, coalesce(sum(s.quantity),0) AS units"+BASE+where, params)[0]

def breakdown(con, f, group):
    where, params = f
    column = GROUPS[group]
    return rows(con, f"SELECT {column} AS label, "+AGG+BASE+where+" GROUP BY 1 ORDER BY 1",params)

@app.get("/api/sales")
def sales(group: Literal["region","category","status","date","product"]="region", f=Depends(filters), con=Depends(connection)):
    return breakdown(con,f,group)

@app.get("/api/customers")
def customers(limit: int=Query(10,ge=1,le=100), f=Depends(filters), con=Depends(connection)):
    where, params = f
    return rows(con,"SELECT s.customer_id, c.region, "+AGG+BASE+where+" GROUP BY 1,2 ORDER BY paid_cents DESC, customer_id LIMIT ?",[*params,limit])

@app.get("/api/payments")
def payments(con=Depends(connection)):
    return rows(con,"SELECT count(*) AS payments, coalesce(sum(amount_cents),0) AS amount_cents FROM analytics.fct_payments")[0]

@app.get("/api/events")
def events(start: date | None=None, end: date | None=None, con=Depends(connection)):
    if start and end and start>end:
        raise HTTPException(422,"start must not be after end")
    clauses, params = [], []
    for op,value in ((">=",start),("<=",end)):
        if value is not None:
            clauses.append(f"cast(event_time as date) {op} ?")
            params.append(value)
    where=" WHERE "+" AND ".join(clauses) if clauses else ""
    base=" FROM analytics.fct_events"+where
    return {"summary":rows(con,"SELECT count(*) AS events,count(distinct session_id) AS sessions"+base,params)[0],
            "types":rows(con,"SELECT event_type,count(*) AS events"+base+" GROUP BY 1 ORDER BY 1",params),
            "timeline":rows(con,"SELECT time_bucket(INTERVAL '5 minutes',event_time) AS window,count(*) AS events"+base+" GROUP BY 1 ORDER BY 1",params)}

@app.get("/api/export/sales.csv")
def export_sales(group: Literal["region","category","status","date","product"]="region", f=Depends(filters), con=Depends(connection)):
    buf=io.StringIO()
    writer=csv.DictWriter(buf,fieldnames=["label","orders","gross_cents","paid_cents"])
    writer.writeheader()
    writer.writerows(breakdown(con,f,group))
    return StreamingResponse(iter([buf.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=sales.csv"})

# The model selects a typed plan; the server alone constructs SQL.
from ecommerce.assistant import Ask, propose, answer, context_for
import httpx
from threading import BoundedSemaphore
assistant_slot=BoundedSemaphore(1)

@app.post("/api/assistant")
def ask_assistant(request: Ask, con=Depends(connection)):
    if not assistant_slot.acquire(blocking=False):
        raise HTTPException(429,"An analytics question is already running")
    try:
        context=context_for(con)
        plan=propose(request.question,request.provider,context)
        return answer(con,plan,context)
    except httpx.HTTPError as exc:
        raise HTTPException(503,"Model service unavailable or timed out") from exc
    except (ValueError,KeyError,TypeError) as exc:
        raise HTTPException(422,"Model returned an invalid or unsupported query plan; rephrase the question") from exc
    finally:
        assistant_slot.release()
