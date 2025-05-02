import time
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from binance.client import Client

# --- Config ---
st.set_page_config(page_title="🔥 Crypto PRE-DIP / PRE-PUMP Screener", layout="wide")

BTC_SYMBOL = "BTCUSDT"
PAIR_TF = Client.KLINE_INTERVAL_15MINUTE
BTC_TF = Client.KLINE_INTERVAL_4HOUR
TICKERS = ["ETHUSDT", "XRPUSDT", "SOLUSDT", "LTCUSDT", "BNBUSDT"]  # Adjust as needed
ATR_LEN = 96
RSI_LEN = 14
VOL_MULT = 2.5
BODY_FCTR = 0.3

# --- Binance Auth ---
BINANCE_API_KEY = st.secrets.get("BINANCE_API_KEY", "")
BINANCE_API_SECRET = st.secrets.get("BINANCE_API_SECRET", "")
client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)

# --- BTC EMA Trend ---
def get_btc_trend():
    klines = client.get_klines(symbol=BTC_SYMBOL, interval=BTC_TF, limit=22)
    closes = pd.Series([float(x[4]) for x in klines])
    btc_close = closes.iloc[-1]
    btc_ema21 = closes.ewm(span=21).mean().iloc[-1]
    return btc_close, btc_ema21, btc_close < btc_ema21

# --- Fetch OHLCV ---
def get_ohlcv(symbol):
    try:
        klines = client.get_klines(symbol=symbol, interval=PAIR_TF, limit=ATR_LEN + 2)
        df = pd.DataFrame(klines, columns=[
            "ts", "o", "h", "l", "c", "v", "c1", "c2", "c3", "c4", "c5", "c6"
        ])
        df = df.astype({"o": float, "h": float, "l": float, "c": float, "v": float})
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        return df[["ts", "o", "h", "l", "c", "v"]]
    except:
        return pd.DataFrame()

# --- Run Screener ---
def run_screening():
    btc_close, btc_ema21, btcBelow = get_btc_trend()
    rows = []

    for symbol in TICKERS:
        df = get_ohlcv(symbol)
        if df.empty or len(df) < ATR_LEN:
            continue

        close, vol = df.c.iat[-1], df.v.iat[-1]
        base = df.c.tail(ATR_LEN).mean()
        atr = df.h.tail(ATR_LEN).max() - df.l.tail(ATR_LEN).min()
        vavg = df.v.tail(ATR_LEN).mean()

        rsi = RSIIndicator(close=df["c"], window=RSI_LEN).rsi().iat[-1]

        cond1 = btcBelow
        cond2 = close < base - BODY_FCTR * atr and vol > vavg * VOL_MULT
        cond3 = rsi < 30

        conditions = [cond1, cond2, cond3]
        score = sum(conditions)

        if score > 0:
            rows.append({
                "Symbol": symbol,
                "Score": score,
                "BTC<EMA21": cond1,
                "Weak+Vol": cond2,
                "RSI<30": cond3,
                "RSI": rsi,
                "Chart": df
            })

    df_all = pd.DataFrame(rows).sort_values("Score", ascending=False)
    return df_all, btc_close, btc_ema21

# === UI ===

st.title("🔥 Crypto PRE-DIP / PRE-PUMP Screener")

with st.spinner("🔄 Fetching market data..."):
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
    st.warning("⚠️ Some dip conditions met. Review below.")

st.markdown("""
### 🚦 Condition Indicators
- 🟢 = **Condition Met**
- 🔴 = **Condition Not Met**

**Conditions:**
1. BTC < EMA-21 (4h)
2. Weak Price + Vol Spike (15m)
3. RSI < 30 (Spot-based condition)
""")

for score_level, label in zip([3, 2, 1], ["🚨 FULL PRE-DIP 🚨", "⚠️ NEAR-DIP", "🔥 WARM-DIP"]):
    subset = df[df["Score"] == score_level]
    if not subset.empty:
        st.subheader(label)
        for _, row in subset.iterrows():
            with st.expander(f"{row['Symbol']} | RSI: {row['RSI']:.1f}"):
                st.write(f"BTC<EMA21: {'🟢' if row['BTC<EMA21'] else '🔴'}")
                st.write(f"Weak+Vol: {'🟢' if row['Weak+Vol'] else '🔴'}")
                st.write(f"RSI<30: {'🟢' if row['RSI<30'] else '🔴'}")

                df_chart = row["Chart"]
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(
                    x=df_chart["ts"], open=df_chart["o"], high=df_chart["h"],
                    low=df_chart["l"], close=df_chart["c"], name="Candles"
                ), row=1, col=1)
                fig.add_trace(go.Bar(
                    x=df_chart["ts"], y=df_chart["v"], name="Volume"
                ), row=2, col=1)

                fig.update_layout(
                    height=500,
                    showlegend=False,
                    xaxis_rangeslider_visible=False
                )
                st.plotly_chart(fig, use_container_width=True)

st.write(f"🕒 Last refreshed: {time.strftime('%Y-%m-%d %H:%M:%S')}")
