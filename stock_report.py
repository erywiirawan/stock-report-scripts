# stock_report.py - Pakai: python stock_report.py
# Atau: python stock_report.py TLKM

import yfinance as yf
import pandas as pd
import numpy as np
import warnings
import os
import sys
warnings.filterwarnings('ignore')

DEFAULT = ["TLKM.JK", "UNTR.JK", "MDKA.JK"]

def get_col(data, name):
    for c in data.columns:
        cn = c[0] if isinstance(c, tuple) else c
        if name.lower() in cn.lower():
            v = data[c]
            return v.iloc[:, 0] if v.ndim > 1 else v
    return data.iloc[:, 0]

def calc_rsi(x, p=14):
    d = x.diff()
    g = d.where(d > 0, 0).rolling(p).mean()
    l = (-d.where(d < 0, 0)).rolling(p).mean()
    return 100 - (100 / (1 + g / l))

def calc_macd(x, f=12, s=26, sig=9):
    m = x.ewm(span=f).mean() - x.ewm(span=s).mean()
    sgn = m.ewm(span=sig).mean()
    return m, sgn, m - sgn

print("=" * 50)
print("STOCK REPORT GENERATOR")
print("=" * 50)

args = sys.argv[1:]
tickers = args if args else DEFAULT

print("Tickers: " + str(tickers))
print("")

for ticker in tickers:
    try:
        print("Downloading: " + ticker)
        d = yf.download(ticker, period="3mo", interval="1d", progress=False)
        if len(d) < 20:
            print("Data kurang, skip")
            continue

        close = get_col(d, "Close")
        high = get_col(d, "High")
        low = get_col(d, "Low")
        vol = get_col(d, "Volume")
        opn = get_col(d, "Open")

        rsi_vals = calc_rsi(close)
        macd_m, macd_s, macd_h = calc_macd(close)
        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        ema9 = close.ewm(span=9).mean()

        bb_mid = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        bb_up = bb_mid + bb_std * 2
        bb_lo = bb_mid - bb_std * 2

        result = pd.DataFrame()
        result["Date"] = d.index.strftime("%Y-%m-%d")
        result["Open"] = opn.values
        result["High"] = high.values
        result["Low"] = low.values
        result["Close"] = close.values
        result["Volume"] = vol.values
        result["RSI"] = rsi_vals.values
        result["MACD"] = macd_m.values
        result["MACD_Signal"] = macd_s.values
        result["MACD_Hist"] = macd_h.values
        result["SMA20"] = sma20.values
        result["SMA50"] = sma50.values
        result["EMA9"] = ema9.values
        result["BB_Mid"] = bb_mid.values
        result["BB_Upper"] = bb_up.values
        result["BB_Lower"] = bb_lo.values

        ticker_clean = ticker.replace(".JK", "")
        fname = ticker_clean + "_data.csv"
        result.to_csv(fname, index=False)
        print("Saved: " + fname)

        last = result.iloc[-1]
        curr = last["Close"]
        rsi = last["RSI"]
        macd_h_val = last["MACD_Hist"]
        sma50_val = last["SMA50"]

        score = 0
        if rsi >= 70: score -= 2
        elif rsi <= 30: score += 2
        elif rsi >= 60: score += 1
        elif rsi <= 40: score -= 1
        if macd_h_val > 0: score += 2
        else: score -= 2
        if curr > sma50_val: score += 1
        else: score -= 1

        if score >= 5: verdict = "STRONG BUY"
        elif score >= 2: verdict = "BUY"
        elif score <= -5: verdict = "STRONG SELL"
        elif score <= -2: verdict = "SELL"
        else: verdict = "HOLD"

        rsi_txt = "OVERBOUGHT" if rsi >= 70 else "OVERSOLD" if rsi <= 30 else "BULLISH" if rsi >= 60 else "BEARISH" if rsi <= 40 else "NETRAL"
        macd_txt = "POSITIVE" if macd_h_val > 0 else "NEGATIVE"

        print("")
        print(" Harga   : " + str(round(float(curr), 0)))
        print(" RSI     : " + str(round(float(rsi), 1)) + " (" + rsi_txt + ")")
        print(" MACD    : " + str(round(float(macd_h_val), 2)) + " (" + macd_txt + ")")
        print(" SMA20   : " + str(round(float(last["SMA20"]), 0)))
        print(" SMA50   : " + str(round(float(sma50_val), 0)))
        print(" BB Upper: " + str(round(float(last["BB_Upper"]), 0)))
        print(" BB Lower: " + str(round(float(last["BB_Lower"]), 0)))
        print(" Score   : " + str(score) + " -> " + verdict)
        print("")

    except Exception as e:
        print("ERROR " + ticker + ": " + str(e))

print("=" * 50)
print("Selesai. File CSV ada di folder yang sama.")
print("=" * 50)
