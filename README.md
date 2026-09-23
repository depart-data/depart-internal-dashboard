# depart-internal-dashboard

디파트 내부용 주간 데이터 대시보드입니다. Streamlit 기반이며, 광고 성과·계정 성과 지표를 브랜드별로 조회합니다.

## 폴더 구조

```
depart-internal-dashboard/
├── dashboard/
│   ├── app.py                      # 진입점 (streamlit run dashboard/app.py)
│   ├── common.py                   # 차트 스타일링 등 공통 헬퍼
│   └── views/                      # 페이지별 화면
│       ├── ad_performance.py       # 광고 성과
│       ├── account_performance.py  # 계정 성과 (팔로워/오가닉 지표)
│       ├── campaign_flow.py        # 캠페인 성과 흐름
│       ├── ad_search.py            # 광고 검색
│       ├── ad_comparison.py        # 광고 비교
│       └── ai_evaluation.py        # AI 평가
├── config/
│   ├── accounts.py                 # 브랜드별 ad_account_id, 핵심 타겟층 정의
│   └── settings.py                 # 캠페인 필터 키워드 등 공통 설정값
├── extract/
│   └── db_connect.py               # DB 연결 및 쿼리 실행 (run_query)
├── requirements.txt                # 의존 패키지 목록
├── .env.example                    # 필요한 환경변수 템플릿 (실제 .env는 git에 올리지 않음)
└── .claude/launch.json             # (선택) Claude Code에서 서버 실행 시 참고용 설정
```

## 실행 방법

1. 가상환경 생성 및 패키지 설치
   ```bash
   python -m venv .venv
   ./.venv/Scripts/pip install -r requirements.txt   # Windows
   ```

2. `.env` 파일 생성 (`.env.example` 참고, git에는 올라가지 않으니 별도 전달받아야 함)
   ```
   DB_HOST=...
   DB_PORT=...
   DB_NAME=...
   DB_USER=...
   DB_PASSWORD=...
   ```

3. 대시보드 실행
   ```bash
   ./.venv/Scripts/streamlit run dashboard/app.py
   ```
   같은 와이파이의 다른 기기에서도 접속하려면:
   ```bash
   ./.venv/Scripts/streamlit run dashboard/app.py --server.address=0.0.0.0
   ```

## 브랜드/계정 추가·수정

`config/accounts.py`의 `AD_ACCOUNT_IDS`, `TARGET_SEGMENTS`를 수정합니다. 계정 추가 시 DB의 `ad_accounts` 테이블에 해당 계정이 이미 등록되어 있어야 합니다.
