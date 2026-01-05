#!/usr/bin/env python3
"""
Analyze Polymarket market to find biggest winners
Assumes market resolves to YES
"""

import requests
import json
import time
from collections import defaultdict
from typing import Dict, List, Any


def fetch_all_trades(condition_id: str) -> List[Dict[str, Any]]:
    """Fetch all trades for a given market condition ID"""
    base_url = "https://data-api.polymarket.com/trades"
    all_trades = []
    seen_hashes = set()  # Track transaction hashes to detect duplicates
    offset = 0
    limit = 500
    page = 1

    print(f"Fetching trades for condition ID: {condition_id}")
    print(f"{'='*60}")

    while True:
        url = f"{base_url}?market={condition_id}&limit={limit}&offset={offset}"

        print(f"Page {page}: Fetching trades {offset+1}-{offset+limit}...", end=" ", flush=True)

        response = requests.get(url)
        response.raise_for_status()
        trades = response.json()

        if not trades:
            print("No more trades found.")
            break

        # Check for duplicate transactions (API returns last page when offset exceeds total)
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
            # All trades in this batch are duplicates - we've reached the end
            print(f"All {len(trades)} trades are duplicates. Reached end of data.")
            print(f"{'='*60}")
            print(f"✓ Completed! Fetched all {len(all_trades)} trades across {page} pages.")
            break

        all_trades.extend(new_trades)

        if duplicate_count > 0:
            print(f"✓ Got {len(new_trades)} new trades ({duplicate_count} duplicates filtered) (Total: {len(all_trades)})")
        else:
            print(f"✓ Got {len(new_trades)} trades (Total: {len(all_trades)})")

        if len(trades) < limit:
            # Last page (got fewer trades than requested)
            print(f"{'='*60}")
            print(f"✓ Completed! Fetched all {len(all_trades)} trades across {page} pages.")
            break

        offset += limit
        page += 1

        # Small delay to avoid rate limiting
        time.sleep(0.1)

    return all_trades


def analyze_trades(trades: List[Dict[str, Any]], resolves_to: str = "Yes") -> List[Dict[str, Any]]:
    """
    Analyze trades to calculate user statistics

    Args:
        trades: List of trade objects
        resolves_to: Which outcome the market resolves to ("Yes" or "No")

    Returns:
        List of user statistics, sorted by P&L
    """
    # Group trades by user
    user_trades = defaultdict(list)
    for trade in trades:
        wallet = trade['proxyWallet']
        user_trades[wallet].append(trade)

    # Calculate statistics for each user
    results = []

    for wallet, user_trade_list in user_trades.items():
        # Track positions for Yes and No outcomes
        yes_shares = 0  # Net position in Yes shares
        no_shares = 0   # Net position in No shares
        total_spent = 0  # Total cost (money out)
        total_received = 0  # Total received from sells (money in)

        yes_buys = []  # Track (size, price) for average calc
        no_buys = []

        # Get user display name
        username = user_trade_list[0].get('name') or user_trade_list[0].get('pseudonym') or wallet[:10]

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
                    yes_buys.append((size, price))
                else:  # No
                    no_shares += size
                    no_buys.append((size, price))
            else:  # SELL
                revenue = size * price
                total_received += revenue

                if outcome == 'Yes':
                    yes_shares -= size
                else:  # No
                    no_shares -= size

        # Calculate average entry price for the winning outcome
        avg_entry_price = 0
        shares_in_winning_outcome = 0

        if resolves_to == 'Yes':
            shares_in_winning_outcome = yes_shares
            if yes_buys:
                total_yes_cost = sum(size * price for size, price in yes_buys)
                total_yes_shares = sum(size for size, _ in yes_buys)
                avg_entry_price = total_yes_cost / total_yes_shares if total_yes_shares > 0 else 0
        else:  # resolves to No
            shares_in_winning_outcome = no_shares
            if no_buys:
                total_no_cost = sum(size * price for size, price in no_buys)
                total_no_shares = sum(size for size, _ in no_buys)
                avg_entry_price = total_no_cost / total_no_shares if total_no_shares > 0 else 0

        # Calculate P&L assuming market resolves
        # At resolution: winning outcome worth $1/share, losing outcome worth $0/share
        # We need to account for positions in BOTH outcomes (can be long or short either)

        if resolves_to == 'Yes':
            # YES = $1, NO = $0
            # Final value = (YES position × $1) + (NO position × $0)
            final_position_value = yes_shares * 1 + no_shares * 0
            final_position_value = yes_shares
        else:
            # NO = $1, YES = $0
            # Final value = (YES position × $0) + (NO position × $1)
            final_position_value = yes_shares * 0 + no_shares * 1
            final_position_value = no_shares

        # P&L = final portfolio value - net cash spent
        # Net cash spent = money paid for buys - money received from sells
        pnl = final_position_value - total_spent + total_received

        # Calculate total amount bet (total capital deployed)
        total_bet = total_spent

        # ROI percentage
        roi = (pnl / total_bet * 100) if total_bet > 0 else 0

        results.append({
            'wallet': wallet,
            'username': username,
            'pnl': pnl,
            'total_bet': total_bet,
            'avg_entry_price': avg_entry_price,
            'avg_entry_pct': avg_entry_price * 100,
            'final_shares': shares_in_winning_outcome,
            'yes_shares': yes_shares,
            'no_shares': no_shares,
            'roi': roi,
            'num_trades': len(user_trade_list)
        })

    # Sort by P&L descending
    results.sort(key=lambda x: x['pnl'], reverse=True)

    return results


