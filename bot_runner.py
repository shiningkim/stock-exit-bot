import os
import sys
import requests
from analyzer import analyze_market_index, analyze_individual_stock

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

def run_daily_market():
    nq = analyze_market_index("^IXIC", "NASDAQ")
    sp = analyze_market_index("^GSPC", "S&P 500")

    max_dist = max(nq['dist_count'], sp['dist_count'])
    if max_dist >= 5 or (not nq['above_50'] and not sp['above_50']):
        verdict = "🔴 **위험 (시장 이탈 / 현금 비중 확대)**"
    elif max_dist >= 3:
        verdict = "🟡 **주의 (신규 매수 자제 / 손절선 타이트하게 관리)**"
    else:
        verdict = "🟢 **양호 (상승 추세 유지 / 주도주 보유)**"

    msg = (
        f"🇺🇸 **[미국 증시 마감 Exit 브리핑]**\n\n"
        f"**시장 상태:** {verdict}\n\n"
        f"• **NASDAQ:** `{nq['close']}` ({nq['change']:+.2f}%)\n"
        f"  └ 50일선: `{'상회' if nq['above_50'] else '이탈'} ({nq['gap_50']:+.1f}%)` | 분배일: **{nq['dist_count']}회** {nq['dist_dates']}\n"
        f"• **S&P 500:** `{sp['close']}` ({sp['change']:+.2f}%)\n"
        f"  └ 50일선: `{'상회' if sp['above_50'] else '이탈'} ({sp['gap_50']:+.1f}%)` | 분배일: **{sp['dist_count']}회** {sp['dist_dates']}\n\n"
        f"💡 *최근 25거래일 내 분배일 5회 이상 누적 시 시장 정점(Exit) 신호로 간주합니다.*"
    )
    send_telegram(msg)

def run_stock_check():
    ticker = os.environ.get("INPUT_TICKER", "").strip()
    buy_price_str = os.environ.get("INPUT_BUY_PRICE", "").strip()

    if not ticker:
        send_telegram("❌ 종목 티커가 입력되지 않았습니다.")
        return

    buy_price = None
    if buy_price_str:
        try:
            buy_price = float(buy_price_str.replace(",", ""))
        except ValueError:
            pass

    report = analyze_individual_stock(ticker, buy_price)
    send_telegram(report)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "market"
    if mode == "market":
        run_daily_market()
    elif mode == "stock":
        run_stock_check()
