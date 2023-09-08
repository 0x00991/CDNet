from threading import Thread
import requests
from fastapi import FastAPI, Response
from fastapi.responses import RedirectResponse, JSONResponse
import time
import json
import tqdm
import random
from secret import CDNS, API_KEY, DOWN_KEY
ONLINECDNS = [] # 마지막 업데이트 주기에서 응답을 보낸 서버들.


FilesInfos = [] # 임시 리스트 - 작업 실행 시마다 비워짐
LatestFilesInfo = {} # 최신 파일 정보 - get route에서 체크, 노드로 전송됨

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
            print(f"[WARNING] CDN `{url}` passed.")
            ONLINECDNS.remove(url) if url in ONLINECDNS else None # 실패시 ONLINECDNS에 있으면 제거.
            
def updateFiles():
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
                print(f"[UPDATE] {'ADD' if not v['deleted'] else 'DEL'} `{k}` URL = `{v['url']}` TS = `{v['lastedit']}`")
                continue
            
            if v["lastedit"] > LatestFilesInfo[k]["lastedit"]: # LatestFilesInfo보다 최신이라면
                LatestFilesInfo[k] = v # 수정
                print(f"[UPDATE] {'MOD' if not v['deleted'] else 'DEL'} `{k}` URL = `{v['url']}` TS = `{v['lastedit']}`")
                continue
            continue
    updateFilesToNode()

UPDATING = False
def updateThread():
    global UPDATING
    print("[INFO] Update Thread Started.")
    while True:
        UPDATING = True
        updateFiles()
        print("[INFO] Task complete.")
        UPDATING = False
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