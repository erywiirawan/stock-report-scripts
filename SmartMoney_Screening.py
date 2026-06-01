#!/usr/bin/env python3
"""
SMART MONEY SCREENING + FULL REPORT — UNIFIED SCRIPT
Kombinasi dari: Screening_SmartMoney.py + stock_full_report.py + stock_report.py

Fitur:
  - RSI, MACD, MFI, SMA20/50/200, EMA9, Bollinger Bands, A/D
  - Smart Money Score (0-100) + Label (IN/OUT/AKUMULASI)
  - Bandar Score (0-100) + Label (AKUMULASI/DISTRIBUSI/etc)
  - Composite Score (rata-rata SM + Bandar)
  - Entry / SL / TP dengan Risk/Reward
  - Money Management (lot, max loss, max profit)
  - Catalyst detection
  - CSV export

Usage:
  python SmartMoney_Screening.py                    # default tickers
  python SmartMoney_Screening.py TLKM UNTR BBCA    # tickers langsung
  python SmartMoney_Screening.py -csv ticker.csv    # dari CSV file
  python SmartMoney_Screening.py -screen            # screening mode (compact)
  python SmartMoney_Screening.py -report            # full report mode (detail)

Author: Hermes Agent for Ery Wirawan
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
# DEFAULTS
# ============================================================
DEFAULT_TICKERS = ["TLKM.JK", "UNTR.JK", "BMRI.JK", "BBCA.JK", "CPIN.JK"]
PERIODE = "3mo"
INTERVAL = "1d"
MODAL = 100_000_000  # Rp 100jt

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

def calc_rsi(x, p=14):
    """Relative Strength Index"""
    d = x.diff()
    g = d.where(d > 0, 0).rolling(p).mean()
    l = (-d.where(d < 0, 0)).rolling(p).mean()
    return 100 - (100 / (1 + g / l))

def calc_macd(x, f=12, s=26, sig=9):
    """MACD: Fast=12, Slow=26, Signal=9"""
    m = x.ewm(span=f).mean() - x.ewm(span=s).mean()
    sgn = m.ewm(span=sig).mean()
    return m, sgn, m - sgn

def calc_mfi(high, low, close, vol, p=14):
    """Money Flow Index - volume-weighted RSI"""
    tp = (high + low + close) / 3
    mf = tp * vol
    po = tp.diff()
    gp = mf.where(po > 0, 0).rolling(p).sum()
    lp = mf.where(po < 0, 0).rolling(p).sum()
    mr = gp / lp
    return 100 - (100 / (1 + mr))

def calc_ad(high, low, close, vol):
    """Accumulation/Distribution Line"""
    clv = ((close - low) - (high - close)) / (high - low + 1e-10)
    clv = clv.fillna(0)
    return (clv * vol).cumsum()

def calc_bollinger(x, p=20, std=2):
    """Bollinger Bands"""
    mid = x.rolling(p).mean()
    s = x.rolling(p).std()
    return mid + s * std, mid - s * std

def calc_sma(x, p):
    """Simple Moving Average"""
    return x.rolling(p).mean()

def calc_ema(x, p):
    """Exponential Moving Average"""
    return x.ewm(span=p).mean()

# ============================================================
# SIGNAL LABELS
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

def ma_signal(price, sma20, sma50):
    if pd.isna(sma50) or sma50 == 0:
        return "NETRAL"
    if price > sma20 and sma20 > sma50: return "BULLISH"
    if price < sma20 and sma20 < sma50: return "BEARISH"
    return "NETRAL"

def mfi_signal(mfi):
    if mfi >= 80: return "OVERBOUGHT"
    if mfi <= 20: return "OVERSOLD"
    if mfi >= 60: return "BULLISH"
    if mfi <= 40: return "BEARISH"
    return "NETRAL"

def bb_position(harga, bb_upper, bb_lower):
    """Posisi harga relatif terhadap Bollinger Bands (0=jumlah, 1=upper)."""
    range_bb = bb_upper - bb_lower
    if range_bb == 0:
        return 0.5
    return (harga - bb_lower) / range_bb

# ============================================================
# SMART MONEY & BANDAR — SCORE (0-100) + LABEL
# ============================================================

def calc_smart_money_score(rsi, mfi, ad_slope, price_vs_sma200, macd_hist, volume_ratio):
    """
    Smart Money Score (0-100)
    Konsep: Smart money masuk saat semua indikator menunjukkan tekanan jual berlebihan
    """
    score = 50  # Start neutral

    # RSI contribution (0-25)
    if rsi < 10: score += 25
    elif rsi < 15: score += 22
    elif rsi < 20: score += 18
    elif rsi < 25: score += 12
    elif rsi < 30: score += 6
    elif rsi > 70: score -= 15
    elif rsi > 60: score -= 8

    # MFI contribution (0-25)
    if mfi < 10: score += 25
    elif mfi < 15: score += 22
    elif mfi < 20: score += 18
    elif mfi < 25: score += 12
    elif mfi < 30: score += 6
    elif mfi > 80: score -= 15
    elif mfi > 70: score -= 8

    # A/D trend (0-20)
    if ad_slope > 0.05: score += 20
    elif ad_slope > 0: score += 12
    elif ad_slope < -0.05: score -= 15

    # Price vs SMA200 (0-15)
    if price_vs_sma200 < 0.7: score += 15
    elif price_vs_sma200 < 0.85: score += 10
    elif price_vs_sma200 < 0.95: score += 5
    elif price_vs_sma200 > 1.3: score -= 10

    # MACD histogram (0-10)
    if macd_hist > 0.1: score += 10
    elif macd_hist > 0: score += 5
    elif macd_hist < -0.1: score -= 10

    # Volume surge (0-5)
    if volume_ratio > 2.0: score += 5
    elif volume_ratio > 1.5: score += 3
    elif volume_ratio > 1.0: score += 1

    return max(0, min(100, score))

def get_sm_label(score):
    """Convert Smart Money Score ke label."""
    if score >= 70: return "SMART MONEY IN"
    elif score >= 50: return "AKUMULASI"
    elif score >= 30: return "NETRAL"
    else: return "SMART MONEY OUT"

def calc_bandar_score(rsi, mfi, bb_position, price_momentum_5d, volume_ratio, ad_slope):
    """
    Bandar Value Score (0-100)
    Konsep: Mengukur apakah saham sedang di"main" Bandar
    """
    score = 50

    # RSI oversold bonus (0-20)
    if rsi < 15: score += 20
    elif rsi < 20: score += 15
    elif rsi < 25: score += 10
    elif rsi < 30: score += 5
    elif rsi > 70: score -= 10

    # MFI oversold bonus (0-20)
    if mfi < 10: score += 20
    elif mfi < 15: score += 15
    elif mfi < 20: score += 10
    elif mfi < 25: score += 5
    elif mfi > 80: score -= 10

    # Bollinger position (0-20) - di bawah lower band = oversold
    if bb_position < 0: score += 20
    elif bb_position < 0.1: score += 15
    elif bb_position < 0.2: score += 10
    elif bb_position < 0.3: score += 5

    # Price momentum 5-day (0-15)
    if price_momentum_5d < -10: score += 15
    elif price_momentum_5d < -5: score += 10
    elif price_momentum_5d < -2: score += 5
    elif price_momentum_5d > 5: score -= 8

    # Volume ratio (0-15)
    if volume_ratio > 2.5: score += 15
    elif volume_ratio > 2.0: score += 10
    elif volume_ratio > 1.5: score += 5
    elif volume_ratio < 0.5: score -= 5

    # A/D slope (0-10)
    if ad_slope > 0.02: score += 10
    elif ad_slope > 0: score += 5
    elif ad_slope < -0.02: score -= 8

    return max(0, min(100, score))

def get_bandar_label(score, ad_slope, price_momentum_5d):
    """Convert Bandar Score ke label."""
    if score >= 70 and ad_slope > 0: return "AKUMULASI"
    elif score >= 70 and ad_slope < 0: return "DISTRIBUSI"
    elif score >= 50: return "AKTIF"
    elif score >= 30: return "NETRAL"
    else: return "PASIF"

# ============================================================
# CATALYST DETECTION
# ============================================================

def detect_catalyst(price, sma20, sma50, volume_ratio, rsi, macd_hist):
    """Deteksi catalyst potensial - return list of catalysts found."""
    catalysts = []

    # Price crash + oversold
    if price < sma20 * 0.95 and rsi < 30:
        catalysts.append("PRICE CRASH")

    # Golden cross potential
    if sma20 > sma50 * 0.98 and sma20 < sma50 * 1.02:
        catalysts.append("GOLDEN CROSS SOON")

    # Volume surge + oversold
    if volume_ratio > 1.8 and rsi < 35:
        catalysts.append("VOLUME SURGE")

    # MACD reversal
    if macd_hist > 0:
        catalysts.append("MACD REVERSAL")

    # General oversold condition
    if rsi < 25:
        catalysts.append("OVERSHOT")

    return catalysts if catalysts else ["NONE"]

# ============================================================
# BUY SIGNAL DETECTION
# ============================================================

def check_buy_signal(sm_score, rsi, mfi, catalysts):
    """
    Buy Signal Check: Smart Money IN + RSI<15 + MFI<10 + Catalyst
    Returns: (signal_label, stars)
    """
    sm_label = get_sm_label(sm_score)
    sm_in = sm_label in ["SMART MONEY IN", "AKUMULASI"]
    rsi_ok = rsi < 15
    mfi_ok = mfi < 10
    catalyst_ok = len(catalysts) > 0 and catalysts[0] != "NONE"

    if sm_in and rsi_ok and mfi_ok and catalyst_ok:
        return "STRONG BUY", "★★★"
    elif sm_score >= 55 and rsi < 20 and mfi < 15:
        return "BUY", "★★"
    elif sm_score >= 45 and rsi < 25:
        return "WATCH", "★"
    elif rsi > 75 or mfi > 85:
        return "OVERBOUGHT", ""
    else:
        return "HOLD", ""

# ============================================================
# ENTRY / SL / TP CALCULATION
# ============================================================

def calc_entry_sl_tp(close, sma20, sma50, bb_upper, bb_lower, rsi_val, macd_hist):
    """Hitung entry, stop loss, dan target price."""
    price = float(close.iloc[-1])
    prev_price = float(close.iloc[-2]) if len(close) >= 2 else price

    # Dynamic SL: bawah BB lower atau -3% whichever lebih kecil
    bb_l = float(bb_lower.iloc[-1])
    sl_pct = min(abs(price - bb_l) / price, 0.03)

    # TP: atas BB upper atau +5% whichever lebih kecil
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

def calc_money_mgmt(entry, sl, tp, modal=MODAL):
    """Hitung lot, modal used, max loss, max profit."""
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
# SCREEN SINGLE TICKER
# ============================================================

def screen_ticker(ticker):
    """Screen single ticker dan return hasil lengkap."""
    try:
        # Download data - 3 bulan untuk RSI yang stabil
        d = yf.download(ticker, period=PERIODE, interval=INTERVAL, progress=False)
        if len(d) < 30:
            return None

        close = get_col(d, "Close").astype(float)
        high = get_col(d, "High").astype(float)
        low = get_col(d, "Low").astype(float)
        vol = get_col(d, "Volume").astype(float)
        opn = get_col(d, "Open").astype(float)

        # Hitung semua indikator
        rsi = calc_rsi(close)
        macd_m, macd_s, macd_h = calc_macd(close)
        mfi = calc_mfi(high, low, close, vol)
        ad = calc_ad(high, low, close, vol)

        sma20 = calc_sma(close, 20)
        sma50 = calc_sma(close, 50)
        sma200 = calc_sma(close, 200)
        ema9 = calc_ema(close, 9)
        bb_up, bb_lo = calc_bollinger(close)

        # Data terakhir
        curr = float(close.iloc[-1])
        prev_close = float(close.iloc[-2]) if len(close) >= 2 else curr
        rsi_val = float(rsi.iloc[-1])
        mfi_val = float(mfi.iloc[-1])
        macd_mv = float(macd_m.iloc[-1])
        macd_sv = float(macd_s.iloc[-1])
        macd_h_val = float(macd_h.iloc[-1])
        ad_val = float(ad.iloc[-1])
        ad_prev = float(ad.iloc[-5]) if len(ad) > 5 else ad_val
        ad_slope = (ad_val - ad_prev) / 5

        # Volume analysis
        avg_vol_20 = float(vol.rolling(20).mean().iloc[-1])
        curr_vol = float(vol.iloc[-1])
        vol_ratio = curr_vol / avg_vol_20 if avg_vol_20 > 0 else 1

        # Price momentum
        price_5d_ago = float(close.iloc[-6]) if len(close) > 5 else curr
        mom_5d = ((curr - price_5d_ago) / price_5d_ago) * 100

        # SMA values
        sma20_val = float(sma20.iloc[-1]) if not pd.isna(sma20.iloc[-1]) else curr
        sma50_val = float(sma50.iloc[-1]) if not pd.isna(sma50.iloc[-1]) else curr
        sma200_val = float(sma200.iloc[-1]) if not pd.isna(sma200.iloc[-1]) else curr
        price_vs_sma200 = curr / sma200_val if sma200_val != 0 else 1

        # Bollinger
        bb_up_val = float(bb_up.iloc[-1])
        bb_lo_val = float(bb_lo.iloc[-1])
        bb_range = bb_up_val - bb_lo_val
        bb_pos = (curr - bb_lo_val) / bb_range if bb_range > 0 else 0.5

        # Scores
        sm_score = calc_smart_money_score(rsi_val, mfi_val, ad_slope, price_vs_sma200, macd_h_val, vol_ratio)
        Bandar_score = calc_bandar_score(rsi_val, mfi_val, bb_pos, mom_5d, vol_ratio, ad_slope)

        # Labels
        sm_label = get_sm_label(sm_score)
        Bandar_label = get_bandar_label(Bandar_score, ad_slope, mom_5d)

        # Catalyst
        catalysts = detect_catalyst(curr, sma20_val, sma50_val, vol_ratio, rsi_val, macd_h_val)

        # Buy signal
        signal, signal_stars = check_buy_signal(sm_score, rsi_val, mfi_val, catalysts)

        # Composite
        composite = (sm_score + Bandar_score) / 2

        # Entry/SL/TP
        est = calc_entry_sl_tp(close, sma20, sma50, bb_up, bb_lo, rsi_val, macd_h_val)

        # Money management
        mm = calc_money_mgmt(est['entry'], est['sl'], est['tp'])

        # Change
        chg_1d = curr - prev_close
        chg_1d_pct = (chg_1d / prev_close * 100) if prev_close != 0 else 0

        # Support & Resistance (20-day)
        h20 = float(high.tail(20).max())
        l20 = float(low.tail(20).min())

        # Signal labels
        rsi_sig = rsi_signal(rsi_val)
        macd_sig = macd_signal(macd_mv, macd_sv, macd_h_val)
        ma_sig = ma_signal(curr, sma20_val, sma50_val)
        mfi_sig = mfi_signal(mfi_val)

        # Build result
        result = {
            'ticker': ticker.replace(".JK", ""),
            'harga': round(curr, 2),
            'chg_1d': round(chg_1d, 2),
            'chg_1d_pct': round(chg_1d_pct, 2),
            'chg_5d_pct': round(mom_5d, 2),
            'rsi': round(rsi_val, 1),
            'rsi_signal': rsi_sig,
            'mfi': round(mfi_val, 1),
            'mfi_signal': mfi_sig,
            'macd': macd_sig,
            'macd_val': round(macd_mv, 3),
            'macd_signal_val': round(macd_sv, 3),
            'macd_hist': round(macd_h_val, 3),
            'sma20': round(sma20_val, 2),
            'sma50': round(sma50_val, 2),
            'sma200': round(sma200_val, 2),
            'ema9': round(float(ema9.iloc[-1]), 2),
            'ma_signal': ma_sig,
            'bb_upper': round(bb_up_val, 2),
            'bb_mid': round(float(close.rolling(20).mean().iloc[-1]), 2),
            'bb_lower': round(bb_lo_val, 2),
            'bb_position': round(bb_pos, 3),
            'smart_money_score': sm_score,
            'smart_money_label': sm_label,
            'bandar_score': Bandar_score,
            'bandar_label': Bandar_label,
            'vol_ratio': round(vol_ratio, 2),
            'ad_slope': round(ad_slope, 4),
            'support': round(l20, 2),
            'resistance': round(h20, 2),
            'entry': est['entry'],
            'sl': est['sl'],
            'tp': est['tp'],
            'sl_pct': est['sl_pct'],
            'tp_pct': est['tp_pct'],
            'rr_ratio': est['rr_ratio'],
            'rekomendasi': signal,
            'signal_stars': signal_stars,
            'catalysts': catalysts,
            'composite': round(composite, 1),
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

        return result

    except Exception as e:
        print(f"  ERROR {ticker}: {str(e)}")
        return None

# ============================================================
# CSV EXPORT
# ============================================================

def export_csv(results, prefix="screening"):
    """Export results ke CSV."""
    if not results:
        return None
    df = pd.DataFrame(results)
    # Drop catalysts list for CSV compatibility
    df_csv = df.copy()
    if 'catalysts' in df_csv.columns:
        df_csv['catalysts'] = df_csv['catalysts'].apply(lambda x: '|'.join(x) if isinstance(x, list) else x)
    fn = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    df_csv.to_csv(fn, index=False)
    return fn

def export_detail_csv(ticker, data, close, rsi, macd_m, macd_s, macd_h, sma20, sma50, ema9, bb_up, bb_mid, bb_lo, mfi, ad):
    """Export OHLC + semua indikator ke CSV per ticker."""
    df_out = pd.DataFrame()
    df_out["Date"] = data.index.strftime("%Y-%m-%d")
    df_out["Open"] = get_col(data, "Open").values
    df_out["High"] = get_col(data, "High").values
    df_out["Low"] = get_col(data, "Low").values
    df_out["Close"] = close.values
    df_out["Volume"] = get_col(data, "Volume").values
    df_out["RSI"] = rsi.values
    df_out["MACD"] = macd_m.values
    df_out["MACD_Signal"] = macd_s.values
    df_out["MACD_Hist"] = macd_h.values
    df_out["SMA20"] = sma20.values
    df_out["SMA50"] = sma50.values
    df_out["EMA9"] = ema9.values
    df_out["BB_Upper"] = bb_up.values
    df_out["BB_Mid"] = bb_mid.values
    df_out["BB_Lower"] = bb_lo.values
    df_out["MFI"] = mfi.values
    df_out["AD"] = ad.values
    ticker_clean = ticker.replace(".JK", "")
    fn = f"{ticker_clean}_full.csv"
    df_out.to_csv(fn, index=False)
    return fn

# ============================================================
# OUTPUT FORMATS
# ============================================================

def format_screen_output(results):
    """Format hasil screening untuk Telegram — compact single-line."""
    if not results:
        return "Tidak ada data untuk ditampilkan."

    results.sort(key=lambda x: x["composite"], reverse=True)

    lines = []
    lines.append("=" * 60)
    lines.append("📊 SMART MONEY SCREENING REPORT")
    lines.append("=" * 60)

    # Header
    lines.append("")
    lines.append("TICKER   PRICE    RSI   MFI   SM%  BD%  CM%  SIG")
    lines.append("-" * 60)

    # Data rows
    for r in results:
        t = r['ticker'].ljust(7)
        p = f"{r['harga']:.0f}".ljust(7)
        rs = f"{r['rsi']:.0f}".ljust(5)
        mf = f"{r['mfi']:.0f}".ljust(5)
        sm = f"{r['smart_money_score']:.0f}".ljust(4)
        bd = f"{r['bandar_score']:.0f}".ljust(4)
        cm = f"{r['composite']:.0f}".ljust(4)
        sig = r['rekomendasi'][:8]
        stars = r['signal_stars']
        line = f"{t} {p} {rs} {mf} {sm} {bd} {cm} {sig}"
        if stars:
            line += f" {stars}"
        lines.append(line)

    # Summary
    lines.append("")
    lines.append("=" * 60)
    lines.append("📈 TOP 5 BY COMPOSITE SCORE:")
    lines.append("-" * 60)

    for i, r in enumerate(results[:5], 1):
        stars = " ⭐" if r['signal_stars'] else ""
        cat = r['catalysts'][0] if r['catalysts'] else ""
        lines.append(f"{i}. {r['ticker']} | CM:{r['composite']:.1f}{stars}")
        lines.append(f"   RSI:{r['rsi']:.0f} MFI:{r['mfi']:.0f} | SM:{r['smart_money_label']} | {r['rekomendasi']}")
        lines.append(f"   Catalyst: {cat}")

    # Strong buys
    strong_buys = [r for r in results if "STRONG BUY" in r['rekomendasi']]
    if strong_buys:
        lines.append("")
        lines.append("=" * 60)
        lines.append("🚨 STRONG BUY SIGNALS:")
        lines.append("-" * 60)
        for r in strong_buys:
            lines.append(f"★ {r['ticker']} @ {r['harga']:.0f}")
            lines.append(f"   SM Score:{r['smart_money_score']:.0f} | RSI:{r['rsi']:.0f} | MFI:{r['mfi']:.0f}")
            lines.append(f"   SM Label:{r['smart_money_label']} | Bandar:{r['bandar_label']}")
            lines.append(f"   Entry:{r['entry']:.0f} | SL:{r['sl']:.0f} ({r['sl_pct']}%) | TP:{r['tp']:.0f} ({r['tp_pct']}%)")
            lines.append(f"   R:R = {r['rr_ratio']} | Catalysts: {', '.join(r['catalysts'])}")

    # Legend
    lines.append("")
    lines.append("=" * 60)
    lines.append("LEGENDA:")
    lines.append("SM% = Smart Money Score (0-100)")
    lines.append("BD% = Bandar Value Score (0-100)")
    lines.append("CM% = Composite Score = (SM + BD) / 2")
    lines.append("SM Label: SMART MONEY IN | AKUMULASI | NETRAL | SMART MONEY OUT")
    lines.append("Bandar: AKUMULASI | DISTRIBUSI | AKTIF | NETRAL | PASIF")
    lines.append("Buy Signal: SM IN + RSI<15 + MFI<10 + Catalyst = STRONG BUY ★★★")
    lines.append("=" * 60)

    return "\n".join(lines)

def format_report_output(r, fname_csv=None):
    """Format hasil full report per ticker — detail."""
    t = r['ticker']
    chg_emoji = "▲" if r['chg_1d_pct'] > 0 else "▼" if r['chg_1d_pct'] < 0 else "─"

    lines = []
    lines.append("=" * 70)
    lines.append(f"  {t} — FULL TECHNICAL REPORT")
    lines.append("=" * 70)

    # Header stats
    lines.append(f"  Harga      : {r['harga']:>10,.2f}  {chg_emoji} {r['chg_1d_pct']:+.2f}% (1d)  {r['chg_5d_pct']:+.2f}% (5d)")
    lines.append(f"  Support    : {r['support']:>10,.2f}")
    lines.append(f"  Resistance : {r['resistance']:>10,.2f}")
    lines.append(f"  Vol Ratio  : {r['vol_ratio']:>10,.2f}x  (avg 20d)")

    lines.append("")
    lines.append("  ── OSILATOR ──")
    lines.append(f"  RSI        : {r['rsi']:>6.1f}  [{r['rsi_signal']}]")
    lines.append(f"  MFI        : {r['mfi']:>6.1f}  [{r['mfi_signal']}]")
    lines.append(f"  MACD       : {r['macd_val']:>8.3f}  Signal: {r['macd_signal_val']:>8.3f}  Hist: {r['macd_hist']:>+8.3f}  [{r['macd']}]")

    lines.append("")
    lines.append("  ── TREND ──")
    lines.append(f"  SMA20      : {r['sma20']:>10,.2f}")
    lines.append(f"  SMA50      : {r['sma50']:>10,.2f}")
    lines.append(f"  SMA200     : {r['sma200']:>10,.2f}")
    lines.append(f"  EMA9       : {r['ema9']:>10,.2f}")
    lines.append(f"  MA Signal  : [{r['ma_signal']}]")

    lines.append("")
    lines.append("  ── BOLLINGER BANDS ──")
    lines.append(f"  Upper      : {r['bb_upper']:>10,.2f}")
    lines.append(f"  Mid        : {r['bb_mid']:>10,.2f}")
    lines.append(f"  Lower      : {r['bb_lower']:>10,.2f}")
    lines.append(f"  Position   : {r['bb_position']:>10.3f}  (0=lower, 0.5=mid, 1=upper)")

    lines.append("")
    lines.append("  ── SMART MONEY & BANDAR ──")
    lines.append(f"  SM Score   : {r['smart_money_score']:>6.0f}  →  [{r['smart_money_label']}]")
    lines.append(f"  Bandar S   : {r['bandar_score']:>6.0f}  →  [{r['bandar_label']}]")
    lines.append(f"  Composite  : {r['composite']:>6.1f}")
    lines.append(f"  Catalysts  : {', '.join(r['catalysts'])}")

    lines.append("")
    lines.append("  ══ RECOMMENDATION ══")
    lines.append(f"  Signal     : [{r['rekomendasi']}] {r['signal_stars']}")

    lines.append("")
    lines.append("  ── ENTRY / SL / TP ──")
    lines.append(f"  Entry      : {r['entry']:>10,.2f}")
    lines.append(f"  Stop Loss  : {r['sl']:>10,.2f}  ({r['sl_pct']}%)")
    lines.append(f"  Target     : {r['tp']:>10,.2f}  ({r['tp_pct']}%)")
    lines.append(f"  R:R Ratio  : {r['rr_ratio']:>10}")

    if 'lot' in r:
        lines.append("")
        lines.append("  ── MONEY MANAGEMENT (Modal Rp 100Jt) ──")
        lines.append(f"  Lot        : {r['lot']:>10,}  saham")
        lines.append(f"  Modal Used : Rp {r['modal_used']:>12,.0f}  ({r['modal_pct']}%)")
        lines.append(f"  Max Loss   : Rp {r['max_loss']:>12,.0f}")
        lines.append(f"  Max Profit : Rp {r['max_profit']:>12,.0f}")
        lines.append(f"  Risk:Reward: {r['risk_reward']:>10}")

    if fname_csv:
        lines.append("")
        lines.append(f"  CSV saved  : {fname_csv}")

    lines.append("=" * 70)
    return "\n".join(lines)

def print_summary(results):
    """Print ringkasan semua ticker."""
    if not results:
        return

    print("")
    print("=" * 70)
    print("  RINGKASAN REKOMENDASI (SORT BY COMPOSITE DESC)")
    print("=" * 70)
    print(f"  {'Ticker':<8} {'Harga':>10} {'RSI':>5} {'MFI':>5} {'SM%':>4} {'BD%':>4} {'CM%':>4} {'Rec':<12} {'Scr':>4}")
    print("  " + "-" * 65)

    df = pd.DataFrame(results).sort_values('composite', ascending=False)
    for _, row in df.iterrows():
        print(f"  {row['ticker']:<8} {row['harga']:>10,.2f} {row['rsi']:>5.1f} {row['mfi']:>5.1f} "
              f"{row['smart_money_score']:>4.0f} {row['bandar_score']:>4.0f} {row['composite']:>4.0f} "
              f"{row['rekomendasi']:<12} {row.get('signal_stars', ''):>4}")

    print("")
    print(f"  Total di-screen: {len(results)}")

# ============================================================
# LOAD TICKERS FROM CSV
# ============================================================

def load_tickers_from_csv(filepath):
    """Load tickers dari CSV file."""
    try:
        df = pd.read_csv(filepath)
        for col in df.columns:
            tickers = df[col].dropna().astype(str).tolist()
            if tickers:
                return [t.strip().upper().replace(".JK", "") + ".JK" for t in tickers
                        if len(t.strip()) > 2 and len(t.strip()) < 10]
        return []
    except Exception as e:
        print(f"CSV Error: {e}")
        return []

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("")
    print("=" * 70)
    print("  SMART MONEY SCREENING + FULL REPORT — UNIFIED")
    print("  " + datetime.now().strftime('%Y-%m-%d %H:%M'))
    print("=" * 70)

    args = sys.argv[1:]
    mode = "screen"  # default mode

    if not args:
        tickers = DEFAULT_TICKERS
        print(f"Tidak ada argumen. Gunakan default: {tickers}")
    elif args[0] == "-csv" and len(args) > 1:
        csv_path = args[1]
        print(f"Load tickers dari CSV: {csv_path}")
        tickers = load_tickers_from_csv(csv_path)
        if not tickers:
            print("Gagal load CSV, gunakan default")
            tickers = DEFAULT_TICKERS
    elif args[0] == "-report":
        mode = "report"
        tickers = [t.upper().replace(".JK", "") + ".JK" for t in args[1:]] if len(args) > 1 else DEFAULT_TICKERS
    elif args[0] == "-screen":
        mode = "screen"
        tickers = [t.upper().replace(".JK", "") + ".JK" for t in args[1:]] if len(args) > 1 else DEFAULT_TICKERS
    else:
        tickers = [t.upper().replace(".JK", "") + ".JK" for t in args]

    print(f"Mode        : {mode.upper()}")
    print(f"Tickers     : {tickers}")
    print(f"Total       : {len(tickers)} ticker")
    print("=" * 70)

    results = []
    for ticker in tickers:
        print(f"\nProcessing: {ticker} ...")
        r = screen_ticker(ticker)
        if r is None:
            print(f"  SKIP {ticker}: data kurang atau error")
            continue

        if mode == "report":
            # Full detail report per ticker
            d = yf.download(ticker, period=PERIODE, interval=INTERVAL, progress=False)
            close = get_col(d, "Close").astype(float)
            high = get_col(d, "High").astype(float)
            low = get_col(d, "Low").astype(float)
            vol = get_col(d, "Volume").astype(float)

            rsi = calc_rsi(close)
            macd_m, macd_s, macd_h = calc_macd(close)
            mfi = calc_mfi(high, low, close, vol)
            ad = calc_ad(high, low, close, vol)
            sma20 = calc_sma(close, 20)
            sma50 = calc_sma(close, 50)
            ema9 = calc_ema(close, 9)
            bb_up, bb_mid, bb_lo = calc_bollinger(close)

            fname_csv = export_detail_csv(ticker, d, close, rsi, macd_m, macd_s, macd_h,
                                          sma20, sma50, ema9, bb_up, bb_mid, bb_lo, mfi, ad)
            print(format_report_output(r, fname_csv))
        else:
            # Screen mode - compact
            print(f"  {r['ticker']} | {r['harga']:,.0f} | RSI:{r['rsi']:.0f} MFI:{r['mfi']:.0f} | "
                  f"SM:{r['smart_money_score']:.0f}({r['smart_money_label']}) BD:{r['bandar_score']:.0f}({r['bandar_label']}) | "
                  f"CM:{r['composite']:.0f} | {r['rekomendasi']} {r['signal_stars']}")

        results.append(r)

    # Save screening CSV
    if results:
        fn_csv = export_csv(results, "screening")
        print(f"\n📁 Screening CSV saved: {fn_csv}")

    # Summary
    if results:
        print_summary(results)

    print("")
    print("=" * 70)
    print("  Selesai.")
    print("=" * 70)