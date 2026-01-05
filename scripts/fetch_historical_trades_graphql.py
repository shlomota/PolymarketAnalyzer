#!/usr/bin/env python3
"""
Fetch historical trades using Polymarket's GraphQL subgraph
This bypasses the 1000-trade limit of the REST API
"""

import requests
import json
from datetime import datetime

# Goldsky-hosted Orderbook Subgraph (public, no API key needed)
SUBGRAPH_URL = "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/orderbook-subgraph/0.0.1/gn"


def fetch_trades_graphql(condition_id: str, limit: int = 1000, skip: int = 0):
    """
    Fetch trades using GraphQL subgraph (ordersMatchedEvents)
    """

    query = """
    query GetTrades($conditionId: String!, $first: Int!, $skip: Int!) {
      ordersMatchedEvents(
        where: { conditionId: $conditionId }
        first: $first
        skip: $skip
        orderBy: timestamp
        orderDirection: desc
      ) {
        id
        timestamp
        conditionId
        tokenId
        makerAssetId
        takerAssetId
        makerAmountFilled
        takerAmountFilled
        maker
        taker
        transactionHash
        blockNumber
      }
    }
    """

    variables = {
        "conditionId": condition_id.lower(),  # GraphQL uses lowercase
        "first": limit,
        "skip": skip
    }

    response = requests.post(
        SUBGRAPH_URL,
        json={"query": query, "variables": variables},
        headers={"Content-Type": "application/json"}
    )

    response.raise_for_status()
    data = response.json()

    if "errors" in data:
        print(f"GraphQL errors: {data['errors']}")
        return []

    return data.get("data", {}).get("ordersMatchedEvents", [])


def fetch_all_trades_graphql(condition_id: str):
    """
    Fetch ALL trades by paginating through GraphQL
    """
    all_trades = []
    skip = 0
    batch_size = 1000  # Max per query

    print(f"Fetching trades from GraphQL subgraph...")
    print(f"Condition ID: {condition_id}")
    print(f"{'='*80}\n")

    while True:
        print(f"Fetching batch (skip={skip}, limit={batch_size})...", end=" ", flush=True)

        trades = fetch_trades_graphql(condition_id, limit=batch_size, skip=skip)

        if not trades:
            print("No more trades.")
            break

        all_trades.extend(trades)
        print(f"✓ Got {len(trades)} trades (Total: {len(all_trades)})")

        if len(trades) < batch_size:
            # Last batch
            break

        skip += batch_size

    print(f"\n{'='*80}")
    print(f"✓ Fetched {len(all_trades)} total trades from subgraph\n")

    return all_trades


def analyze_price_ranges(trades):
    """Analyze price distribution to find mid-range trades"""

    if not trades:
        print("No trades to analyze")
        return

    # Calculate prices from maker/taker amounts
    # Price = takerAmount / makerAmount (or vice versa depending on direction)
    for trade in trades:
        maker_amt = float(trade['makerAmountFilled']) / 1e18  # Convert from wei
        taker_amt = float(trade['takerAmountFilled']) / 1e18  # Convert from wei

        # Price is the ratio (approximate - need to know which side is which)
        if maker_amt > 0:
            trade['price_float'] = taker_amt / maker_amt if taker_amt / maker_amt < 1 else maker_amt / taker_amt
        else:
            trade['price_float'] = 0

        trade['size_float'] = max(maker_amt, taker_amt)

    # Find mid-range trades (0.04 - 0.15)
    midrange_trades = [t for t in trades if 0.04 <= t.get('price_float', 0) <= 0.15]
    midrange_trades.sort(key=lambda x: x['size_float'], reverse=True)

    print(f"Total trades: {len(trades)}")
    print(f"Mid-range trades (0.04-0.15): {len(midrange_trades)}")
    print(f"\n{'='*100}\n")

    if midrange_trades:
        print("TOP 30 LARGEST MID-RANGE TRADES (0.04-0.15):")
        print(f"{'Price (est)':<12} {'Size':<15} {'Date':<20} {'Tx Hash':<20}")
        print("-" * 100)

        for trade in midrange_trades[:30]:
            dt = datetime.fromtimestamp(int(trade['timestamp']))
            print(f"{trade['price_float']:<12.4f} {trade['size_float']:<15,.0f} {dt.strftime('%Y-%m-%d %H:%M:%S'):<20} {trade['transactionHash'][:16]:<20}")
    else:
        print("No mid-range trades found in this dataset")

    # Show date range
    timestamps = [int(t['timestamp']) for t in trades]
    if timestamps:
        oldest = min(timestamps)
        newest = max(timestamps)
        oldest_dt = datetime.fromtimestamp(oldest)
        newest_dt = datetime.fromtimestamp(newest)
        days = (newest - oldest) / 86400

        print(f"\n{'='*100}\n")
        print(f"DATE RANGE:")
        print(f"  Oldest: {oldest_dt}")
        print(f"  Newest: {newest_dt}")
        print(f"  Span: {days:.1f} days")
        print(f"{'='*100}\n")


def main():
    # US forces in Venezuela by January 31st
    condition_id = "0xbb8bfdef9052b2709557a6f8f28b23551e3134bfb86eca800211e2191703ee65"

    trades = fetch_all_trades_graphql(condition_id)

    if trades:
        # Save to JSON for analysis
        with open('graphql_trades.json', 'w') as f:
            json.dump(trades, f, indent=2)
        print(f"✓ Saved trades to graphql_trades.json\n")

        analyze_price_ranges(trades)
    else:
        print("No trades found")


if __name__ == "__main__":
    main()
