#!/usr/bin/env python3
"""
STOCK FULL REPORT - GABUNGAN Bandar_SmartMoney + Costum Screen
RSI, MACD, SMA20/50, EMA9, Bollinger Bands, MFI, A/D, Bandar Value, Smart Money

Usage:
    python stock_full_report.py INCO.JK DEWA.JK
    python stock_full_report.py                    # gunakan default ticker
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import sys
import os
warnings.filterwarnings('ignore')

# ============================================================
# TICKER INPUT
# ============================================================
DEFAULT_TICKERS = ["INCO.JK", "DEWA.JK"]
PERIODE = "3mo"
INTERVAL = "1d"

TICKERS = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_TICKERS

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_col(data, name):
    """Ambil kolom dari DataFrame yfinance (multi-index atau flat)."""
    for c in data.columns:
        cn = c[0] if isinstance(c, tuple) else c
        if name.lower() in cn.lower():
            v = data[c]
            return v.iloc[:, 0] if v.ndim > 1 else v
    return data.iloc[:, 0]

# ============================================================
# INDIKATOR TEKNISAL
# ============================================================

def hitung_rsi(harga, period=14):
    delta = harga.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def hitung_macd(harga, fast=12, slow=26, signal=9):
    ema_fast = harga.ewm(span=fast).mean()
    ema_slow = harga.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def get_sma(harga, n):
    return harga.rolling(n).mean()

def get_ema(harga, n):
    return harga.ewm(span=n).mean()

def hitung_bollinger(harga, period=20, std_mult=2):
    mid = harga.rolling(period).mean()
    std = harga.rolling(period).std()
    upper = mid + std * std_mult
    lower = mid - std * std_mult
    return mid, upper, lower

def hitung_mfi(high, low, close, volume, period=14):
    typical = (high + low + close) / 3
    raw_mf = typical * volume
    mf_change = typical.diff()
    pos_mf = mf_change.where(mf_change > 0, 0).rolling(period).sum()
    neg_mf = (-mf_change.where(mf_change < 0, 0)).rolling(period).sum()
    mfr = pos_mf / neg_mf
    return 100 - (100 / (1 + mfr))

def hitung_ad(high, low, close, volume):
    mfm = ((close - low) - (high - close)) / (high - low)
    mfm = mfm.fillna(0)
    mf_volume = mfm * volume
    ad_line = mf_volume.cumsum()
    return ad_line

# ============================================================
# SIGNAL GENERATORS
# ============================================================

def rsi_signal(rsi):
    if rsi >= 70: return "OVERBOUGHT"
    if rsi <= 30: return "OVERSOLD"
    if rsi >= 60: return "BULLISH"
    if rsi <= 40: return "BEARISH"
    return "NETRAL"

def macd_signal(macd_line, signal_line, histogram):
    if macd_line > signal_line and histogram > 0: return "BUY"
    if macd_line < signal_line and histogram < 0: return "SELL"
    if macd_line > signal_line and histogram < 0: return "TRANSISI UP"
    if macd_line < signal_line and histogram > 0: return "TRANSISI DOWN"
    return "NETRAL"

def ma_signal(harga, sma20, sma50):
    if harga > sma20 and sma20 > sma50: return "BULLISH"
    if harga < sma20 and sma20 < sma50: return "BEARISH"
    return "NETRAL"

def mfi_signal(mfi):
    if mfi >= 80: return "OVERBOUGHT"
    if mfi <= 20: return "OVERSOLD"
    if mfi >= 60: return "BULLISH"
    if mfi <= 40: return "BEARISH"
    return "NETRAL"

def bb_position(harga, bb_upper, bb_lower):
    """Posisi harga relatif terhadap Bollinger Bands (0=jumlah, 1=upper, -1=lower)."""
    range_bb = bb_upper - bb_lower
    if range_bb == 0:
        return 0
    return (harga - bb_lower) / range_bb

# ============================================================
# BANDAR VALUE & SMART MONEY
# ============================================================

def signal_bandar(close, volume, ad_line, period=20):
    vol_avg = volume.rolling(period).mean()
    vol_now = volume.iloc[-1]
    vr = vol_now / vol_avg.iloc[-1] if vol_avg.iloc[-1] > 0 else 1.0

    price_change_5d = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100 if len(close) >= 5 else 0

    ad_now = ad_line.iloc[-1]
    ad_prev = ad_line.iloc[-10] if len(ad_line) >= 10 else ad_now
    ad_trend = "UP" if ad_now > ad_prev else "DOWN"

    if vr > 2.0 and ad_trend == "UP" and price_change_5d > 3:
        return "DISTRIBUSI"
    elif vr > 2.0 and ad_trend == "DOWN" and price_change_5d < -3:
        return "AKUMULASI"
    elif vr > 1.5 and ad_trend == "UP":
        return "AKTIF BELI"
    elif vr > 1.5 and ad_trend == "DOWN":
        return "AKTIF JUAL"
    elif vr < 0.5:
        return "PASIF"
    else:
        return "NETRAL"

def signal_smart_money(close, volume, ad_line, period=20):
    ad_recent = ad_line.tail(10)
    if len(ad_recent) < 5:
        return "NETRAL"

    x = np.arange(len(ad_recent))
    slope = np.polyfit(x, ad_recent.values, 1)[0]

    vol_ma5 = volume.tail(5).mean()
    vol_ma20 = volume.tail(20).mean()

    price_ma5 = close.tail(5).mean()
    price_ma20 = close.tail(20).mean()

    if slope > 0 and vol_ma5 > vol_ma20 and price_ma5 > price_ma20:
        return "SMART MONEY IN"
    elif slope < 0 and vol_ma5 > vol_ma20 and price_ma5 < price_ma20:
        return "SMART MONEY OUT"
    elif slope > 0 and ad_line.iloc[-1] > ad_line.iloc[-5]:
        return "AKUMULASI"
    elif slope < 0:
        return "DISTRIBUSI"
    else:
        return "NETRAL"

# ============================================================
# SCORING - GABUNGAN SEMUA INDIKATOR
# ============================================================

def skor_gabungan(rsi_val, macd_s, ma_s, mfi_val, sm_s, bd_s, bb_pos, vr):
    sc = 0
    detail = []

    # RSI
    if rsi_val <= 30:
        sc += 3
        detail.append(f"RSIOVERSOLD({rsi_val:.1f})+3")
    elif rsi_val <= 40:
        sc += 2
        detail.append(f"RSIjenuhJual({rsi_val:.1f})+2")
    elif rsi_val >= 70:
        sc -= 3
        detail.append(f"RSIOVERBOUGHT({rsi_val:.1f})-3")
    elif rsi_val >= 60:
        sc -= 2
        detail.append(f"RSIjenuhBeli({rsi_val:.1f})-2")

    # MACD
    if macd_s == "BUY":
        sc += 2
        detail.append("MACDBUY+2")
    elif macd_s == "SELL":
        sc -= 2
        detail.append("MACDSELL-2")
    elif macd_s == "TRANSISI UP":
        sc += 1
        detail.append("MACDTRANSISIUP+1")
    elif macd_s == "TRANSISI DOWN":
        sc -= 1
        detail.append("MACDTRANSISIDOWN-1")

    # MA
    if ma_s == "BULLISH":
        sc += 1
        detail.append("MABULLISH+1")
    elif ma_s == "BEARISH":
        sc -= 1
        detail.append("MABEARISH-1")

    # MFI
    if mfi_val <= 20:
        sc += 2
        detail.append(f"MFIJVERSOLD({mfi_val:.1f})+2")
    elif mfi_val >= 80:
        sc -= 2
        detail.append(f"MFIJVERBOUGHT({mfi_val:.1f})-2")
    elif mfi_val >= 60:
        sc -= 1
        detail.append(f"MFIJENJIHBELI({mfi_val:.1f})-1")
    elif mfi_val <= 40:
        sc += 1
        detail.append(f"MFIJENJIHJUAL({mfi_val:.1f})+1")

    # Smart Money
    if sm_s == "SMART MONEY IN":
        sc += 3
        detail.append("SMARTMONEYIN+3")
    elif sm_s == "SMART MONEY OUT":
        sc -= 3
        detail.append("SMARTMONEYOUT-3")
    elif sm_s == "AKUMULASI":
        sc += 1
        detail.append("SMAKUMULASI+1")
    elif sm_s == "DISTRIBUSI":
        sc -= 1
        detail.append("SMDISTRIBUSI-1")

    # Bandar
    if bd_s == "AKUMULASI":
        sc += 2
        detail.append("BANDARAKUMULASI+2")
    elif bd_s == "DISTRIBUSI":
        sc -= 2
        detail.append("BANDARDISTRIBUSI-2")
    elif bd_s == "AKTIF BELI":
        sc += 1
        detail.append("BANDARAKTIFBELI+1")
    elif bd_s == "AKTIF JUAL":
        sc -= 1
        detail.append("BANDARAKTIFJUAL-1")

    # Bollinger position (price near lower band = potentially oversold)
    if bb_pos < 0.15 and bb_pos >= 0:
        sc += 1
        detail.append(f"BBNearLower({bb_pos:.2f})+1")
    elif bb_pos > 0.85 and bb_pos <= 1:
        sc -= 1
        detail.append(f"BBNearUpper({bb_pos:.2f})-1")

    # Volume spike bonus
    if vr > 2.5:
        sc += 1
        detail.append(f"VOLUMESPIKE({vr:.1f}x)+1")
    elif vr < 0.4:
        sc -= 1
        detail.append(f"LOWVOLUME({vr:.1f}x)-1")

    # Rekomendasi
    if sc >= 5:
        return "STRONG BUY", sc, detail
    if sc >= 2:
        return "BUY", sc, detail
    if sc <= -5:
        return "STRONG SELL", sc, detail
    if sc <= -2:
        return "SELL", sc, detail
    return "HOLD", sc, detail

# ============================================================
# ENTRY / EXIT / SL / TP
# ============================================================

def calc_entry_sl_tp(close, sma20, sma50, bb_upper, bb_lower, rsi_val, macd_hist):
    price = float(close.iloc[-1])
    prev_price = float(close.iloc[-2]) if len(close) >= 2 else price

    # Dynamic SL: bawah BB lower atau -3% whichever lebih dekat
    bb_l = float(bb_lower.iloc[-1])
    sl_pct = min(abs(price - bb_l) / price, 0.03)

    # TP: atas BB upper atau +5% whichever lebih dekat
    bb_u = float(bb_upper.iloc[-1])
    tp_pct = min(abs(bb_u - price) / price, 0.05)

    # Trend-based adjustment
    if rsi_val <= 40:
        sl_pct = max(sl_pct, 0.02)  # jangan terlalu ketat di oversold
    if macd_hist > 0:
        tp_pct = max(tp_pct, 0.04)  # momentum bullish -> TP lebih jauh

    sl_price = round(price * (1 - sl_pct), 2)
    tp_price = round(price * (1 + tp_pct), 2)

    # Risk/Reward
    risk = price - sl_price
    reward = tp_price - price
    rr = round(reward / risk, 2) if risk > 0 else 0

    return {
        'entry': round(price, 2),
        'sl': sl_price,
        'tp': tp_price,
        'sl_pct': round(sl_pct * 100, 1),
        'tp_pct': round(tp_pct * 100, 1),
        'rr_ratio': rr
    }

# ============================================================
# MONEY MANAGEMENT
# ============================================================

def calc_money_mgmt(entry, sl, tp, modal=100_000_000):
    risk_pct = 0.02  # 2% modal per trade
    risk_amount = modal * risk_pct

    price_diff = abs(entry - sl)
    if price_diff == 0:
        return None

    lot = int(risk_amount / price_diff)
    if lot == 0:
        lot = 100  # minimum lot

    total_cost = lot * entry
    max_loss = lot * abs(entry - sl)
    max_profit = lot * abs(tp - entry)

    return {
        'lot': lot,
        'modal_used': round(total_cost, 0),
        'modal_pct': round(total_cost / modal * 100, 1),
        'max_loss': round(max_loss, 0),
        'max_profit': round(max_profit, 0),
        'risk_reward': round(max_profit / max_loss, 2) if max_loss > 0 else 0
    }

# ============================================================
# MAIN REPORT
# ============================================================

def generate_report(ticker):
    data = yf.download(ticker, period=PERIODE, interval=INTERVAL, progress=False)
    if len(data) < 20:
        return None, f"SKIP {ticker}: data kurang ({len(data)} baris)"

    # Kolom
    close = get_col(data, "Close").astype(float)
    high = get_col(data, "High").astype(float)
    low = get_col(data, "Low").astype(float)
    vol = get_col(data, "Volume").astype(float)
    opn = get_col(data, "Open").astype(float)

    # Indikator
    rsi_val = float(hitung_rsi(close).iloc[-1])
    macd_m, macd_s, macd_h = hitung_macd(close)
    macd_mv = float(macd_m.iloc[-1])
    macd_sv = float(macd_s.iloc[-1])
    macd_hv = float(macd_h.iloc[-1])

    sma20 = get_sma(close, 20)
    sma50 = get_sma(close, 50)
    sma20v = float(sma20.iloc[-1]) if len(close) >= 20 else float(close.iloc[-1])
    sma50v = float(sma50.iloc[-1]) if len(close) >= 50 else sma20v

    ema9 = get_ema(close, 9)
    ema9v = float(ema9.iloc[-1])

    bb_mid, bb_up, bb_lo = hitung_bollinger(close)
    bb_upv = float(bb_up.iloc[-1])
    bb_lov = float(bb_lo.iloc[-1])
    bb_midv = float(bb_mid.iloc[-1])

    mfi_val = float(hitung_mfi(high, low, close, vol).iloc[-1])
    ad_line = hitung_ad(high, low, close, vol)

    # Signals
    rs = rsi_signal(rsi_val)
    ms = macd_signal(macd_mv, macd_sv, macd_hv)
    ma = ma_signal(float(close.iloc[-1]), sma20v, sma50v)
    mf = mfi_signal(mfi_val)
    sm = signal_smart_money(close, vol, ad_line)
    bd = signal_bandar(close, vol, ad_line)

    # Bollinger position
    bb_pos = bb_position(float(close.iloc[-1]), bb_upv, bb_lov)

    # Volume
    vol_avg = float(vol.tail(20).mean())
    vol_now = float(vol.iloc[-1])
    vr = vol_now / vol_avg if vol_avg > 0 else 1.0

    # Scoring
    rec, sc, detail = skor_gabungan(rsi_val, ms, ma, mfi_val, sm, bd, bb_pos, vr)

    # Entry/SL/TP
    est = calc_entry_sl_tp(close, sma20, sma50, bb_up, bb_lo, rsi_val, macd_hv)
    mm = calc_money_mgmt(est['entry'], est['sl'], est['tp'])

    # Support & Resistance
    h20 = float(high.tail(20).max())
    l20 = float(low.tail(20).min())
    price = float(close.iloc[-1])

    # Change
    chg_1d = float(close.iloc[-1] - close.iloc[-2]) if len(close) >= 2 else 0
    chg_1d_pct = (chg_1d / float(close.iloc[-2]) * 100) if len(close) >= 2 else 0
    chg_5d_pct = float((close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100) if len(close) >= 5 else 0

    # Build result dict
    result = {
        'ticker': ticker.replace(".JK", ""),
        'harga': round(price, 2),
        'chg_1d': round(chg_1d, 2),
        'chg_1d_pct': round(chg_1d_pct, 2),
        'chg_5d_pct': round(chg_5d_pct, 2),
        'rsi': round(rsi_val, 1),
        'rsi_signal': rs,
        'mfi': round(mfi_val, 1),
        'mfi_signal': mf,
        'macd': ms,
        'macd_val': round(macd_mv, 3),
        'macd_signal_val': round(macd_sv, 3),
        'macd_hist': round(macd_hv, 3),
        'sma20': round(sma20v, 2),
        'sma50': round(sma50v, 2),
        'ema9': round(ema9v, 2),
        'ma_signal': ma,
        'bb_upper': round(bb_upv, 2),
        'bb_mid': round(bb_midv, 2),
        'bb_lower': round(bb_lov, 2),
        'bb_position': round(bb_pos, 3),
        'smart_money': sm,
        'bandar': bd,
        'vol_ratio': round(vr, 2),
        'support': round(l20, 2),
        'resistance': round(h20, 2),
        'entry': est['entry'],
        'sl': est['sl'],
        'tp': est['tp'],
        'sl_pct': est['sl_pct'],
        'tp_pct': est['tp_pct'],
        'rr_ratio': est['rr_ratio'],
        'rekomendasi': rec,
        'score': sc,
        'detail': " | ".join(detail),
    }

    if mm:
        result.update({
            'lot': mm['lot'],
            'modal_used': mm['modal_used'],
            'modal_pct': mm['modal_pct'],
            'max_loss': mm['max_loss'],
            'max_profit': mm['max_profit'],
            'risk_reward': mm['risk_reward'],
        })

    # CSV output
    df_out = pd.DataFrame()
    df_out["Date"] = data.index.strftime("%Y-%m-%d")
    df_out["Open"] = opn.values
    df_out["High"] = high.values
    df_out["Low"] = low.values
    df_out["Close"] = close.values
    df_out["Volume"] = vol.values
    df_out["RSI"] = hitung_rsi(close).values
    df_out["MACD"] = macd_m.values
    df_out["MACD_Signal"] = macd_s.values
    df_out["MACD_Hist"] = macd_h.values
    df_out["SMA20"] = sma20.values
    df_out["SMA50"] = sma50.values
    df_out["EMA9"] = ema9.values
    df_out["BB_Upper"] = bb_up.values
    df_out["BB_Mid"] = bb_mid.values
    df_out["BB_Lower"] = bb_lo.values
    df_out["MFI"] = hitung_mfi(high, low, close, vol).values
    df_out["AD"] = ad_line.values

    ticker_clean = ticker.replace(".JK", "")
    fname_csv = ticker_clean + "_full.csv"
    df_out.to_csv(fname_csv, index=False)

    return result, fname_csv

# ============================================================
# PRINT REPORT
# ============================================================

def print_report(r, fname_csv):
    t = r['ticker']
    print("=" * 70)
    print(f"  {t} — FULL TECHNICAL REPORT")
    print("=" * 70)

    # Header stats
    chg_emoji = "▲" if r['chg_1d_pct'] > 0 else "▼" if r['chg_1d_pct'] < 0 else "─"
    print(f"  Harga      : {r['harga']:>10,.2f}  {chg_emoji} {r['chg_1d_pct']:+.2f}% (1d)  {r['chg_5d_pct']:+.2f}% (5d)")
    print(f"  Support    : {r['support']:>10,.2f}")
    print(f"  Resistance : {r['resistance']:>10,.2f}")
    print(f"  Vol Ratio  : {r['vol_ratio']:>10,.2f}x  (avg 20d)")

    print("")
    print("  ── OSILATOR ──")
    print(f"  RSI        : {r['rsi']:>6.1f}  [{r['rsi_signal']}]")
    print(f"  MFI        : {r['mfi']:>6.1f}  [{r['mfi_signal']}]")
    print(f"  MACD       : {r['macd_val']:>8.3f}  Signal: {r['macd_signal_val']:>8.3f}  Hist: {r['macd_hist']:>+8.3f}  [{r['macd']}]")

    print("")
    print("  ── TREND ──")
    print(f"  SMA20      : {r['sma20']:>10,.2f}")
    print(f"  SMA50      : {r['sma50']:>10,.2f}")
    print(f"  EMA9       : {r['ema9']:>10,.2f}")
    print(f"  MA Signal  : [{r['ma_signal']}]")

    print("")
    print("  ── BOLLINGER BANDS ──")
    print(f"  Upper      : {r['bb_upper']:>10,.2f}")
    print(f"  Mid        : {r['bb_mid']:>10,.2f}")
    print(f"  Lower      : {r['bb_lower']:>10,.2f}")
    print(f"  Position   : {r['bb_position']:>10.3f}  (0=lower, 0.5=mid, 1=upper)")

    print("")
    print("  ── ALIR UANG (INSTITUSI) ──")
    print(f"  A/D Signal : [{r['smart_money']}]")
    print(f"  Bandar     : [{r['bandar']}]")

    print("")
    print("  ══ SCORING ══")
    print(f"  Score      : {r['score']:>5}  →  [{r['rekomendasi']}]")
    print(f"  Detail     : {r['detail']}")

    print("")
    print("  ── ENTRY / SL / TP ──")
    print(f"  Entry      : {r['entry']:>10,.2f}")
    print(f"  Stop Loss  : {r['sl']:>10,.2f}  ({r['sl_pct']}%)")
    print(f"  Target     : {r['tp']:>10,.2f}  ({r['tp_pct']}%)")
    print(f"  R:R Ratio  : {r['rr_ratio']:>10}")

    if 'lot' in r:
        print("")
        print("  ── MONEY MANAGEMENT (Modal Rp 100Jt) ──")
        print(f"  Lot        : {r['lot']:>10,}  saham")
        print(f"  Modal Used : Rp {r['modal_used']:>12,.0f}  ({r['modal_pct']}%)")
        print(f"  Max Loss   : Rp {r['max_loss']:>12,.0f}")
        print(f"  Max Profit : Rp {r['max_profit']:>12,.0f}")
        print(f"  Risk:Reward: {r['risk_reward']:>10}")

    print("")
    print(f"  CSV saved  : {fname_csv}")
    print("=" * 70)

# ============================================================
# MAIN
# ============================================================

print("")
print("=" * 70)
print("  STOCK FULL REPORT — GABUNGAN Bandar_SmartMoney + Costum Screen")
print("  " + datetime.now().strftime('%Y-%m-%d %H:%M'))
print("=" * 70)
print(f"  Tickers    : {', '.join(TICKERS)}")
print("=" * 70)

results = []
for ticker in TICKERS:
    print(f"\nProcessing: {ticker} ...")
    r, fname_or_err = generate_report(ticker)
    if r is None:
        print(f"  {fname_or_err}")
        continue
    print_report(r, fname_or_err)
    results.append(r)

# ============================================================
# RINGKASAN
# ============================================================

if len(results) > 0:
    print("")
    print("=" * 70)
    print("  RINGKASAN REKOMENDASI (SORT BY SCORE DESC)")
    print("=" * 70)
    print(f"  {'Ticker':<8} {'Harga':>10} {'RSI':>5} {'MFI':>5} {'MACD':<14} {'SM':<16} {'Bandar':<12} {'Rec':<12} {'Scr':>4}")
    print("  " + "-" * 65)

    df = pd.DataFrame(results).sort_values('score', ascending=False)
    for _, row in df.iterrows():
        print(f"  {row['ticker']:<8} {row['harga']:>10,.2f} {row['rsi']:>5.1f} {row['mfi']:>5.1f} "
              f"{row['macd']:<14} {row['smart_money']:<16} {row['bandar']:<12} "
              f"{row['rekomendasi']:<12} {row['score']:>4}")

    fn_sum = "screening_full_" + datetime.now().strftime('%Y%m%d_%H%M') + ".csv"
    df.drop(columns=['detail'], errors='ignore').to_csv(fn_sum, index=False)
    print("")
    print(f"  Ringkasan CSV : {fn_sum}")
    print(f"  Total di-screen: {len(results)}")
else:
    print("\nGagal dapat data — check koneksi internet.")

print("")
print("=" * 70)
print("  Selesai.")
print("=" * 70)
