# screening.py - Stock Screening dengan Smart Money, Bandar Value, MFI, RSI, MACD
# Pakai: python screening.py (dari CSV ticker_list.csv)
# Atau: python screening.py TLKM UNTR BMRI
# Author: Hermes Agent for Ery Wirawan

import yfinance as yf
import pandas as pd
import numpy as np
import warnings
import sys
import os
warnings.filterwarnings('ignore')

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_col(data, name):
    """Ambil kolom dari DataFrame multi-level atau single-level"""
    for c in data.columns:
        cn = c[0] if isinstance(c, tuple) else c
        if name.lower() in cn.lower():
            v = data[c]
            return v.iloc[:, 0] if v.ndim > 1 else v
    return data.iloc[:, 0]

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
    """Money Flow Index - similar to RSI but volume-weighted"""
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

def detect_catalyst(price, sma20, sma50, volume_ratio, rsi, macd_hist):
    """
    Deteksi catalyst potensial - return list of catalysts found
    """
    catalysts = []

    # Hammer/candlestick pattern (simplified - price rebounding from low)
    if price < sma20 * 0.95 and rsi < 30:
        catalysts.append("PRICE CRASH")

    # Golden cross potential (SMA50 near SMA200)
    if sma20 > sma50 * 0.98 and sma20 < sma50 * 1.02:
        catalysts.append("GOLDEN CROSS SOON")

    # Volume surge + oversold
    if volume_ratio > 1.8 and rsi < 35:
        catalysts.append("VOLUME SURGE")

    # MACD reversal
    if macd_hist > 0 and macd_hist > calc_macd(pd.Series([price])).iloc[-1]:
        catalysts.append("MACD REVERSAL")

    # Near 52-week low
    catalysts.append("OVERSHOT")  # General oversold condition

    return catalysts if catalysts else ["NONE"]

def check_buy_signal(sm_score, rsi, mfi, catalysts):
    """
    Buy Signal Check: Smart Money IN + RSI<15 + MFI<10 + Catalyst
    """
    sm_in = "AKUMULASI" if sm_score >= 60 else ("IN" if sm_score >= 50 else "OUT")
    rsi_ok = rsi < 15
    mfi_ok = mfi < 10
    catalyst_ok = len(catalysts) > 0 and catalysts[0] != "NONE"

    if sm_in in ["AKUMULASI", "IN"] and rsi_ok and mfi_ok and catalyst_ok:
        return "STRONG BUY", "***"
    elif sm_score >= 55 and rsi < 20 and mfi < 15:
        return "BUY", "**"
    elif sm_score >= 45 and rsi < 25:
        return "WATCH", "*"
    elif rsi > 75 or mfi > 85:
        return "OVERBOUGHT", ""
    else:
        return "HOLD", ""

# ============================================================
# MAIN SCREENING FUNCTION
# ============================================================

