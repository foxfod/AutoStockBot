import json
import logging
from datetime import datetime
from app.core.config import settings
from app.core.market_analyst import market_analyst
import openai

logger = logging.getLogger(__name__)

class StrategyOptimizer:
    def __init__(self):
        self.config_file = "strategy_config.json"
        self.history_file = "trade_history.json"
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    def load_config(self):
        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except:
            return {}

    def save_config(self, new_config):
        try:
            with open(self.config_file, "w") as f:
                json.dump(new_config, f, indent=4)
            logger.info("Strategy Config Updated.")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def analyze_history(self, market_type="KR"):
        """Calculate daily performance stats"""
        try:
            with open(self.history_file, "r", encoding='utf-8') as f:
                history = json.load(f)
        except:
            return {"win_rate": 0, "pnl": 0, "count": 0}

        # Filter for TODAY (or recent session)
        # For simplicity, we just analyze the last 10 trades if date filtering is complex, 
        # but let's try to filter by "sell_time" matching today.
        today = datetime.now().strftime("%Y-%m-%d")
        
        target_trades = [
            t for t in history 
            if t.get('market_type') == market_type and t.get('sell_time', '').startswith(today)
        ]
        
        if not target_trades:
            return {"win_rate": 0, "pnl": 0, "count": 0}
            
        wins = sum(1 for t in target_trades if t['profit_rate'] > 0)
        total = len(target_trades)
        avg_pnl = sum(t['profit_rate'] for t in target_trades) / total
        
        return {
            "win_rate": round((wins/total)*100, 1),
            "pnl": round(avg_pnl, 2),
            "count": total
        }

    def run_optimization(self, market_type="KR"):
        """
        1. Analyze Performance
        2. Analyze Market
        3. Ask AI for Parameter Tuning
        4. Apply Changes
        """
        logger.info(f"Running Optimization for {market_type}...")
        
        # 1. Performance
        stats = self.analyze_history(market_type)
        logger.info(f"Daily Stats: {stats}")
        
        # 2. Market Context
        market_status = market_analyst.get_market_status(market_type)
        market_desc = market_status['description']
        trend = market_status['trend']
        
        # 3. AI Prompt
        prompt = f"""
        You are an elite Algo-Trading Strategist. Analyze today's performance and market conditions to tune parameters for tomorrow.
        
        [Context]
        - Market: {market_type} ({trend}, {market_desc})
        - Today's Performance: {stats['count']} Trades, Win Rate {stats['win_rate']}%, Avg P&L {stats['pnl']}%
        - Leading Sectors (Hypothetical): Analyze implies volatility.
        
        [Current Parameters]
        - Target Profit: 3.0%
        - Stop Loss: 2.0%
        
        [Goal]
        - Suggest NEW parameters to maximize profit and minimize risk for tomorrow.
        - Rules: 
          1. Stop Loss range: 1.5% ~ 5.0%
          2. Target Profit range: 2.0% ~ 10.0%
          3. If Market is BEAR, tighten Stop Loss and lower Target.
          4. If Market is BULL, widen Target.
        
        [Output Format]
        JSON Only:
        {{
            "target_profit_rate": float,
            "stop_loss_rate": float,
            "reason": "string summary of why"
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": "You are a JSON-speaking Trading Optimizer."},
                          {"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"AI Optimization Result: {result}")
            
            # 4. Apply Changes
            config = self.load_config()
            
            # Safe access (create key if missing)
            key = "kr_parameters" if market_type == "KR" else "us_parameters"
            if key not in config: config[key] = {}
            
            config[key]['target_profit_rate'] = result['target_profit_rate']
            config[key]['stop_loss_rate'] = result['stop_loss_rate']
            config["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            config["market_sentiment"] = trend
            
            self.save_config(config)
            
            return result
            
        except Exception as e:
            logger.error(f"Optimization Failed: {e}")
            return None

optimizer = StrategyOptimizer()
