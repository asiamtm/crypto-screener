# 🔄 SPOT-ONLY VERSION: No Binance API key required
# ✅ Uses public REST endpoints to screen for dips on Binance spot pairs

import time
import pandas as pd
import numpy as np
import streamlit as st
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator

st.set_page_config(
    page_title="🔥 Crypto PRE-DIP / PRE-PUMP Screener (Spot Only)",
    layout="wide",
    initial_sidebar_state="collapsed"
)

REFRESH_MIN = 15
BTC_SPOT = "BTCUSDT"
SYMS_CSV = "Tickers.csv"
PAIR_TF = "15m"
BTC_TF = "4h"
ATR_LEN = 96
BODY_FCTR = 0.3
VOL_MULT = 2.5
RSI_CUTOFF = 30

@st.cache_data(ttl=REFRESH_MIN * 60)
def load_symbols():
    df = pd.read_csv(SYMS_CSV, header=None, names=["symbol"])
    return df.symbol.astype(str).tolist()

@st.cache_data(ttl=300)
def fetch_klines(symbol, interval="15m", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        data = requests.get(url).json()
        df = pd.DataFrame(data, columns=[
            "ts", "o", "h", "l", "c", "v", "x1", "x2", "x3", "x4", "x5", "x6"
        ])
        df = df.astype({"o": float, "h": float, "l": float, "c": float, "v": float})
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        return df
    except:
        return pd.DataFrame()

def fetch_btc_ema21():
    df = fetch_klines(BTC_SPOT, interval=BTC_TF, limit=30)
    if df.empty: return 0.0, 0.0, False
    close = df["c"].iloc[-1]
    ema21 = df["c"].ewm(span=21).mean().iloc[-1]
    return close, ema21, close < ema21

@st.cache_data(ttl=REFRESH_MIN * 60)
def run_screening():
    syms = load_symbols()
    btc_close, btc_ema21, btcBelow = fetch_btc_ema21()
    rows = []

    for sym in syms:
        df = fetch_klines(sym, interval=PAIR_TF, limit=ATR_LEN + 2)
        if df.empty or len(df) < ATR_LEN:
            continue

        close, vol = df["c"].iat[-1], df["v"].iat[-1]
        base = df["c"].tail(ATR_LEN).mean()
        atr = AverageTrueRange(df["h"], df["l"], df["c"], ATR_LEN).average_true_range().iloc[-1]
        vavg = df["v"].tail(ATR_LEN).mean()
        rsi = RSIIndicator(df["c"], window=14).rsi().iloc[-1]

        cond1 = btcBelow
        cond2 = close < base - BODY_FCTR * atr and vol > vavg * VOL_MULT
        cond3 = rsi < RSI_CUTOFF

        score = sum([cond1, cond2, cond3])
        if score >= 1:
            label = {3: "🚨 FULL PRE-DIP 🚨", 2: "⚠️ NEAR-DIP", 1: "🔥 WARM-DIP"}[score]
            rows.append({
                "Symbol": sym,
                "Score": score,
                "BTC<EMA21": cond1,
                "Weak+Vol": cond2,
                "RSI<30": cond3,
                "RSI": round(rsi, 2),
                "State": label,
                "Chart": df
            })

    df_all = pd.DataFrame(rows).sort_values("Score", ascending=False)
    return df_all, btc_close, btc_ema21

# === UI ===
st.title("🔥 Crypto PRE-DIP / PRE-PUMP Screener (Spot Only)")
with st.spinner("🔄 Fetching data & screening..."):
    df, btc_close, btc_ema21 = run_screening()

st.markdown(
    f"""<div style='font-size:150%; font-weight:bold;'>
    BTCUSDT (4h) — Close: {btc_close:.2f} | EMA-21: {btc_ema21:.2f} | Status: {'🟢 Below EMA' if btc_close < btc_ema21 else '🔴 Above EMA'}
    </div>""",
    unsafe_allow_html=True
)

if df.empty:
    st.success("✅ No dip conditions met right now. Market may be stable or bullish.")
else:
    if any(df['Score'] == 3):
        st.error("🚨 FULL PRE-DIP DETECTED! Act Fast.")
    elif any(df['Score'] == 2):
        st.warning("⚠️ NEAR-DIP Conditions Detected.")
    elif any(df['Score'] == 1):
        st.info("🔥 Only warm dips at the moment.")

st.markdown("""
### 🚦 Condition Indicators
- 🟢 = **Condition Met**
- 🔴 = **Condition Not Met**

**Conditions:**
1. BTC < EMA-21 (4h)
2. Weak Price + Vol Spike (15m)
3. RSI < 30 (Spot-based condition)
""")

if not df.empty:
    for score_level, label in zip([3, 2, 1], ["🚨 FULL PRE-DIP 🚨", "⚠️ NEAR-DIP", "🔥 WARM-DIP"]):
        subset = df[df['Score'] == score_level]
        if not subset.empty:
            st.subheader(label)
            for _, row in subset.iterrows():
                with st.expander(f"{row['Symbol']} | RSI: {row['RSI']:.2f}"):
                    st.write(f"BTC<EMA21: {'🟢' if row['BTC<EMA21'] else '🔴'}")
                    st.write(f"Weak+Vol: {'🟢' if row['Weak+Vol'] else '🔴'}")
                    st.write(f"RSI<30: {'🟢' if row['RSI<30'] else '🔴'}")

                    chart_df = row['Chart'][['ts', 'o', 'h', 'l', 'c', 'v']].rename(
                        columns={"ts": "Time", "o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
                    chart_df.set_index("Time", inplace=True)
                    chart_df['EMA21'] = chart_df['Close'].ewm(span=21).mean()
                    chart_df['VolSpike'] = chart_df['Volume'] > chart_df['Volume'].rolling(ATR_LEN).mean() * VOL_MULT

                    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[0.7, 0.3])

                    fig.add_trace(go.Candlestick(x=chart_df.index,
                                                 open=chart_df['Open'], high=chart_df['High'],
                                                 low=chart_df['Low'], close=chart_df['Close'], name='Candles'), row=1, col=1)

                    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['EMA21'],
                                             mode='lines', name='EMA21', line=dict(color='orange', dash='dash')), row=1, col=1)

                    fig.add_trace(go.Bar(x=chart_df.index, y=chart_df['Volume'],
                                         name='Volume', marker_color=['red' if v else 'gray' for v in chart_df['VolSpike']]), row=2, col=1)

                    fig.update_layout(height=500, margin=dict(l=10, r=10, t=20, b=20),
                                      showlegend=True, xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)

st.write(f"🕒 Last refreshed: {time.strftime('%Y-%m-%d %H:%M:%S')}")
