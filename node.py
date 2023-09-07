from fastapi import FastAPI, Response, Request, UploadFile
from fastapi.responses import JSONResponse, FileResponse
import aiofiles
import aiohttp
from secret import MAX_SIZE, API_KEY
import asyncio
import pickle
from os.path import isfile, isdir
import os
from node_tools import Holder as _Holder
from node_tools import ROOT_DIR, FILES_DIR, FILEDATA_PATH, File, CHUNK_SIZE, EXTS, timestamp
import secrets
import shutil
import json
Holder = _Holder()
DataFileHolder = _Holder()

if not isdir(ROOT_DIR): os.mkdir(ROOT_DIR)
if not isdir(FILES_DIR): os.mkdir(FILES_DIR)
if not isdir(FILES_DIR+"/temp"): os.mkdir(FILES_DIR+"/temp")
if not isdir(ROOT_DIR+"/bak"): os.mkdir(ROOT_DIR+"/bak")
if not isfile(FILEDATA_PATH):
    with open(FILEDATA_PATH, "wb") as f:
        f.write( pickle.dumps( {} ) )# empty dict

with open(FILEDATA_PATH, "rb") as f:
    _filedata = pickle.load(f)
    FILEDATA: dict[str, File] = dict()
    for fn, val in _filedata.items():
        f = File(fn, val["lastedit"], val["deleted"])
        FILEDATA[fn] = f
    del _filedata
        
    
    
if not isinstance(FILEDATA, dict):
    raise Exception(f"FILEDATA is not DICT. (type: {type(FILEDATA)})")

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    exception_handlers={404: lambda req, exc: Response(content="Not Found.", status_code=404, media_type="text/plain")},
)

@app.get("/api/info")
async def api_fileinfo(key: str = None):
    if not key or key != API_KEY:
        return Response(status_code=204)
    if Holder.is_holding():
        return JSONResponse({"error": "현재 파일 정보 업데이트 중입니다."})
    returnjson = {}
    for fd in FILEDATA.values():
        returnjson[fd.name()] = {"lastedit": fd.lastedit(), "deleted": fd.deleted()}
    return JSONResponse(returnjson)

@app.post("/api/update")
async def api_fileupdate(request: Request, key: str = None):
    if not key or key != API_KEY:
        return Response(status_code=204)
    
    body: dict = await request.json()
    
    if type(body) == str:
        body = json.loads(body)
    for k, v in body.items():
        UPDATE_QUEUE.append(
            {
                "name": k,
                "lastedit": v["lastedit"],
                "url": v["url"],
                "deleted": v["deleted"]
            }
        )
    return JSONResponse(content=body, status_code=201)

@app.delete("/api/delete")
async def api_filedelete(key: str = None, filename: str = None):
    if not key or key != API_KEY:
        return Response(status_code=204)
    if not FILEDATA.__contains__(filename):
        return JSONResponse({"status": "error", "message": "존재하지 않는 파일입니다."})
    if FILEDATA[filename].deleted():
        return JSONResponse({"status": "error", "message": "이미 삭제된 파일입니다."})
    FILEDATA[filename].deleted(True)
    FILEDATA[filename].lastedit(timestamp())
    os.remove(FILES_DIR+"/"+filename)
    await writedata()
    return JSONResponse({"status": "success", "message": "요청하신 파일이 삭제되었습니다."})

@app.post("/api/upload")
async def api_fileupload(file: UploadFile = None, key: str = None, filename: str = None):
    if not key or key != API_KEY or not filename or not file:
        return Response(status_code=204)
    if filename.find("/") == 0 or filename.find("..") != -1 or filename.find("\\") != -1:
        return Response(status_code=204)
    if file.size < 8:
        return JSONResponse({"status": "error", "message": "파일의 크기가 너무 작습니다."})
    if file.size > MAX_SIZE:
        return JSONResponse({"status": "error", "message": "파일이 너무 큽니다!"})
    await Holder.wait()
    Holder.hold()
    tempname = secrets.token_hex(16)
    
    loaded = None
    async with aiofiles.open(FILES_DIR+"/temp/"+tempname, "wb") as f:
        loaded = "pass"
        while loaded:
            Holder.hold()
            loaded = await file.read(CHUNK_SIZE)
            if loaded:
                await f.write(loaded)
    if FILEDATA.__contains__(filename):
        FILEDATA[filename].lastedit(timestamp())
        FILEDATA[filename].deleted(False)
        file_obj = FILEDATA[filename]
    else:
        file_obj = File(filename, timestamp(), False)
        FILEDATA[filename] = file_obj
    await writedata()
    
    if file_obj.exists():
        os.remove(FILES_DIR+"/"+filename)
    shutil.move(FILES_DIR+"/temp/"+tempname, FILES_DIR+"/"+filename)
    Holder.unhold()
    
@app.get("/get/{path:path}")
async def file_get(path):
    if path.find("..") != -1 or path.find("./") != -1 or path.find("\\") != -1:
        return Response(status_code=400)
    if not FILEDATA.__contains__(path) or FILEDATA[path].deleted():
        return JSONResponse({"status": "error", "message": "파일이 없거나 삭제되었습니다."})
    if isfile(FILES_DIR+"/"+path):
        return FileResponse(path=f"{FILES_DIR}/{path}", media_type=EXTS.get(path.split("/")[-1].split(".")[-1], "application/octet-stream"))
    
    
