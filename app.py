import pandas as pd
import numpy as np
import streamlit as st
import requests
from ta.volatility import AverageTrueRange
import time

# === CONFIG ===
REFRESH_MIN = 15
PAIR_TF = "15m"
BTC_TF = "4h"
ATR_LEN = 96
BODY_FCTR = 0.3
VOL_MULT = 2.5

SPOT_BASE = "https://api.binance.com/api/v3"

st.set_page_config(
    page_title="🔥 Crypto PRE-DIP Screener",
    layout="wide",
    initial_sidebar_state="collapsed"
)

@st.cache_data(ttl=REFRESH_MIN * 60)
def load_symbols():
    df = pd.read_csv("Tickers.csv", header=None, names=["symbol"])
    return df.symbol.astype(str).tolist()

# === Retry Logic ===
from tenacity import retry, stop_after_attempt, wait_fixed

@retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
def fetch_ohlcv(symbol, interval, limit=ATR_LEN + 2):
    url = f"{SPOT_BASE}/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()  # Raises exception for non-2xx responses
        data = res.json()
        df = pd.DataFrame(data, columns=[
            "ts", "o", "h", "l", "c", "v", "x1", "x2", "x3", "x4", "x5", "x6"])
        df = df.astype({"o": float, "h": float, "l": float, "c": float, "v": float})
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return pd.DataFrame()  # Return empty dataframe on error

def fetch_btc_trend():
    df = fetch_ohlcv("BTCUSDT", BTC_TF, 22)
    if df.empty:
        return 0.0, 0.0, False
    close = df.c.iat[-1]
    ema = df.c.ewm(span=21).mean().iat[-1]
    return close, ema, close < ema

def run_screening():
    syms = load_symbols()
    rows = []
    btc_close, btc_ema21, btcBelow = fetch_btc_trend()

    for s in syms:
        print(f"Fetching data for symbol: {s}")  # Add logging
        df = fetch_ohlcv(s, PAIR_TF)
        if df.empty or len(df) < ATR_LEN:
            print(f"Skipping {s} due to insufficient data")
            continue

        close = df.c.iat[-1]
        vol = df.v.iat[-1]
        base = df.c.tail(ATR_LEN).mean()
        atr = AverageTrueRange(df.h, df.l, df.c, ATR_LEN).average_true_range().iat[-1]
        vavg = df.v.tail(ATR_LEN).mean()

        gain = df.c.pct_change().fillna(0)
        delta = gain.rolling(14).mean()
        loss = (-gain).rolling(14).mean()
        rs = delta / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_val = rsi.iat[-1] if not rsi.empty else 50

        cond1 = btcBelow
        cond2 = close < base - BODY_FCTR * atr and vol > vavg * VOL_MULT
        cond3 = rsi_val < 30

        conditions = [cond1, cond2, cond3]
        score = sum(conditions)

        if score >= 1:
            state = {3: "🚨 FULL PRE-DIP", 2: "⚠️ NEAR-DIP", 1: "🔥 WARM-DIP"}[score]
            rows.append({
                "Symbol": s,
                "Score": score,
                "BTC<EMA21": cond1,
                "Weak+Vol": cond2,
                "RSI<30": cond3,
                "RSI": rsi_val,
                "State": state
            })

    df_all = pd.DataFrame(rows).sort_values("Score", ascending=False)
    return df_all, btc_close, btc_ema21

# === Streamlit UI ===
st.title("🔥 Crypto PRE-DIP / PRE-PUMP Screener")
with st.spinner("🔄 Loading latest data..."):
    df, btc_close, btc_ema21 = run_screening()

st.markdown(
    f"""<div style='font-size:150%; font-weight:bold;'>
    BTCUSDT (4h) — Close: {btc_close:.2f} | EMA-21: {btc_ema21:.2f} | Status: {'🟢 Below EMA' if btc_close < btc_ema21 else '🔴 Above EMA'}
    </div>""",
    unsafe_allow_html=True
)

if df.empty or "Score" not in df.columns:
    st.success("✅ No dip conditions met right now. Market may be stable or bullish.")
else:
    st.markdown("""
    ### 📊 Dip Condition Breakdown
    🟢 = Condition Met  
    🔴 = Not Met  
    
    **Conditions Checked:**
    - BTC < EMA-21 (4h)
    - Weak Price + Vol Spike (15m)
    - RSI < 30 (Oversold)
    """)

    for level, label in zip([3, 2, 1], ["🚨 FULL PRE-DIP", "⚠️ NEAR-DIP", "🔥 WARM-DIP"]):
        subset = df[df["Score"] == level]
        if not subset.empty:
            st.subheader(label)
            st.dataframe(subset.set_index("Symbol"))

st.write(f"🕒 Last refreshed: {time.strftime('%Y-%m-%d %H:%M:%S')}")
