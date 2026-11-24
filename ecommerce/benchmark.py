"""Read-only HTTP latency, pipeline history and isolated synthetic SQL scaling."""
import argparse
import json
import math
import platform
import statistics
import tempfile
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from ecommerce.relational import generate_batch,validate

ROOT=Path(__file__).resolve().parents[1]
def summarize(samples):
    ordered=sorted(samples)
    return {"samples":len(ordered),"mean_ms":round(statistics.mean(ordered),3),
            "p50_ms":round(ordered[math.ceil(len(ordered)*.5)-1],3),
            "p95_ms":round(ordered[math.ceil(len(ordered)*.95)-1],3),
            "max_ms":round(ordered[-1],3)} if ordered else {"samples":0}

def http_benchmark(count,workers,ai):
    import httpx
    base="http://127.0.0.1:8000"
    report={}
    with httpx.Client(timeout=135) as client:
        baseline=client.get(base+"/api/kpis")
        baseline.raise_for_status()
        expected=baseline.json()
        report["snapshot_kpis"]=expected
        for path in ("/health","/api/kpis","/api/sales","/api/customers","/api/events"):
            def run(_):
                start=time.perf_counter()
                try:
                    response=client.get(base+path)
                    return (time.perf_counter()-start)*1000,response.status_code
                except httpx.HTTPError:
                    return (time.perf_counter()-start)*1000,0
            client.get(base+path).raise_for_status()
            start=time.perf_counter()
            with ThreadPoolExecutor(max_workers=workers) as pool:
                outcomes=list(pool.map(run,range(count)))
            elapsed=time.perf_counter()-start
            ok=[ms for ms,status in outcomes if status==200]
            report[path]={**summarize(ok),"attempts":count,"errors":count-len(ok),"workers":workers,"successful_requests_per_second":round(len(ok)/elapsed,2)}
        if ai:
            cases=[("How many total orders do we have?","orders","llm"),("How many unique customers do we have?","customers","rule")]
            for question,key,route in cases:
                samples=[]; errors=0; correct=0
                for _ in range(ai):
                    start=time.perf_counter()
                    try:
                        res=client.post(base+"/api/assistant",json={"question":question,"provider":"ollama"})
                        res.raise_for_status()
                        rows=res.json()["rows"]
                        samples.append((time.perf_counter()-start)*1000)
                        correct+=int(len(rows)==1 and rows[0].get("value")==expected[key])
                    except (httpx.HTTPError,ValueError,KeyError,TypeError):
                        errors+=1
                report["ai_"+key]={**summarize(samples),"attempts":ai,"errors":errors,"correct":correct,"expected":expected[key],"route":route}
    return report

def pipeline_history():
    path=ROOT/"data"/"observability"/"pipeline.jsonl"
    grouped={}
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                row=json.loads(line)
                grouped.setdefault(row["stage"],[]).append(row)
            except (ValueError,KeyError):
                continue
    return {stage:{"attempts":len(rows),"failures":sum(not x["success"] for x in rows),
                   "latest":rows[-1],**summarize([x["duration_seconds"]*1000 for x in rows if x["success"]])}
            for stage,rows in grouped.items()}

def scale(sizes):
    import duckdb
    results=[]
    for n in sizes:
        start=time.perf_counter()
        batch=generate_batch(1,n)
        generated=time.perf_counter()-start
        start=time.perf_counter()
        validate(batch)
        validated=time.perf_counter()-start
        expected=sum(r[4] for r in batch["orders"])
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"scale.duckdb"
            with duckdb.connect(str(path),config={"threads":2,"memory_limit":"512MB"}) as c:
                c.execute("CREATE TABLE orders(order_id BIGINT,customer_id INTEGER,ordered_at TIMESTAMPTZ,status VARCHAR,total_cents BIGINT)")
                start=time.perf_counter()
                # Bulk columnar ingestion; no per-row autocommit or production writes.
                import pandas as pd
                frame=pd.DataFrame(batch["orders"],columns=["order_id","customer_id","ordered_at","status","total_cents"])
                c.register("incoming",frame)
                c.execute("INSERT INTO orders SELECT * FROM incoming")
                c.unregister("incoming")
                c.execute("CHECKPOINT")
                loaded=time.perf_counter()-start
                start=time.perf_counter()
                actual=c.execute("SELECT count(*),sum(total_cents) FROM orders").fetchone()
                queried=time.perf_counter()-start
                if actual!=(n,expected):
                    raise AssertionError("Scaling totals do not reconcile")
                results.append({"orders":n,"order_lines":len(batch["order_items"]),"generate_seconds":generated,"validate_seconds":validated,"load_seconds":loaded,"aggregate_seconds":queried,"gross_cents":expected,"file_bytes":path.stat().st_size,"validated":True})
        del batch,frame
    return results

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=("http","pipeline","scale"))
    p.add_argument("--requests",type=int,default=20)
    p.add_argument("--workers",type=int,default=2)
    p.add_argument("--ai",type=int,default=0)
    p.add_argument("--sizes",type=int,nargs="+",default=[1500,10000,50000])
    a=p.parse_args()
    if not 1<=a.requests<=500 or not 1<=a.workers<=4 or not 0<=a.ai<=10 or any(not 1<=n<=100000 for n in a.sizes):
        p.error("requests 1–500, workers 1–4, AI 0–10, sizes 1–100000")
    report={"mode":a.mode,"platform":platform.platform(),"timestamp":time.time()}
    report["results"]=http_benchmark(a.requests,a.workers,a.ai) if a.mode=="http" else pipeline_history() if a.mode=="pipeline" else scale(a.sizes)
    out=ROOT/"data"/"benchmarks"
    out.mkdir(parents=True,exist_ok=True)
    target=out/f"{a.mode}-{time.time_ns()}.json"
    target.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    print(f"Saved: {target}")

if __name__=="__main__":
    main()
