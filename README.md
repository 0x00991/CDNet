# CDN
구성 요소: 매니저 (1), 노드 (1+)

## 매니저
관리 프로그램의 작동 방식만이 간략하게 서술 돼 있고, CDN 문단에 전체적인 예시가 서술되어 있습니다.
일정 시간마다 모든 CDN 서버에 파일 목록을 요청합니다. 특정 파일이 더 최신일 경우 모든 서버에 해당 CDN 서버의 접근 가능한 파일 주소와 수정 시간을 전송합니다.
요청마다 응답한 노드들만을 온라인으로 기억하고, 사용자가 `/file/<filename>`을 요청할 시 현재 기준으로 온라인인 노드 중 하나로 리다이렉트 시킵니다.
## CDN
매니저에서 파일 목록을 요청할 시 노드는 데이터를 아래 형식 으로 반환합니다. timestamp는 UTC 기준입니다.
```json
{
    "example.txt": {
        "lastedit": timestamp,
        "deleted": false
    },
    "example.exe": {
        "lastedit": timestamp,
        "deleted": false
    }
    ...
}
``` 
매니저는 모든 서버의 응답을 lastedit을 기준으로 취합합니다.

매니저로부터 다음 데이터를 전달받습니다.
```json
{
    "example.txt": {
        "url": URL, // http link
        "lastedit": timestamp,
        "deleted": false
    },
    "example.exe": {
        "url": URL,
        "lastedit": timestamp,
        "deleted": true
    }
    ...
}
```
해당 파일이 존재하지 않거나, lastedit이 저장된 마지막 수정시간보다 최신일 경우 URL로 요청을 보내 파일을 다운로드합니다.
 - 현재는 다운로드 중 파일 엑세스 요청이 들어올 시 수정 전의 파일을 반환합니다.

## API
### Manager
GET /get/<FilePath>?dkey=<DOWN-KEY> - redirect
POST /api/upload?key=<API-KEY>&filename=<FileName> [BODY: File]
DELETE /api/delete?key=<API-KEY>&filename=<FileName>[&delkeys=y]
GET /api/info?key=<API-KEY>
DELETE /api/cleardeleted?key=<API-KEY>
### CDN
GET /api/info?key=<API-KEY> - 200
GET /get/<FilePath>?dkey=<DOWN-KEY> - 200
POST /api/upload?key=<API-KEY>&filename=<FileName> [BODY: File] - 201
DELETE /api/delete?key=<API-KEY>&filename=<FileName>

## 문제점 (수정 예정)
 * 모든 CDN이 파일 수정/삭제/생성 권한이 있음 > 매니저에서 허용한 업데이트만 진행할 수 있도록 수정
 * 임의로 삭제 요청을 하지 않으면 파일 데이터 목록이 무거워지는 문제 > 매니저에서 노드별 ID를 부여하고 모든 노드가 온라인일 때 삭제요청을 넣도록 수정
 * 관리자 노드에 업로드 요청을 할 시 관리자가 파일을 받아서 노드에 업로드하고 그 정보를 반환함 (관리자 노드가 무거워짐) > ?