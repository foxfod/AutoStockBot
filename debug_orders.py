import logging
from app.core.kis_api import kis
import sys

# Force UTF-8
sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DebugOrders")

def check_orders():
    logger.info("🔍 조회 중... (오늘 주문 내역)")
    
    orders = kis.get_orders()
    if not orders:
        logger.info("❌ 오늘 주문 내역이 없습니다.")
        return

    logger.info(f"📋 총 주문 수: {len(orders)}건")
    for o in orders:
        name = o['prdt_name']
        side = "매수" if o['sll_buy_dvsn_cd'] == '02' else "매도"
        qty = int(o['ord_qty'])
        filled_qty = int(o['tot_ccld_qty'])
        price = float(o['ord_unpr'])
        
        status = "체결" if qty == filled_qty else "미체결/부분체결"
        if filled_qty == 0: status = "전량 미체결"
        
        logger.info(f"[{status}] {side} {name}: {filled_qty}/{qty}주 @ {price:,.0f}원 (주문번호: {o['odno']})")

if __name__ == "__main__":
    check_orders()
