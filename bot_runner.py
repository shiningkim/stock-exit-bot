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

def check_telegram_commands():
    """텔레그램 최근 메시지를 읽어 '/sell 종목코드 [평단가]' 명령어 처리"""
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    res = requests.get(url).json()
    if not res.get("ok") or not res["result"]:
        return

    # 가장 마지막 메시지 확인 (중복 처리 방지를 위해 offset 업데이트)
    last_update = res["result"][-1]
    update_id = last_update["update_id"]
    requests.get(url, params={"offset": update_id + 1})

    message = last_update.get("message", {})
    if str(message.get("chat", {}).get("id")) != str(CHAT_ID):
        return

    text = message.get("text", "").strip()
    if text.startswith("/sell") or text.startswith("/check"):
        parts = text.split()
        if len(parts) >= 2:
            ticker = parts[1]
            buy_price = float(parts[2]) if len(parts) >= 3 else None
            report = analyze_individual_stock(ticker, buy_price)
            send_telegram(report)
        else:
            send_telegram("사용법: `/sell NVDA` 또는 `/sell 005930 75000` (평단가 선택)")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "market"
    if mode == "market":
        run_daily_market()
    elif mode == "command":
        check_telegram_commands()
