# 📝 주식 자동 트레이딩 시스템 (Stock Selection & Pipeline Spec)

## 1. 개요 (Overview)
본 문서는 Google Antigravity 기반 자동 트레이딩 시스템의 **종목 선정 로직(Stock Selection Logic)**과 **대시보드(Dashboard)** 요구사항을 정의한다.
시스템은 **장전(Pre-market) 유망 종목 선정(Top 10)**과 **장중(In-market) 실시간 발굴** 프로세스로 나뉘며, 국내(KR)와 미국(US) 시장을 구분하여 운영한다.

---

## 2. Top 10 (오늘 유망 종목) 선정 로직

### 2.1. 수집 및 갱신 정책
* **기본 원칙:** 1일 1회, 장 시작 전 생성 (장 운영일 기준).
* **트리거 시점:**
    * **국내(KR):** 08:00 ~ 08:30 사이 (장 시작 전)
    * **미국(US):** 21:30 ~ 22:00 사이 (프리마켓/장 시작 전)
* **예외 처리:**
    * **주말/휴장일:** 생성하지 않음.
    * **Fallback(장중 비어있을 시):** 장 중인데 Top 10 데이터가 없을 경우, 10분 주기 매수 로직 실행 시 Top 10 생성을 먼저 시도한다.
    * **수동 갱신:** 사용자가 Dashboard에서 [갱신] 버튼 클릭 시 강제 재선정.

### 2.2. Top 10 선정 알고리즘 (AI Agent)
AI는 아래 **2단계 프로세스**를 수행하여 결과를 도출해야 한다.

#### **Step 1: 시장 데이터 수집 및 분석 (Context Analysis)**
* **입력:** 뉴스 API, 경제 지표, 섹터별 등락률.
* **프롬프트 요구사항:** 거시 경제, 오늘 주목할 섹터/뉴스/정책, 투자 전략 수립.

#### **Step 2: 종목 필터링 및 선정 (Selection)**
* **입력:** Step 1의 분석 결과 + 실시간 등락률/수급 데이터.
* **출력 데이터(JSON 필수):** 코드로 처리 가능하도록 반드시 정형화된 데이터로 출력.
    * 종목명, 종목코드(Symbol), 선정 이유(1줄 요약), 시가(Open), 당일 목표가(Target Price).

---

## 3. Dashboard UI/UX 요구사항

### 3.1. Top 10 패널 기능
* **탭 구분:** [국내(KR)] / [미국(US)] 탭으로 분리.
* **상태 표시:**
    * `Empty`: "오늘의 Top 10이 선정되지 않았습니다." 문구 및 [분석 시작/갱신] 버튼 노출.
    * `Success`: 선정 날짜/시간 표시 및 리스트 출력.
    * `Loading`: "AI가 시장을 분석 중입니다..." 스피너 표시.

### 3.2. 리스트 관리 (CRUD)
* **조회 (Read):** AI 선정 종목 + 사용자 추가 종목 통합 리스트.
* **수정 (Update - 갱신):** [갱신] 버튼 클릭 시 AI가 다시 분석하여 리스트를 **덮어쓰기** (단, 사용자 추가 종목은 유지).
* **삭제 (Delete):** 각 행의 [삭제] 버튼으로 개별 제거 가능.
* **추가 (Create - 수동 입력):**
    * **입력 필드:** 종목명, 코드, 이유, 시작가, 목표가.
    * **식별:** 수동 추가된 종목은 UI상 별도 아이콘(예: 👤) 또는 태그로 AI 선정 종목(🤖)과 구분.

---

## 4. 🔄 실시간 종목 선정 프로세스 (Selection Pipeline)

### 4.1. 국내 주식 (KR Market)
* **실행 주기:** 매 10분 (08:30 ~ 14:30)
* **로직 흐름:**

