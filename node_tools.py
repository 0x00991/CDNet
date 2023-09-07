import asyncio
import datetime
import os

ROOT_DIR = "./CDN"
FILES_DIR = ROOT_DIR+"/Files"
FILEDATA_PATH = ROOT_DIR+"/filedata.bin"
CHUNK_SIZE = 16*1024*1024

def timestamp(): return round(datetime.datetime.utcnow().timestamp())

class Holder:
    def ts(self): return round(datetime.datetime.utcnow().timestamp())
    def __init__(self) -> None:
        self.holding = False
        self.updt = self.ts()
    
    def hold(self, boolean: bool = True):
        self.holding = boolean
        if boolean:
            self.updt = self.ts()
        return self.holding
    def unhold(self):
        self.holding = False
        return self.holding
    
    def isHolding(self):
        return self.holding
    def is_holding(self):
        return self.holding
    
    async def wait(self):
        loops = 0
        while self.holding:
            await asyncio.sleep(0.3)
            loops += 1
            if self.updt+6 < self.ts():
                self.unhold()

        return round(loops*0.3, 1)

class File:
    def __init__(self, filename: str, lastedit: int, deleted: bool) -> None:
        self._filename = filename
        self._lastedit = lastedit
        self._deleted = deleted
    def name(self):
        return self._filename
    def lastedit(self, new_ts: int = -1):
        if new_ts < 0:
            return self._lastedit
        self._lastedit = new_ts
        return new_ts
    def deleted(self, new_del: bool = None):
        if new_del is None:
            return self._deleted
        else:
            self._deleted = new_del
            return new_del
    def exists(self):
        return os.path.isfile(FILES_DIR+"/"+self._filename)
    
    def isLegacy(self, new_timestamp):
        return self._lastedit < new_timestamp

EXTS = {
    "jpg": "image/jpeg",
    "png": "image/png",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "apng": "image/apng",
    "js": "text/javascript",
    "css": "text/css",
    "mp4": "video/mp4",
    "mp3": "audio/mpeg",
    "zip": "application/zip",
    "aac": "audio/aac",
    "csv": "text/csv",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "gz": "application/gzip",
    "jar": "application/java-archive",
    "json": "application/json",
    "opus": "audio/opus",
    "otf": "font/otf",
    "pdf": "application/pdf",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "ttf": "font/ttf",
    "txt": "text/plain",
    "wav": "audio/wav",
    "webm": "video/webm",
    "webp": "image/webp",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xml": "application/xml",
    "3gp": "audio/3gp",
    "7z": "application/x-7x-compressed"
}