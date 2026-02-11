# 미국 주식 자동 매매 프로세스 (US Stock Trading Logic)

이 문서는 봇이 미국 주식을 선정하고 매수하는 전체 과정을 설명합니다.

## 1. 스케줄링 및 장 운영 시간
- **운영 시간**: 한국 시간 **22:00 ~ 06:00** (서머타임 미적용 기준, 서머타임 시 21:00 ~ 05:00)
- **스캔 주기**: 매 **10분**마다 실행 (`main_auto_trade.py`)
- **장전/장후**:
    - **프리마켓(장전)**: 22:00 ~ 22:30 (장전 유망 종목 분석)
    - **정규장**: 22:30 ~ 05:40 (실제 매매)
    - **장마감 청산**: 05:40 ~ 06:00 (오버나잇 미설정 시 전량 매도)

## 2. 종목 선정 단계 (Selector.py)
봇은 **장전(Pre-Market) 분석에서 선정된 Top 10 종목**을 최우선으로 검토하며, 이후 사전에 정의된 **미국 우량 기술주** 리스트를 순회하며 분석합니다.

### A. 기술적 필터링 (Technical Filters)
모든 종목에 대해 일봉 데이터를 조회한 후, 다음 기준을 통과해야 AI 분석 대상으로 선정됩니다.
*(최근 하락장 대응을 위해 필터가 완화되었습니다)*

1.  **RSI (상대강도지수)**: **75 미만**이어야 함. (과열 종목 제외)
2.  **변동성 (Daily Change)**: 전일 대비 상승률 **20% 미만**이어야 함. (단기 급등/작전주 제외)
3.  **추세 (Trend)**:
    - 기본적으로 **상승 추세** (현재가 > 20일 이동평균선)를 선호.
    - **예외 허용 (눌림목)**: 하락 추세(현재가 < 20일 선)라도, **RSI가 50 미만**이면 "과매도/눌림목" 구간으로 판단하여 **통과시킴**.

## 3. AI 심층 분석 (AI Analyzer)
기술적 필터를 통과한 종목은 Gemini/GPT 모델이 심층 분석합니다.

- **분석 입력**: 기술적 지표(이평선, RSI, 볼린저밴드 등) + 최근 뉴스 헤드라인
- **판단 기준**:
    - **점수(Score)**: 0~100점 부여. **70점 이상**일 때 매수 고려.
    - **전략**: 단순 추세 추종뿐만 아니라, **눌림목(Dip Buying)** 및 **반등(Reversal)** 패턴을 적극적으로 찾도록 프롬프트가 설정됨.
    - **위험 관리**: "Chasing Highs"(고점 추격 매수)는 감점 요인.

## 4. 자산 배분 및 주문 실행 (Trade Manager)
AI 점수가 70점 이상인 종목에 대해 매수를 진행합니다.

- **예산 확인**:
    - USD(달러) 잔고를 우선 사용.
    - **통합 증거금(Integrated Margin)**: 달러가 부족하더라도 원화(KRW) 예수금이 충분하면, 이를 담보로 주문 가능 여부를 계산하여 진행.
- **주문 집행**:
    - **지정가(Limit Order)**: 현재가(매도 1호가)로 주문 접수.
    - **슬롯 제한**: 최대 보유 종목 수(기본 3~5개) 내에서만 신규 매수 진행.

## 5. 매도 및 청산
- **익절/손절**: AI가 설정한 목표가(Target) 및 손절가(Stop Loss)에 도달하면 자동 매도.
- **장마감 청산**: 오버나잇(Overnight) 홀딩 결정이 없는 종목은 장 종료 20분 전(05:40)에 일괄 청산 시도.

## 6. 대상 종목 리스트 (US Universe)
봇은 아래 정의된 **주요 우량주 및 ETF (약 60개)**를 대상으로 매매를 수행합니다. (유동성과 변동성이 확보된 종목 엄선)

### 💎 Mega Cap & Tech (빅테크)
- **NVDA** (NVIDIA), **TSLA** (Tesla), **AAPL** (Apple), **MSFT** (Microsoft)
- **GOOGL** (Alphabet), **AMZN** (Amazon), **META** (Meta)

### 🔌 Semiconductors (반도체)
- **AMD**, **INTC** (Intel), **MU** (Micron), **AVGO** (Broadcom), **QCOM** (Qualcomm)
- **AMAT** (Applied Materials), **LRCX** (Lam Research)

### ☁️ Software / Cloud / AI
- **PLTR** (Palantir), **SNOW** (Snowflake), **CRWD** (CrowdStrike), **NET** (Cloudflare), **DDOG** (Datadog)
- **ZM** (Zoom), **DOCU** (DocuSign), **U** (Unity)

### 🚗 EV / Auto (전기차)
- **RIVN** (Rivian), **LCID** (Lucid), **NIO**, **F** (Ford), **GM** (General Motors)

### 💸 Fintech / Finance
- **SOFI**, **HOOD** (Robinhood), **COIN** (Coinbase), **SQ** (Block), **PYPL** (PayPal)
- **BAC** (Bank of America), **JPM** (JPMorgan)

### 🪙 Crypto Miners (크립토 관련주)
- **MARA** (Marathon Digital), **RIOT** (Riot Platforms), **CLSK** (CleanSpark)

### 📱 Consumer / Platform
- **UBER**, **LYFT**, **DASH** (DoorDash), **ABNB** (Airbnb), **SHOP** (Shopify)
- **NFLX** (Netflix), **DIS** (Disney), **SNAP**, **SPOT** (Spotify), **RBLX** (Roblox)
- **DKNG** (DraftKings), **PENN** (Penn Entertainment)

### ⚡ Energy (에너지)
- **XOM** (Exxon Mobil), **CVX** (Chevron), **OXY** (Occidental)

### 🧬 Bio / Pharma (바이오)
- **PFE** (Pfizer), **MRNA** (Moderna), **BNTX** (BioNTech)

### ✈️ Travel / Leisure (여행/항공)
- **AAL** (American Airlines), **UAL** (United), **DAL** (Delta)
- **CCL** (Carnival), **NCLH** (Norwegian Cruise)

