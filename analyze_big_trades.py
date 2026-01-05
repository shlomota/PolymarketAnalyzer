#!/usr/bin/env python3
"""
Fetch trades over $1k and calculate leaderboard
"""

import requests
from datetime import datetime
from collections import defaultdict


def fetch_big_trades(condition_id: str, min_cash: int = 1000):
    """Fetch trades with cash value >= min_cash"""
    base_url = "https://data-api.polymarket.com/trades"
    all_trades = []
    seen_hashes = set()
    offset = 0
    limit = 1000

    print(f"Fetching trades with cash value >= ${min_cash}")
    print(f"Condition ID: {condition_id}")
    print(f"{'='*80}\n")

    while offset < 10000:
        params = {
            "market": condition_id,
            "limit": limit,
            "offset": offset,
            "filterType": "CASH",
            "filterAmount": min_cash
        }

        print(f"Fetching offset={offset}...", end=" ", flush=True)

        response = requests.get(base_url, params=params)
        response.raise_for_status()
        trades = response.json()

        if not trades:
            print("No more trades.")
            break

        # Deduplicate
        new_trades = []
        for trade in trades:
            tx_hash = trade.get('transactionHash')
            if tx_hash and tx_hash not in seen_hashes:
                seen_hashes.add(tx_hash)
                new_trades.append(trade)

        if not new_trades:
            print("All duplicates. Done.")
            break

        all_trades.extend(new_trades)
        print(f"✓ Got {len(new_trades)} trades (Total: {len(all_trades)})")

        if len(trades) < limit:
            break

        offset += limit

    print(f"\n{'='*80}")
    print(f"✓ Fetched {len(all_trades)} trades over ${min_cash}\n")

    return all_trades


def calculate_leaderboard(trades, resolves_to="Yes"):
    """Calculate P&L leaderboard for big trades"""

    # Group by user
    user_trades = defaultdict(list)
    for trade in trades:
        wallet = trade['proxyWallet']
        user_trades[wallet].append(trade)

    results = []

    for wallet, user_trade_list in user_trades.items():
        yes_shares = 0
        no_shares = 0
        total_spent = 0
        total_received = 0

        for trade in user_trade_list:
            size = trade['size']
            price = trade['price']
            side = trade['side']
            outcome = trade['outcome']

            if side == 'BUY':
                cost = size * price
                total_spent += cost
                if outcome == 'Yes':
                    yes_shares += size
                else:
                    no_shares += size
            else:  # SELL
                revenue = size * price
                total_received += revenue
                if outcome == 'Yes':
                    yes_shares -= size
                else:
                    no_shares -= size

        # Calculate final value
        if resolves_to == 'Yes':
            shares_in_winning_outcome = yes_shares
        else:
            shares_in_winning_outcome = no_shares

        final_position_value = shares_in_winning_outcome  # $1 per share if won, can be negative if short
        pnl = final_position_value - total_spent + total_received

        results.append({
            'wallet': wallet,
            'pnl': pnl,
            'total_spent': total_spent,
            'total_received': total_received,
            'final_shares': shares_in_winning_outcome,
            'yes_shares': yes_shares,
            'no_shares': no_shares,
            'num_big_trades': len(user_trade_list),
            'total_volume': total_spent + total_received
        })

    results.sort(key=lambda x: x['pnl'], reverse=True)
    return results


def main():
    # Maduro out by January 31, 2026
    condition_id = "0x580adc1327de9bf7c179ef5aaffa3377bb5cb252b7d6390b027172d43fd6f993"

    print(f"\n{'='*80}")
    print(f"ANALYZING BIG TRADES (>$1000)")
    print(f"Market: Maduro out by January 31, 2026?")
    print(f"Resolution: YES")
    print(f"{'='*80}\n")

    # Fetch big trades
    trades = fetch_big_trades(condition_id, min_cash=1000)

    if not trades:
        print("No trades found.")
        return

    # Show date range
    timestamps = [t['timestamp'] for t in trades]
    oldest = datetime.fromtimestamp(min(timestamps))
    newest = datetime.fromtimestamp(max(timestamps))

    print(f"Date range: {oldest} to {newest}")
    print(f"Time span: {(max(timestamps) - min(timestamps)) / 3600:.1f} hours\n")

    # Show some sample trades
    print(f"{'='*80}")
    print(f"SAMPLE BIG TRADES:")
    print(f"{'='*80}\n")
    print(f"{'Price':<10} {'Size':<15} {'Value ($)':<15} {'Side':<6} {'Outcome':<8} {'Date':<20}")
    print("-" * 90)

    for trade in sorted(trades, key=lambda x: x['size'] * x['price'], reverse=True)[:20]:
        dt = datetime.fromtimestamp(trade['timestamp'])
        value = trade['size'] * trade['price']
        print(f"{trade['price']:<10.4f} {trade['size']:<15,.0f} ${value:<14,.2f} {trade['side']:<6} {trade['outcome']:<8} {dt.strftime('%Y-%m-%d %H:%M:%S')}")

    # Calculate leaderboard
    print(f"\n{'='*80}")
    print(f"LEADERBOARD (Users with $1k+ Trades)")
    print(f"{'='*80}\n")

    leaderboard = calculate_leaderboard(trades, resolves_to="Yes")

    print(f"{'Rank':<6} {'Wallet':<44} {'P&L ($)':<15} {'Spent ($)':<15} {'Received ($)':<15} {'Final Shares':<15} {'# Big Trades'}")
    print("-" * 130)

    for i, user in enumerate(leaderboard[:30], 1):
        print(f"{i:<6} {user['wallet']:<44} ${user['pnl']:>13,.2f} ${user['total_spent']:>13,.2f} ${user['total_received']:>13,.2f} {user['final_shares']:>14,.0f} {user['num_big_trades']:>12}")

    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")

    winners = [u for u in leaderboard if u['pnl'] > 0]
    losers = [u for u in leaderboard if u['pnl'] < 0]

    print(f"Total users with big trades: {len(leaderboard)}")
    print(f"Winners: {len(winners)}")
    print(f"Losers: {len(losers)}")
    print(f"Total P&L (winners): ${sum(u['pnl'] for u in winners):,.2f}")
    print(f"Total P&L (losers): ${sum(u['pnl'] for u in losers):,.2f}")
    print(f"Net P&L: ${sum(u['pnl'] for u in leaderboard):,.2f}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
