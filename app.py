import pandas as pd
import numpy as np
import streamlit as st
import requests
import time
from ta.volatility import AverageTrueRange

# === CONFIG ===
REFRESH_MIN = 15
PAIR_TF = "15m"
BTC_TF = "4h"
ATR_LEN = 96
BODY_FCTR = 0.3
VOL_MULT = 2.5

SPOT_BASE = "https://api.binance.com/api/v3"  # Main Binance API
# SPOT_BASE = "https://api.binance.us/api/v3"  # Uncomment for U.S. users if needed

# Proxy configuration (replace with your proxy details)
PROXIES = {
    "http": "http://your-proxy:port",  # e.g., "http://123.45.67.89:8080"
    "https": "http://your-proxy:port"
}
# If using a proxy with authentication, use:
# PROXIES = {
#     "http": "http://username:password@your-proxy:port",
#     "https": "http://username:password@your-proxy:port"
# }

st.set_page_config(
    page_title="🔥 Crypto PRE-DIP Screener",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Button to clear cache
if st.button("Clear Cache"):
    st.cache_data.clear()
    st.write("Cache cleared!")

@st.cache_data(ttl=REFRESH_MIN * 60)
def load_symbols():
    try:
        # Hardcoded symbols for testing
        symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "BNBUSDT", "XRPUSDT"]
        # Uncomment to use Tickers.csv
        # df = pd.read_csv("Tickers.csv", header=None, names=["symbol"])
        # symbols = df.symbol.astype(str).tolist()
        st.write(f"Loaded {len(symbols)} symbols")
        return symbols
    except Exception as e:
        st.error(f"Error loading symbols: {e}")
        return []

def fetch_ohlcv(symbol, interval, limit=ATR_LEN + 2, retries=3):
    url = f"{SPOT_BASE}/klines?symbol={symbol}&interval={interval}&limit={limit}"
    for attempt in range(retries):
        try:
            st.write(f"Fetching data for {symbol} (Attempt {attempt + 1})")
            res = requests.get(url, timeout=10, proxies=PROXIES)
            res.raise_for_status()
            data = res.json()
            if not data:
                st.warning(f"No data returned for {symbol}")
                return pd.DataFrame()
            df = pd.DataFrame(data, columns=["ts", "o", "h", "l", "c", "v", "x1", "x2", "x3", "x4", "x5", "x6"])
            df = df.astype({"o": float, "h": float, "l": float, "c": float, "v": float})
            df["ts"] = pd.to_datetime(df["ts"], unit="ms")
            return df
        except requests.exceptions.HTTPError as e:
            if res.status_code == 451:
                st.error(f"HTTP 451: Binance API unavailable for {symbol}. Check proxy or regional restrictions.")
            else:
                st.warning(f"Error fetching {symbol}: {e}. Retrying...")
            time.sleep(2)
        except Exception as e:
            st.warning(f"Error fetching {symbol}: {e}. Retrying...")
            time.sleep(2)
    st.error(f"Failed to fetch data for {symbol} after {retries} attempts")
    return pd.DataFrame()

# Alternative CoinGecko API (uncomment to use if Binance fails)
# def fetch_ohlcv(symbol, interval, limit=ATR_LEN + 2):
#     coin = symbol.replace("USDT", "").lower()  # e.g., "BTCUSDT" -> "bitcoin"
#     url = f"https://api.coingecko.com/api/v3/coins/{coin}/ohlc?vs_currency=usd&days=7"
#     try:
#         st.write(f"Fetching data for {symbol} from CoinGecko")
#         res = requests.get(url, timeout=10)
#         res.raise_for_status()
#         data = res.json()
#         df = pd.DataFrame(data, columns=["ts", "o", "h", "l", "c"])
#         df["v"] = 0.0  # CoinGecko doesn't provide volume
#         df["ts"] = pd.to_datetime(df["ts"], unit="ms")
#         return df
#     except Exception as e:
#         st.error(f"Error fetching {symbol} from CoinGecko: {e}")
#         return pd.DataFrame()

def fetch_btc_trend():
    df = fetch_ohlcv("BTCUSDT", BTC_TF, 22)
    if df.empty or len(df) < 22:
        st.warning("No or insufficient data for BTCUSDT.")
        return 0.0, 0.0, False
    close = df.c.iat[-1]
    ema = df.c.ewm(span=21).mean().iat[-1]
    return close, ema, close < ema

def run_screening():
    syms = load_symbols()
    rows = []
    btc_close, btc_ema21, btcBelow = fetch_btc_trend()

    if not syms:
        st.warning("No symbols to screen.")
        return pd.DataFrame(), btc_close, btc_ema21

    st.write(f"Screening {len(syms)} symbols...")
    progress_bar = st.progress(0)
    total_syms = len(syms)

    for i, s in enumerate(syms):
        try:
            df = fetch_ohlcv(s, PAIR_TF)
            time.sleep(0.5)  # Delay to avoid rate limits
            if df.empty or len(df) < ATR_LEN:
                st.write(f"Skipping {s} (no data or insufficient data)")
                continue

            close = df.c.iat[-1]
            vol = df.v.iat[-1]
            base = df.c.tail(ATR_LEN).mean()
            atr = AverageTrueRange(df.h, df.l, df.c, ATR_LEN).average_true_range().iat[-1]
            vavg = df.v.tail(ATR_LEN).mean()

            # Validate calculations
            if any(pd.isna(x) for x in [base, atr, vavg]):
                st.write(f"Skipping {s} (invalid base, atr, or vavg)")
                continue

            # RSI calculation with validation
            gain = df.c.pct_change().fillna(0)
            if len(gain) < 14:
                st.write(f"Skipping {s} (insufficient data for RSI)")
                continue

            delta = gain.rolling(14).mean()
            loss = (-gain).rolling(14).mean()

            # Avoid division by zero
            rs = delta / loss
            rs = rs.replace([np.inf, -np.inf], np.nan).fillna(0)
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

        except Exception as e:
            st.error(f"Error processing {s}: {e}")
            continue

        progress_bar.progress((i + 1) / total_syms)

    df_all = pd.DataFrame(rows)
    if not df_all.empty and "Score" in df_all.columns:
        df_all = df_all.sort_values("Score", ascending=False)
    else:
        st.warning("No valid data processed. Check API availability, proxy settings, or symbol list.")
    return df_all, btc_close, btc_ema21

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