def main():
    # US forces in Venezuela by January 31st market
    condition_id = "0xbb8bfdef9052b2709557a6f8f28b23551e3134bfb86eca800211e2191703ee65"
    market_name = "US forces in Venezuela by January 31, 2026"

    print(f"\n{'='*80}")
    print(f"Analyzing: {market_name}")
    print(f"Assumption: Market resolves to YES")
    print(f"{'='*80}\n")

    # Fetch all trades
    trades = fetch_all_trades(condition_id)
    print(f"\nTotal trades fetched: {len(trades)}")

    # Show date range of trades
    if trades:
        from datetime import datetime
        timestamps = [t['timestamp'] for t in trades]
        oldest = min(timestamps)
        newest = max(timestamps)
        print(f"Date range: {datetime.fromtimestamp(oldest)} to {datetime.fromtimestamp(newest)}")
        print(f"Time span: {(newest - oldest) / 86400:.1f} days\n")
    else:
        print()

    # Analyze trades
    results = analyze_trades(trades, resolves_to="Yes")

    # Display top winners
    print(f"\n{'='*80}")
    print(f"TOP 20 WINNERS (assuming market resolves to YES)")
    print(f"{'='*80}\n")
    print(f"{'Rank':<6} {'Username':<25} {'P&L ($)':<15} {'Bet ($)':<15} {'ROI %':<10} {'Avg Entry %':<12} {'Final Shares':<12}")
    print("-" * 120)

    for i, user in enumerate(results[:20], 1):
        print(f"{i:<6} {user['username'][:24]:<25} ${user['pnl']:>13,.2f} ${user['total_bet']:>13,.2f} {user['roi']:>9.1f}% {user['avg_entry_pct']:>10.2f}% {user['final_shares']:>11,.0f}")

    # Export to JSON
    output_file = "market_analysis.json"
    with open(output_file, 'w') as f:
        json.dump({
            'market_name': market_name,
            'condition_id': condition_id,
            'resolves_to': 'Yes',
            'total_trades': len(trades),
            'total_users': len(results),
            'results': results
        }, f, indent=2)

    print(f"\n✓ Full results exported to: {output_file}")

    # Summary statistics
    total_volume = sum(abs(user['pnl']) for user in results)
    winners = [u for u in results if u['pnl'] > 0]
    losers = [u for u in results if u['pnl'] < 0]

    print(f"\n{'='*80}")
    print(f"SUMMARY STATISTICS")
    print(f"{'='*80}")
    print(f"Total users: {len(results)}")
    print(f"Winners: {len(winners)}")
    print(f"Losers: {len(losers)}")
    total_pnl_winners = sum(u['pnl'] for u in winners)
    total_pnl_losers = sum(u['pnl'] for u in losers)
    net_pnl = total_pnl_winners + total_pnl_losers
    print(f"Total P&L (winners): ${total_pnl_winners:,.2f}")
    print(f"Total P&L (losers): ${total_pnl_losers:,.2f}")
    print(f"Net P&L (should be ~$0 for zero-sum): ${net_pnl:,.2f}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
