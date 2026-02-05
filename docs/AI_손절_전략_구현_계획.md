# AI 스마트 손절/리스크 관리 기능 구현 계획

## 🎯 목표 (Goal)
보유 중인 종목이 손실 구간(-0.5% 등)에 진입했을 때, 10분마다 **AI가 차트와 뉴스를 분석**하여 선제적으로 손절할지, 아니면 일시적 조정으로 판단하여 홀딩할지를 결정하는 "스마트 리스크 관리" 기능을 구현합니다.

## ⚠️ 사용자 검토 필요 (User Review Required)
> [!NOTE]
> **뉴스 데이터**: KIS 해외 주식 속보 API (`FHKST01011801` / `brknews-title`)를 사용하여 실시간 뉴스 제목을 가져옵니다.
> **AI 판단**: "최근 일봉 차트(추세)" + "실시간 뉴스(재료)"를 종합하여 판단합니다.

## 🛠️ 변경 예정 사항 (Proposed Changes)

### 1. [KIS API](file:///c:/Users/foxfo/OneDrive/Study/Python/Scalping_Stock_Selector/app/core/kis_api.py)
#### [수정] kis_api.py
- `get_overseas_news_titles(symbol)` 함수 추가.
    - TR ID: `FHKST01011801` (주식 클릭 주문/시세 > 해외주식 > 해외뉴스)
    - URL: `/uapi/overseas-price/v1/quotations/brknews-title`

### 2. [Selector](file:///c:/Users/foxfo/OneDrive/Study/Python/Scalping_Stock_Selector/app/core/selector.py)
#### [수정] selector.py
- `assess_risk(...)` 메서드 추가.
- AI 프롬프트 설계:
    - 입력: 매수가, 현재가, 수익률, 일봉 데이터(OHLCV), 최근 뉴스 제목 3개.
    - 질문: "현재 상황이 기술적 반등(Dip) 기회인가, 아니면 추세 붕괴(Crash)인가? HOLD 또는 SELL로 답하라."
    - 출력: JSON `{"decision": "SELL", "reason": "뉴스 악재 및 지지선 붕괴"}`

### 3. [Trade Manager](file:///c:/Users/foxfo/OneDrive/Study/Python/Scalping_Stock_Selector/app/core/trade_manager.py)
#### [수정] trade_manager.py
- `monitor_risks()` 메서드 신설.
    - 실행 주기: 10분 (Main Loop에서 호출)
    - 대상: 현재 수익률이 **-0.4% 이하**인 종목 (설정 가능)
    - 프로세스:
        1. 일봉 차트 조회 (`get_overseas_daily_price`)
        2. 뉴스 조회 (`get_overseas_news_titles`)
        3. AI 자문 (`selector.assess_risk`)
        4. 결과 처리:
            - **SELL**: 즉시 시장가/지정가 매도 후 텔레그램 알림 ("🚨 AI Risk Cut").
            - **HOLD**: 유지 ("🛡️ AI Hold: 변동성 견디기").

### 4. [Main](file:///c:/Users/foxfo/OneDrive/Study/Python/Scalping_Stock_Selector/main_auto_trade.py)
#### [수정] main_auto_trade.py
- 10분 주기로 `trade_manager.monitor_risks()` 호출 스케줄러 추가.

## ✅ 검증 계획 (Verification Plan)
1. 봇 재시작 및 로그 확인.
2. `monitor_risks`가 정상적으로 뉴스/차트 데이터를 가져오는지 확인.
3. AI가 프롬프트에 대해 적절한 JSON 응답을 주는지 확인.
