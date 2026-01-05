#!/usr/bin/env python3
"""
Find trades with mid-range prices (not extreme 0.001 or 0.999)
"""

import requests
import json
from datetime import datetime
from collections import defaultdict


def fetch_all_trades(condition_id: str):
    """Fetch all trades for a given market condition ID"""
    base_url = "https://data-api.polymarket.com/trades"
    all_trades = []
    seen_hashes = set()
    offset = 0
    limit = 500

    while True:
        url = f"{base_url}?market={condition_id}&limit={limit}&offset={offset}"

        response = requests.get(url)
        response.raise_for_status()
        trades = response.json()

        if not trades:
            break

        new_trades = []
        for trade in trades:
            tx_hash = trade.get('transactionHash')
            if tx_hash and tx_hash not in seen_hashes:
                seen_hashes.add(tx_hash)
                new_trades.append(trade)

        if not new_trades:
            break

        all_trades.extend(new_trades)

        if len(trades) < limit:
            break

        offset += limit

    return all_trades


def analyze_price_distribution(trades):
    """Analyze price distribution and find mid-range trades"""

    # Filter for mid-range prices (between 0.02 and 0.98, excluding extremes)
    midrange_trades = [t for t in trades if 0.02 <= t['price'] <= 0.98]

    print(f"Total trades: {len(trades)}")
    print(f"Mid-range price trades (0.02-0.98): {len(midrange_trades)}")
    print(f"\n{'='*100}\n")

    # Sort by size to find biggest mid-range trades
    midrange_trades.sort(key=lambda x: x['size'], reverse=True)

    print("TOP 20 LARGEST MID-RANGE TRADES:")
    print(f"{'Price':<10} {'Size':<15} {'Side':<6} {'Outcome':<8} {'Date':<20} {'Tx Hash':<20}")
    print("-" * 100)

    for trade in midrange_trades[:20]:
        dt = datetime.fromtimestamp(trade['timestamp'])
        print(f"{trade['price']:<10.4f} {trade['size']:<15,.0f} {trade['side']:<6} {trade['outcome']:<8} {dt.strftime('%Y-%m-%d %H:%M:%S'):<20} {trade['transactionHash'][:16]:<20}")

    # Price range distribution
    print(f"\n{'='*100}\n")
    print("PRICE RANGE DISTRIBUTION:")

    price_buckets = defaultdict(list)
    for trade in trades:
        # Bucket by 0.05 increments
        bucket = int(trade['price'] * 20) * 0.05  # 0.00-0.05, 0.05-0.10, etc.
        price_buckets[bucket].append(trade)

    for bucket in sorted(price_buckets.keys()):
        trades_in_bucket = price_buckets[bucket]
        total_size = sum(t['size'] for t in trades_in_bucket)
        print(f"{bucket:.2f}-{bucket+0.05:.2f}: {len(trades_in_bucket):>6} trades, {total_size:>15,.0f} total size")

    # Find specific trades around 0.06 (user mentioned looking for ~6 cents)
    print(f"\n{'='*100}\n")
    print("TRADES IN 0.04-0.15 RANGE (4-15 cents):")

    trades_at_006 = [t for t in trades if 0.04 <= t['price'] <= 0.15]
    trades_at_006.sort(key=lambda x: x['size'], reverse=True)

    print(f"Found {len(trades_at_006)} trades in this range")
    print(f"{'Price':<10} {'Size':<15} {'Side':<6} {'Outcome':<8} {'Date':<20} {'Wallet':<20}")
    print("-" * 100)

    for trade in trades_at_006[:50]:  # Top 50
        dt = datetime.fromtimestamp(trade['timestamp'])
        wallet = trade['proxyWallet'][:16]
        print(f"{trade['price']:<10.4f} {trade['size']:<15,.0f} {trade['side']:<6} {trade['outcome']:<8} {dt.strftime('%Y-%m-%d %H:%M:%S'):<20} {wallet:<20}")


def main():
    # US forces in Venezuela by January 31st market
    condition_id = "0xbb8bfdef9052b2709557a6f8f28b23551e3134bfb86eca800211e2191703ee65"

    print("Fetching trades for: US forces in Venezuela by January 31, 2026")
    print("Fetching trades...")
    trades = fetch_all_trades(condition_id)
    print(f"Fetched {len(trades)} trades\n")

    analyze_price_distribution(trades)


if __name__ == "__main__":
    main()
