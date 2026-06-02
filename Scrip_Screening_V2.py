#!/usr/bin/env python3
"""
Scrip_Screening_V2 - Auto-Screening Top IDX (Tanpa Input Ticker)
========================================================================
Script screening otomatis untuk saham-saham IDX pilihan.
Default watchlist berisi 60-80 emiten LQ45 + IDX30 + watchlist Ery.

Usage:
  python Scrip_Screening_V2.py                    # Default watchlist
  python Scrip_Screening_V2.py -csv mylist.csv   # Custom dari CSV
  python Scrip_Screening_V2.py -top 20           # Tampilkan top 20 (default 10)
  python Scrip_Screening_V2.py -modal 50000000  # Custom modal (default 100jt)
  python Scrip_Screening_V2.py -period 6mo       # Period data (default 3mo)

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
DEFAULT_MODAL = 100_000_000  # Rp 100jt
DEFAULT_TOP = 10
DEFAULT_PERIOD = "3mo"
DEFAULT_INTERVAL = "1d"

# ============================================================
# DEFAULT WATCHLIST (60+ Saham IDX Pilihan)
# ============================================================
# Gabungan: LQ45 + IDX30 + Watchlist Ery + Saham Aktif
DEFAULT_WATCHLIST = [
    # ===== LQ45 =====
    "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK",
    "ASII.JK", "UNVR.JK", "INDF.JK", "ICBP.JK", "KLBF.JK",
    "UNTR.JK", "PTBA.JK", "ITMG.JK", "ADRO.JK", "ANTM.JK",
    "INCO.JK", "MDKA.JK", "HRUM.JK", "TPIA.JK", "BRPT.JK",
    "SMGR.JK", "INTP.JK", "WIKA.JK", "PTPP.JK", "JSMR.JK",
    "PGAS.JK", "MEDC.JK", "ESSA.JK", "AKRA.JK",
    "CPIN.JK", "JPFA.JK", "SIDO.JK", "MIKA.JK",
    "CTRA.JK", "BSDE.JK", "PWON.JK", "SMRA.JK",
    "EXCL.JK", "ISAT.JK", "TOWR.JK", "TBIG.JK",
    "MNCN.JK", "GOTO.JK", "EMTK.JK",
    # ===== Watchlist Ery =====
    "CUAN.JK", "GULA.JK",
    # ===== Saham Aktif Mei-Juni 2026 =====
    "IRSX.JK", "HRTA.JK", "DRMA.JK", "VKTR.JK", "KETR.JK",
    "CARE.JK", "TOOL.JK", "AMMN.JK", "DSSA.JK", "BIPI.JK",
    "AMRT.JK", "MAPI.JK",
    # ===== Tambahan Blue Chip =====
    "BYAN.JK", "AALI.JK", "INKP.JK", "TINS.JK", "NIPP.JK",
    "AVIA.JK", "SRTG.JK", "HEAL.JK", "BREN.JK",
    "GGRM.JK", "HMSP.JK", "WIIM.JK",
]

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
    return x.rolling(p).mean()

def calc_ema(x, p):
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
    if pd.isna(sma50) or sma50 == 0: return "NETRAL"
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
    range_bb = bb_upper - bb_lower
    if range_bb == 0: return 0.5
    return (harga - bb_lower) / range_bb

# ============================================================
# SMART MONEY & BANDAR SCORE
# ============================================================

def calc_smart_money_score(rsi, mfi, ad_slope, price_vs_sma200, macd_hist, volume_ratio):
    """Smart Money Score (0-100)"""
    score = 50
    if rsi < 10: score += 25
    elif rsi < 15: score += 22
    elif rsi < 20: score += 18
    elif rsi < 25: score += 12
    elif rsi < 30: score += 6
    elif rsi > 70: score -= 15
    elif rsi > 60: score -= 8
    if mfi < 10: score += 25
    elif mfi < 15: score += 22
    elif mfi < 20: score += 18
    elif mfi < 25: score += 12
    elif mfi < 30: score += 6
    elif mfi > 80: score -= 15
    elif mfi > 70: score -= 8
    if ad_slope > 0.05: score += 20
    elif ad_slope > 0: score += 12
    elif ad_slope < -0.05: score -= 15
    if price_vs_sma200 < 0.7: score += 15
    elif price_vs_sma200 < 0.85: score += 10
    elif price_vs_sma200 < 0.95: score += 5
    elif price_vs_sma200 > 1.3: score -= 10
    if macd_hist > 0.1: score += 10
    elif macd_hist > 0: score += 5
    elif macd_hist < -0.1: score -= 10
    if volume_ratio > 2.0: score += 5
    elif volume_ratio > 1.5: score += 3
    elif volume_ratio > 1.0: score += 1
    return max(0, min(100, score))

def get_sm_label(score):
    if score >= 70: return "SMART MONEY IN"
    elif score >= 50: return "AKUMULASI"
    elif score >= 30: return "NETRAL"
    else: return "SMART MONEY OUT"

def calc_bandar_score(rsi, mfi, bb_position, price_momentum_5d, volume_ratio, ad_slope):
    """Bandar Value Score (0-100)"""
    score = 50
    if rsi < 15: score += 20
    elif rsi < 20: score += 15
    elif rsi < 25: score += 10
    elif rsi < 30: score += 5
    elif rsi > 70: score -= 10
    if mfi < 10: score += 20
    elif mfi < 15: score += 15
    elif mfi < 20: score += 10
    elif mfi < 25: score += 5
    elif mfi > 80: score -= 10
    if bb_position < 0: score += 20
    elif bb_position < 0.1: score += 15
    elif bb_position < 0.2: score += 10
    elif bb_position < 0.3: score += 5
    if price_momentum_5d < -10: score += 15
    elif price_momentum_5d < -5: score += 10
    elif price_momentum_5d < -2: score += 5
    elif price_momentum_5d > 5: score -= 8
    if volume_ratio > 2.5: score += 15
    elif volume_ratio > 2.0: score += 10
    elif volume_ratio > 1.5: score += 5
    elif volume_ratio < 0.5: score -= 5
    if ad_slope > 0.02: score += 10
    elif ad_slope > 0: score += 5
    elif ad_slope < -0.02: score -= 8
    return max(0, min(100, score))

def get_bandar_label(score, ad_slope, price_momentum_5d):
    if score >= 70 and ad_slope > 0: return "AKUMULASI"
    elif score >= 70 and ad_slope < 0: return "DISTRIBUSI"
    elif score >= 50: return "AKTIF"
    elif score >= 30: return "NETRAL"
    else: return "PASIF"

# ============================================================
# CATALYST DETECTION
# ============================================================

def detect_catalyst(price, sma20, sma50, volume_ratio, rsi, macd_hist):
    catalysts = []
    if price < sma20 * 0.95 and rsi < 30:
        catalysts.append("PRICE CRASH")
    if sma20 > sma50 * 0.98 and sma20 < sma50 * 1.02:
        catalysts.append("GOLDEN CROSS SOON")
    if volume_ratio > 1.8 and rsi < 35:
        catalysts.append("VOLUME SURGE")
    if macd_hist > 0:
        catalysts.append("MACD REVERSAL")
    if rsi < 25:
        catalysts.append("OVERSHOT")
    return catalysts if catalysts else ["NONE"]

# ============================================================
# BUY SIGNAL
# ============================================================

def check_buy_signal(sm_score, rsi, mfi, catalysts):
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
# ENTRY / SL / TP
# ============================================================

def calc_entry_sl_tp(close, bb_lower, bb_upper, rsi_val, macd_hist):
    price = float(close.iloc[-1])
    bb_l = float(bb_lower.iloc[-1])
    bb_u = float(bb_upper.iloc[-1])

    sl_pct = min(abs(price - bb_l) / price, 0.03)
    tp_pct = min(abs(bb_u - price) / price, 0.05)

    if rsi_val <= 40:
        sl_pct = max(sl_pct, 0.02)
    if macd_hist > 0:
        tp_pct = max(tp_pct, 0.04)

    sl_price = round(price * (1 - sl_pct), 2)
    tp_price = round(price * (1 + tp_pct), 2)

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

def calc_money_mgmt(entry, sl, tp, modal):
    risk_pct = 0.02  # 2% modal per trade
    risk_amount = modal * risk_pct
    price_diff = abs(entry - sl)
    if price_diff == 0: return None
    lot = int(risk_amount / price_diff)
    if lot == 0: lot = 100
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

def screen_ticker(ticker, period=DEFAULT_PERIOD, modal=DEFAULT_MODAL):
    """Screen single ticker dan return hasil lengkap."""
    try:
        d = yf.download(ticker, period=period, interval=DEFAULT_INTERVAL, progress=False)
        if len(d) < 30:
            return None

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
        sma200 = calc_sma(close, 200)
        ema9 = calc_ema(close, 9)
        bb_up, bb_lo = calc_bollinger(close)

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

        avg_vol_20 = float(vol.rolling(20).mean().iloc[-1])
        curr_vol = float(vol.iloc[-1])
        vol_ratio = curr_vol / avg_vol_20 if avg_vol_20 > 0 else 1

        price_5d_ago = float(close.iloc[-6]) if len(close) > 5 else curr
        mom_5d = ((curr - price_5d_ago) / price_5d_ago) * 100

        sma20_val = float(sma20.iloc[-1]) if not pd.isna(sma20.iloc[-1]) else curr
        sma50_val = float(sma50.iloc[-1]) if not pd.isna(sma50.iloc[-1]) else curr
        sma200_val = float(sma200.iloc[-1]) if not pd.isna(sma200.iloc[-1]) else curr
        price_vs_sma200 = curr / sma200_val if sma200_val != 0 else 1

        bb_up_val = float(bb_up.iloc[-1])
        bb_lo_val = float(bb_lo.iloc[-1])
        bb_range = bb_up_val - bb_lo_val
        bb_pos = (curr - bb_lo_val) / bb_range if bb_range > 0 else 0.5

        sm_score = calc_smart_money_score(rsi_val, mfi_val, ad_slope, price_vs_sma200, macd_h_val, vol_ratio)
        bandar_score = calc_bandar_score(rsi_val, mfi_val, bb_pos, mom_5d, vol_ratio, ad_slope)
        sm_label = get_sm_label(sm_score)
        bandar_label = get_bandar_label(bandar_score, ad_slope, mom_5d)
        catalysts = detect_catalyst(curr, sma20_val, sma50_val, vol_ratio, rsi_val, macd_h_val)
        signal, signal_stars = check_buy_signal(sm_score, rsi_val, mfi_val, catalysts)
        composite = (sm_score + bandar_score) / 2
        est = calc_entry_sl_tp(close, bb_lo, bb_up, rsi_val, macd_h_val)
        mm = calc_money_mgmt(est['entry'], est['sl'], est['tp'], modal)

        chg_1d = curr - prev_close
        chg_1d_pct = (chg_1d / prev_close * 100) if prev_close != 0 else 0

        h20 = float(high.tail(20).max())
        l20 = float(low.tail(20).min())

        rsi_sig = rsi_signal(rsi_val)
        macd_sig = macd_signal(macd_mv, macd_sv, macd_h_val)
        ma_sig = ma_signal(curr, sma20_val, sma50_val)
        mfi_sig = mfi_signal(mfi_val)

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
            'bandar_score': bandar_score,
            'bandar_label': bandar_label,
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

def export_csv(results, prefix="screening_v2"):
    """Export results ke CSV."""
    if not results: return None
    df = pd.DataFrame(results)
    df_csv = df.copy()
    if 'catalysts' in df_csv.columns:
        df_csv['catalysts'] = df_csv['catalysts'].apply(lambda x: '|'.join(x) if isinstance(x, list) else x)
    fn = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    df_csv.to_csv(fn, index=False)
    return fn

# ============================================================
# LOAD TICKERS FROM CSV
# ============================================================

def load_tickers_from_csv(filepath):
    """Load tickers dari CSV file (1 column)."""
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
# OUTPUT FORMAT
# ============================================================

def print_top_results(results, top_n=10):
    """Print top N results dalam format compact."""
    if not results:
        print("Tidak ada hasil.")
        return

    results_sorted = sorted(results, key=lambda x: x['composite'], reverse=True)

    print("")
    print("=" * 80)
    print(f"  TOP {top_n} SAHAM BY COMPOSITE SCORE — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 80)
    print(f"  {'#':<3} {'Ticker':<8} {'Harga':>9} {'RSI':>5} {'MFI':>5} {'SM%':>4} {'BD%':>4} {'CM%':>4} {'Rekomendasi':<14} {'Stars':<5}")
    print("  " + "-" * 77)

    for i, r in enumerate(results_sorted[:top_n], 1):
        ticker = r['ticker']
        harga = f"{r['harga']:,.0f}"
        rsi = f"{r['rsi']:.0f}"
        mfi = f"{r['mfi']:.0f}"
        sm = f"{r['smart_money_score']:.0f}"
        bd = f"{r['bandar_score']:.0f}"
        cm = f"{r['composite']:.0f}"
        rec = r['rekomendasi'][:14]
        stars = r['signal_stars']

        # Highlight BUY signals
        prefix = "🚨" if "BUY" in r['rekomendasi'] else "  "

        print(f"  {prefix} {i:<2} {ticker:<8} {harga:>9} {rsi:>5} {mfi:>5} {sm:>4} {bd:>4} {cm:>4} {rec:<14} {stars:<5}")

    # Show detail top 5
    print("")
    print("=" * 80)
    print("  DETAIL TOP 5:")
    print("=" * 80)
    for i, r in enumerate(results_sorted[:5], 1):
        print(f"\n  {i}. {r['ticker']} — Composite {r['composite']} {r['signal_stars']}")
        print(f"     Harga     : Rp {r['harga']:,.0f}  (1d: {r['chg_1d_pct']:+.2f}%, 5d: {r['chg_5d_pct']:+.2f}%)")
        print(f"     RSI/MFI   : {r['rsi']:.0f} ({r['rsi_signal']}) / {r['mfi']:.0f} ({r['mfi_signal']})")
        print(f"     MACD      : {r['macd']} (hist: {r['macd_hist']:+.3f})")
        print(f"     SM        : {r['smart_money_score']:.0f} → [{r['smart_money_label']}]")
        print(f"     Bandar    : {r['bandar_score']:.0f} → [{r['bandar_label']}]")
        print(f"     A/D Slope : {r['ad_slope']:+.4f} | Vol Ratio: {r['vol_ratio']:.2f}x")
        print(f"     Catalysts : {', '.join(r['catalysts'])}")
        print(f"     Entry     : Rp {r['entry']:,.0f}")
        print(f"     Stop Loss : Rp {r['sl']:,.0f} ({r['sl_pct']}%)")
        print(f"     Target    : Rp {r['tp']:,.0f} ({r['tp_pct']}%)")
        print(f"     R:R       : {r['rr_ratio']} | Rekomendasi: {r['rekomendasi']}")
        if 'lot' in r:
            print(f"     Lot {r['lot']:,} | Modal {r['modal_pct']:.0f}% | Max Loss: Rp {r['max_loss']:,.0f} | Max Profit: Rp {r['max_profit']:,.0f}")

    # Summary stats
    print("")
    print("=" * 80)
    print("  RINGKASAN:")
    print("=" * 80)
    total = len(results_sorted)
    buys = [r for r in results_sorted if "BUY" in r['rekomendasi']]
    strong_buys = [r for r in results_sorted if "STRONG BUY" in r['rekomendasi']]
    watch = [r for r in results_sorted if r['rekomendasi'] == "WATCH"]
    print(f"  Total di-screen  : {total} saham")
    print(f"  STRONG BUY       : {len(strong_buys)} ({', '.join([r['ticker'] for r in strong_buys]) or 'tidak ada'})")
    print(f"  BUY              : {len(buys)} ({', '.join([r['ticker'] for r in buys if 'STRONG' not in r['rekomendasi']]) or 'tidak ada'})")
    print(f"  WATCH            : {len(watch)} ({', '.join([r['ticker'] for r in watch]) or 'tidak ada'})")
    print("=" * 80)

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("")
    print("=" * 80)
    print("  Scrip_Screening_V2 — Auto Screening IDX")
    print("  " + datetime.now().strftime('%Y-%m-%d %H:%M'))
    print("=" * 80)

    # Parse args
    args = sys.argv[1:]
    tickers = DEFAULT_WATCHLIST.copy()
    top_n = DEFAULT_TOP
    modal = DEFAULT_MODAL
    period = DEFAULT_PERIOD

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "-csv" and i + 1 < len(args):
            csv_path = args[i + 1]
            print(f"Load tickers dari CSV: {csv_path}")
            tickers = load_tickers_from_csv(csv_path)
            if not tickers:
                print("Gagal load CSV, gunakan default watchlist")
                tickers = DEFAULT_WATCHLIST
            i += 2
        elif arg == "-top" and i + 1 < len(args):
            top_n = int(args[i + 1])
            i += 2
        elif arg == "-modal" and i + 1 < len(args):
            modal = int(args[i + 1])
            i += 2
        elif arg == "-period" and i + 1 < len(args):
            period = args[i + 1]
            i += 2
        elif arg == "-all":
            tickers = DEFAULT_WATCHLIST.copy()
            i += 1
        else:
            # Treat as ticker
            tickers = [arg.upper().replace(".JK", "") + ".JK"]
            i += 1

    print(f"Mode        : AUTO-SCREENING")
    print(f"Top N       : {top_n}")
    print(f"Modal       : Rp {modal:,.0f}")
    print(f"Period      : {period}")
    print(f"Watchlist   : {len(tickers)} saham")
    print("=" * 80)

    # Run screening
    results = []
    total = len(tickers)
    for idx, ticker in enumerate(tickers, 1):
        print(f"\n[{idx}/{total}] Processing: {ticker} ...", end=" ")
        r = screen_ticker(ticker, period=period, modal=modal)
        if r is None:
            print("SKIP (data kurang)")
            continue
        print(f"OK | CM:{r['composite']:.0f} | {r['rekomendasi']}")
        results.append(r)

    # Save CSV
    if results:
        fn_csv = export_csv(results, "screening_v2")
        print(f"\n📁 CSV saved: {fn_csv}")

    # Print top N
    print_top_results(results, top_n=top_n)

    print("")
    print("=" * 80)
    print("  Selesai.")
    print("=" * 80)
