import logging
import time
from datetime import datetime
from app.core.kis_api import kis
from app.core.telegram_bot import bot

logger = logging.getLogger(__name__)

class TradeManager:
    def __init__(self):
        self.active_trades = {} # {symbol: {buy_price, target_price, stop_loss_price, qty, market_type, excg}}
        self.capital_krw = 0
        self.capital_usd = 0
        self.total_asset_krw = 0 # Equity (Cash + Stock)
        self.total_asset_usd = 0
        self.start_balance_krw = 0 
        self.start_balance_usd = 0
        self.trade_history = [] 
        self.manual_slots = {} # {market_type: count}

    def update_balance(self):
        """Fetch latest balance from KIS (KRW & USD)"""
        # 1. Domestic
        balance = kis.get_balance()
        if balance:
            logger.info(f"DEBUG: Balance Content: {balance}")
            
            current_eval = float(balance.get('tot_evlu_mony', 0))
            if self.start_balance_krw == 0 and current_eval > 0:
                self.start_balance_krw = current_eval
                logger.info(f"Start Balance Set (KRW): {self.start_balance_krw:,.0f}")
            
            # Prioritize Orderable Cash (Explicit Endpoint)
            real_cash = kis.get_orderable_cash()
            if real_cash is not None:
                self.capital_krw = float(real_cash)
                logger.info(f"DEBUG: Real Orderable Cash: {self.capital_krw:,.0f}")
            else:
                # Fallback to Balance Keys
                val = balance.get('ord_psbl_dnca')
                if val is None:
                    val = balance.get('prvs_rcdl_excc_amt')
                if val is None:
                    val = balance.get('dnca_tot_amt', 0)
                self.capital_krw = float(val)

            self.total_asset_krw = float(balance.get('tot_evlu_amt', self.capital_krw)) # Total Asset
            
        # 2. Overseas (US)
        ovs_bal = kis.get_overseas_balance()
        if ovs_bal and 'summary' in ovs_bal:
            summary = ovs_bal['summary']
            logger.info(f"DEBUG: US Balance Summary: {summary}")

            # frcr_evlu_amt2: Foreign Eval Amount (USD)
            val_usd = float(summary.get('frcr_evlu_amt2', 0)) 
            
            # Use Orderable Amount if available, else Deposit
            val_u = summary.get('ovrs_ord_psbl_amt')
            if val_u is None:
                val_u = summary.get('frcr_dncl_amt_2', 0)
            self.capital_usd = float(val_u)
            
            if self.capital_usd < 1 and self.capital_krw > 50000:
                logger.warning("WARNING: USD Balance is 0! (But KRW is available)")
                logger.warning("Tip: Enable 'Integrated Margin' (통합증거금) in KIS App or Exchange Currency.")
            
            # Total Asset USD (Estimate if key missing)
            # ovrs_tot_asst_amt might be the key? Using Sum for safety
            self.total_asset_usd = val_usd + self.capital_usd
            
            if self.start_balance_usd == 0 and val_usd > 0:
                self.start_balance_usd = val_usd
                logger.info(f"Start Balance Set (USD): {self.start_balance_usd:,.2f}")

    def get_available_budget(self, market_type="KR"):
        """Get available buying power for the market"""
        self.update_balance()
        if market_type == "US":
            budget = self.capital_usd
            # Integrated Margin Logic: If USD is low but KRW exists, add approximate purchasing power
            if budget < 20 and self.capital_krw > 30000:
                approx_usd = self.capital_krw / 1450 # Conservative Rate
                budget += approx_usd
            return budget
        
        return self.capital_krw
    
    def get_target_slot_budget_us(self):
        """
        Calculate the budget available for the NEXT US slot.
        Handles 'Last Slot Sweep' logic (use all remaining cash).
        """
        self.update_balance()
        
        # Unified Margin Support logic
        buying_power = self.capital_usd
        if buying_power < 20 and self.capital_krw > 30000:
                buying_power += self.capital_krw / 1450
        
        # Calculate Total Equity properly (Cash + Holdings Value)
        # Note: self.total_asset_usd from KIS might be unreliable or exclude cash depending on endpoint.
        current_holdings_val = sum(t['buy_price'] * t['qty'] for t in self.active_trades.values() if t.get('market_type') == 'US')
        
        # Self-Healing: Check for missing trades (Discrepancy Check)
        # If Balance says we have stock, but active_trades is empty/low
        estimated_stock_val = self.total_asset_usd - self.capital_usd
        if estimated_stock_val > current_holdings_val + 20: # $20 tolerance
             logger.warning(f"Equity Mismatch! Balance Stock: ${estimated_stock_val:.2f}, Active: ${current_holdings_val:.2f}. Triggering Re-sync...")
             self.sync_portfolio()
             # Recalculate after sync
             current_holdings_val = sum(t['buy_price'] * t['qty'] for t in self.active_trades.values() if t.get('market_type') == 'US')

        base_equity = buying_power + current_holdings_val
        
        logger.info(f"Target Budget Calc: Cash ${buying_power:.0f} + Stock ${current_holdings_val:.0f} = Equity ${base_equity:.0f}")
        
        # Explicit Slot Limit
        # Check Manual Override first
        if "US" in self.manual_slots:
             max_slots = self.manual_slots["US"]
             logger.info(f"Using Manual Slot Limit (US): {max_slots}")
        else:
             # Lowered threshold to $300 to allow execution for smaller accounts
             max_slots = 2 if base_equity < 300 else 3
             
        current_us_slots = sum(1 for t in self.active_trades.values() if t.get('market_type') == 'US')
        
        # If already full, return 0 (Shouldn't select anything)
        if current_us_slots >= max_slots:
            return 0
            
        remaining_slots = max_slots - current_us_slots
        
        if remaining_slots == 1:
            # Last available slot -> Use ALL remaining power
            logger.info(f"Target Budget (Last Slot): ${buying_power:.2f}")
            return buying_power
        else:
            # Standard Allocation
            # If manual slots are high, we should split accordingly
            alloc_ratio = 1.0 / remaining_slots
            target_amount = buying_power * alloc_ratio # Use buying power split, not equity alloc?
            # Original logic was Equity * Alloc. 
            # If 3 slots, 0.33. If 5 slots, 0.2.
            # Let's stick to safe logic: Base Equity / Max Slots
            target_amount = base_equity / max_slots
            
            logger.info(f"Target Budget (Standard): ${target_amount:.2f}")
            return target_amount

    
    def sync_portfolio(self):
        """
        Sync existing holdings from KIS to active_trades.
        Ensures Restart doesn't ignore existing positions.
        """
        logger.info("🔄 Starting portfolio sync...")
        self.update_balance()
        holdings = kis.get_my_stock_balance()
        if not holdings:
            logger.warning("⚠️ No KR holdings found")
        else:
            logger.info(f"📦 Found {len(holdings)} KR holdings")

        for stock in holdings:
            symbol = stock['pdno']
            name = stock['prdt_name']
            qty = int(stock['hldg_qty'])
            buy_price = float(stock['pchs_avg_pric'])
            
            if qty > 0 and symbol not in self.active_trades:
                # Add to active trades to manage/monitor
                # Default Target 3%, Stop 2%
                self.active_trades[symbol] = {
                    "name": name,
                    "buy_price": buy_price,
                    "qty": qty,
                    "target_price": buy_price * 1.03,
                    "stop_loss_price": buy_price * 0.98,
                    "market_type": "KR", # Sync currently only implemented for KR logic
                    "excg": "N/A"
                }
                logger.info(f"Recovered Holding: {name} ({qty}sh) @ {buy_price:,.0f}")

        # 2. US Holdings
        try:
            us_bal = kis.get_overseas_balance()
            logger.debug(f"🔍 US Balance Response: {us_bal}")
            
            if us_bal and 'holdings' in us_bal:
                holdings_list = us_bal['holdings']
                logger.info(f"📦 Found {len(holdings_list)} US holdings to process")
                
                for stock in holdings_list:
                    symbol = stock.get('ovrs_pdno')
                    name = stock.get('ovrs_item_name')
                    qty = int(float(stock.get('ovrs_cblc_qty', 0)))  # Convert to int for KIS API
                    buy_price = float(stock.get('pchs_avg_pric', 0))
                    excg = stock.get('ovrs_excg_cd', 'NAS')
                    
                    # DEBUG: Log raw keys for the first item to verify API field names
                    if holdings_list.index(stock) == 0:
                        logger.debug(f"🔍 First US Stock Raw Keys: {stock.keys()}")
                    
                    logger.debug(f"  📊 Processing: {symbol} ({name}), Qty={qty}, Price={buy_price}, Excg={excg}")

                    if qty > 0 and symbol not in self.active_trades:
                        self.active_trades[symbol] = {
                            "name": name,
                            "buy_price": buy_price,
                            "qty": qty,  # Now stored as int
                            "target_price": buy_price * 1.03,
                            "stop_loss_price": buy_price * 0.98,
                            "market_type": "US",
                            "excg": excg
                        }
                        logger.info(f"✅ Recovered Holding (US): {name} ({qty}sh) @ ${buy_price:.2f}")
                    elif qty <= 0:
                        logger.debug(f"  ⏭️ Skipping {symbol}: Qty={qty} (zero or negative)")
                    elif symbol in self.active_trades:
                        logger.debug(f"  ⏭️ Skipping {symbol}: Already in active_trades")
            else:
                logger.warning(f"⚠️ No US holdings found or invalid response: {us_bal}")
            
            # DEBUG: Check what is actually in active_trades
            us_keys = [k for k, v in self.active_trades.items() if v.get('market_type') == 'US']
            logger.info(f"🎯 Current US Active Trades: {us_keys} (Count: {len(us_keys)})")

        except Exception as e:
            logger.error(f"❌ Failed to sync US holdings: {e}", exc_info=True)

    def get_account_status_str(self):
        """Generate status report text: Balance + Holdings"""
        self.update_balance()
        
        msg = "📊 [Current Account Status]\n"
        msg += f"💰 Balance: {self.capital_krw:,.0f} KRW / {self.capital_usd:,.2f} USD\n\n"
        
        msg += "📋 Holdings:\n"
        if not self.active_trades:
            msg += "(No active trades)\n"
        else:
            for sym, t in self.active_trades.items():
                # Get current price
                # Helper for safe float
                def safe_float(v):
                    try:
                        return float(v)
                    except (ValueError, TypeError):
                        return 0.0

                if t['market_type'] == "US":
                    p_data = kis.get_overseas_price(sym, t.get('excg', 'NAS'))
                    curr = safe_float(p_data.get('last')) if p_data else 0
                    if curr == 0:
                        logger.warning(f"DEBUG: Price 0 for {sym} ({t.get('excg')}). Raw Data: {p_data}")
                else:
                    p_data = kis.get_current_price(sym)
                    curr = safe_float(p_data.get('stck_prpr')) if p_data else 0
                
                pnl = ((curr - t['buy_price']) / t['buy_price'] * 100) if t['buy_price'] > 0 else 0
                currency = "USD" if t['market_type'] == "US" else "KRW"
                
                msg += f"- {t['name']}\n"
                msg += f"  Buy: {t['buy_price']:,.2f} / Cur: {curr:,.2f} {currency}\n"
                msg += f"  P&L: {pnl:.2f}%\n"
        
        return msg

    def process_signals(self, selected_stocks: list):
        """
        Process buy signals from Selector (KR & US).
        """
        self.update_balance()
        if not selected_stocks:
            return

        for stock in selected_stocks:
            symbol = stock['symbol']
            name = stock['name']
            current_price = float(stock['price'])
            market_type = stock.get('market_type', 'KR')
            excg = stock.get('excg', 'NAS')
            
            if symbol in self.active_trades:
                # Add-on Buy Logic (Pyramiding/Averaging)
                trade = self.active_trades[symbol]
                
                # Check current P&L
                buy_price = trade['buy_price']
                pnl_rate = ((current_price - buy_price) / buy_price) * 100
                
                # Condition: Only Add-on if P&L is valid (e.g. not too high to chase)
                # Strategy: 
                # - If P&L > 3%: Too high, skip to avoid raising avg price too much.
                # - If P&L <= 3%: Good for adding more (Momentum or Dip).
                if pnl_rate > 3.0:
                    logger.info(f"Skipping Add-on for {name}: P&L {pnl_rate:.2f}% > 3% (Too high)")
                    continue
                else:
                    logger.info(f"Adding to Position {name}: P&L {pnl_rate:.2f}% (Add-on Buy)")
                    # Proceed to Buy Logic below... (It will calculate qty and execute)
                    # Note: We need to update avg price later.

            # Allocation Logic (Based on Total Equity to keep slots equal)
            # Allocation Logic (Based on Total Equity to keep slots equal)
            if market_type == "US":
                # Unified Margin Support: Calculate total buying power (USD + KRW)
                buying_power = self.capital_usd
                if buying_power < 20 and self.capital_krw > 30000:
                     buying_power += self.capital_krw / 1450
                
                # Estimate Total USD Equity (Holdings + Buying Power)
                base_equity = max(self.total_asset_usd, buying_power)
                
                # --- Explicit Slot Limit Logic ---
                # Capital < $300 -> Max 2 Slots
                # Capital >= $300 -> Max 3 Slots
                max_slots = 2 if base_equity < 300 else 3
                
                # Count current US active trades
                current_us_slots = sum(1 for t in self.active_trades.values() if t.get('market_type') == 'US')
                
                if current_us_slots >= max_slots:
                    logger.info(f"Skipping {symbol}: Max Slots Reached ({current_us_slots}/{max_slots}) for Capital ${base_equity:.0f}")
                    continue
                # ---------------------------------

                # ---------------------------------

                # Dynamic Allocation: Capital < $1000 -> 2 Slots (50%), else 3 Slots (33%)
                # Optimization: If this is the LAST available slot, use ALL remaining buying power.
                remaining_slots = max_slots - current_us_slots
                
                if remaining_slots == 1:
                    logger.info(f"Last Slot Allocation: Using Full Buying Power (${buying_power:.2f})")
                    target_amt = buying_power
                else:
                    default_alloc = 0.5 if base_equity < 1000 else 0.33
                    target_amt = base_equity * default_alloc
                
                invest_amt = min(target_amt, buying_power) # Cap at available buying power
                
                if invest_amt < 20: # Min $20
                    logger.warning(f"Insufficient USD for {name} ({invest_amt:.2f}).")
                    continue
                qty = int(invest_amt // current_price)
            else:
                # KR Market Allocation
                # Calculate remaining slots for KR
                if symbol in self.active_trades:
                    # If Add-on, we ignore slot limit (it's existing slot). 
                    # Use 33% of remaining cash for Add-on (User Request)
                    remaining_slots = 3 
                    logger.info(f"Add-on Allocation for {name}: Treating as 3 slots (Using 33% of Cash)")
                else:
                    current_kr_slots = sum(1 for t in self.active_trades.values() if t.get('market_type', 'KR') == 'KR')
                    
                    if "KR" in self.manual_slots:
                        MAX_KR_SLOTS = self.manual_slots["KR"]
                    else:
                        MAX_KR_SLOTS = 3 
                        
                    remaining_slots = max(0, MAX_KR_SLOTS - current_kr_slots)

                # Dynamic Allocation based on Remaining Slots (Split remaining cash equally)
                # e.g., If 3 slots left and 3M KRW cash -> 1M per slot.
                if remaining_slots > 0:
                     invest_amt = (self.capital_krw * 0.95) / remaining_slots
                else:
                     invest_amt = 0
                
                # Check Min Amount
                if invest_amt < 10000: # Min 10,000 KRW
                    logger.warning(f"Insufficient KRW for {name}. Invest: {invest_amt:,.0f} < Min 10k. Cash: {self.capital_krw:,.0f}")
                    continue
                qty = int(invest_amt // current_price)

            if qty == 0:
                logger.warning(f"Skipping {name}: Qty is 0. Invest: {invest_amt:,.0f} < Price: {current_price:,.0f}")
                continue

            # Execute Buy
            logger.info(f"Buying {market_type}: {name} ({qty}sh) @ {current_price}")
            
            if market_type == "US":
                # Limit Order for US (Current + 1% buffer)
                res = kis.buy_overseas_order(symbol, qty, price=current_price*1.01, excg_cd=excg) 
                
                # Retry Logic for Exchange Code Mismatch (APBK0656)
                if isinstance(res, dict) and (res.get('msg_cd') == 'APBK0656' or '해당종목' in res.get('msg1', '')):
                    logger.warning(f"Order failed for {symbol} ({excg}). Retrying with other exchanges...")
                    for alt_excg in ['NAS', 'NYS', 'AMS', 'NASD', 'NYSE', 'AMEX']:
                        if alt_excg == excg: continue
                        
                        logger.info(f"Retrying {symbol} on {alt_excg}...")
                        res = kis.buy_overseas_order(symbol, qty, price=current_price*1.01, excg_cd=alt_excg)
                        if isinstance(res, dict) and res.get('rt_cd') == '0':
                            logger.info(f"Retry Successful on {alt_excg}!")
                            excg = alt_excg # Update for record
                            stock['excg'] = alt_excg
                            break
            else:
                # Market Order for KR (Immediate Execution)
                # Note: Market orders may require higher available balance calc (Upper Limit)
                # but ensures execution vs Limit orders that miss fast moves.
                res = kis.buy_order(symbol, qty, price=0) 

            # Standardize Failure (KIS returns rt_cd but no error key sometimes)
            if isinstance(res, dict) and res.get("rt_cd", "0") != "0":
                 res['error'] = res.get('msg1', 'KIS API Error')

            if "error" not in res:
                currency = "USD" if market_type == "US" else "KRW"
                reason = stock.get('reason', 'No details')
                
                # Sane Defaults if AI returns None (Calculate BEFORE sending message)
                # Load Dynamic Strategy Config
                from app.core.optimizer import optimizer
                config = optimizer.load_config()
                
                market_key = "us_parameters" if market_type == "US" else "kr_parameters"
                default_target = float(config.get(market_key, {}).get('target_profit_rate', 3.0))
                default_stop = float(config.get(market_key, {}).get('stop_loss_rate', 2.0))
                
                t_val = stock.get('target')
                if t_val is None: t_val = default_target
                target_pct = float(t_val)
                
                # Stop Loss Logic
                sl_val = stock.get('stop_loss')
                if sl_val is None: sl_val = default_stop
                
                raw_stop = float(sl_val)
                stop_pct = abs(raw_stop)
                
                # AI might suggest very loose stop (e.g. 10%), allow it ONLY if it's within Config "Safety" limits?
                # For now, let's trust AI but enforce Hard Floor 1.5%
                if stop_pct < 1.5:
                    stop_pct = 1.5 # Enforce Hard Limit 1.5%

                bot.send_message(
                    f"🚀 {market_type} 매수 체결: {name}\n"
                    f"수량: {qty}\n"
                    f"가격: {current_price:,.2f} {currency}\n"
                    f"목표가: {target_pct}%\n"
                    f"AI 분석: {reason}"
                )
                
                buy_price = current_price # Approximate
                
                # Update Active Trades (Handle Add-on)
                if symbol in self.active_trades:
                    old_trade = self.active_trades[symbol]
                    old_qty = old_trade['qty']
                    old_price = old_trade['buy_price']
                    
                    new_qty = old_qty + qty
                    new_avg_price = ((old_qty * old_price) + (qty * current_price)) / new_qty
                    
                    self.active_trades[symbol].update({
                        "buy_price": new_avg_price,
                        "qty": new_qty,
                        "target_price": new_avg_price * (1 + target_pct/100),
                        "stop_loss_price": new_avg_price * (1 - stop_pct/100),
                        "buy_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Update time? Maybe keep original? Let's update for now so we know action happened.
                    })
                    logger.info(f"Updated Position {name}: Avg Price {old_price:.0f}->{new_avg_price:.0f}, Qty {old_qty}->{new_qty}")
                else:
                    self.active_trades[symbol] = {
                        "name": name,
                        "buy_price": current_price,
                        "qty": qty,
                        "target_price": current_price * (1 + target_pct/100),
                        "stop_loss_price": current_price * (1 - stop_pct/100),
                        "market_type": market_type,
                        "excg": excg,
                        "buy_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                
                # Update Wallet Balance Locally (to prevent over-spending in same batch)
                spent_amount = qty * buy_price
                if market_type == "US":
                    self.capital_usd = max(0, self.capital_usd - spent_amount)
                    logger.info(f"Local Wallet Update: -${spent_amount:.2f} (Rem: ${self.capital_usd:.2f})")
                else:
                    fees = spent_amount * 0.00015 # Approx fees
                    self.capital_krw = max(0, self.capital_krw - (spent_amount + fees))
                    logger.info(f"Local Wallet Update: -{spent_amount:,.0f} KRW (Rem: {self.capital_krw:,.0f})")
                
                # Subscribe to WebSocket for real-time monitoring
                if kis.websocket and kis.websocket.is_connected:
                    kis.websocket.subscribe_stock(symbol, market_type)
                    logger.info(f"📡 WebSocket subscribed: {symbol}")
                
                # Send Status Update
                bot.send_message(self.get_account_status_str())
                
                # Refresh Balance for next iteration
                self.update_balance()

            else:
                bot.send_message(f"❌ 매수 실패 ({name}): {res.get('error')}")

    def monitor_active_trades(self, market_filter="ALL"):
        if not self.active_trades:
            return

        active_symbols = list(self.active_trades.keys())
        
        for symbol in active_symbols:
            trade = self.active_trades[symbol]
            name = trade['name']
            market_type = trade.get('market_type', 'KR')
            
            # Filter by Market (KR/US)
            if market_filter != "ALL" and market_type != market_filter:
                continue

            excg = trade.get('excg', 'NAS')
            
            # Helper
            def safe_float(v):
                try: return float(v)
                except: return 0.0

            # Get Price - Use WebSocket if available
            price_data = kis.get_realtime_price(symbol, market_type)
            
            if not price_data:
                logger.warning(f"⚠️ {name}: No price data available")
                continue
            
            current_price = safe_float(price_data.get('price', 0))
            
            if current_price <= 0:
                logger.warning(f"⚠️ {name}: Invalid price {current_price}")
                continue
            
            buy_price = trade['buy_price']
            qty = trade['qty']
            profit_rate = ((current_price - buy_price) / buy_price) * 100
            
            # Debug logging for stop-loss monitoring
            stop_loss_price = trade.get('stop_loss_price', 0)
            target_price = trade.get('target_price', 0)
            
            logger.debug(f"📊 {name}: Current=${current_price:.2f}, Buy=${buy_price:.2f}, "
                        f"P&L={profit_rate:.2f}%, StopLoss=${stop_loss_price:.2f}, Target=${target_price:.2f}")

            # Check for suspicious Profit Rate (e.g. exactly equal to daily change?)
            if abs(profit_rate) > 20: 
                 logger.warning(f"⚠️ High P&L detected for {name}: {profit_rate:.2f}% (Buy: {buy_price}, Curr: {current_price})")
            
            # UPDATE DICT for Frontend
            trade['current_price'] = current_price
            trade['profit_rate'] = profit_rate
            trade['value'] = current_price * qty
            if market_type == 'US':
                # Approx value in KRW for total calculation
                trade['value_krw'] = trade['value'] * 1450 # simplified
            else:
                 trade['value_krw'] = trade['value']
            
            # Trailing Stop Logic
            trade.setdefault('max_price', buy_price)
            trade.setdefault('trailing_active', False)
            
            if current_price > trade['max_price']:
                trade['max_price'] = current_price
                
            action = None
            
            if trade['trailing_active']:
                # Already hit target, now trailing (Sell if drops 1% from peak)
                if current_price < trade['max_price'] * 0.99:
                    action = "트레일링 익절 (고점 대비 -1%)"
                    logger.info(f"🎯 {name}: Trailing stop triggered at {profit_rate:.2f}%")
            else:
                # Normal Monitoring
                if current_price >= trade['target_price']:
                    # Hit Target -> Activate Trailing
                    trade['trailing_active'] = True
                    logger.info(f"✅ {name}: Target Hit. Activating Trailing Stop.")
                elif current_price <= trade['stop_loss_price']:
                    action = "손절매 (Stop Loss)"
                    logger.warning(f"🛑 {name}: Stop-loss triggered! Current=${current_price:.2f} <= StopLoss=${stop_loss_price:.2f} (P&L={profit_rate:.2f}%)")
                
            if action:
                logger.info(f"🔔 Executing {action} for {name}")
                
                if market_type == "US":
                    res = kis.sell_overseas_order(symbol, qty, price=current_price*0.99, excg_cd=excg)
                else:
                    res = kis.sell_order(symbol, qty, price=0)
                
                if "error" not in res:
                    currency = "USD" if market_type == "US" else "KRW"
                    bot.send_message(f"💰 {action}: {name}\n수익률: {profit_rate:.2f}%")
                    
                    self.trade_history.append({
                        "name": name,
                        "market": market_type,
                        "qty": qty,
                        "buy_price": buy_price,
                        "sell_price": current_price,
                        "profit_rate": profit_rate,
                        "result": "WIN" if profit_rate > 0 else "LOSS",
                        "buy_time": trade.get('buy_time', 'Unknown'),
                        "sell_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    self.save_history() # Persist immediately
                    
                    # Unsubscribe from WebSocket
                    if kis.websocket:
                        kis.websocket.unsubscribe_stock(symbol)
                        logger.info(f"📡 WebSocket unsubscribed: {symbol}")
                    
                    del self.active_trades[symbol]
                    
                    # Send Status Update
                    bot.send_message(self.get_account_status_str())
                    
                else:
                    logger.error(f"❌ Sell order failed for {name}: {res.get('error')}")
                    bot.send_message(f"⚠️ 매도 실패 ({name}): {res.get('error')}")


    def monitor_risks(self, market_filter="ALL"):
        """
        AI-Based Risk & Profit Monitor.
        - Checks LOSING positions (-0.4%) for early stop-loss
        - Checks WINNING positions (+1%) for early profit-taking
        Supports both Korean (KR) and US stocks.
        """
        from app.core.selector import selector
        
        if not self.active_trades: return
        
        for symbol in list(self.active_trades.keys()):
            trade = self.active_trades[symbol]
            market_type = trade.get('market_type', 'KR')
            name = trade['name']
            
            # Filter by Market
            if market_filter != "ALL" and market_type != market_filter:
                continue

            # 1. Get Current Status
            try:
                if market_type == "US":
                    excg = trade.get('excg', 'NAS')
                    p_data = kis.get_overseas_price(symbol, excg)
                    if not p_data: continue
                    curr_price = float(p_data.get('last', 0))
                else:  # KR
                    p_data = kis.get_current_price(symbol)
                    if not p_data: continue
                    curr_price = float(p_data.get('stck_prpr', 0))
            except: 
                continue

            if curr_price <= 0: continue
            
            buy_price = trade['buy_price']
            qty = trade['qty']
            pnl_rate = ((curr_price - buy_price) / buy_price) * 100
            
            # AI Analysis Conditions:
            # 1. Loss >= -0.4% (Early stop-loss)
            # 2. Profit >= +1% (Early profit-taking)
            should_analyze = False
            analysis_type = ""
            
            if pnl_rate < -0.4:
                should_analyze = True
                analysis_type = "RISK"
                logger.info(f"⚠️ {name} ({market_type}) in Loss ({pnl_rate:.2f}%). Requesting AI Risk Analysis...")
            elif pnl_rate >= 1.0:
                should_analyze = True
                analysis_type = "PROFIT"
                logger.info(f"💰 {name} ({market_type}) in Profit ({pnl_rate:.2f}%). Requesting AI Profit Analysis...")
            
            if should_analyze:
                # 2. Fetch Deep Data
                if market_type == "US":
                    daily_data = kis.get_overseas_daily_price(symbol, excg)
                    news = kis.get_overseas_news_titles(symbol)
                else:  # KR
                    daily_data = kis.get_daily_price(symbol)
                    news = kis.get_news_titles(symbol)
                
                # 3. AI Assessment
                try:
                    decision = selector.assess_risk(symbol, curr_price, buy_price, daily_data, news)
                    verdict = decision.get('decision')
                    reason = decision.get('reason')
                    
                    logger.info(f"🤖 AI Verdict ({name}): {verdict} - {reason}")
                    
                    if verdict == "SELL":
                        # Execute Early Cut/Profit-Taking
                        if market_type == "US":
                            res = kis.sell_overseas_order(symbol, qty, price=curr_price*0.99, excg_cd=excg)
                        else:  # KR - Market order for quick execution
                            res = kis.sell_order(symbol, qty, price=0)
                        
                        if "error" not in res:
                            currency = "USD" if market_type == "US" else "KRW"
                            
                            if analysis_type == "RISK":
                                msg = f"🚨 AI 리스크 관리 (손절): {name}\n이유: {reason}\n수익률: {pnl_rate:.2f}%"
                                result_type = "LOSS (AI)"
                            else:  # PROFIT
                                msg = f"💎 AI 수익 실현 (익절): {name}\n이유: {reason}\n수익률: {pnl_rate:.2f}%"
                                result_type = "WIN (AI)"
                            
                            bot.send_message(msg)
                            
                            trade['sell_price'] = curr_price
                            trade['profit_rate'] = pnl_rate
                            trade['result'] = result_type
                            trade['sell_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            self.trade_history.append(trade)
                            self.save_history()
                            
                            # Unsubscribe from WebSocket
                            if kis.websocket:
                                kis.websocket.unsubscribe_stock(symbol)
                                logger.info(f"📡 WebSocket unsubscribed: {symbol}")
                            
                            del self.active_trades[symbol]
                            self.update_balance()
                        else:
                            bot.send_message(f"⚠️ AI {analysis_type} 매도 실패 ({name}): {res.get('error')}")
                    else:
                        logger.info(f"✋ {name}: AI recommends HOLD. Continuing to monitor.")
                        
                except Exception as e:
                    logger.error(f"AI {analysis_type} Analysis Error ({name}): {e}")


    def clean_pending_orders(self):
        # Only implemented for KR currently
        orders = kis.get_orders() # Returns list of orders today
        if not orders: return

        for order in orders:
            rem_qty = int(order.get('rmn_qty', 0))
            if rem_qty > 0:
                ord_no = order['odno']
                name = order['prdt_name']
                logger.info(f"Checking Pending Order {ord_no} for {name} ({rem_qty} sh left)...")

    def liquidate_all_positions(self, market_filter="ALL"):
        """
        Liquidate positions. market_filter: "ALL", "KR", "US"
        """
        logger.info(f"Liquidating {market_filter}...")
        
        # 1. KR Liquidation
        if market_filter in ["ALL", "KR"]:
            holdings = kis.get_my_stock_balance()
            if holdings:
                for stock in holdings:
                    qty = int(stock['hldg_qty'])
                    if qty > 0:
                        kis.sell_order(stock['pdno'], qty, 0)
                        bot.send_message(f"⏹️ 국장 청산 완료: {stock['prdt_name']}")

        # 2. US Liquidation
        if market_filter in ["ALL", "US"]:
            # Step A: Cancel Outstanding Orders to Unlock Qty
            try:
                orders = kis.get_overseas_outstanding_orders()
                if orders:
                    logger.info(f"Found {len(orders)} outstanding US orders. Cancelling...")
                    for o in orders:
                        oid = o['odno']
                        sym = o['pdno']
                        excg = o.get('ovrs_excg_cd', 'NAS') # Default fallback
                        
                        logger.info(f"Cancelling Order {oid} for {sym} ({excg})")
                        kis.cancel_overseas_order(oid, sym, excg)
                    
                    # Wait for cancellation to process
                    time.sleep(2)
            except Exception as e:
                logger.error(f"Failed to cancel US orders: {e}")

            # Step B: Sell All Holdings
            ovs_bal = kis.get_overseas_balance()
            if ovs_bal and 'holdings' in ovs_bal:
                for stock in ovs_bal['holdings']:
                    # ovrs_ord_psbl_qty or cclt_qty based on availability
                    # Assuming ovrs_ord_psbl_qty is Orderable Qty
                    qty_str = stock.get('ovrs_ord_psbl_qty', '0')
                    qty = int(float(qty_str))
                    
                    # If qty is 0, check 'ovrs_cblc_qty' (Total Balance) as fallback IF we just cancelled orders
                    if qty == 0:
                        qty = int(float(stock.get('ovrs_cblc_qty', '0')))
                    
                    if qty > 0:
                        symbol = stock['ovrs_pdno']
                        excg = stock['ovrs_excg_cd']
                        name = stock['ovrs_item_name']
                        # Sell with Market Price (Price=0) for immediate execution
                        # User requested strict Market Order to ensure liquidation at session end.
                        # API Doc: Input "0" for Market Price.
                        kis.sell_overseas_order(symbol, qty, price=0, excg_cd=excg)
                        bot.send_message(f"⏹️ 미장 청산 완료 (시장가): {name}")

        keys_to_remove = [k for k, v in self.active_trades.items() 
                          if (market_filter == "ALL") or (v.get('market_type') == market_filter)]
        
        # Unsubscribe from WebSocket
        for k in keys_to_remove:
            if kis.websocket:
                kis.websocket.unsubscribe_stock(k)
                logger.info(f"📡 WebSocket unsubscribed: {k}")
            del self.active_trades[k]

        # Return remaining holdings count for verification
        rem_count = 0
        if market_filter in ["ALL", "US"]:
             ovs_bal = kis.get_overseas_balance()
             if ovs_bal and 'holdings' in ovs_bal:
                 rem_count += len(ovs_bal['holdings'])
        if market_filter in ["ALL", "KR"]:
             kr_bal = kis.get_my_stock_balance()
             if kr_bal:
                 rem_count += len(kr_bal)
                 
        if rem_count == 0:
            logger.info("✅ All positions successfully liquidated.")
        else:
            logger.warning(f"⚠️ Liquidation incomplete. {rem_count} positions remaining.")
            
        return rem_count

    def load_history(self):
        try:
            with open("trade_history.json", "r", encoding='utf-8') as f:
                self.trade_history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.trade_history = []

    def save_history(self):
        try:
            with open("trade_history.json", "w", encoding='utf-8') as f:
                json.dump(self.trade_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def get_daily_report(self, market_filter="ALL"):
        self.update_balance()
        
        # Filter History for Today (or just return all session history if that's what user wants. 
        # User asked for "Trade History", usually implies "Today's Closed Trades")
        # For simplicity, returning all history in file implies "Since Last Reset".
        # Ideally we filter by date, but let's show all available in history file.
        
        target_history = [t for t in self.trade_history if market_filter == "ALL" or t['market'] == market_filter]
        
        report = f"📊 [{market_filter if market_filter != 'ALL' else '통합'} 일일 리포트]\n"
        report += "\n📜 거래 내역:\n"
        
        total_profit_amt = 0
        total_invest_amt = 0
        
        if not target_history:
            report += "(체결된 거래 없음)\n"
        else:
            for idx, t in enumerate(target_history, 1):
                # Data Extraction
                name = t['name']
                qty = t['qty']
                buy_price = t['buy_price']
                sell_price = t['sell_price']
                buy_amt = buy_price * qty
                sell_amt = sell_price * qty
                profit = sell_amt - buy_amt
                roi = t['profit_rate']
                buy_time = t.get('buy_time', 'N/A')
                sell_time = t.get('sell_time', datetime.now().strftime("%H:%M:%S"))
                
                total_profit_amt += profit
                total_invest_amt += buy_amt
                
                # Format: Symbol / BuyAmt / BuyPrice(Qty) / BuyTime / SellAmt / SellTime / Profit / ROI
                report += f"{idx}. {name}\n"
                report += f"   매수 : {buy_amt:,.0f} ({buy_price:,.0f} x {qty}) @ {buy_time}\n"
                report += f"   매도 : {sell_amt:,.0f} @ {sell_time}\n"
                report += f"   손익 : {profit:+,.0f} ({roi:+.2f}%)\n"
                report += "-"*20 + "\n"

        # Footer
        total_roi = (total_profit_amt / total_invest_amt * 100) if total_invest_amt > 0 else 0.0
        
        report += "\n💰 요약:\n"
        report += f"총 수익금: {total_profit_amt:+,.0f}\n"
        report += f"총 수익률: {total_roi:+.2f}%\n"
        
        if market_filter in ["ALL", "KR"]:
            report += f"KRW 잔고 : {self.capital_krw:,.0f} KRW\n"
        if market_filter in ["ALL", "US"]:
            report += f"USD 잔고 : {self.capital_usd:,.2f} USD\n"
            
        return report

trade_manager = TradeManager()
