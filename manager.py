from threading import Thread
import requests
import aiohttp
from aiohttp import FormData
from fastapi import FastAPI, Response, UploadFile
from fastapi.responses import RedirectResponse, JSONResponse
import time
import json
import tqdm
import datetime
import random
from io import BytesIO
from node_tools import timestamp
from secret import CDNS, CDNS_LABEL, API_KEY, DOWN_KEY, MAX_SIZE
ONLINECDNS = [] # 마지막 업데이트 주기에서 응답을 보낸 서버들.


FilesInfos = [] # 임시 리스트 - 작업 실행 시마다 비워짐
LatestFilesInfo = {} # 최신 파일 정보 - get route에서 체크, 노드로 전송됨
LastUpdate = -1
def getFilesInfoFromNode(url: str):
    try:
        res = requests.get(f"https://{url}/api/info?key={API_KEY}", timeout=5)
        data: dict = res.json()
        if data.__contains__("error"):
            raise Exception(f"error: {data['error']}")
        
        new_data = {}
        for k, v in data.items():
            new_data[k] = v
            new_data[k]["url"] = f"https://{url}/get/{k}?dkey={DOWN_KEY}"
            new_data[k]["node"] = CDNS_LABEL[url]
        FilesInfos.append(new_data)
    except:
        return
    ONLINECDNS.append(url)

def updateFilesToNode(): # 최대 len(CDNS)*5초 소요됨.
    if not LatestFilesInfo:
        return
    
    latestjson = json.dumps(LatestFilesInfo, ensure_ascii=False)
    print("[INFO] Sending updated file information to nodes..")
    for url in tqdm.tqdm(CDNS, leave=False):
        try:
            res = requests.post(f"https://{url}/api/update?key={API_KEY}", timeout=5, json=latestjson) # json 파일을 서버에 보낸다.
            res.raise_for_status()
        except:
            print(f"[WARNING] CDN `{CDNS_LABEL[url]}` passed.")
            ONLINECDNS.remove(url) if url in ONLINECDNS else None # 실패시 ONLINECDNS에 있으면 제거.
            
def _updateFiles():
    global LastUpdate
    FilesInfos.clear()
    ONLINECDNS.clear() # 기존 데이터 정리
    threads = []
    for c in CDNS:
        thr = Thread(target=getFilesInfoFromNode, args=(c,), daemon=True) # 노드에서 파일 정보 받기
        thr.start()
        threads.append(thr)
    print("[INFO] Collecting file information from nodes..")
    for t in threads:
        t.join()
    
    for d in FilesInfos: # 각 노드에서 보낸 파일 정보들
        for k, v in d.items():
            if not LatestFilesInfo.__contains__(k): # LatestFilesInfo에 포함되어 있지 않으면
                LatestFilesInfo[k] = v # 그대로 설정
                print(f"[UPDATE] {'ADD' if not v['deleted'] else 'DEL'} `{k}` URL = `{v['url']}` NODE = `{v['node']}` TS = `{v['lastedit']}`")
                continue
            
            if v["lastedit"] > LatestFilesInfo[k]["lastedit"]: # LatestFilesInfo보다 최신이라면
                LatestFilesInfo[k] = v # 수정
                print(f"[UPDATE] {'MOD' if not v['deleted'] else 'DEL'} `{k}` URL = `{v['url']}` NODE = `{v['node']}` TS = `{v['lastedit']}`")
                continue
            continue
    LastUpdate = datetime.datetime.now().timestamp()
    updateFilesToNode()
    
UPDATING = False

def updateFiles():
    global UPDATING
    
    max_waits = 3
    if UPDATING:
        while UPDATING and max_waits:
            time.sleep(1)
            max_waits -= 1
    else:
        UPDATING = True
        _updateFiles()
        UPDATING = False
        return True
    return False

def updateThread():
    global UPDATING
    print("[INFO] Update Thread Started.")
    while True:
        updateFiles()
        print("[INFO] Task complete.")
        time.sleep(180) # 3분

updateThr = Thread(target=updateThread, daemon=True)
updateThr.start()

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    exception_handlers={404: lambda req, exc: Response(content="Not Found.", status_code=404, media_type="text/plain")}
)

@app.get("/")
async def main():
    return Response(status_code=500)

@app.get("/get/{path:path}")
async def web_get(path, dkey: str = None):
    if not dkey or dkey != DOWN_KEY:
        return Response(status_code=400)
    if UPDATING:
        return JSONResponse(content={"status": "updating", "message": "현재 네트워크의 파일을 업데이트하고 있습니다. 잠시만 기다려주세요.."})
    if not ONLINECDNS:
        return JSONResponse(content={"status": "nodeoffline", "message": "현재 모든 노드가 접속 불가 상태입니다. 개발자에게 이 오류를 알려주세요."})
    if not LatestFilesInfo.__contains__(path):
        return JSONResponse(content={"status": "notfound", "message": "요청하신 파일이 없거나, 아직 동기화되지 않았습니다. 잠시만 기다려주세요."})
    return RedirectResponse(url=f"https://{random.choice(ONLINECDNS)}/get/{path}?dkey={DOWN_KEY}")

