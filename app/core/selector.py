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

    async def select_pre_market_picks(self, market_type="KR"):
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

        TOP_PICKS_FILE = "app/data/top_picks.json"
        
        # Check if already done today
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        try:
            if os.path.exists(TOP_PICKS_FILE):
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
            pass 
            
        if not candidates and market_type == "US":
             # Temporary: Define US List here (Subset of main list)
             candidates = [
                {"symbol": "NVDA", "excg": "NASD", "name": "NVIDIA"},
                {"symbol": "TSLA", "excg": "NASD", "name": "Tesla"},
                {"symbol": "AAPL", "excg": "NASD", "name": "Apple"},
                {"symbol": "MSFT", "excg": "NASD", "name": "Microsoft"},
                {"symbol": "AMD", "excg": "NASD", "name": "AMD"},
                {"symbol": "PLTR", "excg": "NYSE", "name": "Palantir"},
                {"symbol": "COIN", "excg": "NASD", "name": "Coinbase"},
                {"symbol": "MARA", "excg": "NASD", "name": "Marathon Digital"},
                {"symbol": "NET", "excg": "NYSE", "name": "Cloudflare"},
                {"symbol": "IONQ", "excg": "NYSE", "name": "IonQ"},
                {"symbol": "SOXL", "excg": "NYSE", "name": "Direxion Daily Semi Bull 3X"},
                {"symbol": "TQQQ", "excg": "NASD", "name": "ProShares UltraPro QQQ"}
             ]
             
        # 2. Analyze Candidates (Parallel Batch Processing)
        bot.send_message(f"🔬 후보 {len(candidates)}개 심층 분석 중 (뉴스+차트)... (병렬 처리)")
        
        scored_candidates = []
        BATCH_SIZE = 5 # Process 5 at a time to avoid rate limits/overload
        
        for i in range(0, len(candidates), BATCH_SIZE):
            batch = candidates[i : i + BATCH_SIZE]
            logger.info(f"Processing Batch {i//BATCH_SIZE + 1} ({len(batch)} items)...")
            
            # Prepare Tasks
            tasks = []
            
            for stock in batch:
                tasks.append(self._analyze_single_stock(stock, market_type))

            # Run Parallel
            results = await asyncio.gather(*tasks)
            
            for res in results:
                if res:
                    scored_candidates.append(res)
            
            # Rate Limit Buffer
            await asyncio.sleep(1)

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
        msg = f"🌟 [{market_type}] 오늘의 Top 10 유망 종목\n"
        for i, s in enumerate(top_10, 1):
            msg += f"{i}. {s['name']} ({s['symbol']}) - {s['score']}점\n"
        bot.send_message(msg)
        
        return top_10

    async def _analyze_single_stock(self, stock, market_type):
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
                daily_data = await loop.run_in_executor(None, kis.get_overseas_daily_price, symbol, excg)
                
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
            if tech['rsi'] >= 70: return None # Stricter RSI (was 75)
            if tech.get('daily_change', 0) >= 15.0: return None # Avoid chasing spikes (>15%)
            if tech['trend'] == "DOWN": return None
            if tech['sma_5'] <= tech['sma_20']: return None
            
            # 2. Get News (Blocking) - Only if passed tech
            news = []
            if market_type == "KR":
                news_items = await loop.run_in_executor(None, kis.get_news_titles, symbol)
                news = [n['hts_pbnt_titl_cntt'] for n in news_items[:3]] if news_items else []
            
            # 3. Assess via AI (Async)
            analysis_result = await ai_analyzer.analyze_stock(name, news, tech)
            score = analysis_result.get('score', 0)
            reason = analysis_result.get('reason', 'Analysis Failed')
            
            if score >= 70:
                stock['reason'] = reason
                stock['score'] = score
                stock['tech'] = tech # Attach tech info
                return stock
        except Exception as e:
            logger.error(f"Error analyzing {name}: {e}")
            return None
        return None

    async def select_stocks(self, budget=None, target_count=3):
        """
        Main logic to select stocks for scalping (Async Optimized).
        budget: Available KRW. If set, filter out expensive stocks.
        target_count: Number of stocks to select (to fill slots).
        """
        import asyncio
        from app.core.telegram_bot import bot # Import bot for reporting
        from app.core.market_analyst import market_analyst
        
        start_time = time.time()
        
        # 0. Market Context (Top-Down)
        market_ctx = market_analyst.get_market_context_for_ai("KR")
        logger.info(f"Market Context: {market_ctx}")
        bot.send_message(f"🌍 시장 분석 결과: {market_ctx}")

        logger.info(f"Starting stock selection (Budget: {budget:,.0f} KRW, Target: {target_count})...")
        bot.send_message(f"🔍 종목 선정 시작 (예산: {budget:,.0f}원, 목표: {target_count}개)")
        
        # 0.5 Load Pre-Market Picks
        import json
        import os
        from datetime import datetime
        TOP_PICKS_FILE = "app/data/top_picks.json"
        pre_market_picks = []
        
        try:
            if os.path.exists(TOP_PICKS_FILE):
                with open(TOP_PICKS_FILE, "r", encoding='utf-8') as f:
                    data = json.load(f)
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    if data.get("date") == today_str and data.get("market") == "KR":
                        pre_market_picks = data.get("picks", [])
                        logger.info(f"Loaded {len(pre_market_picks)} Pre-Market Picks for KR.")
                        bot.send_message(f"📂 장전 Top 10 종목 {len(pre_market_picks)}개를 후보에 추가합니다.")
        except Exception as e:
            logger.error(f"Failed to load top picks: {e}")

        # 1. Get Candidates (Volume Rank)
        candidates = kis.get_volume_rank()
        if not candidates:
            msg = "❌ 거래량 상위 종목 조회 실패 (후보 없음)"
            logger.warning(msg)
            if not pre_market_picks:
                bot.send_message(msg)
                return []
            candidates = [] 

        # Filter out ETFs, ETNs, Futures, SPACs
        filtered_candidates = []
        exclusion_keywords = ["KODEX", "TIGER", "KBSTAR", "SOL", "ACE", "HANARO", "KOSEF", "ARIRANG", "ETN", "스팩", "선물", "레버리지", "인버스"]
        
        # Add Pre-Market Picks First (Priority 1)
        existing_symbols = set()
        for pick in pre_market_picks:
            filtered_candidates.append({
                'mksc_shrn_iscd': pick['symbol'],
                'hts_kor_isnm': pick['name'],
                'is_pre_pick': True,
                'source': 'Pre-Market'
            })
            existing_symbols.add(pick['symbol'])

        # --- Trend-based Picks (Priority 2) ---
        bot.send_message("🌊 실시간 뉴스 트렌드 종목 발굴 중...")
        trend_candidates = await market_analyst.get_trend_candidates("KR")
        
        trend_added_count = 0
        for t_stock in trend_candidates:
            t_code = t_stock.get('code')
            t_name = t_stock.get('name')
            
            if not t_code or t_code == "000000":
                # AI didn't know code. Try simple search or skip?
                # Resolving code by name is hard without master file list loaded.
                # Ideally we ask KIS to search, but KIS search API might be slow/limited.
                # For now, skip if no code.
                continue
                
            # Normalize code (make sure 6 digits)
            t_code = str(t_code).zfill(6)
            
            if t_code in existing_symbols: continue

            # Validate with KIS (Get Price check) to ensure it's a valid traded symbol
            # Optimization: Just try to get price in the batch loop. 
            # But we want to add to 'filtered_candidates'.
            # Let's assume it's valid if code looks right.
            
            filtered_candidates.append({
                'mksc_shrn_iscd': t_code,
                'hts_kor_isnm': t_name,
                'is_trend_pick': True, # Mark as trend
                'source': 'Live-Trend'
            })
            existing_symbols.add(t_code)
            trend_added_count += 1
            
        if trend_added_count > 0:
            bot.send_message(f"🔥 AI 트렌드 종목 {trend_added_count}개 추가 (뉴스 기반 Priority)")
            logger.info(f"Added {trend_added_count} trend candidates.")
            
        # -------------------------------------
            
        for stock in candidates:
            symbol = stock['mksc_shrn_iscd']
            if symbol in existing_symbols: continue
            
            name = stock['hts_kor_isnm']
            if any(keyword in name for keyword in exclusion_keywords):
                continue
            filtered_candidates.append(stock)
            existing_symbols.add(symbol)
            
        logger.info(f"Filtered {len(candidates) - (len(filtered_candidates) - len(pre_market_picks) - trend_added_count)} items. Total Candidates: {len(filtered_candidates)}")
        
        # Report Top 20 Candidates
        top_20 = filtered_candidates[:20]
        top_20_names = ", ".join([s['hts_kor_isnm'] for s in top_20])
        logger.info(f"Top 20 Candidates: {top_20_names}")
        bot.send_message(f"📋 1차 후보(거래량 상위): {len(filtered_candidates)}개\n상위 20개: {top_20_names}")

        # Data collection list (Process in batches)
        BATCH_SIZE = 5
        total_candidates = len(filtered_candidates)
        
        bot.send_message(f"🔬 총 {total_candidates}개 후보를 {BATCH_SIZE}개씩 순차 분석합니다.")
        
        final_selected = []
        
        for i in range(0, total_candidates, BATCH_SIZE):
            batch = filtered_candidates[i : i + BATCH_SIZE]
            current_batch_num = (i // BATCH_SIZE) + 1
            
            logger.info(f"Processing Batch {current_batch_num} ({len(batch)} items)...")
            bot.send_message(f"🔄 {current_batch_num}차 분석 중... ({i+1}~{i+len(batch)}위)")
            
            analysis_jobs = []
            
            for stock in batch:
                symbol = stock['mksc_shrn_iscd']
                name = stock['hts_kor_isnm']
                
                await asyncio.sleep(0.1)
                
                # 2. Get Chart Data & Technical Analysis
                daily_data = kis.get_daily_price(symbol)
                if not daily_data:
                    logger.info(f"Skipping {name}: No Data")
                    continue
                    
                tech_summary = technical.analyze(daily_data)
                if tech_summary.get("status") in ["Error", "Not enough data"]:
                    logger.info(f"Skipping {name}: Tech Error")
                    continue
                
                # Calculate Daily Change
                try:
                    if len(daily_data) >= 2:
                        prev_close = float(daily_data[1]['stck_clpr'])
                        curr_close = float(daily_data[0]['stck_clpr'])
                        if prev_close > 0:
                            change_rate = ((curr_close - prev_close) / prev_close) * 100
                            tech_summary['daily_change'] = change_rate
                        else:
                            tech_summary['daily_change'] = 0.0
                    else:
                        tech_summary['daily_change'] = 0.0
                except Exception:
                    tech_summary['daily_change'] = 0.0
                    
                # Budget Filter
                current_price = tech_summary['close']
                if budget is not None and current_price > budget:
                    continue
                
                # 2.5 Strict Technical Filters (Relaxed -> Tightened)
                fail_reason = None
                if tech_summary['rsi'] >= 70:
                     fail_reason = f"RSI 과열 ({tech_summary['rsi']:.1f})"
                elif tech_summary.get('daily_change', 0) >= 15.0:
                     fail_reason = f"급등 부담 (+{tech_summary.get('daily_change'):.1f}%)"
                elif tech_summary['trend'] == "DOWN":
                     fail_reason = "하락 추세"
                if fail_reason:
                    continue 

                # 3. Get News
                await asyncio.sleep(0.1)
                news_items = kis.get_news_titles(symbol)
                news_titles = [n['hts_pbnt_titl_cntt'] for n in news_items[:3]] if news_items else []
                
                # Prepare job for AI Analysis
                analysis_jobs.append({
                    "symbol": symbol,
                    "name": name,
                    "tech_summary": tech_summary,
                    "news_titles": news_titles
                })
            
            if not analysis_jobs:
                bot.send_message(f"⚠️ {current_batch_num}차 분석 결과: 기술적 분석 통과 종목 없음.")
                continue

            logger.info(f"Batch {current_batch_num}: {len(analysis_jobs)} candidates passed technical check. Running AI...")
            
            # 4. Run AI Analysis (Batch) [ASYNC]
            for job in analysis_jobs:
                job['market_status'] = market_ctx 
            
            # Use await for async batch analysis
            batch_results = await ai_analyzer.analyze_stocks_batch(analysis_jobs)
            
            # 5. Process Results
            batch_selected = []
            report_lines = []
            
            for job in analysis_jobs:
                name = job['name']
                symbol = job['symbol']
                
                ai_result = batch_results.get(symbol, {})
                if not ai_result:
                    report_lines.append(f"- {name}: 분석 실패")
                    continue
                    
                score = ai_result.get('score', 0)
                reason = ai_result.get('reason', 'N/A')
                
                if score >= 60: 
                    strategy = ai_result.get('strategy', {})
                    if not isinstance(strategy, dict): strategy = {}
                    
                    batch_selected.append({
                        "symbol": symbol,
                        "name": name,
                        "price": job['tech_summary']['close'],
                        "score": score,
                        "reason": reason,
                        "action": ai_result.get('action', 'Watch'),
                        "target": strategy.get('target_price'),
                        "stop_loss": strategy.get('stop_loss'),
                        "rsi": job['tech_summary']['rsi']
                    })
                    logger.info(f"Selected: {name} ({score})")
                    report_lines.append(f"✅ {name}: {score}점 (선정됨)")
                else:
                     short_reason = reason[:30] + "..." if len(reason) > 30 else reason
                     report_lines.append(f"🔻 {name}: {score}점 (탈락)\n   └ {short_reason}")
            
            if report_lines:
                bot.send_message(f"🤖 {current_batch_num}차 AI 분석 결과:\n" + "\n".join(report_lines))

            if batch_selected:
                final_selected.extend(batch_selected)
                if len(final_selected) >= target_count:
                    bot.send_message(f"✨ 매수 후보 {len(final_selected)}개 발굴 완료 (목표 {target_count}개 달성).")
                    break
        
        final_selected.sort(key=lambda x: x['score'], reverse=True)
        elapsed = time.time() - start_time
        logger.info(f"Selected {len(final_selected)} stocks in {elapsed:.2f} seconds.")
        
        if not final_selected:
             bot.send_message("❌ 모든 후보군을 검색했으나 적합한 종목이 없습니다.")

        return final_selected

    async def select_us_stocks(self, budget=None):
        """
        Stock Selection for US Market (Async Wrapper).
        """
        import asyncio
        from app.core.market_analyst import market_analyst

        start_time = time.time()
        
        market_ctx = market_analyst.get_market_context_for_ai("US")
        logger.info(f"US Market Context: {market_ctx}")
        
        logger.info(f"Starting US stock selection (Budget: {budget if budget else 'N/A'} USD)...")
        
        import json
        import os
        from datetime import datetime
        TOP_PICKS_FILE = "app/data/top_picks.json"
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
            {"symbol": "ARKK", "excg": "NYSE", "name": "ARK Innovation"},
            {"symbol": "ZM", "excg": "NASD", "name": "Zoom"},
            {"symbol": "DOCU", "excg": "NASD", "name": "DocuSign"},
            {"symbol": "U", "excg": "NYSE", "name": "Unity Software"},
        ]
        
        for stock in default_list:
            if stock['symbol'] not in existing_symbols:
                us_candidates.append(stock)
                existing_symbols.add(stock['symbol'])
        
        logger.info(f"US Candidates: {len(us_candidates)} items (Pre-Picks: {len(pre_market_picks)})")
        
        analysis_jobs = []
        
        for stock in us_candidates:
            symbol = stock['symbol']
            excg = stock['excg']
            name = stock['name']
            
            await asyncio.sleep(0.1)
            
            # 1. Get Daily Data
            daily_data = kis.get_overseas_daily_price(symbol, excg)
            if not daily_data:
                logger.warning(f"No Daily Data for {name} ({excg})")
                continue
                
            current_price = float(daily_data[0]['clos'])
            safe_budget = budget if budget else 0
            
            if budget is not None and current_price > safe_budget:
                logger.info(f"Skipping {name}: Price {current_price} > Budget {safe_budget:.1f} (Too Expensive)")
                continue
                
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
            if tech_summary.get("status") in ["Error", "Not enough data"]:
                continue
            
            # 3. Filters
            if tech_summary['sma_5'] <= tech_summary['sma_20']:
                continue
            if tech_summary['rsi'] >= 70: # Stricter RSI
                continue
            
            # Calculate daily change for US if not already in tech_summary
            # (tech_summary usually has 'daily_change' if computed in analyze or earlier)
            # Let's check if we computed it. 
            # In select_us_stocks, we computed mapped_data but didn't explicitly add daily_change to tech_summary object yet? 
            # technical.analyze might not add it. 
            # Let's calculate it here for safety or rely on pre-calculation if added.
            # Actually, let's just use the Price we have.
            
            daily_change = 0.0
            if len(daily_data) >= 2:
                 curr = float(daily_data[0]['clos'])
                 prev = float(daily_data[1]['clos'])
                 if prev > 0: daily_change = ((curr - prev) / prev) * 100
            
            if daily_change >= 15.0: # Avoid chasing US spikes too
                continue
            if tech_summary['trend'] == "DOWN":
               continue 
               
            # 4. Prepare Job
            analysis_jobs.append({
                "symbol": symbol,
                "name": name,
                "excg": excg,
                "tech_summary": tech_summary,
                "news_titles": [] 
            })
            
        logger.info(f"US Data collected for {len(analysis_jobs)} stocks. Analyzing...")

        logger.info(f"US Data collected for {len(analysis_jobs)} stocks. Analyzing (Batch)...")
        
        for job in analysis_jobs:
            job['market_status'] = market_ctx
            
        batch_results = await ai_analyzer.analyze_stocks_batch(analysis_jobs)
        
        selected = []
        for job in analysis_jobs:
            symbol = job['symbol']
            
            ai_result = batch_results.get(symbol, {})
            if not ai_result:
                continue

            if ai_result.get('score', 0) >= 70:
                strategy = ai_result.get('strategy', {})
                if not isinstance(strategy, dict):
                    strategy = {}
                
                selected.append({
                    "symbol": job['symbol'],
                    "name": job['name'],
                    "price": job['tech_summary']['close'],
                    "score": ai_result['score'],
                    "reason": ai_result['reason'],
                    "action": ai_result.get('action', 'Watch'),
                    "target": strategy.get('target_price'),
                    "stop_loss": strategy.get('stop_loss'),
                    "rsi": job['tech_summary']['rsi'],
                    "market_type": "US",
                    "excg": job['excg']
                })
                logger.info(f"Selected US: {job['name']} ({ai_result['score']})")

        selected.sort(key=lambda x: x['score'], reverse=True)
        return selected

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
