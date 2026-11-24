"""Manage only project-owned local processes; never kill unknown port owners."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/"data"/"services"
COMPOSE=["docker","compose","-f","compose.yaml","-f","compose.kafka.yaml","-f","compose.monitoring.yaml"]
SERVICES={
    "ollama":(11434,"/api/tags",["ollama","serve"]),
    "api":(8000,"/health",[sys.executable,"-m","uvicorn","ecommerce.api:app","--host","127.0.0.1","--port","8000"]),
    "dashboard":(8501,"/_stcore/health",[sys.executable,"-m","streamlit","run","dashboard/app.py","--server.address","127.0.0.1","--server.port","8501"]),
    "dagster":(3000,"/",[sys.executable,"-m","dagster","dev","-m","ecommerce.orchestration","-h","127.0.0.1","-p","3000"]),
}

def listening(port):
    with socket.socket() as s:
        s.settimeout(.3)
        return s.connect_ex(("127.0.0.1",port))==0

def healthy(port,path):
    try:
        with urlopen(f"http://127.0.0.1:{port}{path}",timeout=2) as response:
            return response.status==200
    except OSError:
        return False

def identity(pid):
    result=subprocess.run(["ps","-p",str(pid),"-o","lstart=","-o","command="],capture_output=True,text=True)
    return result.stdout.strip() if result.returncode==0 else ""

def owned(name):
    try:
        data=json.loads((STATE/(name+".json")).read_text())
        if data["identity"] and identity(data["pid"])==data["identity"] and os.getpgid(data["pid"])==data["pid"]:
            return data["pid"]
    except (OSError,ValueError,KeyError,TypeError):
        pass
    return None

def start(name):
    port,path,cmd=SERVICES[name]
    if listening(port):
        if not healthy(port,path):
            raise RuntimeError(f"{name}: port {port} occupied but health check failed; inspect manually")
        print(f"{name}: already reachable ({'managed' if owned(name) else 'external; not adopted'})")
        return
    if owned(name):
        raise RuntimeError(f"{name}: managed process exists but port not ready; inspect logs")
    STATE.mkdir(parents=True,exist_ok=True)
    (ROOT/"data"/"dagster").mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,DAGSTER_HOME=str(ROOT/"data"/"dagster"))
    env.setdefault("OLLAMA_NUM_PARALLEL","1")
    env.setdefault("OLLAMA_MAX_LOADED_MODELS","1")
    with (STATE/(name+".log")).open("ab") as log:
        p=subprocess.Popen(cmd,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    (STATE/(name+".json")).write_text(json.dumps({"pid":p.pid,"identity":identity(p.pid)}))
    for _ in range(60):
        if p.poll() is not None:
            raise RuntimeError(f"{name} exited; inspect data/services/{name}.log")
        if healthy(port,path):
            print(f"{name}: ready on {port}")
            return
        time.sleep(1)
    raise RuntimeError(f"{name}: health timeout; inspect data/services/{name}.log")

def stop(name):
    pid=owned(name)
    if pid is None:
        print(f"{name}: no verified managed process; external services left untouched")
        return
    os.killpg(pid,signal.SIGTERM)
    for _ in range(30):
        if not owned(name):
            (STATE/(name+".json")).unlink(missing_ok=True)
            print(f"{name}: stopped")
            return
        time.sleep(.5)
    raise RuntimeError(f"{name}: still running; inspect manually (no forced kill)")

def compose(*args):
    subprocess.run([*COMPOSE,*args],cwd=ROOT,check=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=("start","stop","restart","status"))
    p.add_argument("service",nargs="?",choices=(*SERVICES,"app","infra","all"),default="app")
    a=p.parse_args()
    names=list(SERVICES) if a.service=="all" else ["ollama","api","dashboard"] if a.service=="app" else [] if a.service=="infra" else [a.service]
    infra=a.service in ("infra","all")
    if a.action=="status":
        for name in names:
            port,path,_=SERVICES[name]
            print(f"{name:12} {port:5} {'healthy' if healthy(port,path) else 'unhealthy' if listening(port) else 'stopped'} {'managed' if owned(name) else 'external or idle'}")
        if infra: compose("ps")
        return
    if a.action in ("stop","restart"):
        for name in reversed(names): stop(name)
        if infra: compose("stop")
    if a.action in ("start","restart"):
        if infra:
            (ROOT/"data"/"observability"/"metrics").mkdir(parents=True,exist_ok=True)
            compose("up","-d","--wait")
        for name in names: start(name)

if __name__=="__main__":
    main()
