import streamlit as st
import pandas as pd
import numpy as np
import time
import subprocess
import sys
import requests
from ta.volatility import AverageTrueRange
from ta import momentum

# Install missing packages (if local)
for pkg in ["plotly"]:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="🔥 Crypto PRE-DIP / PRE-PUMP Screener", layout="wide")

# Constants
REFRESH_MIN = 15
BTC_SPOT = "BTCUSDT"
SYMS_CSV = "Tickers.csv"
PAIR_TF = "15m"
BTC_TF = "4h"
ATR_LEN = 96
BODY_FCTR = 0.3
VOL_MULT = 2.5

@st.cache_data(ttl=REFRESH_MIN * 60)
def load_symbols():
    df = pd.read_csv(SYMS_CSV, header=None, names=["symbol"])
    return df.symbol.astype(str).tolist()

def get_klines(symbol, interval, limit):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        data = requests.get(url, timeout=10).json()
        if isinstance(data, dict) and "code" in data:
            return pd.DataFrame()  # Error response
        df = pd.DataFrame(data, columns=[
            "Time", "Open", "High", "Low", "Close", "Volume",
            "x1", "x2", "x3", "x4", "x5", "x6"
        ])
        df["Time"] = pd.to_datetime(df["Time"], unit="ms")
        df = df.astype({
            "Open": "float", "High": "float", "Low": "float",
            "Close": "float", "Volume": "float"
        })
        return df[["Time", "Open", "High", "Low", "Close", "Volume"]]
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=REFRESH_MIN * 60)
def run_screening():
    syms = load_symbols()
    rows = []

    btc_df = get_klines(BTC_SPOT, BTC_TF, 22)
    if btc_df.empty:
        return pd.DataFrame(columns=["Symbol", "Score", "BTC<EMA21", "Weak+Vol", "RSI<30", "State", "Chart"]), 0.0, 0.0

    btc_close = btc_df["Close"].iat[-1]
    btc_ema21 = btc_df["Close"].ewm(span=21).mean().iat[-1]
    btcBelow = btc_close < btc_ema21

    for symbol in syms:
        df = get_klines(symbol, PAIR_TF, ATR_LEN + 2)
        if df.empty or len(df) < ATR_LEN:
            continue

        close = df["Close"].iat[-1]
        vol = df["Volume"].iat[-1]
        base = df["Close"].tail(ATR_LEN).mean()
        vavg = df["Volume"].tail(ATR_LEN).mean()
        atr = AverageTrueRange(df["High"], df["Low"], df["Close"], ATR_LEN).average_true_range().iat[-1]
        rsi = momentum.RSIIndicator(df["Close"], window=14).rsi().iat[-1]

        cond1 = btcBelow
        cond2 = close < base - BODY_FCTR * atr and vol > vavg * VOL_MULT
        cond3 = rsi < 30
        conditions = [cond1, cond2, cond3]
        score = sum(conditions)

        if score >= 1:
            state = {3: "🚨 FULL PRE-DIP 🚨", 2: "⚠️ NEAR-DIP", 1: "🔥 WARM-DIP"}[score]
            rows.append({
                "Symbol": symbol,
                "Score": score,
                "BTC<EMA21": cond1,
                "Weak+Vol": cond2,
                "RSI<30": cond3,
                "State": state,
                "Chart": df
            })

    if not rows:
        return pd.DataFrame(columns=["Symbol", "Score", "BTC<EMA21", "Weak+Vol", "RSI<30", "State", "Chart"]), btc_close, btc_ema21

    df_all = pd.DataFrame(rows).sort_values("Score", ascending=False)
    return df_all, btc_close, btc_ema21

# UI
st.title("🔥 Crypto PRE-DIP / PRE-PUMP Screener")

with st.spinner("🔄 Fetching data & screening..."):
    df, btc_close, btc_ema21 = run_screening()

st.markdown(
    f"""<div style='font-size:150%; font-weight:bold;'>
    BTCUSDT (4h) — Close: {btc_close:.2f} | EMA-21: {btc_ema21:.2f} | Status: {'🟢 Below EMA' if btc_close < btc_ema21 else '🔴 Above EMA'}
    </div>""",
    unsafe_allow_html=True
)

if not df.empty:
    if any(df["Score"] == 3):
        st.error("🚨 FULL PRE-DIP DETECTED! Act Fast.")
    elif any(df["Score"] == 2):
        st.warning("⚠️ NEAR-DIP Conditions Detected.")
    elif any(df["Score"] == 1):
        st.info("🔥 Only warm dips at the moment.")
else:
    st.success("✅ No dip conditions met right now. Market may be stable or bullish.")

st.markdown(f"""
### 🚦 Condition Indicators
- 🟢 = **Condition Met**
- 🔴 = **Condition Not Met**

**Conditions:**
1. BTC < EMA-21 (4h)
2. Weak Price + Vol Spike (15m)
3. RSI < 30 (Spot-based condition)
""")

if df.empty:
    st.warning("No triggers met currently.")
else:
    for score_level, label in zip([3, 2, 1], ["🚨 FULL PRE-DIP 🚨", "⚠️ NEAR-DIP", "🔥 WARM-DIP"]):
        subset = df[df['Score'] == score_level]
        if not subset.empty:
            st.subheader(label)
            for _, row in subset.iterrows():
                with st.expander(f"{row['Symbol']} | {row['State']}"):
                    c1, c2, c3 = row['BTC<EMA21'], row['Weak+Vol'], row['RSI<30']
                    st.write(f"BTC<EMA21: {'🟢' if c1 else '🔴'}")
                    st.write(f"Weak+Vol: {'🟢' if c2 else '🔴'}")
                    st.write(f"RSI<30: {'🟢' if c3 else '🔴'}")

                    chart_df = row["Chart"].copy()
                    chart_df["EMA21"] = chart_df["Close"].ewm(span=21).mean()
                    chart_df["VolSpike"] = chart_df["Volume"] > chart_df["Volume"].rolling(ATR_LEN).mean() * VOL_MULT

                    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[0.7, 0.3])

                    fig.add_trace(go.Candlestick(
                        x=chart_df["Time"],
                        open=chart_df["Open"], high=chart_df["High"],
                        low=chart_df["Low"], close=chart_df["Close"], name="Candles"), row=1, col=1)

                    fig.add_trace(go.Scatter(
                        x=chart_df["Time"], y=chart_df["EMA21"],
                        mode='lines', name="EMA21", line=dict(color='orange', dash='dash')), row=1, col=1)

                    fig.add_trace(go.Bar(
                        x=chart_df["Time"], y=chart_df["Volume"],
                        name="Volume", marker_color=['red' if spike else 'gray' for spike in chart_df["VolSpike"]]),
                        row=2, col=1)

                    fig.update_layout(height=500, margin=dict(l=10, r=10, t=20, b=20),
                                      showlegend=True, xaxis_rangeslider_visible=False)

                    st.plotly_chart(fig, use_container_width=True)

st.write(f"🕒 Last refreshed: {time.strftime('%Y-%m-%d %H:%M:%S')}")
