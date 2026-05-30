#!/usr/bin/env python3
"""
News Monitor — Auto-fetch news from RSS feeds filtered by ticker watchlist
Usage: python news_monitor.py ANTM BBCA BBRI DSNG
"""

import feedparser
import requests
from datetime import datetime, timedelta
import sys
import re
import html

# === CONFIG ===
RSS_FEEDS = {
    "Kontan Market":    "https://www.kontan.co.id/rss/market",
    "CNBC Indonesia":  "https://www.cnbcindonesia.com/market/rss",
    "Investor.id":      "https://investor.id/rss",
    "Emitennews":       "https://emitennews.com/feed/",
}

TICKERS = sys.argv[1:] if len(sys.argv) > 1 else [
    "ANTM", "BBCA", "BBRI", "INCO", "NCKL", "DSNG", "LSIP", "AALI", "SMAR",
    "PTBA", "UNTR", "ASII", "TLKM", "MYOR", "DSSA", "BRMS", "BYAN", "HRTA"
]

MAX_AGE_DAYS = 3  # Only show news from last 3 days
MAX_ARTICLES_PER_FEED = 10

# === COLOR ===
merah  = "\033[91m"
hijau  = "\033[92m"
kuning = "\033[93m"
biru   = "\033[94m"
bold   = "\033[1m"
reset  = "\033[0m"

def strip_html(text):
    clean = re.sub(r'<[^>]+>', '', text)
    clean = html.unescape(clean)
    return clean.strip()

def parse_date(entry):
    """Parse various date formats from RSS entries"""
    for fmt in [
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%d %b %Y %H:%M:%S",
    ]:
        for attr in ['published', 'updated', 'created']:
            val = getattr(entry, attr, None)
            if val:
                try:
                    dt = datetime.strptime(val[:25], fmt)
                    return dt
                except:
                    pass
    return None

def age_days(entry):
    """Return days since publication"""
    dt = parse_date(entry)
    if dt:
        return (datetime.now() - dt).days
    return 999

def ticker_match(title, summary, tickers):
    """Check if any ticker mentioned in title/summary"""
    text = f"{title} {summary}".upper()
    found = []
    for t in tickers:
        # Match .JK suffix or standalone
        if re.search(rf'\b{t}(\.JK)?\b', text):
            found.append(t)
    return found

def fetch_feed(name, url, tickers):
    """Fetch and filter a single RSS feed"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; NewsMonitor/1.0)'}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception as e:
        return []

    results = []
    for entry in feed.entries[:MAX_ARTICLES_PER_FEED]:
        title   = strip_html(entry.get('title', ''))
        summary = strip_html(entry.get('summary', entry.get('description', '')))[:300]
        link    = entry.get('link', '')
        days    = age_days(entry)

        if days > MAX_AGE_DAYS:
            continue

        matched = ticker_match(title, summary, tickers)
        if matched:
            dt = parse_date(entry)
            date_str = dt.strftime("%d/%m %H:%M") if dt else "???"
            results.append({
                'date': date_str,
                'title': title,
                'summary': summary,
                'link': link,
                'tickers': matched,
                'days': days,
            })
    return results

def main():
    print(f"\n{bold}{'='*60}")
    print(f"  📰 NEWS MONITOR — {datetime.now().strftime('%d %b %Y %H:%M')}")
    print(f"  Ticklers: {', '.join(TICKERS)}")
    print(f"{'='*60}{reset}\n")

    all_results = []
    ticker_counts = {t: 0 for t in TICKERS}
    ticker_articles = {t: [] for t in TICKERS}

    for name, url in RSS_FEEDS.items():
        print(f"  🔍 Fetching: {name}...", end=" ", flush=True)
        articles = fetch_feed(name, url, TICKERS)
        print(f"{hijau}✓ {len(articles)} match{reset}")
        all_results.extend(articles)
        for a in articles:
            for t in a['tickers']:
                ticker_counts[t] += 1
                ticker_articles[t].append(a)

    # Sort by date
    all_results.sort(key=lambda x: x['days'])

    print(f"\n{bold}{'-'*60}")
    print(f"  📊 DITEMUKAN: {len(all_results)} berita dalam {MAX_AGE_DAYS} hari")
    print(f"{'-'*60}{reset}\n")

    # Ticker summary
    print(f"{bold}📈 TICKER ACTIVITY (berita count):{reset}")
    active = [(t, c) for t, c in ticker_counts.items() if c > 0]
    active.sort(key=lambda x: -x[1])
    if active:
        for t, c in active:
            bar = "█" * c
            print(f"  {biru}{t:6s}{reset} {c:2d}x  {bar}")
    else:
        print(f"  {merah}Tidak ada berita match untuk watchlist{reset}")
    print()

    # Grouped by ticker
    if active:
        print(f"{bold}📋 BERITA PER TICKER:{reset}")
        for ticker, count in active:
            print(f"\n  {biru}{bold}【{ticker}】{reset} — {count} berita")
            for a in ticker_articles[ticker][:5]:
                days_ago = f"{a['days']}d" if a['days'] > 0 else "today"
                print(f"    {kuning}{a['date']}{reset} [{days_ago}]")
                print(f"    {a['title'][:80]}{'...' if len(a['title']) > 80 else ''}")
                print(f"    {a['link']}")

    # Chronological all
    print(f"\n{bold}{'='*60}")
    print(f"  📅 SEMUA BERITA (chronological):")
    print(f"{'='*60}{reset}")
    for a in all_results:
        days_ago = f"{a['days']}d ago" if a['days'] > 0 else "TODAY"
        tags = ",".join([f"{biru}{t}{reset}" for t in a['tickers']])
        print(f"\n  {kuning}{a['date']}{reset} [{days_ago}] {tags}")
        print(f"  {bold}{a['title']}{reset}")
        print(f"  {a['summary'][:150]}{'...' if len(a['summary']) > 150 else ''}")
        print(f"  {a['link']}")

    print(f"\n{bold}{'='*60}{reset}\n")

if __name__ == "__main__":
    main()