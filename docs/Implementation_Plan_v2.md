# 구현 계획 - 주식 선정 v2 (Stock Selection v2)

## 목표 설명
`docs/주식 선정 1차 개선 Top10 포함_v2.md`에 정의된 개선된 "주식 선정 v2" 로직을 구현합니다. 주요 내용은 다음과 같습니다:
1.  **`selector.py` 리팩토링**: KR(한국)과 US(미국) 선정 파이프라인을 분리하고, 각기 다른 소싱 및 필터링 로직을 적용합니다.
2.  **`market_analyst.py` 강화**: 구조화된 JSON 프롬프트를 사용하여 새로운 "Top 10" 선정 알고리즘을 구현합니다.
3.  **대시보드 업데이트**: KR/US 탭, 상태 표시기, 수동 CRUD 기능을 갖춘 "Top 10" 패널을 추가합니다.
4.  **스케줄링**: 지정된 장전 시간(Pre-market)에 Top 10 생성이 실행되도록 보장합니다.

## 사용자 검토 필요 사항
> [!IMPORTANT]
> 이번 업데이트는 핵심 주식 선정 로직을 변경합니다. 이제 "Top 10"이 후보군의 1순위 소스가 됩니다.
> 새로운 UI 변경 사항을 반영하려면 웹 서버(대시보드)를 재시작해야 합니다.

## 변경 제안

### 핵심 로직 (Core Logic)

#### [MODIFY] [selector.py](file:///c:/Users/foxfo/OneDrive/Study/Python/Scalping_Stock_Selector/app/core/selector.py)
- `select_stocks`를 `select_stocks_kr`과 `select_stocks_us`로 분리 (또는 명확하게 구분).
- `1순위 (Top 10)`, `2순위 (트렌드)`, `3순위 (거래량)` 소싱 로직 구현.
- KR(하드 필터)과 US(컨텍스트 필터)에 대해 서로 다른 필터링 규칙 적용.

#### [MODIFY] [market_analyst.py](file:///c:/Users/foxfo/OneDrive/Study/Python/Scalping_Stock_Selector/app/core/market_analyst.py)
- `generate_top_10_picks(market_type)` 함수 구현.
- 시장 분석 및 주식 선정을 위한 새로운 시스템 프롬프트(JSON 출력) 통합.
- `app/data/top_picks_{market}.json`에 Top 10 데이터 저장/로드 기능 구현.

### 웹 대시보드 (Web Dashboard)

#### [MODIFY] [dashboard.html](file:///c:/Users/foxfo/OneDrive/Study/Python/Scalping_Stock_Selector/app/web/templates/dashboard.html)
- UI에 "Top 10" 패널 추가 (새로운 탭 또는 섹션).
- 수동 Top 10 재생성을 위한 "새로고침(Refresh)" 버튼 구현.
- 수동 종목 관리를 위한 "추가/삭제" UI 구현.

#### [MODIFY] [main.py](file:///c:/Users/foxfo/OneDrive/Study/Python/Scalping_Stock_Selector/app/web/main.py)
- API 엔드포인트 추가:
    - `GET /api/top-picks/{market}`: 현재 Top 10 조회.
    - `POST /api/top-picks/{market}/refresh`: AI 재생성 트리거.
    - `POST /api/top-picks/{market}/add`: 수동 종목 추가.
    - `DELETE /api/top-picks/{market}/{symbol}`: 종목 삭제.

## 검증 계획

### 자동화 테스트
- 없음 (로직이 외부 API 및 AI에 크게 의존함).

### 수동 검증
1.  **Top 10 생성**:
    - 대시보드 또는 Swagger를 통해 `POST /api/top-picks/KR/refresh` 트리거.
    - `app/data/top_picks_KR.json`이 유효한 JSON 10개 항목으로 생성되는지 확인.
    - 대시보드의 "Top 10" 패널에 리스트가 올바르게 표시되는지 확인.
2.  **주식 선정 통합**:
    - `test_market_data.py` (또는 새 스크립트)를 실행하여 10분 주기 선정 시뮬레이션.
    - `top_picks_KR.json`의 종목들이 "1순위(Priority 1)"로 후보군에 포함되는지 확인.
3.  **대시보드 CRUD**:
    - UI를 통해 종목 수동 추가 ("User Pick").
    - 리스트에 구분된 아이콘과 함께 표시되는지 확인.
    - 종목 삭제 후 리스트에서 사라지는지 확인.
