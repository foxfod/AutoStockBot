import google.generativeai as genai
from openai import AsyncOpenAI
import json
from app.core.config import settings
import logging
import asyncio

logger = logging.getLogger(__name__)

class AIAnalyzer:
    def __init__(self):
        # Initialize OpenAI (Fallback) - Async Client
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.gpt_model = settings.GPT_MODEL
        
        # Initialize Gemini (Primary)
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.gemini_model = genai.GenerativeModel(settings.GEMINI_MODEL)
            logger.info(f"Gemini initialized with model: {settings.GEMINI_MODEL}")
        else:
            self.gemini_model = None
            logger.warning("Gemini API Key not found. Using GPT only.")

    async def analyze_stock(self, stock_name: str, news_list: list[str], tech_summary: dict, market_ctx: str = "Neutral") -> dict:
        """
        Analyze stock using GPT (Primary) -> Gemini (Fallback) [Async].
        """
        prompt = self._create_prompt(stock_name, news_list, tech_summary, market_ctx)
        
        # 1. Try GPT (Primary)
        try:
            return await self._analyze_with_gpt(prompt)
        except Exception as e:
            logger.error(f"GPT Analysis Failed: {e}. Switching to Gemini...")
            
        # 2. Fallback to Gemini
        if self.gemini_model:
            try:
                logger.info(f"Analyzing {stock_name} with Gemini (Fallback)...")
                # Gemini Async Call
                response = await self.gemini_model.generate_content_async(
                    prompt,
                    generation_config={"response_mime_type": "application/json"}
                )
                return json.loads(self._clean_json_text(response.text))
            except Exception as e:
                logger.error(f"Gemini Analysis Failed: {e}")
        
        return {"score": 50, "reason": "AI Analysis Failed (Both Models)", "action": "Pass", "strategy": {}}

    async def _analyze_with_gpt(self, prompt: str) -> dict:
        logger.info(f"Analyzing with GPT ({self.gpt_model})...")
        response = await self.openai_client.chat.completions.create(
            model=self.gpt_model,
            messages=[
                {"role": "system", "content": "You are a professional stock trader analyzing news for scalping opportunities."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(self._clean_json_text(content))

    def _create_prompt(self, stock_name: str, news_list: list[str], tech_summary: dict, market_ctx: str) -> str:
        if not news_list:
            news_text = "No recent news."
        else:
            news_text = json.dumps(news_list, ensure_ascii=False)

        return f"""
        Analyze the following stock '{stock_name}' for potential UPSIDE TODAY based on Market Context & News.
        
        [Market Context]
        {market_ctx}
        
        [Technical Indicators]
        - Close: {tech_summary.get('close')}
        - Trend (vs 20MA): {tech_summary.get('trend')}
        - SMA5 vs SMA20: {"Bullish" if tech_summary.get('sma_5', 0) > tech_summary.get('sma_20', 0) else "Bearish"}
        - RSI (14): {tech_summary.get('rsi')}
        - Volatility: {tech_summary.get('volatility')}%
        
        [Recent News]
        {news_text}
        
        Task:
        1. Evaluate if this stock is likely to OUTPERFORM today given the Market Context.
        2. IF Market is Bearish/Down -> Be Conservative. Look for Defensive stocks or Short Candidates (if applicable).
        3. IF Market is Bullish/Up -> Look for Momentum/Breakout stocks.
        4. **CRITICAL**: IF Daily Change > 20%, REJECT (Score < 50) due to "Chasing Highs".
        5. IF RSI is > 75, penalize score (Risk of top).
        6. IF SMA5 < SMA20, Penalize Score UNLESS looking for "Dip Buy" or "Reversal".
        7. Look for "Pullback" or "Early Uptrend" patterns. Avoid "Vertical Spikes".
        
        Return JSON format ONLY:
        {{
            "score": <0-100 integer, 80+ Strong Buy>,
            "reason": "<Korean explanation, max 2 sentences. Mention Market Context impact. Must be in Korean (Hangul)>",
            "action": "<Buy/Watch/Pass>",
            "strategy": {{
                "entry": "<Suggestion>",
                "target_price": <Target profit %>,
                "stop_loss": <Stop loss %>
            }}
        }}
        """

    async def analyze_risk(self, symbol: str, current_price: float, buy_price: float, tech_summary: dict, news_titles: list) -> dict:
        """
        Analyze whether to HOLD or SELL a losing position [Async].
        """
        pnl = ((current_price - buy_price) / buy_price) * 100
        news_text = json.dumps(news_titles, ensure_ascii=False) if news_titles else "No recent breaking news."
        
        prompt = f"""
        You are a Risk Manager for a scalping bot.
        We hold '{symbol}'.
        - Buy Price: {buy_price}
        - Current Price: {current_price}
        - P&L: {pnl:.2f}% (Loss)
        
        [Technical Context (Daily)]
        - Trend: {tech_summary.get('trend')}
        - RSI: {tech_summary.get('rsi')}
        - SMA5 vs SMA20: {"Bullish" if tech_summary.get('sma_5', 0) > tech_summary.get('sma_20', 0) else "Bearish"}
        
        [Breaking News]
        {news_text}
        
        Task:
        Determine if we should STOP LOSS immediately or HOLD for recovery.
        - If News is negative (e.g. Earnings Miss, Lawsuit, Delisting), signal SELL.
        - If Chart is breaking major support/trend is clearly DOWN, signal SELL.
        - If just normal volatility, HOLD.
        
        Return JSON ONLY:
        {{
            "decision": "SELL" or "HOLD",
            "reason": "Short explanation (Must be in Korean/Hangul)"
        }}
        """
        
        # 1. GPT
        try:
            res = await self.openai_client.chat.completions.create(
                model=self.gpt_model,
                messages=[{"role": "system", "content": "Risk Manager Mode."}, {"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            return json.loads(self._clean_json_text(res.choices[0].message.content))
        except Exception as e:
            logger.error(f"GPT Risk Analysis Failed: {e}. Switching to Gemini...")
            
        # 2. Gemini
        if self.gemini_model:
            try:
                res = await self.gemini_model.generate_content_async(prompt, generation_config={"response_mime_type": "application/json"})
                return json.loads(self._clean_json_text(res.text))
            except Exception as e:
                logger.error(f"Gemini Risk Analysis Failed: {e}")
                
        return {"decision": "HOLD", "reason": "AI Error (Default Hold)"}
            
    async def analyze_stocks_batch(self, jobs: list) -> dict:
        """
        Analyze multiple stocks in one request to save API calls/Cost [Async].
        """
        if not jobs:
            return {}
            
        # Construct Batch Prompt
        market_context = jobs[0].get('market_status', 'Neutral Market')
        
        prompt = f"Current Market Environment: {market_context}\n\n"
        prompt += "Analyze the following stocks for scalping opportunities at market open.\n"
        prompt += "Return a JSON Object where keys are 'symbols' and values are analysis results.\n"
        prompt += "Format: { 'SYMBOL': { 'score': ..., 'reason': ..., 'action': ..., 'strategy': ... } }\n\n"
        
        for job in jobs:
            daily_change = job['tech_summary'].get('daily_change', 0.0)
            prompt += f"--- Stock: {job['name']} ({job['symbol']}) ---\n"
            prompt += f"Price: {job['tech_summary']['close']} (Change: {daily_change:.2f}%)\n"
            prompt += f"Technical: Trend={job['tech_summary']['trend']}, RSI={job['tech_summary']['rsi']}, Volatility={job['tech_summary']['volatility']}%\n"
            prompt += f"News: {job['news_titles']}\n\n"
            
        prompt += """
        Criteria:
        1. Score 0-100 (80+ Strong Buy, 60+ Watch, <60 Pass).
        2. Market Context Adaptation:
           - IF Market is "BEAR" or "Down": Be VERY CONSERVATIVE. Require strong news catalyst. Score < 70 if no news.
           - IF Market is "BULL" or "Up": Focus on momentum.
        3. Daily Change Penalties:
           - IF > 20%: REJECT (Too high risk of reversal). Score MUST be < 60.
           - IF > 15%: Apply CAUTION.
        4. IF SMA5 < SMA20:
           - Generally bearish, BUT allow "Dip Buying" if RSI < 40 or Reversal Pattern detected.
           - If no reversal signal, Penalize Score.
        5. Favor "Dip Buying" (Pullback by -1~-3% after breakout) over "Market Order at High".
        6. "reason" MUST be in Korean (Hangul).
        """
        
        # Call GPT (Primary) -> Gemini (Fallback)
        response_text = ""
        used_model = "GPT"
        
        try:
            logger.info(f"Batch Analyzing {len(jobs)} stocks with GPT ({self.gpt_model})...")
            res = await self.openai_client.chat.completions.create(
                model=self.gpt_model,
                messages=[
                    {"role": "system", "content": "You are a professional stock trader."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            response_text = res.choices[0].message.content
            
        except Exception as e:
            logger.error(f"GPT Batch Analysis Failed: {e}. Switching to Gemini...")
            used_model = "Gemini"
            
            if self.gemini_model:
                try:
                    logger.info(f"Batch Analyzing {len(jobs)} stocks with Gemini...")
                    res = await self.gemini_model.generate_content_async(
                        prompt, 
                        generation_config={"response_mime_type": "application/json"}
                    )
                    response_text = res.text
                except Exception as g_e:
                    logger.error(f"Gemini Batch Analysis Failed: {g_e}")
                    return {}
            else:
                logger.error("Gemini model not initialized.")
                return {}

        try:
            parsed = json.loads(self._clean_json_text(response_text))
            
            # Normalize Result to Dict { 'SYMBOL': { ... } }
            results = {}
            if isinstance(parsed, list):
                # AI returned a list of objects
                for item in parsed:
                    sym = item.get('symbol')
                    if sym: results[sym] = item
            elif isinstance(parsed, dict):
                # Check if nested
                if "stocks" in parsed and isinstance(parsed["stocks"], list):
                    for item in parsed["stocks"]:
                        sym = item.get('symbol')
                        if sym: results[sym] = item
                elif "results" in parsed and isinstance(parsed["results"], list):
                    for item in parsed["results"]:
                        sym = item.get('symbol')
                        if sym: results[sym] = item
                else:
                    # Assume formatted as requested { 'SYMBOL': ... }
                    results = parsed
            
            # Final Validation: Ensure all values are dicts
            cleaned_results = {}
            for k, v in results.items():
                if isinstance(v, dict):
                    cleaned_results[k] = v
                elif isinstance(v, str):
                    try:
                        # Try to fix "double encoded" json or just string garbage
                        v_parsed = json.loads(self._clean_json_text(v))
                        if isinstance(v_parsed, dict):
                            cleaned_results[k] = v_parsed
                        else:
                            logger.warning(f"Batch Item {k} parsed but not dict: {v_parsed}")
                    except:
                         logger.warning(f"Batch Item {k} is string and parse failed: {v}")
                else:
                    logger.warning(f"Batch Item {k} invalid type: {type(v)}")
            
            return cleaned_results
            
        except Exception as e:
            logger.error(f"Batch Analysis Parsing Failed ({used_model}): {e}")
            return {}

    async def analyze_holding_stock(self, symbol: str, stock_name: str, tech_summary: dict, news_list: list) -> str:
        """
        Generate a detailed analysis report for a held stock [Async].
        """
        news_text = json.dumps(news_list, ensure_ascii=False) if news_list else "최근 주요 뉴스 없음."
        
        prompt = f"""
        당신은 전문 주식 트레이더이자 리스크 관리자입니다.
        현재 보유 중인 종목 '{stock_name} ({symbol})'에 대한 상세 분석 리포트를 작성해주세요.
        
        [기술적 지표]
        - 현재가: {tech_summary.get('close')}
        - 추세 (vs 20MA): {tech_summary.get('trend')}
        - RSI (14): {tech_summary.get('rsi')}
        - 변동성: {tech_summary.get('volatility')}%
        - 거래량 변화: {tech_summary.get('volume_change')}% 이
        
        [최근 뉴스]
        {news_text}
        
        [작성 요청 사항]
        1. **종목 개요 및 뉴스 분석**: 최근 뉴스가 주가에 미치는 영향 (호재/악재) 요약.
        2. **기술적 분석**: 현재 추세와 보조지표(RSI, 이평선)를 기반으로 한 상승/하락 가능성 진단.
        3. **대응 전략**: 
            - 현재가 기준 강력 홀딩, 분할 매도, 또는 전량 매도 추천.
            - 단기 목표가 및 손절가 재조정 제안.
        4. **결론**: 한 줄 요약.
        
        *반드시 한국어로 작성하고, 가독성 좋은 마크다운(Markdown) 형식으로 출력해주세요.*
        """
        
        # 1. GPT
        try:
            logger.info(f"Generating Analysis Report for {stock_name} with GPT...")
            res = await self.openai_client.chat.completions.create(
                model=self.gpt_model,
                messages=[
                    {"role": "system", "content": "You are a helpful financial analyst."},
                    {"role": "user", "content": prompt}
                ]
            )
            return res.choices[0].message.content
        except Exception as e:
            logger.error(f"GPT Report Gen Failed: {e}. Switching to Gemini...")
            
        # 2. Gemini
        if self.gemini_model:
            try:
                res = await self.gemini_model.generate_content_async(prompt)
                return res.text
            except Exception as e:
                logger.error(f"Gemini Report Gen Failed: {e}")
                return "AI 분석 서비스 일시적 오류. 잠시 후 다시 시도해주세요."
        
        return "AI 모델을 사용할 수 없습니다."

    async def recommend_trend_stocks(self, news_titles: list, market_type: str = "KR") -> list:
        """
        Analyze news headlines and recommend TOP 5-10 stocks that benefit from the news.
        Returns: [{"name": "StockName", "code": "000000", "reason": "Why"}]
        """
        if not news_titles: return []
        
        news_str = "\n".join(f"- {t}" for t in news_titles)
        
        prompt = f"""
        You are a seasoned stock market analyst. 
        Given the following latest market news headlines ({market_type}),
        Identify the **Top 5 most promising stocks** that will benefit TODAY.
        
        [Recent News]
        {news_str}
        
        Task:
        1. Extract relevant sectors/themes (e.g. AI, Semiconductor, Bio, Batteries).
        2. Identify specific 'Leader Stocks' (대장주) for those themes.
        3. Even if the stock is not explicitly named in the news, infer the beneficiary based on sector news.
        4. Provide the stock Name and Code (if known). 
           - For KR, try to provide 6-digit code. If unknown, leave empty or 000000.
           - For US, provide Ticker Symbol (e.g. NVDA, TSLA).
        
        Output JSON Format ONLY:
        [
          {{ "name": "Stock Name", "code": "Ticker/Code", "reason": "Brief reason based on news" }},
          ...
        ]
        """
        
        try:
            # Call GPT (Primary)
            res = await self.openai_client.chat.completions.create(
                model=self.gpt_model,
                messages=[
                    {"role": "system", "content": "You are a professional stock analyst."},
                    {"role": "user", "content": prompt}
                ]
            )
            response_text = res.choices[0].message.content
            
            # Simple cleanup
            response_text = self._clean_json_text(response_text)
            import json
            data = json.loads(response_text)
            
            # Validate format
            valid_list = []
            if isinstance(data, list):
                for item in data:
                    if 'name' in item:
                        valid_list.append(item)
            return valid_list
            
        except Exception as e:
            logger.error(f"Trend Analysis Error: {e}")
            return []

    def _clean_json_text(self, text: str) -> str:
        if not text: return "{}"
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    async def analyze_overnight_potential(self, symbol: str, current_price: float, buy_price: float, tech_summary: dict, news_titles: list) -> dict:
        """
        Analyze if we should HOLD this stock overnight (Gap-Up Potential).
        """
        pnl = ((current_price - buy_price) / buy_price) * 100
        news_text = json.dumps(news_titles, ensure_ascii=False) if news_titles else "No recent breaking news."
        
        prompt = f"""
        You are a Swing Trading Expert.
        We are considering holding '{symbol}' overnight instead of selling at market close.
        
        [Current Status]
        - P&L: {pnl:.2f}%
        - Current Price: {current_price}
        
        [Technical Context]
        - Trend: {tech_summary.get('trend')}
        - RSI: {tech_summary.get('rsi')}
        - Daily Change: {tech_summary.get('daily_change', 0):.2f}%
        
        [News/Catalyst]
        {news_text}
        
        Task:
        Predict if this stock is likely to GAP UP tomorrow.
        Conditions for HOLD:
        1. Strong Upward Trend OR Clear Reversal Signal (e.g. Hammer at support).
        2. Positive News Catalyst that is not fully priced in.
        3. P&L is positive OR Loss is recoverable ( > -3%).
        
        If it looks weak or risky, signal LIQUIDATE.
        
        Return JSON ONLY:
        {{
            "decision": "HOLD" or "LIQUIDATE",
            "reason": "Brief explanation in Korean (Hangul)"
        }}
        """
        
        # 1. GPT
        try:
            res = await self.openai_client.chat.completions.create(
                model=self.gpt_model,
                messages=[{"role": "system", "content": "Swing Trader Mode."}, {"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            return json.loads(self._clean_json_text(res.choices[0].message.content))
        except Exception as e:
            logger.error(f"GPT Overnight Analysis Failed: {e}. Switching to Gemini...")
            
        # 2. Gemini
        if self.gemini_model:
            try:
                res = await self.gemini_model.generate_content_async(prompt, generation_config={"response_mime_type": "application/json"})
                return json.loads(self._clean_json_text(res.text))
            except Exception as e:
                logger.error(f"Gemini Overnight Analysis Failed: {e}")
                
        return {"decision": "LIQUIDATE", "reason": "AI Error (Safety Liquidate)"}

    async def analyze_hot_trends(self, jobs: list) -> dict:
        """
        Analyze stocks for 'Top 10 Hot Trends' (Pure AI, No Technical Filter).
        Prioritize: News Catalyst, Sector Strength, Momentum (Even if High RSI).
        """
        if not jobs:
            return {}
            
        # Construct Batch Prompt
        market_context = jobs[0].get('market_status', 'Neutral Market')
        
        prompt = f"Current Market Environment: {market_context}\n\n"
        prompt += "Identify the TOP 'HOT' stocks from the list below for a 'Must Watch' list.\n"
        prompt += "Focus on: 1. Strong News/Catalyst 2. Sector Rotation 3. Explostive Momentum.\n"
        prompt += "**IGNORE Technical Overbought signals (RSI > 75 is OK for Hot stocks).**\n"
        
        prompt += "Return JSON: { 'SYMBOL': { 'score': <0-100, Hotness>, 'reason': '<Korean explanation>' } }\n\n"
        
        for job in jobs:
            daily_change = job['tech_summary'].get('daily_change', 0.0)
            prompt += f"--- Stock: {job['name']} ({job['symbol']}) ---\n"
            prompt += f"Change: {daily_change:.2f}%\n"
            prompt += f"Technical: Trend={job['tech_summary']['trend']}, RSI={job['tech_summary']['rsi']}\n"
            prompt += f"News: {job['news_titles']}\n\n"
            
        prompt += """
        Criteria:
        1. Score based on 'Excitement' and 'Potential for today'. 
           - Good Earnings/Contract News = 90+
           - Strong Sector Move (e.g. AI Rally) = 80+
           - Just momentum without news = 70+
           - Bad News / Boring = < 50
        2. Describe the 'Reason' engagingly in Korean (e.g. 'AI 섹터 수급 폭발', '실적 서프라이즈').
        """
        
        # Call AI (GPT -> Gemini)
        response_text = ""
        try:
            logger.info(f"Hot Trend Analysis for {len(jobs)} stocks (GPT)...")
            res = await self.openai_client.chat.completions.create(
                model=self.gpt_model,
                messages=[{"role": "system", "content": "You are a momentum trader."}, {"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            response_text = res.choices[0].message.content
        except Exception as e:
            logger.error(f"GPT Hot Trend Failed: {e}. Switching to Gemini...")
            if self.gemini_model:
                try:
                    res = await self.gemini_model.generate_content_async(prompt, generation_config={"response_mime_type": "application/json"})
                    response_text = res.text
                except Exception as g_e:
                    logger.error(f"Gemini Hot Trend Failed: {g_e}")
                    return {}
            else:
                return {}

        # Parse
        try:
             return json.loads(self._clean_json_text(response_text))
        except:
             logger.error("Failed to parse Hot Trend JSON")
             return {}

    async def select_candidates_by_trend(self, stock_list: list, market_ctx: str) -> list:
        """
        [Top-Down Optimization]
        Select Top 15 candidates from the universe based on Market Context & Sector Rotation.
        Returns: List of symbols (e.g. ['NVDA', 'TSLA', ...])
        """
        # Format list for prompt
        stocks_str = ", ".join([f"{s['name']}({s['symbol']})" for s in stock_list])
        
        prompt = f"""
        You are a Global Macro Strategist.
        
        [Current Market Context]
        {market_ctx}
        
        [Candidate Universe]
        {stocks_str}
        
        Task:
        1. Based on the Market Context (e.g. Inflation, AI Boom, War, Rate Cuts),
        2. Select the **Top 15 Stocks** from the list that are most likely to have high volatility or momentum TODAY.
        3. Logic:
           - If Tech is rallying, pick NVDA, AMD, SOXL, etc.
           - If Defensive, pick XOM, PFE, KO.
           - If Tesla is newsy, pick TSLA, RIVN.
           
        Return JSON ONLY:
        {{
            "selected_symbols": ["SYM1", "SYM2", ...],
            "reason": "Brief strategy summary"
        }}
        """
        
        try:
            logger.info("🤖 AI Pre-Filtering Candidates (Top-Down)...")
            res = await self.openai_client.chat.completions.create(
                model=self.gpt_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            data = json.loads(self._clean_json_text(res.choices[0].message.content))
            selected = data.get('selected_symbols', [])
            logger.info(f"✅ AI Selected {len(selected)} candidates: {selected}")
            return selected
            
        except Exception as e:
            logger.error(f"AI Pre-Filter Failed: {e}")
            # Fallback: Return first 10 stocks or safe defaults
            return [s['symbol'] for s in stock_list[:15]]


    async def analyze_market_context_and_pick_top10(self, market_type: str, market_status: dict, news_titles: list) -> dict:
        """
        [Stock Selection v2]
        Analyze Market Context + News -> Generate Top 10 Picks (JSON).
        """
        trend = market_status.get('trend', 'Neutral')
        desc = market_status.get('description', 'Flat')
        
        news_str = "\n".join([f"- {t}" for t in news_titles]) if news_titles else "No major news."
        
        prompt = f"""
        You are a Top-Tier Fund Manager with 20 years of experience.
        Your goal is to select the **Top 10 Most Promising Stocks** for TODAY's trading session in the **{market_type} Market**.
        
        [Current Market Status]
        - Trend: {trend} ({desc})
        - Date: {market_status.get('data', {}).get('date', 'Today')}
        
        [Latest Headlines]
        {news_str}
        
        [Task]
        1. **Analyze Context**: Based on the news and market trend, determine the 'Key Themes' (e.g. AI Rally, Rate Cut Hopes, War Fear).
        2. **Select Stocks**: Identify 10 stocks that will benefit MOST from these themes.
           - If Market is BULL: Pick High Beta / Momentum Leaders.
           - If Market is BEAR: Pick Defensive / Dividend / Inverse ETFs (if applicable).
        3. **Criteria**:
           - Must be a valid traded symbol in {market_type}.
           - For KR: Use 6-digit code if possible (e.g. 005930).
           - For US: Use Ticker (e.g. NVDA).
           
        [Output Format (JSON Compliance is CRITICAL)]
        {{
            "market_summary": {{
                "outlook": "Bullish/Bearish/Neutral",
                "key_issues": ["Issue 1", "Issue 2"],
                "strategy": "Your comprehensive trading strategy for today (Korean)"
            }},
            "top_sectors": [
                {{ "sector_name": "Sector Name", "reason": "Why moving today", "related_stocks": ["Stock A", "Stock B"] }}
            ],
            "top_10_picks": [
                {{
                    "stock_name": "Stock Name",
                    "ticker": "Symbol/Code",
                    "selection_reason": "One line reason (Korean)",
                    "expected_open_price": <Estimated Open Price or 0>,
                    "target_price_today": <Target Price or 0>
                }}
                // ... Exactly 10 items
            ]
        }}
        """
        
        try:
            logger.info(f"AI Generating Top 10 for {market_type}...")
            
            # 1. GPT Analysis
            res = await self.openai_client.chat.completions.create(
                model=self.gpt_model,
                messages=[
                    {"role": "system", "content": "You are a professional fund manager. Output JSON only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            data = json.loads(self._clean_json_text(res.choices[0].message.content))
            return data
            
        except Exception as e:
            logger.error(f"GPT Top 10 Generation Failed: {e}")
            # Fallback to Gemini?
            if self.gemini_model:
                try:
                    logger.info("Switching to Gemini for Top 10...")
                    res = await self.gemini_model.generate_content_async(
                        prompt, 
                        generation_config={"response_mime_type": "application/json"}
                    )
                    return json.loads(self._clean_json_text(res.text))
                except Exception as g_e:
                    logger.error(f"Gemini Top 10 Generation Failed: {g_e}")
                    
            return {}



ai_analyzer = AIAnalyzer()
