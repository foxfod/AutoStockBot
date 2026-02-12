# 버전 히스토리 (Version History)

이 문서는 프로젝트의 주요 변경 사항과 업데이트 내역을 기록합니다.

## [v.20260209_010] 시스템 안정화 및 대시보드 개선

### [v.20260209_010-01] 수익률 표시 오류 수정 (Profit Rate Fix)
- **문제**: 대시보드 수익률이 일일 등락률과 혼동되거나, 갱신이 지연되는 문제.
- **수정**:
    - `main.py`: `daily_change`(일일 변동률) 계산 로직 추가.
    - `kis_api.py`: 실시간 시세 조회 시 `prev_close`(전일 종가) 데이터 포함.
    - `dashboard.html`: 종목 카드에 **Total P&L**(총 수익률)과 **Daily Change**(일일 변동률)을 구분하여 표시.

### [v.20260209_010-02] 미국 주식 동기화 오류 수정 (US Stock Sync Fix)
- **문제**: 미국 주식 보유량이 실제보다 많이 표시되거나(중복), 아예 표시되지 않는 문제.
- **수정**:
    - `kis_api.py`: 여러 거래소(NASD, NYSE, AMEX) 조회 시 발생하는 중복 종목 제거 로직(Deduplication) 추가.
    - `trade_manager.py`: 미국 주식 동기화 과정에 상세 디버그 로그 추가.

### [v.20260209_010-03] 주문 가능 금액 초과 오류 수정 (Insufficient Funds Fix)
- **문제**: 매수 주문 시 잔고를 100% 사용하여 수수료나 시장가 변동으로 인해 주문 거부 발생.
- **수정**:
    - `trade_manager.py`: 매수 수량 계산 시 **안전 버퍼(Safety Buffer)** 적용.
        - **미국 주식**: 예산의 **98%** 사용 (지정가 +1% 및 수수료 고려).
        - **한국 주식**: 예산의 **95%** 사용 (시장가 변동성 고려).

### [v.20260209_010-04] 대시보드 UI/UX 개선
- **기능 추가**:
    - 슬롯 영역(KR/US) 클릭 시 해당 국가 종목만 필터링하여 보여주는 기능 추가.
    - 웹소켓 연결 오류 수정 (`connectWebSocket` 함수 복구).

### [v.20260209_010-05] 버전 관리 시스템 (Versioning System)
- **기능 추가**:
### [v.20260209_010-06] 대시보드 콘솔 에러 수정 (Console Fix)
- **문제**: 대시보드 로딩 시 `fetchState is not defined`, `logContainer is not defined` 에러 발생.
- **수정**:
### [v.20260209_010-07] 동시 주문 시 잔고 부족 오류 수정 (Multi-Buy Insufficient Funds Fix)
- **문제**: 여러 종목 동시 매수 시, API 잔고 갱신 지연으로 인해 초기 잔고 기준으로 중복 계산되어 주문 거부 발생.
- **수정**:
    - `trade_manager.py`: 매수 루프 내에서 잔고를 실시간으로 차감(`current_kr_cash`)하여 다음 종목 계산에 반영.
    - API `update_balance` 호출을 루프 내부에서 제거하여 Stale Data 참조 방지.

### [v.20260209_010-08] AI 분석 정확도 향상 (AI Accuracy)
- **문제**: AI 분석 시 시장 환경 정보(Market Context)가 누락되어, 하락장에서도 공격적인 매수를 추천함.
- **수정**: `ai_analyzer.py` 프롬프트에 시장 상태(Bull/Bear)를 주입하고, 하락장 시 보수적 기준을 적용하도록 로직 개선.

### [v.20260209_010-09] 시장가 주문 잔고 부족 수정 (Market Order Margin Fix)
- **문제**: 시장가 주문(Price=0) 시 거래소가 '상한가(+30%)' 기준으로 증거금을 요구하여, 잔고가 충분함에도 `주문가능금액 초과` 오류 발생.
- **수정**: KR 종목 매수 수량 계산 시 분모를 `현재가` 대신 `현재가 * 1.3`으로 변경하여 증거금 부족 방지.

### [v.20260209_010-10] 변수 참조 오류 긴급 수정 (Hotfix)
- **문제**: Patch 09 적용 과정에서 `safe_invest_amt` 변수 정의가 누락되어 `UnboundLocalError` 발생.
- **수정**: `trade_manager.py` 내 KR 매수 로직에 `safe_invest_amt` 변수 선언 복구.

