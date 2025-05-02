
# 🔥 Crypto PRE-DIP / PRE-PUMP Screener

This Streamlit app scans all USDT spot trading pairs on Binance and identifies potential **PRE-DIP** setups based on:

- 📉 BTC 4H Close < EMA-21
- 💥 Spot pair price drop + volume spike
- 📉 RSI < 30 (oversold trigger)

---

## 🚀 Live Demo

You can try the live deployed version on [Streamlit Cloud](https://streamlit.io/cloud) *(after deploying this repo)*

---

## 📦 Installation (Local)

1. **Clone this repository**:
    ```bash
    git clone https://github.com/asiamtm/crypto-screener.git
    cd crypto-screener
    ```

2. **Create a virtual environment (optional but recommended)**:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3. **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4. **Run the app**:
    ```bash
    streamlit run app.py
    ```

---

## ☁️ Deployment on Streamlit Cloud

1. **Push your code to GitHub**, including `app.py`, `Tickers.csv`, and `requirements.txt`.

2. **Go to**: [https://streamlit.io/cloud](https://streamlit.io/cloud)

3. **Log in with GitHub** and click **"New app"**

4. **Choose your repo** and `app.py` as the entry point

5. **Add a secrets file (optional)** if you're using Binance API keys:
    - Go to **“Secrets”** in app settings
    - Paste:

      ```
      BINANCE_API_KEY = "your_key"
      BINANCE_API_SECRET = "your_secret"
      ```

6. Click **“Deploy”** — that's it!

---

## 📄 Files

- `app.py` — Main Streamlit app
- `Tickers.csv` — List of USDT pairs
- `requirements.txt` — Python package dependencies

---

## 🔒 Note on Binance API

Binance Futures may be restricted in your country. This version uses **spot market data only**, and does not require authentication.

---