UPDATE_QUEUE = [] # ele: {"name": "filename", "lastedit": timestamp, "url": "URL", "deleted": False}

async def writedata():
    wrtdict = {}
    for data in FILEDATA.values(): # FILEDATA의 value loop
        wrtdict[data.name()] = {"lastedit": data.lastedit(), "deleted": data.deleted()} # dict에 저장

    print("[WARNING] 파일 정보를 저장하고 있습니다. 서버를 종료하지 마세요!!")
    await DataFileHolder.wait()
    DataFileHolder.hold()
    bakn = secrets.token_hex(16)
    shutil.copy(FILEDATA_PATH, ROOT_DIR+"/bak/"+bakn)
    async with aiofiles.open(FILEDATA_PATH, "wb") as f:
        await f.write(pickle.dumps(wrtdict))
    DataFileHolder.unhold()
    print(f"[INFO] 파일 정보 저장 완료. (이전 파일 백업: bak/{bakn})")
    

async def _task():
    await Holder.wait() # hold가 풀릴 때까지 대기
    if UPDATE_QUEUE: print("[WARNING] 파일 동기화 작업이 시작되었습니다. 서버를 종료하지 마세요.") # 업데이트 큐에 아이템이 있다면 출력
    for fd in UPDATE_QUEUE.copy(): # 업데이트 큐에 들어간 모든 아이템 루프
        Holder.hold() # 홀드를 걸어 파일과 dict 접근을 막는다.
        _update = False # _update가 True일 시 작업 시작
        if not FILEDATA.__contains__(fd["name"]): # 해당 파일이 저장 되어 있지 않다면 업데이트 True
            _update = True
        else:
            file = FILEDATA[fd["name"]] # 파일 클래스를 얻는다.
            if file.exists(): # 파일이 존재한다면
                if file.isLegacy(fd["lastedit"]): # 기존 파일이 과거의 것인지 확인하고 참이라면 업데이트 설정
                    _update = True
            else:
                _update = True # 파일이 존재하지 않아도 True
        
        if not _update: # 업데이트 할 필요가 없다면 continue
            UPDATE_QUEUE.remove(fd) # org update queue에서 삭제
            continue
        
        # update가 true일 때만 실행됨
        
        if fd["deleted"]: # 삭제되었다면
            if FILEDATA[fd["name"]].exists(): # 파일이 존재하면 삭제한다
                os.remove(FILES_DIR+"/"+fd["name"])
            FILEDATA[fd["name"]].lastedit(fd["lastedit"]) # 최신 수정 시간을 요청대로 바꾸고
            FILEDATA[fd["name"]].deleted(True) # 삭제 True로
            await writedata() # continue 예정이기에 save
            UPDATE_QUEUE.remove(fd) # org update queue에서 삭제
            continue
        
        tempname = secrets.token_hex(16) # 다운로드를 위한 임시 이름을 설정한다.
        try:
            async with aiohttp.ClientSession(conn_timeout=3) as session: # 연결 제한시간을 3초로 세션 오픈
                # res = await session.get(fd["url"])
                print(f"[UPDATE] Downloading: `{fd['name']}` FROM `{fd['url']}`")
                async with session.get(fd["url"]) as res: # fd의 url로 요청을 보낸다.
                    res.raise_for_status() # 2XX대 응답이 아니라면 오류 발생시키기
                    async with aiofiles.open(FILES_DIR+"/temp/"+tempname, "wb") as f: # 파일을 async open한다.
                        async for data in res.content.iter_chunked(CHUNK_SIZE): # CHUNK_SIZE만큼만 메모리에 올려
                            Holder.hold() # hold 상태를 업데이트한다.
                            await f.write(data) # 파일 write
        except:
            continue # 다운로드 중 오류 발생시 패스
        
        if isfile(FILES_DIR+"/"+fd["name"]): # 파일이 있으면 삭제하고 이동
            os.remove(FILES_DIR+"/"+fd["name"])
        shutil.move(FILES_DIR+"/temp/"+tempname, FILES_DIR+"/"+fd["name"])
        
        if not FILEDATA.__contains__(fd["name"]): # 만약 리스트에 파일이 없다면
            file_obj = File(fd["name"], fd["lastedit"], fd["deleted"]) # 클래스 생성 
            FILEDATA[fd["name"]] = file_obj # 후 저장
        else:
            FILEDATA[fd["name"]].lastedit(fd["lastedit"]) # 저장되어 있으면 lastedit 시간만 변경.
            FILEDATA[fd["name"]].deleted(fd["deleted"])
        await writedata() # continue 전 이번 파일 저장
        UPDATE_QUEUE.remove(fd) # org update queue에서 삭제
        continue
    Holder.unhold()
    
async def downtask():
    print("[INFO] 파일 업데이트 태스크가 시작되었습니다.")
    while True:
        await _task()
        await asyncio.sleep(5) # 5초마다 체크.

asyncio.create_task(downtask())
# use uvicorn to run