### [v.20260209_010-11] 청산 오류 메시지 수정 (Liquidation Error Fix)
- **문제**: 매도 주문 실패 시에도 봇이 "청산 완료" 메시지를 보내 사용자가 혼동함.
- **수정**: `liquidate_all_positions` 함수에서 매도 주문 결과를 확인하고, 실패 시 에러 메시지 전송 및 1회 재시도(Retry) 로직 추가.

### [v.20260209_010-12] 토큰 만료 오류 자동 복구 (Token Auto-Refresh)
- **문제**: 간혹 '기간이 만료된 token 입니다(EGW00123)' 오류와 함께 주문/잔고조회가 실패함.
- **수정**: `kis_api.py` 내 주요 통신 함수(잔고조회, 주문)에 만료 오류 감지 시 토큰을 강제 갱신(Force Refresh)하고 즉시 재시도하는 로직을 전면 적용.

### [v.20260209_010-13] 장전 Top 10 추천 기능 추가 (Pre-Market Top 10)
- **기능**: 매일 장 시작 30분 전(KR 08:30, US 22:00), AI가 시장 상황과 뉴스를 분석하여 '오늘의 Top 10 유망 종목'을 선정하고 리포팅함.
- **연동**: 선정된 Top 10 종목은 `app/data/top_picks.json`에 저장되며, 장 중 매수 후보군(Candidate Pool)에 최우선적으로 포함됨.

### [v.20260209_010-14] 대시보드 전량 매도 버튼 오류 수정 (Dashboard Sell-All Fix)
- **문제**: 대시보드 내 '전량 매도' 버튼 클릭 시, 백엔드 함수 미구현으로 인해 동작하지 않음.
- **수정**: `TradeManager`에 `sell_position` 함수를 추가하여, 대시보드 요청 시 즉시 시장가(Market Price)로 매도 주문을 실행하도록 개선함.

### [v.20260210_010-15] 대시보드 편의 기능 추가 (Dashboard Enhancements)
- **Top 10**: 대시보드 상단 '🏆 Top 10' 버튼을 통해 장전 유망 종목 리스트를 확인하고, '🔄 갱신' 버튼으로 즉시 재분석 가능.
- **연결**: 웹소켓 연결 끊김 시, 헤더의 '재연결(🔄)' 버튼을 눌러 즉시 재연결 시도 가능.

### [v.20260210_010-16] 미국장 청산 실패 및 시작 오류 수정 (Liquidation Fail Fix)
- **문제**: 한국투자증권 API 일시적 오류(None 반환)로 인해 봇 시작 시 크래시 발생, 이로 인해 미국장 주식 동기화 및 청산 실패. 또한 로컬 `run.bat`이 매매 봇을 실행하지 않는 문제 발견.
- **수정**: 
    - `trade_manager.py`: `sync_portfolio` 메서드에 API 응답 예외 처리 추가 (None 반환 시 빈 리스트로 처리).
    - `run.bat`: 실행 대상을 `app.main`에서 `main_auto_trade.py`로 변경하여 트레이딩 루프 정상 구동.

### [v.20260210_010-17] 미국장 청산 및 잔고 조회 오류 수정 (US Liquidation & Balance Fix)
- **문제**: 
    - 미국 주식 매도 시 '시장가(Price=0)' 주문 불가로 인한 "주문단가를 입력 하십시오" 오류.
    - 한국투자증권 API 정책 변경으로 잔고 조회 시 `OPSQ2001` (INVALID_CHECK_INQR_DVSN) 오류 발생.
- **수정**:
    - `trade_manager.py`: 미국 청산 시 **현재가 대비 -5% 지정가** 주문으로 변경하여 즉시 체결 유도.
    - `kis_api.py`: 잔고 조회 파라미터 `INQR_DVSN` 값을 `02`에서 **`01`**로 변경.

### [v.20260210_010-18] Top 10 갱신 오류 수정 (Top 10 Refresh Fix)
- **문제**: 대시보드에서 'Top 10 갱신' 버튼 클릭 시 `TypeError` (인자 개수 불일치) 발생.
- **수정**: `selector.py`의 `analyze_stock` 호출부를 함수 정의에 맞게 수정 (인자 3개, 동기 호출).