@app.post("/api/upload")
async def web_upload(file: UploadFile = None, key: str = None, filename: str = None):
    if not key or key != API_KEY or not filename or not file:
        return Response(status_code=204)
    if filename.find("/") == 0 or filename.find("..") != -1 or filename.find("\\") != -1:
        return Response(status_code=204)
    if file.size < 8:
        return JSONResponse({"status": "error", "message": "파일의 크기가 너무 작습니다."})
    if file.size > MAX_SIZE:
        return JSONResponse({"status": "error", "message": "파일이 너무 큽니다!"})
    

    async with aiohttp.ClientSession(conn_timeout=5) as session:
        formdata = FormData()
        formdata.add_field("file", BytesIO(await file.read()), filename="fake")
        selcdn = random.choice(ONLINECDNS)
        print(f"[UPL] ADD `{filename}` TO `{selcdn}`")
        res = await session.post(f"https://{selcdn}/api/upload?key={key}&filename={filename}", data=formdata)
        
        js = await res.json()
        js["uploaded"] = {"name": CDNS_LABEL[selcdn], "host": selcdn}
        while not updateFiles():
            time.sleep(1)
        js["affected"] = list(map(lambda c: CDNS_LABEL[c], ONLINECDNS))
        return JSONResponse(js, res.status)

@app.delete("/api/delete")
async def web_delete(key: str = None, filename: str = None, delkeys: str = None):
    print(delkeys)
    if not key or key != API_KEY:
        return Response(status_code=204)
    if filename.find("/") == 0 or filename.find("..") != -1 or filename.find("\\") != -1:
        return Response(status_code=204)
    updateFiles()
    
    async with aiohttp.ClientSession(conn_timeout=5) as session:
        selcdn = random.choice(ONLINECDNS)
        print(f"[DEL] DEL `{filename}` FROM `{selcdn}`")
        res = await session.delete(f"https://{selcdn}/api/delete?key={key}&filename={filename}")
        js = await res.json()
        js["node"] = CDNS_LABEL[selcdn]
        js["node_url"] = selcdn
        if js["status"] == "success":
            if delkeys:
                dk = await _api_deldeleted()
                js["DelKeyResponse"] = dk
            else:
                while not updateFiles():
                    time.sleep(1)
                
        return JSONResponse(js)

@app.get("/api/info")
async def api_fileinfo(key: str = None):
    if not key or key != API_KEY:
        return Response(status_code=204)
    
    lu = {}
    
    for k, v in LatestFilesInfo.items():
        vc = v.copy()
        del vc["url"]
        del vc["node"]
        lu[k] = vc
    return JSONResponse({"lastupdate": f"-{round(datetime.datetime.now().timestamp()-LastUpdate)}", "data": lu})

_delfail = {}
def senddeldict(url: str, filename: str):
    res = requests.delete(f"https://{url}/api/delete_key?key={API_KEY}&filename={filename}")
    js = res.json()
    if js["status"] == "success":
        print(f"[DELK] SUC `{CDNS_LABEL[url]}` FN = `{filename}`")
    else:
        print(f"[DELK] FAL `{CDNS_LABEL[url]}` FN = `{filename}` RES = `{js['message']}`")
        _delfail[CDNS_LABEL[url]].append(filename)

def cleardeleted():
    global UPDATING
    updateFiles()
    _delfail.clear()
    for n in CDNS:
        _delfail[CDNS_LABEL[n]] = []

    dels = []
    for k, v in LatestFilesInfo.items():
        if v["deleted"]:
            dels.append(k)
    UPDATING = True
    try:
        for node in CDNS:
            for d in dels:
                senddeldict(node, d)
    except:
        UPDATING = False
        return
    UPDATING = False
    _ds = _delfail.copy()
    _delfail.clear()
    return dels, _ds
        
@app.delete("/api/cleardeleted")
async def api_deldeleted(key: str = None, raw: bool = None):
    if not key or key != API_KEY:
        return Response(status_code=204)
    dels = cleardeleted()
    LatestFilesInfo.clear()
    updateFiles()
    if not raw:
        return JSONResponse({"status": "completed", "requested": dels[0], "failed": dels[1]})
    else:
        return {"status": "completed", "requested": dels[0], "failed": dels[1]}

async def _api_deldeleted():
    dels = cleardeleted()
    LatestFilesInfo.clear()
    updateFiles()
    return {"status": "completed", "requested": dels[0], "failed": dels[1]}
        