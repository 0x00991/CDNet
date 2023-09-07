# Content Delivery 'Network'  
구성 요소: `매니저 (1개, Light)`, `CDN (많이)`
`(CDN 서버들)` <-> `매니저`  

## 매니저
관리 프로그램의 작동 방식만이 간략하게 서술 돼 있고, CDN 문단에 전체적인 예시가 서술되어 있습니다.
일정 시간 (수정됨)마다 모든 CDN 서버에 파일 목록을 요청합니다. (응답 예시 - CDN 문단) 특정 파일이 더 최신일 경우 (확인 방법 - CDN 문단) 모든 서버에 해당 CDN 서버의 접근 가능한 파일 주소, `<CDN 문단 서술>`을 전송합니다.
*(보류) 웹소켓으로 모든 CDN 서버와 연결하며, 사용자가 `/file/<filename>`을 요청할 시 현재 소켓으로 연결되어 있는 서버 [(보류) 부하가 가장 낮은 서버]로 리다이렉트합니다.*
## CDN
매니저에서 파일 목록을 요청할 시, 아래 데이터 형식 (json) 으로 반환합니다. timestamp는 int 형식이며 UTC 기준입니다.
```json
{
    "example.txt": {
        "lastedit": timestamp, // int, UTC
        "deleted": false
    },
    "example.exe": {
        "lastedit": timestamp
    },
    "directory/examplei.txt": {
        "lastedit": timestamp
    }
    ...
}
``` 
매니저는 모든 서버의 응답을 lastedit을 기준으로 취합합니다. (for loop - if lastedit > lastedit_old replace to new)  

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
}
```

해당 파일이 존재하지 않거나, lastedit이 저장된 마지막 수정시간보다 최신일 경우 URL로 요청을 보내 파일을 다운로드합니다. (URL/filename 으로)
 **- 다운로드 중** 파일 엑세스 요청이 들어올 시 `과거 버전 파일을 반환하거나` `다운로드가 완료될 때까지 응답을 홀드하거나` `업데이트 중이라고 *다른* 서버로 리다이렉트 시킵니다. (현재 다운로드 중인 URL?)`


## API
### Manager
/get/<FilePath>?dkey=<DOWN-KEY> - Redirect
### CDN
/api/info?key=<API-KEY> - 200
POST /api/update?key=<API-KEY> - 201

/get/<FilePath>?dkey=<DOWN-KEY> - 200
/api/upload?key=<API-KEY>&filename=<FILENAME> [BODY: File] - 201


## 보안
 * 모든 CDN이 파일 수정/삭제/생성 권한이 있음. > [매니저의 수정 요청만 시행하거나] [매니저에서 허용한 업데이트만 진행할 수 있도록 수정]