**Step 1: 후보군 수집 (Sourcing)**
1.  **Priority 1 (Top 10):** 대시보드에 등록된 Top 10 종목 (가중치 최상).
2.  **Priority 2 (Market Trend):** `market_analyst` 모듈이 실시간 뉴스/테마 분석으로 추출한 주도주.
3.  **Priority 3 (Volume Spike):** KIS API 기준 거래량/거래대금 급증 종목 (ETF, 스팩, ETN 제외).

**Step 2: 기술적 1차 필터링 (Hard Filter)**
* `RSI(14)` >= 70 (과매수) → **제외**
* `Daily Change` >= +15% (급등 피로감) → **제외**
* `Trend` == Down (이동평균선 역배열 등 하락 추세) → **제외**

**Step 3: AI 심층 스코어링 (Scoring)**
* 후보 종목에 대해 `0~100점` 부여.
* **평가 요소:** 기술적 지표(40%) + 뉴스 호재 강도(30%) + 수급(외인/기관)(30%).
* **Action:** 60점 이상인 종목만 최종 매수 리스트에 등록.

### 4.2. 미국 주식 (US Market)
* **실행 주기:** 매 10분 (22:10 ~ 05:00)
* **로직 흐름:**

**Step 1: 후보군 수집 (Sourcing)**
1.  **Priority 1 (Top 10):** 장전 선정된 Top 10.
2.  **Priority 2 (Watchlist):** 사전 정의된 우량주/기술주 60선 (NVDA, MSFT, TSLA, AAPL 등 Mega Cap).

**Step 2: Top-Down 스크리닝 (Context Filter)**
* **방식:** 하드 필터(RSI 등)를 사용하지 않고 **AI의 정성적 판단** 우선.
* AI가 현재 시장 상황(나스닥 지수, 금리, 뉴스)을 기반으로 Priority 2 리스트 중 "오늘 상승 확률이 높은 테마" 15개 내외를 1차 선별.

**Step 3: AI 심층 스코어링 (Scoring)**
* 선별된 종목의 `OHLCV` 데이터 분석.
* 상승 확률과 손익비(Risk/Reward Ratio) 계산.
* 점수 상위 순으로 매매 집행.

---

## 5. 🧠 AI 분석 프롬프트 (System Prompt Spec)

개발 시 AI Agent에게 전달할 프롬프트는 **시스템이 파싱 가능한 구조(JSON)**로 답변을 받아야 합니다.

**Role:**
당신은 20년 경력의 베테랑 펀드매니저이자 파이썬 개발자입니다. 시장의 데이터를 분석하여 JSON 포맷으로 정확한 투자 전략을 도출해야 합니다.

**Constraints:**
1.  **Time Awareness:** 반드시 '오늘 날짜({CURRENT_DATE})' 기준 최신 데이터를 사용할 것. (휴장일인 경우 직전 거래일 기준)
2.  **Fact Check:** 없는 뉴스를 생성하지 말 것. (Hallucination 방지)
3.  **Output Format:** **반드시 아래 JSON 형식으로만 응답할 것.** 설명 텍스트를 JSON 바깥에 붙이지 말 것.

**Task Input:**
(여기에 API로 수집한 뉴스 헤드라인, 주요 지수 등 Raw Data가 주입됩니다)

**Output JSON Structure:**
```json
{
  "market_summary": {
    "outlook": "Bullish/Bearish/Neutral",
    "key_issues": ["이슈1", "이슈2"],
    "strategy": "종합 투자 전략 텍스트"
  },
  "top_sectors": [
    {
      "sector_name": "반도체",
      "reason": "엔비디아 실적 호조에 따른 기대감",
      "related_stocks": ["삼성전자", "SK하이닉스"]
    }
  ],
  "top_10_picks": [
    {
      "stock_name": "종목명",
      "ticker": "종목코드(123456)",
      "market_type": "KR", 
      "selection_reason": "선정 이유 한 줄 요약",
      "expected_open_price": 10000,
      "target_price_today": 11500
    }
    // ... 총 10개 종목
  ]
}