def screen_ticker(ticker):
    """Screen single ticker dan return hasil"""
    try:
        # Download data - 3 bulan untuk RSI yang stabil
        d = yf.download(ticker, period="3mo", interval="1d", progress=False)
        if len(d) < 30:
            return None

        close = get_col(d, "Close")
        high = get_col(d, "High")
        low = get_col(d, "Low")
        vol = get_col(d, "Volume")
        opn = get_col(d, "Open")

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
        prev_close = float(close.iloc[-2])
        rsi_val = float(rsi.iloc[-1])
        mfi_val = float(mfi.iloc[-1])
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

        # Price vs SMA
        sma20_val = float(sma20.iloc[-1])
        sma50_val = float(sma50.iloc[-1])
        sma200_val = float(sma200.iloc[-1]) if not pd.isna(sma200.iloc[-1]) else curr
        price_vs_sma200 = curr / sma200_val

        # Bollinger position
        bb_up_val = float(bb_up.iloc[-1])
        bb_lo_val = float(bb_lo.iloc[-1])
        bb_range = bb_up_val - bb_lo_val
        bb_pos = (curr - bb_lo_val) / bb_range if bb_range > 0 else 0.5

        # Smart Money Score
        sm_score = calc_smart_money_score(rsi_val, mfi_val, ad_slope, price_vs_sma200, macd_h_val, vol_ratio)

        # Bandar Value Score
        Bandar_score = calc_bandar_score(rsi_val, mfi_val, bb_pos, mom_5d, vol_ratio, ad_slope)

        # Catalyst detection
        catalysts = detect_catalyst(curr, sma20_val, sma50_val, vol_ratio, rsi_val, macd_h_val)

        # Buy signal
        signal, signal_stars = check_buy_signal(sm_score, rsi_val, mfi_val, catalysts)

        # Composite score (rata-rata Smart Money + Bandar)
        composite = (sm_score + Bandar_score) / 2

        return {
            "ticker": ticker.replace(".JK", ""),
            "price": curr,
            "change_pct": ((curr - prev_close) / prev_close) * 100,
            "rsi": rsi_val,
            "mfi": mfi_val,
            "macd_hist": macd_h_val,
            "sma20": sma20_val,
            "sma50": sma50_val,
            "sma200": sma200_val,
            "bb_up": bb_up_val,
            "bb_lo": bb_lo_val,
            "ema9": float(ema9.iloc[-1]),
            "ad": ad_val,
            "vol_ratio": vol_ratio,
            "sm_score": sm_score,
            "bandar_score": Bandar_score,
            "composite": composite,
            "catalysts": catalysts,
            "signal": signal,
            "signal_stars": signal_stars
        }

    except Exception as e:
        print(f"  ERROR {ticker}: {str(e)}")
        return None

def load_tickers_from_csv(filepath):
    """Load tickers dari CSV file"""
    try:
        df = pd.read_csv(filepath)
        # Ambil kolom pertama yang terlihat seperti ticker
        for col in df.columns:
            tickers = df[col].dropna().astype(str).tolist()
            if tickers:
                # Filter yang terlihat seperti kode saham
                return [t.strip().upper() for t in tickers if len(t.strip()) > 2 and len(t.strip()) < 10]
        return []
    except Exception as e:
        print(f"CSV Error: {e}")
        return []

def format_output(results):
    """Format hasil screening untuk Telegram - compact single-line output"""
    if not results:
        return "Tidak ada data untuk ditampilkan."

    # Sort by composite score
    results.sort(key=lambda x: x["composite"], reverse=True)

    lines = []
    lines.append("=" * 50)
    lines.append("📊 STOCK SCREENING REPORT")
    lines.append("=" * 50)

    # Header
    lines.append("")
    lines.append("TICKER   PRICE    RSI   MFI   SM%  BD%  SIG")
    lines.append("-" * 50)

    # Data rows - compact format
    for r in results:
        ticker = r["ticker"].ljust(7)
        price = f"{r['price']:.0f}".ljust(7)
        rsi = f"{r['rsi']:.0f}".ljust(5)
        mfi = f"{r['mfi']:.0f}".ljust(5)
        sm = f"{r['sm_score']:.0f}".ljust(4)
        bd = f"{r['bandar_score']:.0f}".ljust(4)
        sig = r['signal'][:6]

        line = f"{ticker} {price} {rsi} {mfi} {sm} {bd} {sig}"
        if r['signal_stars']:
            line += f" {r['signal_stars']}"
        lines.append(line)

    # Summary section
    lines.append("")
    lines.append("=" * 50)
    lines.append("📈 TOP 5 BY COMPOSITE SCORE:")
    lines.append("-" * 50)

    for i, r in enumerate(results[:5], 1):
        sig_ext = " ⭐" if r['signal_stars'] else ""
        cat = r['catalysts'][0] if r['catalysts'] else ""
        lines.append(f"{i}. {r['ticker']} | Composite: {r['composite']:.1f}{sig_ext}")
        lines.append(f"   RSI:{r['rsi']:.0f} MFI:{r['mfi']:.0f} | {r['signal']}")
        lines.append(f"   Catalyst: {cat}")

    # Buy signals section
    strong_buys = [r for r in results if "STRONG BUY" in r['signal']]
    if strong_buys:
        lines.append("")
        lines.append("=" * 50)
        lines.append("🚨 STRONG BUY SIGNALS:")
        lines.append("-" * 50)
        for r in strong_buys:
            lines.append(f"★ {r['ticker']} @ {r['price']:.0f}")
            lines.append(f"  SM Score:{r['sm_score']:.0f} | RSI:{r['rsi']:.0f} | MFI:{r['mfi']:.0f}")
            lines.append(f"  Catalyst: {', '.join(r['catalysts'])}")

    # Legend
    lines.append("")
    lines.append("=" * 50)
    lines.append("LEGENDA:")
    lines.append("SM% = Smart Money Score (0-100)")
    lines.append("BD% = Bandar Value Score (0-100)")
    lines.append("RSI < 15 + MFI < 10 = Oversold Extreme")
    lines.append("Composite = (SM + BD) / 2")
    lines.append("=" * 50)

    return "\n".join(lines)

