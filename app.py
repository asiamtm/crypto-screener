import time
import pandas as pd
import numpy as np
import streamlit as st
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.volatility import AverageTrueRange

st.set_page_config(page_title="🔥 Crypto PRE-DIP / PRE-PUMP Screener", layout="wide")

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

def fetch_ohlcv_klines(symbol, interval="15m", limit=100):
    url = f"https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(url, params=params)
    if r.status_code != 200:
        return pd.DataFrame()
    df = pd.DataFrame(r.json(), columns=[
        "ts", "o", "h", "l", "c", "v", "x1", "x2", "x3", "x4", "x5"
    ])
    df = df.astype({"o": float, "h": float, "l": float, "c": float, "v": float})
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df[["ts", "o", "h", "l", "c", "v"]]

def fetch_btc_status():
    df = fetch_ohlcv_klines(BTC_SPOT, interval=BTC_TF, limit=22)
    if df.empty:
        return 0.0, 0.0, False
    btc_close = df["c"].iloc[-1]
    btc_ema21 = df["c"].ewm(span=21).mean().iloc[-1]
    return btc_close, btc_ema21, btc_close < btc_ema21

@st.cache_data(ttl=REFRESH_MIN * 60)
def run_screening():
    syms = load_symbols()
    btc_close, btc_ema21, btcBelow = fetch_btc_status()

    rows = []
    for symbol in syms:
        df = fetch_ohlcv_klines(symbol, interval=PAIR_TF, limit=ATR_LEN + 2)
        if df.empty or len(df) < ATR_LEN:
            continue

        close = df["c"].iat[-1]
        vol = df["v"].iat[-1]
        base = df["c"].tail(ATR_LEN).mean()
        atr = AverageTrueRange(df["h"], df["l"], df["c"], ATR_LEN).average_true_range().iat[-1]
        vavg = df["v"].tail(ATR_LEN).mean()

        rsi = 100 - (100 / (1 + df["c"].pct_change().add(1).rolling(14).mean().iloc[-1]))

        cond1 = btcBelow
        cond2 = close < base - BODY_FCTR * atr and vol > vavg * VOL_MULT
        cond3 = rsi < 30

        score = sum([cond1, cond2, cond3])

        if score >= 1:
            rows.append({
                "Symbol": symbol,
                "Score": score,
                "BTC<EMA21": cond1,
                "Weak+Vol": cond2,
                "RSI<30": cond3,
                "Chart": df
            })

    df_all = pd.DataFrame(rows).sort_values("Score", ascending=False)
    return df_all, btc_close, btc_ema21

# === UI ===
st.title("🔥 Crypto PRE-DIP / PRE-PUMP Screener")

with st.spinner("🔄 Fetching spot data..."):
    df, btc_close, btc_ema21 = run_screening()

st.markdown(f"""
### BTCUSDT (4h) — Close: {btc_close:.2f} | EMA-21: {btc_ema21:.2f} | Status: {'🟢 Below EMA' if btc_close < btc_ema21 else '🔴 Above EMA'}

🚦 **Condition Indicators**
- 🟢 = Condition Met
- 🔴 = Condition Not Met

**Conditions:**
1. BTC < EMA-21 (4h)
2. Weak Price + Vol Spike (15m)
3. RSI < 30 (Spot-based condition)
""")

if df.empty:
    st.success("✅ No dip conditions met right now. Market may be stable or bullish.")
else:
    for score_level, label in zip([3, 2, 1], ["🚨 FULL PRE-DIP 🚨", "⚠️ NEAR-DIP", "🔥 WARM-DIP"]):
        subset = df[df['Score'] == score_level]
        if not subset.empty:
            st.subheader(label)
            for _, row in subset.iterrows():
                with st.expander(row["Symbol"]):
                    st.write(f"BTC<EMA21: {'🟢' if row['BTC<EMA21'] else '🔴'}")
                    st.write(f"Weak+Vol: {'🟢' if row['Weak+Vol'] else '🔴'}")
                    st.write(f"RSI<30: {'🟢' if row['RSI<30'] else '🔴'}")

                    dfc = row['Chart'].copy()
                    dfc["EMA21"] = dfc["c"].ewm(span=21).mean()
                    dfc["VolSpike"] = dfc["v"] > dfc["v"].rolling(ATR_LEN).mean() * VOL_MULT

                    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03)
                    fig.add_trace(go.Candlestick(x=dfc.ts, open=dfc.o, high=dfc.h, low=dfc.l, close=dfc.c, name="Candles"), row=1, col=1)
                    fig.add_trace(go.Scatter(x=dfc.ts, y=dfc.EMA21, mode="lines", name="EMA21", line=dict(color="orange")), row=1, col=1)
                    fig.add_trace(go.Bar(x=dfc.ts, y=dfc.v, name="Volume",
                                         marker_color=["red" if v else "gray" for v in dfc["VolSpike"]]), row=2, col=1)
                    fig.update_layout(height=500, showlegend=True, margin=dict(l=10, r=10, t=20, b=20))
                    st.plotly_chart(fig, use_container_width=True)

st.write(f"🕒 Last refreshed: {time.strftime('%Y-%m-%d %H:%M:%S')}")
