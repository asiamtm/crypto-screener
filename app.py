import asyncio
import time
import pandas as pd
import numpy as np
import streamlit as st
import subprocess
import sys

import os
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

# Auto-install missing packages
for pkg in ["matplotlib", "plotly"]:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.volatility import AverageTrueRange
from binance import AsyncClient

st.set_page_config(
    page_title="🔥 Crypto PRE-DIP / PRE-PUMP Screener",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

async def fetch_funding(client, symbols):
    out = {}
    for s in symbols:
        try:
            data = await client.futures_mark_price(symbol=s)
            out[s] = float(data["lastFundingRate"])
        except Exception as e:
            print(f"Funding rate fetch error for {s}: {e}")
            out[s] = np.nan
    return out

async def fetch_ohlcv(client, symbol):
    try:
        bars = await client.get_klines(
            symbol=symbol, interval=PAIR_TF, limit=ATR_LEN + 2
        )
        df = pd.DataFrame(bars, columns=[
            "ts","o","h","l","c","v","x1","x2","x3","x4","x5","x6"
        ])
        df = df.astype({"o":"float","h":"float","l":"float","c":"float","v":"float"})
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    except:
        df = pd.DataFrame()
    return df

async def fetch_btc_ema_and_close(client):
    bars = await client.get_klines(
        symbol=BTC_SPOT, interval=BTC_TF, limit=22
    )
    btc_df = pd.DataFrame(bars)
    btc_close = float(btc_df[4].astype(float).iat[-1])
    btc_ema21 = float(btc_df[4].astype(float).rolling(21).mean().iat[-1])
    return btc_close, btc_ema21, btc_close < btc_ema21

async def load_and_screen():
    syms = load_symbols()
    client = AsyncClient(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)
    await client._init_session()  # Avoids ping that gets blocked
  
    frates = await fetch_funding(client, syms)
    funding_values = [f for f in frates.values() if not np.isnan(f) and f != 0.0]
    dynamic_threshold = np.percentile(funding_values, 25) if funding_values else -0.0001

    tasks = [fetch_ohlcv(client, s) for s in syms]
    ohlcvs = await asyncio.gather(*tasks)
    btc_close, btc_ema21, btcBelow = await fetch_btc_ema_and_close(client)

    await client.close_connection()

    rows = []
    for s, df in zip(syms, ohlcvs):
        fr = frates.get(s, np.nan)
        if df.empty or len(df) < ATR_LEN or np.isnan(fr):
            continue

        close, vol = df.c.iat[-1], df.v.iat[-1]
        base = df.c.tail(ATR_LEN).mean()
        atr = AverageTrueRange(df.h, df.l, df.c, ATR_LEN).average_true_range().iat[-1]
        vavg = df.v.tail(ATR_LEN).mean()

        conditions = [
            btcBelow,
            close < base - BODY_FCTR * atr and vol > vavg * VOL_MULT,
            fr < dynamic_threshold
        ]
        score = sum(conditions)

        if score >= 1:
            state = {3: "🚨 FULL PRE-DIP 🚨", 2: "⚠️ NEAR-DIP", 1: "🔥 WARM-DIP"}[score]
            rows.append({
                "Symbol": s,
                "Score": score,
                "BTC<EMA21": conditions[0],
                "Weak+Vol": conditions[1],
                "Fund<Thr": conditions[2],
                "FundingRate": fr,
                "State": state,
                "Chart": df
            })

    df_all = pd.DataFrame(rows).sort_values("Score", ascending=False)
    return df_all, dynamic_threshold, btc_close, btc_ema21

st.title("🔥 Crypto PRE-DIP / PRE-PUMP Screener")

with st.spinner("🔄 Fetching data & screening..."):
    df, dynamic_threshold, btc_close, btc_ema21 = asyncio.run(load_and_screen())

st.markdown(
    f"""<div style='font-size:150%; font-weight:bold;'>
    BTCUSDT (4h) — Close: {btc_close:.2f} | EMA-21: {btc_ema21:.2f} | Status: {'🟢 Below EMA' if btc_close < btc_ema21 else '🔴 Above EMA'}
    </div>""",
    unsafe_allow_html=True
)

if not df.empty:
    if any(df['Score'] == 3):
        st.error("🚨 FULL PRE-DIP DETECTED! Act Fast.")
    elif any(df['Score'] == 2):
        st.warning("⚠️ NEAR-DIP Conditions Detected.")
    elif any(df['Score'] == 1):
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
3. Funding Rate below dynamic threshold ({dynamic_threshold:.6f})
""")

if df.empty:
    st.warning("No triggers met currently.")
else:
    for score_level, label in zip([3, 2, 1], ["🚨 FULL PRE-DIP 🚨", "⚠️ NEAR-DIP", "🔥 WARM-DIP"]):
        subset = df[df['Score'] == score_level]
        if not subset.empty:
            st.subheader(label)
            for _, row in subset.iterrows():
                with st.expander(f"{row['Symbol']} | Funding: {row['FundingRate']:.6f}"):
                    c1, c2, c3 = row['BTC<EMA21'], row['Weak+Vol'], row['Fund<Thr']
                    st.write(f"BTC<EMA21: {'🟢' if c1 else '🔴'}")
                    st.write(f"Weak+Vol: {'🟢' if c2 else '🔴'}")
                    st.write(f"Fund<Thr: {'🟢' if c3 else '🔴'}")

                    chart_df = row['Chart'][['ts', 'o', 'h', 'l', 'c', 'v']].rename(
                        columns={"ts": "Time", "o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
                    chart_df.set_index("Time", inplace=True)
                    chart_df['EMA21'] = chart_df['Close'].ewm(span=21).mean()
                    chart_df['VolSpike'] = chart_df['Volume'] > chart_df['Volume'].rolling(ATR_LEN).mean() * VOL_MULT

                    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                        vertical_spacing=0.02, row_heights=[0.7, 0.3])

                    fig.add_trace(go.Candlestick(
                        x=chart_df.index,
                        open=chart_df['Open'], high=chart_df['High'],
                        low=chart_df['Low'], close=chart_df['Close'], name='Candles'), row=1, col=1)

                    fig.add_trace(go.Scatter(
                        x=chart_df.index, y=chart_df['EMA21'],
                        mode='lines', name='EMA21', line=dict(color='orange', dash='dash')), row=1, col=1)

                    fig.add_trace(go.Bar(
                        x=chart_df.index, y=chart_df['Volume'],
                        name='Volume', marker_color=['red' if v else 'gray' for v in chart_df['VolSpike']]),
                        row=2, col=1)

                    fig.update_layout(
                        height=500,
                        margin=dict(l=10, r=10, t=20, b=20),
                        showlegend=True,
                        xaxis_rangeslider_visible=False
                    )

                    st.plotly_chart(fig, use_container_width=True)

st.write(f"🕒 Last refreshed: {time.strftime('%Y-%m-%d %H:%M:%S')}")
