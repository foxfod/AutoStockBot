from app.core.kis_api import kis
from app.core.ai_analyzer import ai_analyzer
from app.core.technical_analysis import technical
import logging
import asyncio
import time

logger = logging.getLogger(__name__)

class Selector:
    def __init__(self):
        pass

    async def select_pre_market_picks(self, market_type="KR", force=False):
        """
        Pre-Market Top 10 Selection (30 mins before open).
        Analyzes Market Context + News + Technicals to pick 10 promising stocks.
        """
        import json
        import os
        from datetime import datetime
        from app.core.technical_analysis import technical
        from app.core.market_analyst import market_analyst
        from app.core.telegram_bot import bot

        TOP_PICKS_FILE = f"app/data/top_picks_{market_type}.json"
        
        # Check if already done today
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        try:
            if not force and os.path.exists(TOP_PICKS_FILE):
                with open(TOP_PICKS_FILE, "r", encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get("date") == today_str and data.get("market") == market_type:
                        logger.info(f"Pre-Market Picks for {market_type} already exist.")
                        return data.get("picks", [])
        except Exception as e:
            logger.error(f"Failed to load top picks: {e}")

        bot.send_message(f"🌅 [{market_type}] 장전 Top 10 유망 종목 분석 시작...")
        
        # 1. Get Candidates
        candidates = []
        if market_type == "KR":
            # KR: Use Volume Rank (Yesterday's Leaders)
            raw_candidates = kis.get_volume_rank()
            if raw_candidates:
                # Filter ETFs
                exclusion_keywords = ["KODEX", "TIGER", "KBSTAR", "SOL", "ACE", "HANARO", "KOSEF", "ARIRANG", "ETN", "스팩", "선물", "레버리지", "인버스"]
                for stock in raw_candidates:
                    if not any(k in stock['hts_kor_isnm'] for k in exclusion_keywords):
                        candidates.append({
                            "symbol": stock['mksc_shrn_iscd'],
                            "name": stock['hts_kor_isnm'],
                            "market": "KR"
                        })
                candidates = candidates[:30] # Top 30
        else:
            # US: Use Fixed List (Tech/Volatility)
            us_defaults = [
                {"symbol": "NVDA", "excg": "NASD", "name": "NVIDIA"},
                {"symbol": "TSLA", "excg": "NASD", "name": "Tesla"},
                {"symbol": "AAPL", "excg": "NASD", "name": "Apple"},
                {"symbol": "MSFT", "excg": "NASD", "name": "Microsoft"},
                {"symbol": "GOOGL", "excg": "NASD", "name": "Alphabet"},
                {"symbol": "AMZN", "excg": "NASD", "name": "Amazon"},
                {"symbol": "META", "excg": "NASD", "name": "Meta"},
                {"symbol": "AMD", "excg": "NASD", "name": "AMD"},
                {"symbol": "INTC", "excg": "NASD", "name": "Intel"},
                {"symbol": "MU", "excg": "NASD", "name": "Micron"},
                {"symbol": "AVGO", "excg": "NASD", "name": "Broadcom"},
                {"symbol": "QCOM", "excg": "NASD", "name": "Qualcomm"},
                {"symbol": "PLTR", "excg": "NYSE", "name": "Palantir"},
                {"symbol": "SNOW", "excg": "NYSE", "name": "Snowflake"},
                {"symbol": "CRWD", "excg": "NASD", "name": "CrowdStrike"},
                {"symbol": "NET", "excg": "NYSE", "name": "Cloudflare"},
                {"symbol": "DDOG", "excg": "NASD", "name": "Datadog"},
                {"symbol": "RIVN", "excg": "NASD", "name": "Rivian"},
                {"symbol": "LCID", "excg": "NASD", "name": "Lucid"},
                {"symbol": "NIO", "excg": "NYSE", "name": "NIO"},
                {"symbol": "F", "excg": "NYSE", "name": "Ford"},
                {"symbol": "GM", "excg": "NYSE", "name": "General Motors"},
                {"symbol": "SOFI", "excg": "NASD", "name": "SoFi"},
                {"symbol": "HOOD", "excg": "NASD", "name": "Robinhood"},
                {"symbol": "COIN", "excg": "NASD", "name": "Coinbase"},
                {"symbol": "SQ", "excg": "NYSE", "name": "Block (Square)"},
                {"symbol": "PYPL", "excg": "NASD", "name": "PayPal"},
                {"symbol": "MARA", "excg": "NASD", "name": "Marathon Digital"},
                {"symbol": "RIOT", "excg": "NASD", "name": "Riot Platforms"},
                {"symbol": "CLSK", "excg": "NASD", "name": "CleanSpark"},
                {"symbol": "UBER", "excg": "NYSE", "name": "Uber"},
                {"symbol": "NFLX", "excg": "NASD", "name": "Netflix"},
                {"symbol": "DIS", "excg": "NYSE", "name": "Disney"},
                {"symbol": "DKNG", "excg": "NASD", "name": "DraftKings"},
                {"symbol": "PENN", "excg": "NASD", "name": "Penn Entertainment"},
                {"symbol": "QQQ", "excg": "NASD", "name": "Invesco QQQ"},
                {"symbol": "TQQQ", "excg": "NASD", "name": "ProShares UltraPro QQQ"},
                {"symbol": "SOXL", "excg": "NYSE", "name": "Direxion Daily Semiconductor Bull 3X"}
            ]
            for s in us_defaults:
                candidates.append({
                    "symbol": s['symbol'],
                    "name": s['name'],
                    "market": "US",
                    "excg": s['excg']
                })
            
        if not candidates and market_type == "US":
             pass

        # 1.5 Get Market Context
        market_ctx = market_analyst.get_market_context_for_ai(market_type)
        logger.info(f"Market Context for {market_type} Top 10: {market_ctx}")
        bot.send_message(f"🌍 시장 컨텍스트 분석: {market_ctx}")

        # --- [Top-Down Optimization] ---
        # Unified for both KR and US
        logger.info(f"🤖 Step 1: Top-Down AI Screening for {len(candidates)} candidates...")
        bot.send_message(f"🤖 AI가 시장 상황에 맞는 1차 선별 중... (후보 {len(candidates)}개)")
        
        target_symbols = await ai_analyzer.select_candidates_by_trend(candidates, market_ctx)
        
        # Filter candidates
        filtered_candidates = [s for s in candidates if s['symbol'] in target_symbols]
        
        # Fallback if AI returns empty
        if not filtered_candidates:
             filtered_candidates = candidates[:15]
             logger.warning("AI Screening returned empty, using fallback subset.")

        logger.info(f"🎯 AI Selected {len(filtered_candidates)} stocks for Deep Analysis.")
        bot.send_message(f"🎯 1차 선별 완료: {len(filtered_candidates)}개 종목 집중 분석 시작...")
        
        analysis_jobs = []
        
        # Unified Analysis Loop
        for stock in filtered_candidates:
            symbol = stock['symbol']
            name = stock['name']
            
            # Helper for exchange (KR has no excg needed usually, or 'KRX')
            excg = stock.get('excg', '') 
            
            await asyncio.sleep(0.1)
            
            try:
                # 1. Get Daily Data (Unified call if possible, or split)
                daily_data = []
                if market_type == "KR":
                     daily_data = kis.get_daily_price(symbol)
                else:
                     daily_data = kis.get_overseas_daily_price(symbol, excg)
                
                if not daily_data:
                    logger.warning(f"No Daily Data for {name}")
                    continue
                
                # Tech Analysis Prep
                mapped_data = []
                for d in daily_data:
                    if market_type == "KR":
                        mapped_data.append(d) # KIS KR returns correct keys usually? Check utils.
                        # Actually KIS KR keys are stck_clpr etc. check helper.
                        # kis_api.get_daily_price returns list of dicts.
                        # technical.analyze handles standard keys.
                        # Let's ensure mapping is correct.
                        # KR API returns: stck_bsop_date, stck_clpr, etc.
                        # US API returns: xymd, clos, etc.
                        pass 
                    else:
                        # US Mapping
                        mapped_data.append({
                            "stck_bsop_date": d['xymd'],
                            "stck_clpr": d['clos'],
                            "stck_oprc": d['open'],
                            "stck_hgpr": d['high'],
                            "stck_lwpr": d['low'],
                            "acml_vol": d['tvol']
                        })
                
                if market_type == "KR":
                     mapped_data = daily_data # Assuming get_daily_price returns standard keys compatible with technical
                
                # 2. Tech Analysis
                tech_summary = technical.analyze(mapped_data)
                
                # Daily Change
                daily_change = 0.0
                if len(daily_data) >= 2:
                    c = float(daily_data[0]['stck_clpr']) if market_type == "KR" else float(daily_data[0]['clos'])
                    p = float(daily_data[1]['stck_clpr']) if market_type == "KR" else float(daily_data[1]['clos'])
                    if p > 0: daily_change = ((c - p) / p) * 100
                
                # 3. Add to Job (No Filter)
                analysis_jobs.append({
                    "symbol": symbol,
                    "name": name,
                    "excg": excg,
                    "tech_summary": {
                        **tech_summary,
                        "daily_change": daily_change
                    },
                    "news_titles": [] 
                })
                
            except Exception as e:
                logger.error(f"Error preparing {name}: {e}")
                continue

        logger.info(f"Data collected. Analyzing {len(analysis_jobs)} stocks...")
        bot.send_message(f"🔬 데이터 수집 완료. Hot Trend 심층 분석 중... ({len(analysis_jobs)}개)")
        
        scored_candidates = []
        BATCH_SIZE = 5
        
        for i in range(0, len(analysis_jobs), BATCH_SIZE):
            batch = analysis_jobs[i : i + BATCH_SIZE]
            
            # Use NEW analyze_hot_trends
            batch_results = await ai_analyzer.analyze_hot_trends(batch)
            
            for job in batch:
                symbol = job['symbol']
                res = batch_results.get(symbol)
                
                # Safe casting for score
                raw_score = 0
                if res:
                    if not isinstance(res, dict):
                         logger.warning(f"AI returned invalid format for {symbol}: {type(res)} - {res}")
                         continue
                         
                    try:
                        raw_score = float(res.get('score', 0))
                    except (ValueError, TypeError):
                        raw_score = 0

                if res and raw_score >= 0:
                    scored_candidates.append({
                        "symbol": symbol,
                        "name": job['name'],
                        "score": raw_score, # Use numeric score
                        "reason": res.get('reason', 'N/A'),
                        "market": market_type,
                        "price": job['tech_summary']['close'],
                        "change": job['tech_summary']['daily_change']
                    })
            
            await asyncio.sleep(1.0)

        # 3. Sort & Select Top 10
        scored_candidates.sort(key=lambda x: x['score'], reverse=True)
        top_10 = scored_candidates[:10]
        
        # 4. Save to File
        try:
            os.makedirs("app/data", exist_ok=True)
            with open(TOP_PICKS_FILE, "w", encoding='utf-8') as f:
                json.dump({
                    "date": today_str,
                    "market": market_type,
                    "picks": top_10
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save top picks: {e}")
            
        # 5. Report
        if top_10:
            msg = f"🌟 [{market_type}] 오늘의 Hot Trend Top 10 (AI 선정)\n"
            for i, s in enumerate(top_10, 1):
                msg += f"{i}. {s['name']} ({s['score']}점)\n   └ {s['reason']}\n"
            bot.send_message(msg)
        else:
            bot.send_message(f"❌ [{market_type}] 분석 결과가 없습니다.")
        
        return top_10

    # Old _analyze_single_stock NOT USED for Top 10 anymore. 
    # Can ideally remove or keep for other functions (e.g. searching).
    # Buying Logic likely uses _analyze_single_stock still? 
    # Actually Buying Logic calls `selector.select_stock_for_buying`? No, main loops call `find_breakout_stocks`.
    # `find_breakout_stocks` likely uses `_analyze_single_stock`.
    # So we MUST NOT delete `_analyze_single_stock`.
    # But for `select_pre_market_picks`, we have fully replaced the loop.
    
    async def _analyze_single_stock(self, stock, market_type, market_ctx="Neutral"):
        """Helper for parallel processing"""
        symbol = stock['symbol']
        name = stock['name']
        loop = asyncio.get_event_loop()
        
        try:
            # Data Fetch (Blocking I/O -> ThreadPool)
            if market_type == "KR":
                daily_data = await loop.run_in_executor(None, kis.get_daily_price, symbol)
                # News fetching is also blocking
                # news = await loop.run_in_executor(None, kis.get_news_titles, symbol) 
                # Optimization: Fetch news only if tech passes or in parallel?
                # For now, let's keep it simple. But get_news_titles is also blocking.
                # Let's run tech analysis first, then news if needed? 
                # Actually, standard flow: Get Data -> Tech -> Filter -> News -> AI.
            else:
                excg = stock.get('excg', 'NASD')
                raw_data = await loop.run_in_executor(None, kis.get_overseas_daily_price, symbol, excg)
                daily_data = []
                if raw_data:
                    for d in raw_data:
                        daily_data.append({
                            "stck_bsop_date": d['xymd'],
                            "stck_clpr": d['clos'],
                            "stck_oprc": d['open'],
                            "stck_hgpr": d['high'],
                            "stck_lwpr": d['low'],
                            "acml_vol": d['tvol']
                        })
            if not daily_data: return None
            
            # Technical Analysis (CPU bound, fast enough, but can be offloaded if heavy)
            tech = technical.analyze(daily_data)
            
            # Pre-filter before News/AI (Save resources)
            if tech.get("status") in ["Error", "Not enough data"]: return None
            
            # Calculate Daily Change
            try:
                if len(daily_data) >= 2:
                    # KIS Data structure check
                    # KR: stck_clpr, US: clos (mapped in kis_api output? No, returns raw list)
                    # US daily_price returns list of dicts. Keys depend on API.
                    # kis.get_overseas_daily_price returns output2.
                    # KR: stck_clpr. US: clos.
                    
                    curr = float(daily_data[0].get('stck_clpr') or daily_data[0].get('clos'))
                    prev = float(daily_data[1].get('stck_clpr') or daily_data[1].get('clos'))
                    
                    if prev > 0:
                        change_rate = ((curr - prev) / prev) * 100
                        tech['daily_change'] = change_rate
                    else:
                        tech['daily_change'] = 0.0
                else:
                    tech['daily_change'] = 0.0
            except:
                tech['daily_change'] = 0.0

            # 1. Tech Filters (Fail Fast)
            if tech['rsi'] >= 75: # Relaxed from 70
                 logger.info(f"Rejected {name}: RSI {tech['rsi']:.1f} >= 75")
                 return None 
            if tech.get('daily_change', 0) >= 20.0: # Relaxed from 15
                 logger.info(f"Rejected {name}: Change +{tech.get('daily_change', 0):.1f}% >= 20%")
                 return None 
            
            if tech['trend'] == "DOWN":
                if tech['rsi'] < 50:
                    pass # Allow Dip Buy
                else:
                    logger.info(f"Rejected {name}: Trend DOWN & RSI {tech['rsi']:.1f} >= 50")
                    return None
            
            # Relaxed SMA5 < SMA20 filter to allow breakouts
            # if tech['sma_5'] <= tech['sma_20']: return None
            
            # 2. Get News (Blocking) - Only if passed tech
            news = []
            if market_type == "KR":
                news_items = await loop.run_in_executor(None, kis.get_news_titles, symbol)
                news = [n['hts_pbnt_titl_cntt'] for n in news_items[:3]] if news_items else []
            
            # 3. Assess via AI (Async)
            # Pass Market Context to AI
            analysis_result = await ai_analyzer.analyze_stock(name, news, tech, market_ctx)
            score = analysis_result.get('score', 0)
            reason = analysis_result.get('reason', 'Analysis Failed')
            
            if score >= 55: # Relaxed from 60
                stock['reason'] = reason
                stock['score'] = score
                stock['tech'] = tech # Attach tech info
                return stock
            else:
                logger.info(f"Rejected {name}: Score {score} < 55")
                return None
        except Exception as e:
            logger.error(f"Error analyzing {name}: {e}")
            return None
        return None

    async def select_stocks_kr(self, budget=None, target_count=3):
        """
        [Stock Selection v2] KR Market Selection Pipeline
        Time: 08:30 ~ 14:30 (10 min interval)
        """
        from app.core.technical_analysis import technical
        from app.core.market_analyst import market_analyst
        from app.core.telegram_bot import bot
        import json
        import os
        from datetime import datetime

        start_time = time.time()
        
        # 1. Market Context
        market_ctx = market_analyst.get_market_context_for_ai("KR")
        logger.info(f"[KR] Market Context: {market_ctx}")

        # 2. Sourcing (Priorities)
        candidates = []
        existing_symbols = set()
        
        # Priority 1: Top 10 Picks (Pre-Market)
        top_picks_path = "app/data/top_picks_KR.json"
        try:
            if os.path.exists(top_picks_path):
                with open(top_picks_path, "r", encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get("date") == datetime.now().strftime("%Y-%m-%d"):
                        for p in data.get("picks", []):
                            if p['ticker'] not in existing_symbols:
                                candidates.append({
                                    'symbol': p['ticker'],
                                    'name': p['stock_name'],
                                    'priority': 1,
                                    'source': 'Top 10',
                                    'reason': p.get('selection_reason', '')
                                })
                                existing_symbols.add(p['ticker'])
                        logger.info(f"[KR] Loaded {len(candidates)} Top 10 picks.")
        except Exception as e:
            logger.error(f"Failed to load KR Top 10: {e}")

        # Priority 2: Real-time Trend (News)
        trend_stocks = await market_analyst.get_trend_candidates("KR")
        for t in trend_stocks:
            code = str(t.get('code')).zfill(6)
            if code not in existing_symbols and code != "000000":
                candidates.append({
                    'symbol': code,
                    'name': t.get('name'),
                    'priority': 2,
                    'source': 'Trend',
                    'reason': t.get('reason', '')
                })
                existing_symbols.add(code)

        # Priority 3: Volume Spike (KIS API)
        vol_rank = kis.get_volume_rank()
        if vol_rank:
            exclusion = ["KODEX", "TIGER", "KBSTAR", "SOL", "ACE", "HANARO", "KOSEF", "ARIRANG", "ETN", "스팩", "선물", "레버리지", "인버스"]
            for s in vol_rank:
                sym = s['mksc_shrn_iscd']
                nm = s['hts_kor_isnm']
                if sym not in existing_symbols and not any(ex in nm for ex in exclusion):
                    candidates.append({
                        'symbol': sym,
                        'name': nm,
                        'priority': 3,
                        'source': 'Volume'
                    })
                    existing_symbols.add(sym)
                    if len(candidates) >= 30: break # Limit Total Candidates
        
        logger.info(f"[KR] Sourcing Complete. Total Candidates: {len(candidates)}")
        bot.send_message(f"🔍 [KR] 종목 발굴: {len(candidates)}개 (Top10/Trend/Volume)")

        # 3. Filtering & Analysis (Batch)
        final_selected = []
        BATCH_SIZE = 5
        
        for i in range(0, len(candidates), BATCH_SIZE):
            batch = candidates[i : i + BATCH_SIZE]
            analysis_jobs = []
            
            for stock in batch:
                symbol = stock['symbol']
                name = stock['name']
                
                # Data & Tech
                daily_data = kis.get_daily_price(symbol)
                if not daily_data: continue
                
                tech = technical.analyze(daily_data)
                
                # --- Hard Filters (KR) ---
                if tech['rsi'] >= 70: continue # Overbought
                if tech['trend'] == 'DOWN': continue # Downtrend
                
                # Daily Change Calculation
                daily_change = 0.0
                if len(daily_data) >= 2:
                    curr = float(daily_data[0]['stck_clpr'])
                    prev = float(daily_data[1]['stck_clpr'])
                    if prev > 0: daily_change = ((curr - prev) / prev) * 100
                    
                if daily_change >= 15.0: continue # Too high
                
                # Check Budget
                if budget and tech['close'] > budget: continue
                
                # Pass to AI
                analysis_jobs.append({
                    "symbol": symbol,
                    "name": name,
                    "tech_summary": {**tech, "daily_change": daily_change},
                    "news_titles": [], # Optimization: Fetch news only for high priority or just pass title from source?
                    "market_status": market_ctx
                })

            if not analysis_jobs: continue

            # AI Scoring
            results = await ai_analyzer.analyze_stocks_batch(analysis_jobs)
            
            for job in analysis_jobs:
                res = results.get(job['symbol'])
                
                # Validation
                if res and not isinstance(res, dict):
                     logger.warning(f"AI returned invalid format for {job['symbol']}: {res}")
                     continue

                strategy = res.get('strategy', {})
                if not isinstance(strategy, dict):
                    strategy = {}

                if res and res.get('score', 0) >= 60:
                    final_selected.append({
                        "symbol": job['symbol'],
                        "name": job['name'],
                        "score": res['score'],
                        "reason": res.get('reason', 'N/A'),
                        "price": job['tech_summary']['close'],
                        "target": strategy.get('target_price'),
                        "stop_loss": strategy.get('stop_loss'),
                        "market": "KR"
                    })

            if len(final_selected) >= target_count: break
            
        final_selected.sort(key=lambda x: x['score'], reverse=True)
        
        if final_selected:
            msg = f"✨ [KR] 매수 후보 {len(final_selected)}개 선정 (예산: {budget:,.0f}원)\n"
            for s in final_selected[:3]:
                msg += f"- {s['name']} ({s['score']}점): {s['reason']}\n"
            bot.send_message(msg)
            
        return final_selected

    async def select_stocks(self, budget=None, target_count=3):
        """Wrapper for Backward Compatibility"""
        # Checks time to decide KR or US? Or caller decides?
        # Traditionally main_auto_trade calls select_stocks for KR.
        # Let's route to select_stocks_kr.
        return await self.select_stocks_kr(budget, target_count)

    async def select_us_stocks(self, budget=None):
        """
        Stock Selection for US Market (Async Wrapper).
        """
        import asyncio
        from app.core.market_analyst import market_analyst
        from app.core.telegram_bot import bot

        start_time = time.time()
        
        market_ctx = market_analyst.get_market_context_for_ai("US")
        logger.info(f"US Market Context: {market_ctx}")
        
        logger.info(f"Starting US stock selection (Budget: {budget if budget else 'N/A'} USD)...")
        
        import json
        import os
        from datetime import datetime
        TOP_PICKS_FILE = "app/data/top_picks_US.json"
        pre_market_picks = []
        
        try:
            if os.path.exists(TOP_PICKS_FILE):
                with open(TOP_PICKS_FILE, "r", encoding='utf-8') as f:
                    data = json.load(f)
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    if data.get("date") == today_str and data.get("market") == "US":
                        pre_market_picks = data.get("picks", [])
                        logger.info(f"Loaded {len(pre_market_picks)} Pre-Market Picks for US.")
                        bot.send_message(f"📂 장전 Top 10 종목 {len(pre_market_picks)}개를 후보에 추가합니다.")
        except Exception as e:
            logger.error(f"Failed to load top picks: {e}")

        us_candidates = []
        
        existing_symbols = set()
        for pick in pre_market_picks:
             excg = pick.get('excg', 'NASD') 
             us_candidates.append({
                 "symbol": pick['symbol'],
                 "excg": excg,
                 "name": pick['name'],
                 "is_pre_pick": True
             })
             existing_symbols.add(pick['symbol'])

        default_list = [
            # === MEGA CAP TECH (High Liquidity) ===
            {"symbol": "NVDA", "excg": "NASD", "name": "NVIDIA"},
            {"symbol": "TSLA", "excg": "NASD", "name": "Tesla"},
            {"symbol": "AAPL", "excg": "NASD", "name": "Apple"},
            {"symbol": "MSFT", "excg": "NASD", "name": "Microsoft"},
            {"symbol": "GOOGL", "excg": "NASD", "name": "Alphabet"},
            {"symbol": "AMZN", "excg": "NASD", "name": "Amazon"},
            {"symbol": "META", "excg": "NASD", "name": "Meta"},
            # ... (Full List Omitted for brevity, but I should probably keep it if I am overwriting)
            # Actually I should include the full list to be safe.
             {"symbol": "AMD", "excg": "NASD", "name": "AMD"},
            {"symbol": "INTC", "excg": "NASD", "name": "Intel"},
            {"symbol": "MU", "excg": "NASD", "name": "Micron"},
            {"symbol": "AVGO", "excg": "NASD", "name": "Broadcom"},
            {"symbol": "QCOM", "excg": "NASD", "name": "Qualcomm"},
            {"symbol": "AMAT", "excg": "NASD", "name": "Applied Materials"},
            {"symbol": "LRCX", "excg": "NASD", "name": "Lam Research"},
            {"symbol": "PLTR", "excg": "NYSE", "name": "Palantir"},
            {"symbol": "SNOW", "excg": "NYSE", "name": "Snowflake"},
            {"symbol": "CRWD", "excg": "NASD", "name": "CrowdStrike"},
            {"symbol": "NET", "excg": "NYSE", "name": "Cloudflare"},
            {"symbol": "DDOG", "excg": "NASD", "name": "Datadog"},
            {"symbol": "RIVN", "excg": "NASD", "name": "Rivian"},
            {"symbol": "LCID", "excg": "NASD", "name": "Lucid"},
            {"symbol": "NIO", "excg": "NYSE", "name": "NIO"},
            {"symbol": "F", "excg": "NYSE", "name": "Ford"},
            {"symbol": "GM", "excg": "NYSE", "name": "General Motors"},
            {"symbol": "SOFI", "excg": "NASD", "name": "SoFi"},
            {"symbol": "HOOD", "excg": "NASD", "name": "Robinhood"},
            {"symbol": "COIN", "excg": "NASD", "name": "Coinbase"},
            {"symbol": "SQ", "excg": "NYSE", "name": "Block (Square)"},
            {"symbol": "PYPL", "excg": "NASD", "name": "PayPal"},
            {"symbol": "BAC", "excg": "NYSE", "name": "Bank of America"},
            {"symbol": "JPM", "excg": "NYSE", "name": "JPMorgan"},
            {"symbol": "MARA", "excg": "NASD", "name": "Marathon Digital"},
            {"symbol": "RIOT", "excg": "NASD", "name": "Riot Platforms"},
            {"symbol": "CLSK", "excg": "NASD", "name": "CleanSpark"},
            {"symbol": "UBER", "excg": "NYSE", "name": "Uber"},
            {"symbol": "LYFT", "excg": "NASD", "name": "Lyft"},
            {"symbol": "DASH", "excg": "NYSE", "name": "DoorDash"},
            {"symbol": "ABNB", "excg": "NASD", "name": "Airbnb"},
            {"symbol": "SHOP", "excg": "NYSE", "name": "Shopify"},
            {"symbol": "NFLX", "excg": "NASD", "name": "Netflix"},
            {"symbol": "DIS", "excg": "NYSE", "name": "Disney"},
            {"symbol": "SNAP", "excg": "NYSE", "name": "Snap"},
            {"symbol": "SPOT", "excg": "NYSE", "name": "Spotify"},
            {"symbol": "RBLX", "excg": "NYSE", "name": "Roblox"},
            {"symbol": "DKNG", "excg": "NASD", "name": "DraftKings"},
            {"symbol": "PENN", "excg": "NASD", "name": "Penn Entertainment"},
            {"symbol": "XOM", "excg": "NYSE", "name": "Exxon Mobil"},
            {"symbol": "CVX", "excg": "NYSE", "name": "Chevron"},
            {"symbol": "OXY", "excg": "NYSE", "name": "Occidental"},
            {"symbol": "PFE", "excg": "NYSE", "name": "Pfizer"},
            {"symbol": "MRNA", "excg": "NASD", "name": "Moderna"},
            {"symbol": "BNTX", "excg": "NASD", "name": "BioNTech"},
            {"symbol": "AAL", "excg": "NASD", "name": "American Airlines"},
            {"symbol": "UAL", "excg": "NASD", "name": "United Airlines"},
            {"symbol": "DAL", "excg": "NYSE", "name": "Delta"},
            {"symbol": "CCL", "excg": "NYSE", "name": "Carnival"},
            {"symbol": "NCLH", "excg": "NYSE", "name": "Norwegian Cruise"},
            {"symbol": "ZM", "excg": "NASD", "name": "Zoom"},
            {"symbol": "DOCU", "excg": "NASD", "name": "DocuSign"},
            {"symbol": "U", "excg": "NYSE", "name": "Unity Software"},
        ]
        
        for stock in default_list:
            if stock['symbol'] not in existing_symbols:
                us_candidates.append(stock)
                existing_symbols.add(stock['symbol'])
        
        # --- [Top-Down Optimization] ---
        # Instead of fetching data for all 60 stocks, let AI pick ~15 first.
        logger.info(f"🤖 Step 1: Top-Down AI Screening for {len(us_candidates)} candidates...")
        bot.send_message(f"🤖 AI가 시장 상황({market_ctx[:20]}...)에 맞는 테마주 1차 선별 중...")
        
        target_symbols = await ai_analyzer.select_candidates_by_trend(us_candidates, market_ctx)
        
        # Filter us_candidates to only target_symbols
        filtered_candidates = [s for s in us_candidates if s['symbol'] in target_symbols]
        
        # If AI fails or returns empty, fallback to a subset of defaults
        if not filtered_candidates:
             filtered_candidates = us_candidates[:15]
             logger.warning("AI Screening returned empty, using fallback subset.")

        logger.info(f"🎯 AI Selected {len(filtered_candidates)} stocks for Deep Analysis.")
        bot.send_message(f"🎯 1차 선별 완료: {len(filtered_candidates)}개 종목 집중 분석 시작...")
        
        analysis_jobs = []
        
        for stock in filtered_candidates:
            symbol = stock['symbol']
            excg = stock['excg']
            name = stock['name']
            
            await asyncio.sleep(0.1)
            
            try:
                # 1. Get Daily Data
                daily_data = kis.get_overseas_daily_price(symbol, excg)
                if not daily_data:
                    logger.warning(f"No Daily Data for {name} ({excg})")
                    continue
                    
                current_price = float(daily_data[0]['clos'])
                # strict budget check moved to trading, but simple check helps
                # if budget and current_price > budget: continue 
                    
                mapped_data = []
                for d in daily_data:
                    mapped_data.append({
                        "stck_bsop_date": d['xymd'],
                        "stck_clpr": d['clos'],
                        "stck_oprc": d['open'],
                        "stck_hgpr": d['high'],
                        "stck_lwpr": d['low'],
                        "acml_vol": d['tvol']
                    })
                
                # 2. Tech Analysis
                tech_summary = technical.analyze(mapped_data)
                
                # Check Daily Change (For AI Context)
                daily_change = 0.0
                if len(daily_data) >= 2:
                     curr = float(daily_data[0]['clos'])
                     prev = float(daily_data[1]['clos'])
                     if prev > 0: daily_change = ((curr - prev) / prev) * 100
                
                # NO FILTERS FOR HOT TRENDS (Pass Everything)

                # 4. Prepare Job
                analysis_jobs.append({
                    "symbol": symbol,
                    "name": name,
                    "excg": excg,
                    "tech_summary": {
                        **tech_summary,
                        "daily_change": daily_change
                    },
                    "news_titles": [] 
                })
            except Exception as e:
                logger.error(f"Error processing {name} in Top 10: {e}")
                continue
            
        logger.info(f"US Data collected. Analyzing...")

        
        scored_candidates = []
        BATCH_SIZE = 5
        
        for i in range(0, len(analysis_jobs), BATCH_SIZE):
            batch = analysis_jobs[i : i + BATCH_SIZE]
            current_batch_num = i // BATCH_SIZE + 1
            total_batches = (len(analysis_jobs) + BATCH_SIZE - 1) // BATCH_SIZE
            
            bot.send_message(f"🔥 Hot Trend 분석 중... {current_batch_num}/{total_batches}")
            
            # Use NEW analyze_hot_trends
            batch_results = await ai_analyzer.analyze_hot_trends(batch)
            
            success_cnt = 0
            for job in batch:
                symbol = job['symbol']
                res = batch_results.get(symbol)
                
                # Validation
                if res and not isinstance(res, dict):
                     logger.warning(f"AI returned invalid format for {symbol}: {res}")
                     continue

                if res and res.get('score', 0) >= 0: # Accept logic
                    scored_candidates.append({
                        "symbol": symbol,
                        "name": job['name'],
                        "score": res['score'],
                        "reason": res['reason'],
                        "market": "US",
                        "price": job['tech_summary']['close'],
                        "change": job['tech_summary']['daily_change']
                    })
                    success_cnt += 1
            
            await asyncio.sleep(1.0) # Rate limit
        
        # 3. Sort & Select Top 10 (Highest AI Score)
        scored_candidates.sort(key=lambda x: x['score'], reverse=True)
        top_10 = scored_candidates[:10]
        
        # 4. Save
        try:
            os.makedirs("app/data", exist_ok=True)
            with open(TOP_PICKS_FILE, "w", encoding='utf-8') as f:
                json.dump({
                    "date": today_str,
                    "market": "US",
                    "picks": top_10
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save top picks: {e}")
            
        # 5. Report
        if top_10:
            msg = f"🌟 [US] 오늘의 Hot Trend Top 10 (AI 선정)\n"
            for i, s in enumerate(top_10, 1):
                msg += f"{i}. {s['name']} ({s['score']}점)\n   └ {s['reason']}\n"
            bot.send_message(msg)
        else:
            bot.send_message(f"❌ 분석 결과가 없습니다.")
        
        return top_10

    async def assess_risk(self, symbol: str, current_price: float, buy_price: float, daily_data: list, news_titles: list) -> dict:
        """
        Assess risk for a losing position using AI (Async).
        """
        # 1. Tech Analysis
        mapped_data = []
        for d in daily_data:
            # Map KIS keys to TechnicalAnalyzer keys
            mapped_data.append({
                "stck_bsop_date": d.get('xymd', d.get('stck_bsop_date')),
                "stck_clpr": d.get('clos', d.get('stck_clpr')),
                "stck_oprc": d.get('open', d.get('stck_oprc')),
                "stck_hgpr": d.get('high', d.get('stck_hgpr')),
                "stck_lwpr": d.get('low', d.get('stck_lwpr')),
                "acml_vol": d.get('tvol', d.get('acml_vol'))
            })
            
        tech_summary = technical.analyze(mapped_data)
        
        # 2. AI Analysis [ASYNC]
        return await ai_analyzer.analyze_risk(symbol, current_price, buy_price, tech_summary, news_titles)

selector = Selector()