### [v.20260210_010-19] 대시보드 연결 안정성 개선 (Dashboard Connection Fix)
- **문제**: 재연결 버튼 클릭 시 시각적 반응이 없고, 기존 좀비 연결이 남아있어 불안정함.
- **수정**: 
    - `dashboard.html`: 웹소켓 변수 전역 관리 및 중복 연결 방지 로직 추가.
    - 재연결 버튼에 **로딩 인디케이터(Spinner)** 추가하여 사용자 경험 개선.

### [v.20260210_010-20] Top 10 분석 로직 비동기 전환 (Async Top 10 Analysis)
- **문제**: Top 10 분석 시(약 1~2분 소요) **서버 응답이 멈춰** 대시보드에서 "데이터 로드 실패" 에러 발생.
- **수정**:
    - `ai_analyzer.py`: OpenAI/Gemini 호출을 **비동기(Async)** 방식으로 변경하여 Non-blocking I/O 구현.
    - `selector.py`: 종목 분석 루프를 `asyncio.gather`를 사용한 **병렬 처리(Parallel Processing)**로 전환.
    - **결과**: 분석 속도가 획기적으로 개선되고, 분석 중에도 서버가 멈추지 않음.

### [20260211_010-01] 주문가능금액 수정
- `kis_api.py`: 주문 가능 금액 계산 로직 변경 (`nrcvb_buy_amt` 미수없는매수금액 사용)
- `debug_balance_real.py`: 잔고 조회 테스트 스크립트 추가 및 검증 완료
### [20260211_010-02] 긴급 버그 수정
- `main_auto_trade.py`: `SCAN_INTERVAL` 변수 정의 누락으로 인한 NameError 수정 (긴급 복구)

### [20260211_010-03] 긴급수정
- `main_auto_trade.py`: `SCAN_INTERVAL` 변수 정의 누락으로 인한 NameError 수정 (긴급 복구)

### [20260211_010-04] AI 분석 오류 수정
- `ai_analyzer.py`: AI 응답 파싱 전처리 로직 추가 (Markdown 코드 블록 제거) - 분석 실패 해결

### [20260211_010-06] 전략 고도화 (수익률 개선)
- `selector.py`: 매수 필터 강화 (RSI 75->70 하향, 당일 등락률 15% 이상 진입 금지)
- `ai_analyzer.py`: 프롬프트 수정 (추격 매수 경고, 눌림목/조정 구간 선호 로직 추가)
- `trade_manager.py`: 익절 로직 변경 (AI 조기 익절 +1% 제거, 트레일링 스탑 +2% 도달 시 즉시 가동)

## v2.2.1 (2026-02-12)
- **[Fix] 미국 주식 매수 로직 수정**
    - 기술적 필터 완화: `SMA5 < SMA20` 조건 제거 (눌림목 매수 허용)
    - AI 프롬프트 개선: 하락 추세 시 반등 가능성 분석 강화, 급등주 기준 20%로 완화
    - 디버깅 스크립트 추가 (`debug_us_stock_data.py`)

## v2.2.0 (2026-02-11)
- **[Feature] 미국 주식(해외 주식) 자동 매매 기능 추가**

### [20260211_010-07] 트렌드 기반 종목 선정 기능 추가
- `requirements.txt`: `beautifulsoup4` 추가 (뉴스 크롤링용)
- `market_analyst.py`: 네이버 금융 뉴스 크롤링 및 트렌드 종목 추출 기능 추가 (`get_trend_candidates`)
- `ai_analyzer.py`: AI 뉴스 분석 및 주도주 추출 프롬프트 추가 (`recommend_trend_stocks`)
- `selector.py`: Top 10 선정 시 트렌드 종목(0순위) 우선 분석 로직 통합

### [20260211_010-05] AI 분석
- `main_auto_trade.py`: `SCAN_INTERVAL` 변수 정의 누락으로 인한 NameError 수정 (긴급 복구)

### [20260211_010-07] `main_auto_trade.py`: `SCAN_INTERVAL` 변수 정의 누락으로 인한 NameError 수정 (긴급 복구)
- ### [20260211_010-03] 긴급수정

### [20260211_010-08] 트렌드 기반 종목선정 기능 추가
- 1시간 마다 캐싱

### [20260211_010-10] 종목분석 오류 수정
- dashboard

