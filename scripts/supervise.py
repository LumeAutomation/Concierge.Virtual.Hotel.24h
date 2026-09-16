"""Supervisor por usuario Windows: login, recuperacao e backup diario."""
import json
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import socket
import subprocess
import psutil
import sys
import time
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
config=Path(__file__).with_name('project.json')
if config.is_file():os.environ['AURA_PROJECT_ROOT']=json.loads(config.read_text(encoding='utf-8-sig'))['root']
import operations as ops

ROOT=ops.ROOT
PYTHON=Path(sys.executable).with_name('python.exe')
N8N=Path(os.environ['APPDATA'])/'npm/node_modules/n8n/bin/n8n'
NODE=Path(os.environ['ProgramFiles'])/'nodejs/node.exe'
DOCKER_DIR=Path(os.environ['LOCALAPPDATA'])/'Programs/DockerDesktop'
if not DOCKER_DIR.exists():DOCKER_DIR=Path(os.environ['ProgramFiles'])/'Docker/Docker'
DOCKER=DOCKER_DIR/'resources/bin/docker.exe'
N8N_ENV = {
    'DB_SQLITE_POOL_SIZE':'1',
    'N8N_CONCURRENCY_PRODUCTION_LIMIT':'1',
    'N8N_RUNNERS_MAX_CONCURRENCY':'1',
    'N8N_RUNNERS_MAX_OLD_SPACE_SIZE':'256',
    'N8N_RUNNERS_GRANT_TOKEN_TTL':'120',
    'N8N_DIAGNOSTICS_ENABLED':'false',
    'N8N_DISABLED_MODULES':'mcp-registry,community-packages',
    'N8N_VERSION_NOTIFICATIONS_ENABLED':'false',
}
children={}
last_attempt={}


def run(args,timeout=15,env=None):
    return subprocess.run([str(x) for x in args],capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW,env=env)


def listening(port):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=1):return True
    except OSError:return False


def already_starting(name):
    child=children.get(name)
    if child is not None and child.poll() is None:return True
    target=str(N8N).casefold() if name=='n8n' else 'app.py'
    expected='node.exe' if name=='n8n' else 'python.exe'
    for process in psutil.process_iter(['name']):
        if (process.info['name'] or '').lower()!=expected:continue
        try:
            command=process.cmdline()
            if name=='n8n' and any(target==arg.casefold() for arg in command):return True
            if name=='aura' and any(Path(arg).name.lower()=='app.py' for arg in command):return True
        except psutil.NoSuchProcess:continue
        # AccessDenied propagates: do not create a duplicate when ownership is unknown.
    return False



def start(name,port,args):
    if listening(port) or already_starting(name):return
    if time.monotonic()-last_attempt.get(name,-1000)<180:return
    last_attempt[name]=time.monotonic()
    log_dir=ops.LOCAL/'logs';log_dir.mkdir(parents=True,exist_ok=True)
    log=log_dir/(name+'.log')
    if log.exists() and log.stat().st_size>5_000_000:os.replace(log,log.with_suffix('.previous.log'))
    environment={**os.environ,**N8N_ENV} if name=='n8n' else os.environ.copy()
    if name=='n8n':
        environment['N8N_DISABLED_MODULES']=','.join(sorted(set(filter(None,(os.environ.get('N8N_DISABLED_MODULES','')+',mcp-registry,community-packages').split(',')))))
    with log.open('ab') as output:
        children[name]=subprocess.Popen([str(x) for x in args],cwd=ops.LOCAL,env=environment,stdout=output,stderr=output,creationflags=subprocess.CREATE_NO_WINDOW)


def ensure_waha():
    if listening(3000):return
    available=run([DOCKER,'info','--format','{{.ServerVersion}}'],timeout=8)
    if available.returncode:
        if time.monotonic()-last_attempt.get('docker',-1000)>600:
            last_attempt['docker']=time.monotonic()
            info=subprocess.STARTUPINFO();info.dwFlags|=subprocess.STARTF_USESHOWWINDOW;info.wShowWindow=0
            subprocess.Popen([str(DOCKER_DIR/'Docker Desktop.exe')],startupinfo=info,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return
    if time.monotonic()-last_attempt.get('waha',-1000)<180:return
    last_attempt['waha']=time.monotonic()
    response=run([DOCKER,'start','aura-waha'],timeout=25)
    if response.returncode:raise RuntimeError('waha_container_start')


def tick():
    errors=[]
    for name,action in [('aura',lambda:start('aura',8787,[PYTHON,ROOT/'app.py'])),('n8n',lambda:start('n8n',5678,[NODE,N8N,'start'])),('waha',ensure_waha)]:
        try:
            ops.write_json(ops.STATE,{'heartbeat':ops.now().isoformat(),'errors':errors,'pid':os.getpid(),'checking':name})
            action()
        except Exception as error:errors.append(name+':'+type(error).__name__)
    previous=ops.read_json(ops.BACKUP_STATE)
    try:due=(ops.now()-datetime.fromisoformat(previous['created_at'])).total_seconds()>=86400
    except (KeyError,ValueError,TypeError):due=True
    if due and time.monotonic()-last_attempt.get('backup',-1000)>300:
        last_attempt['backup']=time.monotonic()
        try:ops.write_json(ops.BACKUP_STATE,ops.backup())
        except Exception as error:
            ops.write_json(ops.BACKUP_STATE,{**previous,'status':'error','last_error':type(error).__name__})
            errors.append('backup:'+type(error).__name__)
    ops.write_json(ops.STATE,{'heartbeat':ops.now().isoformat(),'errors':errors,'pid':os.getpid()})


if __name__=='__main__':
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.restype=wintypes.HANDLE
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
    handle=kernel.CreateMutexW(None,False,'Local\\AURAConciergeSupervisor')
    if not handle:raise OSError('Mutex indisponivel')
    if ctypes.get_last_error()==183:sys.exit(0)
    try:
        while True:
            try:tick()
            except Exception:
                pass  # A proxima rodada tenta novamente; heartbeat velho fica visivel no painel.
            if '--once' in sys.argv:break
            time.sleep(30)
    finally:
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        kernel.CloseHandle(handle)
