import time
import pandas as pd
import numpy as np
import streamlit as st
import requests
from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="🔥 Crypto PRE-DIP Screener",
    layout="wide"
)

REFRESH_MIN = 15
SYMS_CSV = "Tickers.csv"
PAIR_TF = "15m"
BTC_TF = "4h"
ATR_LEN = 96
BODY_FCTR = 0.3
VOL_MULT = 2.5

@st.cache_data(ttl=REFRESH_MIN * 60)
def load_symbols():
    df = pd.read_csv(SYMS_CSV, header=None, names=["symbol"])
    return df.symbol.tolist()

@st.cache_data(ttl=REFRESH_MIN * 60)
def fetch_ohlcv(symbol, interval, limit):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    r = requests.get(url)
    if r.status_code != 200:
        return pd.DataFrame()
    df = pd.DataFrame(r.json(), columns=[
        "ts", "o", "h", "l", "c", "v", "x1", "x2", "x3", "x4", "x5"
    ])
    df = df.astype({"o": float, "h": float, "l": float, "c": float, "v": float})
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df[["ts", "o", "h", "l", "c", "v"]]

@st.cache_data(ttl=REFRESH_MIN * 60)
def run_screening():
    syms = load_symbols()
    rows = []

    btc_df = fetch_ohlcv("BTCUSDT", BTC_TF, 22)
    if btc_df.empty:
        return pd.DataFrame(), 0.0, 0.0

    btc_close = btc_df["c"].iloc[-1]
    btc_ema21 = btc_df["c"].ewm(span=21).mean().iloc[-1]
    btc_below = btc_close < btc_ema21

    for s in syms:
        df = fetch_ohlcv(s, PAIR_TF, ATR_LEN + 2)
        if df.empty or len(df) < ATR_LEN:
            continue

        close = df["c"].iloc[-1]
        vol = df["v"].iloc[-1]
        base = df["c"].tail(ATR_LEN).mean()
        atr = AverageTrueRange(df["h"], df["l"], df["c"], ATR_LEN).average_true_range().iloc[-1]
        vavg = df["v"].tail(ATR_LEN).mean()
        rsi = RSIIndicator(df["c"], 14).rsi().iloc[-1]

        cond1 = btc_below
        cond2 = close < base - BODY_FCTR * atr and vol > vavg * VOL_MULT
        cond3 = rsi < 30

        conditions = [cond1, cond2, cond3]
        score = sum(conditions)

        if score >= 1:
            label = {3: "🚨 FULL PRE-DIP", 2: "⚠️ NEAR DIP", 1: "🔥 WARM DIP"}[score]
            df["EMA21"] = df["c"].ewm(span=21).mean()
            rows.append({
                "Symbol": s,
                "Score": score,
                "BTC<EMA": cond1,
                "Weak+Vol": cond2,
                "RSI<30": cond3,
                "State": label,
                "Chart": df
            })

    df_all = pd.DataFrame(rows).sort_values("Score", ascending=False)
    return df_all, btc_close, btc_ema21

# UI Rendering
st.title("🔥 Crypto PRE-DIP Screener")

with st.spinner("⏳ Screening market..."):
    df, btc_close, btc_ema21 = run_screening()

st.markdown(
    f"<div style='font-size:140%; font-weight:bold;'>"
    f"BTCUSDT (4h) — Close: {btc_close:.2f} | EMA-21: {btc_ema21:.2f} | "
    f"Status: {'🟢 Below EMA' if btc_close < btc_ema21 else '🔴 Above EMA'}"
    f"</div>",
    unsafe_allow_html=True
)

if df.empty:
    st.success("✅ No dip conditions met right now.")
else:
    st.warning(f"⚠️ {len(df)} coins show dip signals!")

st.markdown("### 📊 Dip Condition Breakdown")
st.markdown("""
- 🟢 = Condition Met  
- 🔴 = Not Met

**Conditions Checked:**  
1. BTC < EMA-21 (4h)  
2. Weak Price + Vol Spike (15m)  
3. RSI < 30 (Oversold)
""")

for level, label in zip([3, 2, 1], ["🚨 FULL PRE-DIP", "⚠️ NEAR DIP", "🔥 WARM DIP"]):
    subset = df[df["Score"] == level]
    if not subset.empty:
        st.subheader(label)
        for _, row in subset.iterrows():
            with st.expander(f"{row['Symbol']}"):
                st.write(f"BTC < EMA21: {'🟢' if row['BTC<EMA'] else '🔴'}")
                st.write(f"Weak+Vol: {'🟢' if row['Weak+Vol'] else '🔴'}")
                st.write(f"RSI < 30: {'🟢' if row['RSI<30'] else '🔴'}")

                chart_df = row["Chart"].copy()
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02)
                fig.add_trace(go.Candlestick(
                    x=chart_df["ts"], open=chart_df["o"], high=chart_df["h"],
                    low=chart_df["l"], close=chart_df["c"], name="Candles"
                ), row=1, col=1)
                fig.add_trace(go.Scatter(
                    x=chart_df["ts"], y=chart_df["EMA21"],
                    line=dict(color="orange", dash="dash"), name="EMA21"
                ), row=1, col=1)
                fig.add_trace(go.Bar(
                    x=chart_df["ts"], y=chart_df["v"], name="Volume"
                ), row=2, col=1)
                fig.update_layout(height=500, showlegend=True)
                st.plotly_chart(fig, use_container_width=True)

st.write(f"🕒 Last refreshed: {time.strftime('%Y-%m-%d %H:%M:%S')}")
