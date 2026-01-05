#!/usr/bin/env python3
"""
Polymarket Leaderboard App
"""

import streamlit as st
import requests
from datetime import datetime
from collections import defaultdict
import pandas as pd
import json


def search_markets(query: str):
    """Search for markets by name using public search API"""
    url = "https://gamma-api.polymarket.com/public-search"
    params = {
        "q": query,  # Parameter is 'q' not 'query'
        "limit": 20
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Extract markets from events
        markets = []
        events = data.get('events', [])

        for event in events:
            event_markets = event.get('markets', [])
            for market in event_markets:
                # Add volume from event level if not in market
                if 'volume' not in market and 'volume' in event:
                    market['volume'] = event['volume']
                markets.append(market)

        # Filter to only valid markets with required fields
        valid_markets = [
            m for m in markets
            if 'conditionId' in m and 'question' in m
        ]

        return valid_markets

    except Exception as e:
        st.error(f"Error searching markets: {e}")
        return []


def get_market_by_condition_id(condition_id: str):
    """Get market details by condition ID - simplified version"""
    # The gamma API doesn't support direct lookup by condition ID
    # Return None so user knows to use search for resolution detection
    return None


def fetch_big_trades(condition_id: str, min_cash: int = 1000):
    """Fetch trades with cash value >= min_cash"""
    base_url = "https://data-api.polymarket.com/trades"
    all_trades = []
    seen_hashes = set()
    offset = 0
    limit = 500  # Max results per request

    progress_bar = st.progress(0)
    status_text = st.empty()

    # API has hard limit around offset=1000, but we'll try up to 10000 and stop on duplicates
    while offset < 10000:
        params = {
            "market": condition_id,
            "limit": limit,
            "offset": offset,
            "filterType": "CASH",
            "filterAmount": min_cash
        }

        status_text.text(f"Fetching trades... offset={offset}")

        try:
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            trades = response.json()
        except Exception as e:
            st.error(f"Error fetching trades: {e}")
            break

        if not trades:
            break

        # Deduplicate
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
        progress = min(offset / 10000, 1.0)
        progress_bar.progress(progress)

    progress_bar.empty()
    status_text.empty()

    # Show final stats
    if all_trades:
        st.info(f"Fetched {len(all_trades)} unique trades after deduplication (checked {offset} records)")

    return all_trades


def calculate_leaderboard(trades, resolves_to="Yes"):
    """Calculate P&L leaderboard"""
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
        total_shares_bought = 0  # Track total shares bought for avg price calculation

        # Get username from first trade (name or pseudonym)
        # Check for both existence and non-empty string
        name = user_trade_list[0].get('name', '').strip()
        pseudonym = user_trade_list[0].get('pseudonym', '').strip()
        username = name or pseudonym or None

        # Get first trade timestamp for profile URL
        first_trade_timestamp = user_trade_list[0]['timestamp']

        for trade in user_trade_list:
            size = trade['size']
            price = trade['price']
            side = trade['side']
            outcome = trade['outcome']

            if side == 'BUY':
                cost = size * price
                total_spent += cost
                total_shares_bought += size  # Track shares bought
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

        final_position_value = shares_in_winning_outcome
        pnl = final_position_value - total_spent + total_received

        # Calculate average purchase price
        avg_purchase_price = (total_spent / total_shares_bought) if total_shares_bought > 0 else 0

        results.append({
            'wallet': wallet,
            'username': username,
            'timestamp': first_trade_timestamp,
            'pnl': pnl,
            'total_spent': total_spent,
            'total_received': total_received,
            'final_shares': shares_in_winning_outcome,
            'num_big_trades': len(user_trade_list),
            'total_volume': total_spent + total_received,
            'avg_purchase_price': avg_purchase_price
        })

    return results


def get_profile_url(wallet: str, timestamp: int = None):
    """Generate Polymarket profile URL with activity tab"""
    # Simple URL without timestamp (timestamp format doesn't work reliably)
    return f"https://polymarket.com/@{wallet}?tab=activity"


def main():
    st.set_page_config(
        page_title="Polymarket Leaderboard",
        page_icon="polymarket_logo.png",
        layout="wide"
    )

    # Custom CSS for wider sidebar
    st.markdown("""
        <style>
        [data-testid="stSidebar"][aria-expanded="true"] {
            min-width: 400px;
            max-width: 400px;
        }
        </style>
    """, unsafe_allow_html=True)

    # Header with logo
    col1, col2 = st.columns([1, 12])
    with col1:
        st.image("polymarket_logo.png", width=80)
    with col2:
        st.title("Polymarket Trading Leaderboard")

    st.subheader("Analyze big trades and top performers on any Polymarket market")

    # Sidebar for inputs
    st.sidebar.header("Settings")

    # Market input
    st.sidebar.subheader("Select Market")
    input_method = st.sidebar.radio(
        "Input method:",
        ["Search by Name", "Enter Condition ID"]
    )

    condition_id = None
    market_name = None

    if input_method == "Search by Name":
        search_query = st.sidebar.text_input(
            "Market name:",
            placeholder="e.g., Maduro out by January 31"
        )

        if search_query:
            with st.spinner("Searching markets..."):
                markets = search_markets(search_query)

            if markets:
                # Sort markets by volume (descending)
                markets_sorted = sorted(markets, key=lambda x: float(x.get('volume', 0)) if x.get('volume') else 0, reverse=True)

                # Create selection dropdown
                market_options = {}
                market_volumes = {}  # Store volumes separately
                for m in markets_sorted[:10]:
                    vol = m.get('volume', 0)
                    # Convert volume to float if it's a string
                    try:
                        vol_num = float(vol) if vol else 0
                        vol_str = f"${vol_num:,.0f}"
                    except (ValueError, TypeError):
                        vol_num = 0
                        vol_str = str(vol)

                    key = f"{m['question']} ({vol_str} volume)"
                    market_options[key] = m['conditionId']
                    market_volumes[m['conditionId']] = vol_num

                selected = st.sidebar.selectbox(
                    "Select market:",
                    options=list(market_options.keys())
                )

                if selected:
                    condition_id = market_options[selected]
                    market_name = selected.split(' (')[0]

                    # Find and store the full market data
                    selected_market = next((m for m in markets if m['conditionId'] == condition_id), None)
                    if selected_market:
                        st.session_state.selected_market_data = selected_market
                        st.session_state.selected_market_volume = market_volumes.get(condition_id, 0)
            else:
                st.sidebar.warning("No markets found. Try a different search term.")

    else:  # Enter Condition ID
        condition_id = st.sidebar.text_input(
            "Condition ID:",
            placeholder="0x..."
        )

        if condition_id:
            # Note: Direct condition ID entry doesn't fetch market data
            # Use search by name for automatic resolution detection
            market_name = None
            st.sidebar.info("💡 Use 'Search by Name' for automatic resolution detection")

    # Filter settings
    st.sidebar.subheader("Filter Settings")
    min_trade_value = st.sidebar.number_input(
        "Minimum trade value ($):",
        min_value=100,
        max_value=100000,
        value=1000,
        step=100
    )

    # Try to detect actual resolution
    actual_resolution = None

    if 'selected_market_data' in st.session_state:
        market_data = st.session_state.selected_market_data
        outcome_prices_raw = market_data.get('outcomePrices', [])

        # Parse if it's a JSON string
        outcome_prices = outcome_prices_raw
        if isinstance(outcome_prices_raw, str):
            try:
                outcome_prices = json.loads(outcome_prices_raw)
            except:
                outcome_prices = []

        # Detect resolution from outcomePrices: "1" or 1 means that outcome won
        if isinstance(outcome_prices, list) and len(outcome_prices) >= 2:
            if str(outcome_prices[0]) == "1":
                actual_resolution = "Yes"
            elif str(outcome_prices[1]) == "1":
                actual_resolution = "No"

    # Determine default index for selectbox
    default_index = 0
    if actual_resolution == "No":
        default_index = 1

    if actual_resolution:
        st.sidebar.success(f"✓ Market resolved to: **{actual_resolution}**")
    elif condition_id and 'selected_market_data' not in st.session_state:
        st.sidebar.info("💡 Use 'Search by Name' for auto-resolution detection")

    # Always show selectbox to allow user override
    resolution = st.sidebar.selectbox(
        "Select outcome for analysis:",
        options=["Yes", "No"],
        index=default_index
    )

    # Analyze button
    analyze_button = st.sidebar.button("🔍 Analyze", type="primary", use_container_width=True)

    # Main content
    if analyze_button and condition_id:
        st.header(f"Market: {market_name or 'Unknown'}")
        st.code(f"Condition ID: {condition_id}", language=None)

        # Fetch trades
        with st.spinner(f"Fetching trades over ${min_trade_value:,.0f}..."):
            trades = fetch_big_trades(condition_id, min_cash=min_trade_value)

        if not trades:
            st.warning("No trades found with the specified criteria.")
            return

        # Calculate leaderboard
        with st.spinner("Calculating leaderboard..."):
            leaderboard = calculate_leaderboard(trades, resolves_to=resolution)

        # Summary stats
        st.subheader("📈 Summary Statistics")

        # Calculate metrics
        timestamps = [t['timestamp'] for t in trades]
        time_span_days = (max(timestamps) - min(timestamps)) / 86400

        # Get market volume from selected market data (if available)
        market_volume = "N/A"
        if 'selected_market_volume' in st.session_state:
            market_volume = f"${st.session_state.selected_market_volume:,.0f}"

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Time Span", f"{time_span_days:.1f} days")
        with col2:
            st.metric("Trades Analyzed", f"{len(trades):,}")
        with col3:
            st.metric(f"Users (>${min_trade_value:,})", len(leaderboard))
        with col4:
            st.metric("Market Volume", market_volume)

        # Tabs for different views
        tab1, tab2, tab3 = st.tabs(["💰 By Total Gain", "💵 By Total Spent", "📊 Sample Trades"])

        with tab1:
            st.subheader("Leaderboard by Total Gain (P&L)")

            # Sort by P&L
            leaderboard_pnl = sorted(leaderboard, key=lambda x: x['pnl'], reverse=True)

            # Create DataFrame
            df_pnl = pd.DataFrame([
                {
                    'Rank': i + 1,
                    'User': u['username'] if u['username'] else (u['wallet'][:10] + '...'),
                    'Full Wallet': u['wallet'],
                    'P&L ($)': f"${u['pnl']:,.2f}",
                    'Avg Price': f"${u['avg_purchase_price']:.4f}",
                    'Spent ($)': f"${u['total_spent']:,.2f}",
                    'Received ($)': f"${u['total_received']:,.2f}",
                    'Final Shares': f"{u['final_shares']:,.0f}",
                    '# Trades': u['num_big_trades'],
                    'Profile': get_profile_url(u['wallet'], u['timestamp'])
                }
                for i, u in enumerate(leaderboard_pnl[:50])
            ])

            # Display with clickable links
            st.dataframe(
                df_pnl,
                column_config={
                    "Profile": st.column_config.LinkColumn("Profile Link"),
                    "Full Wallet": st.column_config.TextColumn("Full Wallet Address")
                },
                hide_index=True,
                use_container_width=True
            )

        with tab2:
            st.subheader("Leaderboard by Total Amount Spent")

            # Sort by total spent
            leaderboard_spent = sorted(leaderboard, key=lambda x: x['total_spent'], reverse=True)

            # Create DataFrame
            df_spent = pd.DataFrame([
                {
                    'Rank': i + 1,
                    'User': u['username'] if u['username'] else (u['wallet'][:10] + '...'),
                    'Full Wallet': u['wallet'],
                    'Spent ($)': f"${u['total_spent']:,.2f}",
                    'Avg Price': f"${u['avg_purchase_price']:.4f}",
                    'P&L ($)': f"${u['pnl']:,.2f}",
                    'ROI (%)': f"{(u['pnl'] / u['total_spent'] * 100) if u['total_spent'] > 0 else 0:.1f}%",
                    'Final Shares': f"{u['final_shares']:,.0f}",
                    '# Trades': u['num_big_trades'],
                    'Profile': get_profile_url(u['wallet'], u['timestamp'])
                }
                for i, u in enumerate(leaderboard_spent[:50])
            ])

            st.dataframe(
                df_spent,
                column_config={
                    "Profile": st.column_config.LinkColumn("Profile Link"),
                    "Full Wallet": st.column_config.TextColumn("Full Wallet Address")
                },
                hide_index=True,
                use_container_width=True
            )

        with tab3:
            st.subheader("Sample Big Trades")

            # Show largest trades by dollar value
            trades_sorted = sorted(trades, key=lambda x: x['size'] * x['price'], reverse=True)

            df_trades = pd.DataFrame([
                {
                    'Price': f"{t['price']:.4f}",
                    'Size': f"{t['size']:,.0f}",
                    'Value ($)': f"${t['size'] * t['price']:,.2f}",
                    'Side': t['side'],
                    'Outcome': t['outcome'],
                    'Date': datetime.fromtimestamp(t['timestamp']).strftime('%Y-%m-%d %H:%M'),
                    'Trader': (t.get('name', '').strip() or t.get('pseudonym', '').strip() or (t['proxyWallet'][:10] + '...')),
                    'Wallet': t['proxyWallet'],
                    'Profile': get_profile_url(t['proxyWallet'], t['timestamp'])
                }
                for t in trades_sorted[:50]
            ])

            st.dataframe(
                df_trades,
                column_config={
                    "Profile": st.column_config.LinkColumn("Trader Profile")
                },
                hide_index=True,
                use_container_width=True
            )

    elif not condition_id:
        # Instructions
        st.info("👈 Use the sidebar to search for a market or enter a Condition ID")

        st.markdown("""
        ### How to use:

        1. **Search by Name**: Enter keywords from the market question (e.g., "Maduro", "Venezuela")
        2. **Or enter Condition ID**: If you have the exact condition ID (0x...), enter it directly
        3. **Set minimum trade value**: Filter for trades above a certain dollar amount (default $1,000)
        4. **Choose resolution**: Select whether you assume the market resolves to "Yes" or "No"
        5. **Click Analyze**: View the leaderboard and trade statistics

        ### Finding Condition IDs:

        You can find condition IDs by:
        - Inspecting the market page on Polymarket
        - Using the browser developer tools (Network tab)
        - Or just use the name search feature above!

        ### Example Markets:

        Try searching for:
        - "Maduro out by January 31"
        - "US forces in Venezuela"
        - Any current trending market
        """)


if __name__ == "__main__":
    main()