def format_csv_output(results):
    """Format CSV output untuk further analysis"""
    if not results:
        return

    # Sort by composite
    results.sort(key=lambda x: x["composite"], reverse=True)

    # Create DataFrame
    data = []
    for r in results:
        data.append({
            "Ticker": r["ticker"],
            "Price": round(r["price"], 2),
            "Change%": round(r["change_pct"], 2),
            "RSI": round(r["rsi"], 1),
            "MFI": round(r["mfi"], 1),
            "MACD_Hist": round(r["macd_hist"], 4),
            "SMA20": round(r["sma20"], 2),
            "SMA50": round(r["sma50"], 2),
            "SMA200": round(r["sma200"], 2),
            "BB_Upper": round(r["bb_up"], 2),
            "BB_Lower": round(r["bb_lo"], 2),
            "EMA9": round(r["ema9"], 2),
            "A/D": round(r["ad"], 2),
            "Vol_Ratio": round(r["vol_ratio"], 2),
            "SM_Score": round(r["sm_score"], 1),
            "Bandar_Score": round(r["bandar_score"], 1),
            "Composite": round(r["composite"], 1),
            "Signal": r["signal"],
            "Catalysts": "|".join(r["catalysts"])
        })

    df = pd.DataFrame(data)
    return df

# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("STOCK SCREENING TOOL")
    print("Smart Money + Bandar Value + MFI + RSI + MACD")
    print("=" * 50)

    # Parse arguments
    args = sys.argv[1:]

    if not args:
        # Default tickers if no args
        tickers = ["TLKM.JK", "UNTR.JK", "BMRI.JK", "BBCA.JK"]
        print(f"Tidak ada argumen. Gunakan default: {tickers}")
    elif args[0] == "-csv" and len(args) > 1:
        # Load from CSV
        csv_path = args[1]
        print(f"Load tickers dari CSV: {csv_path}")
        tickers = load_tickers_from_csv(csv_path)
        if not tickers:
            print("Gagal load CSV, gunakan default")
            tickers = ["TLKM.JK", "UNTR.JK"]
    else:
        # Direct ticker input
        tickers = [t.upper() if ".JK" in t else f"{t.upper()}.JK" for t in args]

    print(f"Tickers: {tickers}")
    print(f"Total: {len(tickers)} ticker")
    print("")

    # Screen each ticker
    results = []
    for ticker in tickers:
        print(f"Processing: {ticker}...")
        result = screen_ticker(ticker)
        if result:
            results.append(result)

    print(f"\nSelesai. {len(results)} ticker berhasil di-screen.")

    # Output to console (Telegram-friendly)
    output = format_output(results)
    print("\n" + output)

    # Save to CSV
    if results:
        df_output = format_csv_output(results)
        csv_filename = "screening_results.csv"
        df_output.to_csv(csv_filename, index=False)
        print(f"\n📁 Results saved to: {csv_filename}")
