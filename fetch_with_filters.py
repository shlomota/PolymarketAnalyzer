#!/usr/bin/env python3
"""
Fetch trades using Core API with higher limits (0-10,000) and filters
"""

import requests
import json
from datetime import datetime
from collections import defaultdict


def fetch_all_trades_core_api(condition_id: str, filter_type=None, filter_amount=None):
    """
    Fetch trades using Core API with higher limits
    - limit: 0-10,000 (vs 500)
    - offset: 0-10,000 (vs 1,000)
    """
    base_url = "https://data-api.polymarket.com/trades"
    all_trades = []
    seen_hashes = set()
    offset = 0
    limit = 1000  # Higher batch size
    page = 1

    print(f"Fetching trades using Core API...")
    print(f"Condition ID: {condition_id}")
    if filter_type and filter_amount:
        print(f"Filter: {filter_type} >= ${filter_amount}")
    print(f"{'='*80}\n")

    while offset < 10000:  # Max offset is 10,000
        params = {
            "market": condition_id,
            "limit": limit,
            "offset": offset
        }

        if filter_type and filter_amount:
            params["filterType"] = filter_type
            params["filterAmount"] = filter_amount

        print(f"Page {page} (offset={offset})...", end=" ", flush=True)

        response = requests.get(base_url, params=params)
        response.raise_for_status()
        trades = response.json()

        if not trades:
            print("No more trades.")
            break

        # Deduplicate
        new_trades = []
        duplicate_count = 0
        for trade in trades:
            tx_hash = trade.get('transactionHash')
            if tx_hash and tx_hash not in seen_hashes:
                seen_hashes.add(tx_hash)
                new_trades.append(trade)
            else:
                duplicate_count += 1

        if not new_trades:
            print(f"All {len(trades)} trades are duplicates. Reached end.")
            break

        all_trades.extend(new_trades)

        if duplicate_count > 0:
            print(f"✓ {len(new_trades)} new ({duplicate_count} dups) Total: {len(all_trades)}")
        else:
            print(f"✓ {len(new_trades)} trades Total: {len(all_trades)}")

        if len(trades) < limit:
            print(f"\n{'='*80}")
            print(f"✓ Fetched all {len(all_trades)} trades")
            break

        offset += limit
        page += 1

    print(f"\n{'='*80}\n")
    return all_trades


def analyze_price_distribution(trades):
    """Find trades in mid-range prices"""

    if not trades:
        print("No trades found")
        return

    # Show date range
    timestamps = [t['timestamp'] for t in trades]
    if timestamps:
        oldest = min(timestamps)
        newest = max(timestamps)
        oldest_dt = datetime.fromtimestamp(oldest)
        newest_dt = datetime.fromtimestamp(newest)
        days = (newest - oldest) / 86400

        print(f"DATE RANGE:")
        print(f"  Oldest: {oldest_dt}")
        print(f"  Newest: {newest_dt}")
        print(f"  Span: {days:.1f} days\n")
        print(f"{'='*100}\n")

    # Price distribution
    price_buckets = defaultdict(list)
    for trade in trades:
        price = trade['price']
        bucket = int(price * 20) * 0.05  # 5-cent buckets
        price_buckets[bucket].append(trade)

    print("PRICE DISTRIBUTION (5-cent buckets):")
    print(f"{'Range':<15} {'Count':<10} {'Total Size':<20} {'Total Value ($)':<20}")
    print("-" * 100)

    for bucket in sorted(price_buckets.keys()):
        bucket_trades = price_buckets[bucket]
        total_size = sum(t['size'] for t in bucket_trades)
        total_value = sum(t['size'] * t['price'] for t in bucket_trades)
        print(f"{bucket:.2f}-{bucket+0.05:.2f}     {len(bucket_trades):<10} {total_size:<20,.0f} ${total_value:<19,.2f}")

    # Find mid-range trades (0.05-0.15)
    print(f"\n{'='*100}\n")
    print("MID-RANGE TRADES (0.05-0.15 price range):")

    midrange_trades = [t for t in trades if 0.05 <= t['price'] <= 0.15]
    midrange_trades.sort(key=lambda x: x['size'], reverse=True)

    print(f"Found {len(midrange_trades)} trades in this range\n")

    if midrange_trades:
        print(f"{'Price':<10} {'Size':<15} {'Value ($)':<15} {'Side':<6} {'Date':<20} {'User':<20}")
        print("-" * 100)

        for trade in midrange_trades[:50]:  # Top 50
            dt = datetime.fromtimestamp(trade['timestamp'])
            value = trade['size'] * trade['price']
            user = trade['proxyWallet'][:16]
            print(f"{trade['price']:<10.4f} {trade['size']:<15,.0f} ${value:<14,.2f} {trade['side']:<6} {dt.strftime('%Y-%m-%d %H:%M'):<20} {user:<20}")


def main():
    # Maduro out by January 31, 2026
    condition_id = "0x580adc1327de9bf7c179ef5aaffa3377bb5cb252b7d6390b027172d43fd6f993"
    market_name = "Maduro out by January 31, 2026?"

    print(f"\n{'='*80}")
    print(f"Market: {market_name}")
    print(f"{'='*80}\n")

    # First, fetch all trades without filter
    print("=== FETCHING ALL TRADES ===\n")
    all_trades = fetch_all_trades_core_api(condition_id)

    print(f"Total trades fetched: {len(all_trades)}\n")

    # Save to JSON
    with open('maduro_out_trades.json', 'w') as f:
        json.dump(all_trades, f, indent=2)
    print(f"✓ Saved to maduro_out_trades.json\n")

    # Analyze
    analyze_price_distribution(all_trades)

    # Now try with filter for big trades (>$100 cash value)
    print(f"\n\n{'='*80}")
    print("=== FETCHING BIG TRADES (>$100 cash value) ===\n")
    big_trades = fetch_all_trades_core_api(condition_id, filter_type="CASH", filter_amount=100)

    print(f"\nBig trades fetched: {len(big_trades)}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
