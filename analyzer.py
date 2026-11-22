import yfinance as yf
import pandas as pd
import numpy as np

def get_stock_data(ticker: str):
    """미국 티커 및 한국 종목코드(6자리) 자동 판별 수집"""
    ticker = ticker.strip().upper()
    if ticker.isdigit() and len(ticker) == 6:
        # 코스피(.KS) 먼저 조회 후 데이터 없으면 코스닥(.KQ) 조회
        df = yf.download(f"{ticker}.KS", period="1y", progress=False)
        if df.empty:
            df = yf.download(f"{ticker}.KQ", period="1y", progress=False)
            ticker_name = f"{ticker}.KQ"
        else:
            ticker_name = f"{ticker}.KS"
    else:
        df = yf.download(ticker, period="1y", progress=False)
        ticker_name = ticker

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df, ticker_name

def analyze_market_index(ticker: str, name: str):
    """미국 지수 분배일(Distribution Day) 및 이평선 이탈 분석"""
    df, _ = get_stock_data(ticker)
    df['SMA50'] = df['Close'].rolling(50).mean()
    df['SMA200'] = df['Close'].rolling(200).mean()
    df['Pct_Change'] = df['Close'].pct_change() * 100
    df['Vol_Up'] = df['Volume'] > df['Volume'].shift(1)

    # 최근 25거래일 내 분배일 계산 (-0.2% 이상 하락 + 전일 대비 거래량 증가)
    recent_25 = df.iloc[-25:].copy()
    dist_days = []
    
    for idx, row in recent_25.iterrows():
        if row['Pct_Change'] <= -0.20 and row['Vol_Up']:
            # 발생 이후 종가 기준 +5% 이상 반등했으면 분배일 무효화
            subsequent_max = df.loc[idx:, 'Close'].max()
            if (subsequent_max / row['Close'] - 1) * 100 < 5.0:
                dist_days.append(idx.strftime('%m/%d'))

    curr_close = df['Close'].iloc[-1]
    sma50 = df['SMA50'].iloc[-1]
    sma200 = df['SMA200'].iloc[-1]
    gap_50 = (curr_close / sma50 - 1) * 100

    return {
        "name": name,
        "close": round(curr_close, 2),
        "change": round(df['Pct_Change'].iloc[-1], 2),
        "dist_count": len(dist_days),
        "dist_dates": dist_days,
        "above_50": curr_close > sma50,
        "above_200": curr_close > sma200,
        "gap_50": round(gap_50, 2)
    }

def analyze_individual_stock(ticker: str, buy_price: float = None):
    """개별 종목 오닐(과열/정점) + 미네르비니(추세 훼손) 진단"""
    df, resolved_ticker = get_stock_data(ticker)
    if df.empty or len(df) < 200:
        return f"❌ `{ticker}` 데이터를 불러올 수 없거나 상장 기간이 200일 미만입니다."

    df['SMA50'] = df['Close'].rolling(50).mean()
    df['SMA200'] = df['Close'].rolling(200).mean()
    df['Vol_SMA50'] = df['Volume'].rolling(50).mean()
    df['Pct_Change'] = df['Close'].pct_change() * 100

    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    gap_50 = (curr['Close'] / curr['SMA50'] - 1) * 100
    gap_200 = (curr['Close'] / curr['SMA200'] - 1) * 100
    vol_ratio = (curr['Volume'] / curr['Vol_SMA50']) * 100

    # 1. 연속 상승일 수 계산 (이미지1-④)
    consec_up = 0
    for val in reversed(df['Pct_Change'].values):
        if val > 0: consec_up += 1
        else: break

    # 2. 매물 출회(Churning) 체크: 거래량 200% 이상 폭발 + 상승률 0.5% 미만 (이미지1-⑤)
    is_churning = (vol_ratio >= 200) and (abs(curr['Pct_Change']) < 0.5)

    # 3. 소진 갭(Exhaustion Gap): 200일선 대비 +50% 이상 상태 + 3% 이상 갭상승 후 음봉 (이미지1-③)
    gap_open = (curr['Open'] / prev['High'] - 1) * 100
    is_exhaustion_gap = (gap_200 >= 50) and (gap_open >= 3.0) and (curr['Close'] < curr['Open'])

    # 4. 50일선 대량 거래 하향 이탈 (추세 훼손)
    broken_50_vol = (curr['Close'] < curr['SMA50']) and (curr['Volume'] > curr['Vol_SMA50'])

    # 5. 최근 60일 고점 대비 하락폭 (트레일링 스탑 기준)
    peak_60 = df['High'].iloc[-60:].max()
    drop_from_peak = (curr['Close'] / peak_60 - 1) * 100

    # 리포트 생성
    warnings = []
    if gap_50 >= 30: warnings.append(f"🔥 **50일선 이격 과열:** +{gap_50:.1f}% (기준 +30% 이상)")
    if gap_200 >= 70: warnings.append(f"🔥 **200일선 이격 과열:** +{gap_200:.1f}% (기준 +70% 이상)")
    if consec_up >= 7: warnings.append(f"🔥 **클라이맥스 연속 상승:** {consec_up}거래일 연속 상승")
    if is_churning: warnings.append(f"⚠️ **매물 출회(Churning):** 거래량 {vol_ratio:.0f}% 폭발 대비 주가 정체")
    if is_exhaustion_gap: warnings.append(f"⚠️ **소진 갭 발생:** 갭상승({gap_open:.1f}%) 후 음봉 마감")
    if broken_50_vol: warnings.append(f"🚨 **50일선 대량거래 이탈:** 기관 매도 출회 경고")
    if drop_from_peak <= -10: warnings.append(f"🚨 **고점 대비 급락:** 60일 최고가 대비 {drop_from_peak:.1f}%")

    if buy_price:
        pnl = (curr['Close'] / buy_price - 1) * 100
        if pnl <= -7.0:
            warnings.append(f"🚨 **절대 손절선 도달:** 평단가 대비 {pnl:.1f}% (기준 -7~8%)")

    status = "✅ **추세 양호 (보유 지속)**"
    if any("🚨" in w for w in warnings):
        status = "🚨 **위험 경보 (손절 또는 전량 매도 고려)**"
    elif any("🔥" in w or "⚠️" in w for w in warnings):
        status = "🔥 **과열/정점 신호 (분할 익절 고려)**"

    msg = [
        f"🔍 **[{resolved_ticker} 매도/정점 진단]**",
        f"• 현재가: `{curr['Close']:,.2f}` ({curr['Pct_Change']:+.2f}%)",
        f"• 종합 판정: {status}\n",
        f"📊 **핵심 지표 현황**",
        f"• 50일선 이격: `{gap_50:+.1f}%` | 200일선 이격: `{gap_200:+.1f}%`",
        f"• 거래량(50일평균 대비): `{vol_ratio:.0f}%` | 연속상승: `{consec_up}일`",
        f"• 60일 고점 대비: `{drop_from_peak:.1f}%`"
    ]

    if warnings:
        msg.append("\n🚩 **포착된 매도/경계 신호**")
        msg.extend([f"• {w}" for w in warnings])
    else:
        msg.append("\n✨ 현재 포착된 오닐/미네르비니 매도 신호가 없습니다.")

    return "\n".join(msg)
