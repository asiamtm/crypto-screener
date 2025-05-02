import requests
import pandas as pd
import numpy as np
import streamlit as st
import time
from datetime import datetime, timedelta
from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator
from plotly.subplots import make_subplots
import plotly.graph_objects as go

# === CONFIG ===
BTC_SYMBOL = "BTCUSDT"
SYMBOL_LIST_URL = "https://api.binance.com/api/v3/exchangeInfo"
CANDLE_URL = "https://api.binance.com/api/v3/klines"
PAIR_TF = "15m"
BTC_TF = "4h"
ATR_LEN = 96
BODY_FCTR = 0.3
VOL_MULT = 2.5
RSI_LEN = 14

# === UI ===
st.set_page_config(page_title="🔥 PRE-DIP SCREENER", layout="wide")
st.title("🔥 Crypto PRE-DIP / PRE-PUMP Screener")

# === Functions ===

@st.cache_data(ttl=900)
def get_spot_symbols():
    res = requests.get(SYMBOL_LIST_URL).json()
    return [s["symbol"] for s in res["symbols"] if s["quoteAsset"] == "USDT" and s["status"] == "TRADING"]

@st.cache_data(ttl=900)
def fetch_ohlcv(symbol, interval, limit=100):
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    res = requests.get(CANDLE_URL, params=params).json()
    if not isinstance(res, list): return pd.DataFrame()
    df = pd.DataFrame(res, columns=[
        "ts", "o", "h", "l", "c", "v", "_", "_", "_", "_", "_", "_"
    ])
    df = df.astype({"o": float, "h": float, "l": float, "c": float, "v": float})
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df

def compute_conditions(df, btc_below):
    if df.empty or len(df) < ATR_LEN:
        return None

    close, vol = df["c"].iloc[-1], df["v"].iloc[-1]
    base = df["c"].tail(ATR_LEN).mean()
    atr = AverageTrueRange(df["h"], df["l"], df["c"], ATR_LEN).average_true_range().iloc[-1]
    vavg = df["v"].tail(ATR_LEN).mean()
    rsi = RSIIndicator(df["c"], window=RSI_LEN).rsi().iloc[-1]

    cond1 = btc_below
    cond2 = close < base - BODY_FCTR * atr and vol > vavg * VOL_MULT
    cond3 = rsi < 30

    return cond1, cond2, cond3, close, vol, atr, rsi

@st.cache_data(ttl=900)
def screen():
    symbols = get_spot_symbols()
    btc_df = fetch_ohlcv(BTC_SYMBOL, BTC_TF, 22)
    btc_close = btc_df["c"].iloc[-1] if not btc_df.empty else 0
    btc_ema21 = btc_df["c"].ewm(span=21).mean().iloc[-1] if not btc_df.empty else 0
    btc_below = btc_close < btc_ema21 if btc_close and btc_ema21 else False

    rows = []
    for symbol in symbols:
        df = fetch_ohlcv(symbol, PAIR_TF, ATR_LEN + 2)
        result = compute_conditions(df, btc_below)
        if result:
            c1, c2, c3, close, vol, atr, rsi = result
            score = sum([c1, c2, c3])
            if score > 0:
                rows.append({
                    "Symbol": symbol,
                    "Score": score,
                    "BTC<EMA21": c1,
                    "Weak+Vol": c2,
                    "RSI<30": c3,
                    "RSI": rsi,
                    "Chart": df
                })

    df = pd.DataFrame(rows).sort_values("Score", ascending=False)
    return df, btc_close, btc_ema21

# === Run Screen ===
with st.spinner("🔄 Screening market..."):
    df, btc_close, btc_ema21 = screen()

# === BTC Status ===
st.markdown(
    f"<div style='font-size:150%; font-weight:bold;'>"
    f"BTCUSDT (4h) — Close: {btc_close:.2f} | EMA-21: {btc_ema21:.2f} | "
    f"Status: {'🟢 Below EMA' if btc_close < btc_ema21 else '🔴 Above EMA'}"
    f"</div>", unsafe_allow_html=True)

# === Dip Alerts ===
if not df.empty:
    if any(df['Score'] == 3): st.error("🚨 FULL PRE-DIP DETECTED")
    elif any(df['Score'] == 2): st.warning("⚠️ NEAR-DIP Signals Present")
    elif any(df['Score'] == 1): st.info("🔥 Warm dips in market")
else:
    st.success("✅ No dip triggers met right now")

# === Legend ===
st.markdown(f"""
### 🚦 Condition Indicators
- 🟢 = **Condition Met**  🔴 = **Not Met**

**Conditions:**
1. BTC < EMA-21 (4h)
2. Weak price + volume spike (15m)
3. RSI < 30
""")

# === Output Charts ===
for score, label in zip([3, 2, 1], ["🚨 FULL PRE-DIP 🚨", "⚠️ NEAR-DIP", "🔥 WARM-DIP"]):
    subset = df[df["Score"] == score]
    if not subset.empty:
        st.subheader(label)
        for _, row in subset.iterrows():
            with st.expander(f"{row['Symbol']} | RSI: {row['RSI']:.2f}"):
                c1, c2, c3 = row["BTC<EMA21"], row["Weak+Vol"], row["RSI<30"]
                st.write(f"BTC<EMA21: {'🟢' if c1 else '🔴'}")
                st.write(f"Weak+Vol: {'🟢' if c2 else '🔴'}")
                st.write(f"RSI<30: {'🟢' if c3 else '🔴'}")

                dfc = row['Chart'].copy()
                dfc.rename(columns={"ts": "Time", "o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"}, inplace=True)
                dfc.set_index("Time", inplace=True)

                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(
                    x=dfc.index, open=dfc["Open"], high=dfc["High"],
                    low=dfc["Low"], close=dfc["Close"], name="Candles"), row=1, col=1)
                fig.add_trace(go.Scatter(
                    x=dfc.index, y=dfc["Close"].ewm(span=21).mean(),
                    mode="lines", name="EMA21", line=dict(color="orange", dash="dot")), row=1, col=1)
                fig.add_trace(go.Bar(
                    x=dfc.index, y=dfc["Volume"], name="Volume", marker_color="grey"), row=2, col=1)

                fig.update_layout(
                    height=500, margin=dict(l=10, r=10, t=30, b=20),
                    showlegend=True, xaxis_rangeslider_visible=False)

                st.plotly_chart(fig, use_container_width=True)

st.write(f"🕒 Last refreshed: {time.strftime('%Y-%m-%d %H:%M:%S')}")