### [v.20260211_011-00] 오버나잇 전략(Overnight Hold Strategy) 구현
- **기능 추가**:
    - `ai_analyzer.py`: 장 마감 전 상승 추세 및 뉴스 호재 분석을 통한 오버나잇(HOLD) 판단 로직 추가 (`analyze_overnight_potential`).
    - `trade_manager.py`: 청산(Liquidation) 프로세스에서 오버나잇 승인 종목 제외 처리 (`check_overnight_holds`, `liquidate_all_positions`).
    - `main_auto_trade.py`: KR(15:10), US(05:35) 장 마감 직전 오버나잇 심사 스케줄링 추가.
- **정책**:
    - AI 판단 시 수익 중이거나 손실이 -3% 이내인 경우만 오버나잇 허용 (깊은 손실은 리스크 관리 차원에서 청산).

### [20260211_011-01] 판매 규칙 보강
- 장마감 규칙 - HOLD 추가

### [20260212_010-01] AI 분석 데이터 타입 및 데이터 지속성 수정 (Critical Fixes)
- **AI 점수 타입 안정화**: `selector.py`에서 AI 점수 파싱 시 `TypeError` (문자열 비교 오류)를 방지하기 위한 안전한 형변환 로직(`try-except float`) 추가.
- **Top 10 지속성 보장**:
    - 기존: `top_picks.json` 하나에 덮어쓰기 되어 KR 데이터가 유실됨.
    - 수정: `top_picks_KR.json`, `top_picks_US.json`으로 분리하여 데이터 보존.
    - 대시보드 API 수정: 요청된 마켓(`market=KR/US`)에 맞는 파일을 읽도록 변경.

### [20260212_010-05] 미국 주식 매수 로직 안정화 (US Trading Stabilization)
- **변수명 오류 수정**: `selector.py` 내 `market_type` NameError 수정 (`"KR"`, `"US"` 명시적 지정).
- **거래소 코드 호환성 패치**:
    - 문제: 봇 내부 4자리 코드(`NASD`) vs KIS API 3자리 코드(`NAS`) 불일치로 주문 실패.
    - 해결: `kis_api.py` 내 `buy_overseas_order`, `sell_overseas_order` 함수에 자동 변환 로직 추가. -> **[롤백]** 주문 API는 4자리 코드(`NASD`)가 정상임을 확인하여 원복.
- **매수 실행 오류 수정**:
    - 문제: `trade_manager.py`가 미국 주식(`market="US"`)을 한국 주식(`market_type="KR"` 기본값)으로 인식하여 주문 실패.
    - 해결: `market` 키와 `market_type` 키를 모두 확인하도록 로직 개선.

### [20260212_010-10] 기타 최적화 및 버그 수정
- **Top 10 갱신 속도 개선**: 불필요한 중복 분석 제거 및 비동기 처리 최적화.
- **서버 불안정 수정**: 봇 실행 스크립트(`run.bat`) 및 모듈 실행 경로 점검.


### [20260212_010-19] 자동 업데이트 (미국 주식 매수 실패 긴급 수정)
- **거래소 코드 정규화 롤백**:
    - `kis_api.py`: 주문 API(`buy_overseas_order`)는 시세 API와 달리 4자리 코드(`NASD`)를 사용해야 함을 확인.
    - 기존에 추가했던 `NASD -> NAS` 강제 변환 로직을 제거하고, `NASD` 코드가 그대로 전송되도록 원복함.
- **시장 구분 키 불일치 수정**:
    - `trade_manager.py`: `selector.py`에서 전달하는 키(`market`)와 `trade_manager`가 기대하는 키(`market_type`)가 달라 미국 주식을 한국 주식으로 오인함.
    - `market_type` 조회 시 `market` 키도 함께 확인하도록 수정하여 정상적으로 미국 시장(`US`)으로 인식되게 함.

### [20260212_010-20] 미국 주식 주문 코드 강제 적용 (Force 4-Char Code)
- **주문 실패 해결**: `trade_manager.py`에서 미국 주식 주문 시 3자리 코드(`NAS`, `NYS`, `AMS`)가 들어오면 즉시 4자리 코드(`NASD`, `NYSE`, `AMEX`)로 변환하여 전송하도록 강제 로직 추가.
- **재시도 로직 개선**: 주문 실패 시 재시도 순서를 4자리 코드 우선(`NASD` -> `NYSE`...)으로 변경하여 성공 확률 높임.

### [20260213_010-01] 자동 업데이트
- .

### [20260213_010-02] AI문석 속도 향상
- .
