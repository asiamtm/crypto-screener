<p align="center">
  <img src="https://raw.githubusercontent.com/asiamtm/crypto-screener/media/banner.png" width="80%">
</p>
<h1 align="center">🔥 Crypto PRE-DIP / PRE-PUMP Screener</h1>
<p align="center">
  <strong>Spot-based crypto screener for early dip signals</strong><br>
  <code>BTC Trend</code> • <code>Volume Spike</code> • <code>RSI Oversold</code>
</p>

<p align="center">
  <img alt="Streamlit" src="https://img.shields.io/badge/Streamlit-Cloud-red?logo=streamlit&logoColor=white">
  <a href="./LICENSE"><img alt="License" src="https://img.shields.io/badge/License-MIT-blue.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white">
</p>

---

## 📊 What It Does

This app screens all **Binance USDT spot pairs** every 15 minutes and highlights tokens showing:

- 🔻 **BTC below EMA-21 (4h)**
- 🚨 **Price drop** and **volume spike** (15m)
- 🟡 **RSI < 30** for potential oversold bounce

It scores each token 0–3 and groups them as:

- 🚨 Full PRE-DIP: All 3 triggers
- ⚠️ Near-DIP: Any 2 triggers
- 🔥 Warm-DIP: Any 1 trigger

---

## 🚀 Deploy to Streamlit Cloud

**One-click deploy instructions:**

1. Fork or clone this repo  
2. Go to [streamlit.io/cloud](https://streamlit.io/cloud) → "New app"
3. Connect your GitHub + select this repo
4. Select `app.py` as the entry script
5. Optional: add secrets for Binance API (not needed for spot-only version)
6. Hit **Deploy** ✅

---

## 🧑‍💻 Run Locally

```bash
git clone https://github.com/asiamtm/crypto-screener.git
cd crypto-screener

# Optional: virtual environment
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

---

## 📁 Files

| File              | Purpose                                      |
|-------------------|----------------------------------------------|
| `app.py`          | Main Streamlit app logic                     |
| `Tickers.csv`     | USDT spot pairs to scan                      |
| `requirements.txt`| All required Python libraries                |
| `README.md`       | This beautiful readme                        |

---

## 🔒 Binance API Keys (Optional)

If you're in a region with access to Binance Spot API:

1. Go to your [Streamlit app settings → Secrets](https://share.streamlit.io/)
2. Add:

```
BINANCE_API_KEY = "your_key"
BINANCE_API_SECRET = "your_secret"
```

---

## 🧾 License

This project uses the **MIT License** — feel free to fork, extend, and improve it!

---

> Built with ❤️ using Python, Streamlit, Plotly, and ta-lib
