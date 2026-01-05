# The $400K Maduro Trade: How I Built a Polymarket Anomaly Detection Tool

## The Future is a Market

Prediction markets represent one of humanity's most fascinating experiments in collective intelligence. The concept is elegantly simple: allow people to bet real money on future events, and the resulting prices reveal what the crowd truly believes will happen. Unlike polls or expert forecasts, prediction markets harness a powerful economic force—the opportunity to profit from others' biases.

Here's the beautiful equilibrium at work: if a market says there's a 70% chance of an event, but you believe it's actually 90%, you can buy shares and profit when you're proven right. This financial incentive means that mispriced probabilities don't last long. Traders rush in to correct them, and the market price converges toward the actual probability. It's crowdsourced truth-finding with skin in the game.

This mechanism recently captured international attention in January 2025 when the U.S. executed a covert operation to extract Venezuelan leader Nicolás Maduro. Within hours, headlines appeared across major outlets:

- *"Someone made a huge profit predicting Maduro's capture. Here's what happened"*
- *"Was Someone Insider Trading Right Before Trump's Attack on Venezuela?"* ([The New Republic](https://newrepublic.com/post/204885/insider-trading-trump-attack-venezuela-maduro-polymarket))
- *"Suspicious bets on Maduro's removal raise eyebrows as user nets over US$400,000"*

One trader had made over $400,000 betting on Maduro's removal—apparently knowing something the market didn't. The trading pattern was striking: large positions entered days before the operation became public, at prices suggesting only a 7-15% probability of success.

Reading these headlines, I was fascinated: **How can we analyze these phenomena systematically? Can we build tools to detect unusual trading patterns and study information asymmetry in prediction markets?**

## The Problem: Polymarket's Limited Data Access

Polymarket's website offers impressive statistics—global leaderboards, category leaders, and market-level data. You can see who won the most on "Politics" this week. But there's a critical gap: **you can't see a leaderboard for a specific market question.**

Who were the top 10 traders on "Maduro out by January 31, 2026?" What were their average entry prices? How much did they stake? This granular, market-specific analysis isn't available on the platform.

Fortunately, Polymarket has a public API. Time to build something custom.

## The API Challenge: The 1,000 Trade Wall

According to the official Polymarket API documentation, the `/trades` endpoint should support offset values up to 10,000. In theory, you could paginate through 10,000+ trades per market. In practice? **The API hits a hard limit around offset=1,000.**

Here's what happens when you try to fetch beyond that limit:

```python
def fetch_all_trades(condition_id: str):
    """Attempt to fetch all trades - hits the 1000 offset wall"""
    base_url = "https://data-api.polymarket.com/trades"
    all_trades = []
    offset = 0
    limit = 500

    while offset < 10000:
        params = {
            "market": condition_id,
            "limit": limit,
            "offset": offset
        }

        response = requests.get(base_url, params=params)
        trades = response.json()

        if not trades:
            break

        all_trades.extend(trades)
        offset += limit

    return all_trades
```

Testing revealed that once offset exceeds ~1,000, the API returns duplicate data. You're stuck with roughly 1,500 unique trades—not nearly enough for comprehensive market analysis.

## The Solution: Filter by Trade Size

The breakthrough came from discovering two undocumented(?) parameters: `filterType` and `filterAmount`. These let you filter trades by cash value:

```python
def fetch_big_trades(condition_id: str, min_cash: int = 1000):
    """Fetch only trades above a certain dollar value"""
    base_url = "https://data-api.polymarket.com/trades"
    all_trades = []
    seen_hashes = set()  # Deduplication
    offset = 0
    limit = 500

    while offset < 10000:
        params = {
            "market": condition_id,
            "limit": limit,
            "offset": offset,
            "filterType": "CASH",      # Filter by cash value
            "filterAmount": min_cash    # Minimum trade value
        }

        response = requests.get(base_url, params=params)
        trades = response.json()

        if not trades:
            break

        # Deduplicate using transaction hash
        new_trades = []
        for trade in trades:
            tx_hash = trade.get('transactionHash')
            if tx_hash and tx_hash not in seen_hashes:
                seen_hashes.add(tx_hash)
                new_trades.append(trade)

        if not new_trades:  # All duplicates? We've hit the end
            break

        all_trades.extend(new_trades)
        offset += limit

    return all_trades
```

With a $1,000 minimum trade filter, I suddenly had access to **13.5 days of trading history** instead of just 2-3 hours. The "big money" traders—the ones who likely have conviction and information—became visible.

## Building the Leaderboard

The next challenge: calculating profit and loss (P&L) for each trader. Polymarket markets are binary—each share pays $1 if your outcome wins, $0 if it loses. Traders can BUY shares (going long) or SELL shares (going short).

Here's the P&L calculation:

```python
def calculate_leaderboard(trades, resolves_to="Yes"):
    """Calculate P&L for each trader"""
    from collections import defaultdict

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

        # Calculate final position value
        if resolves_to == 'Yes':
            final_value = yes_shares  # $1 per share
        else:
            final_value = no_shares

        # P&L = Final position value - money spent + money received
        pnl = final_value - total_spent + total_received

        results.append({
            'wallet': wallet,
            'pnl': pnl,
            'total_spent': total_spent,
            'total_received': total_received,
            'final_shares': final_value
        })

    results.sort(key=lambda x: x['pnl'], reverse=True)
    return results
```

**Critical insight:** Negative shares represent a short position (a liability), not a zero value. Early versions of my code capped negative shares at zero, which incorrectly showed massive profits for traders with large short positions. The market is zero-sum—all gains equal all losses (minus fees).

## Detecting Market Resolution

The final piece: automatically detecting which outcome won. Polymarket returns an `outcomePrices` field that shows final prices:

```python
# Parse market data
market_data = get_market_data(condition_id)
outcome_prices_raw = market_data.get('outcomePrices', [])

# API returns JSON string, need to parse
import json
outcome_prices = json.loads(outcome_prices_raw) if isinstance(outcome_prices_raw, str) else outcome_prices_raw

# ["1", "0"] means first outcome won
# ["0", "1"] means second outcome won
if outcome_prices[0] == "1":
    resolution = "Yes"
elif outcome_prices[1] == "1":
    resolution = "No"
```

With resolution detection in place, the leaderboard automatically shows the real winners—no guessing required.

## The Streamlit Dashboard

I wrapped everything in a Streamlit web app that lets you:
- **Search markets by name** (e.g., "Maduro", "Trump", "Venezuela")
- **Set minimum trade values** (focus on whales or include small traders)
- **View multiple leaderboards**: by P&L, by amount spent, and sample trades
- **Auto-detect resolution** with manual override option
- **Link directly to trader profiles** on Polymarket

The full source code is available on GitHub: [PolymarketAnalyzer](https://github.com/yourusername/PolymarketAnalyzer) *(update with your actual link)*

## The Maduro Market: A $400K Winner

Running the analyzer on "Maduro out by January 31, 2026?" revealed the suspected insider trader. This individual:
- Made over **$400,000 profit**
- Spent only ~$32,000 (buying at average price of $0.07)
- Appeared on Polymarket's global Politics leaderboard for the week
- Entered positions **days before** the U.S. operation became public

The timing is striking. While the rest of the market priced Maduro's removal at 7-15% probability, someone was quietly accumulating massive positions. Either extraordinary conviction or extraordinary information.

## Prediction Markets as Truth Machines

This investigation reveals something profound about prediction markets. Despite occasional disputes over resolution criteria, **there's often more consensus on betting outcomes than on Wikipedia articles or "fact-checks."**

When money is at stake, people become remarkably careful about truth. Biased or incorrect beliefs cost you. Accurate beliefs pay you. Over time, this creates a form of truth-finding that transcends political tribalism.

Could we leverage this property to battle disinformation? Imagine prediction markets for disputed factual claims:
- "COVID-19 originated from a lab leak" (resolves based on future evidence)
- "Crime rates increased in City X in 2024" (resolves based on official statistics)
- "Candidate Y's policy will reduce inflation" (resolves based on economic data)

The market prices wouldn't be perfect, but they might be more reliable than social media consensus or partisan news coverage.

**If you have ideas about using prediction markets to differentiate truth from falsehood, please reach out.** I'm genuinely curious whether this tool could help combat disinformation at scale.

## Building with Claude Code

A brief note on the development process: I built this entire analyzer in a few hours using **Claude Code**, Anthropic's AI-powered coding CLI. The experience was remarkable.

Claude Code can:
- **Access the internet** to fetch API documentation
- **Make live API calls** to test endpoints
- **Iterate rapidly** on bugs and edge cases
- **Write and refactor** across multiple files

The back-and-forth felt like pair programming with an expert who never gets tired. "The offset limit isn't working—add deduplication." Done in 30 seconds. "Parse the JSON string for outcomePrices." Fixed immediately. "Add automatic resolution detection." Implemented with tests.

For exploratory projects like this—where you're reverse-engineering an API, discovering edge cases, and building a UI—Claude Code shines. Highly recommended for rapid prototyping.

## Conclusion: Skin in the Game Creates Signal

Prediction markets work because they force people to put their money where their mouth is. Empty speculation becomes costly. Genuine insight becomes profitable. The result is a price signal that aggregates information from thousands of participants, weighted by confidence and capital.

The Maduro market demonstrates both the power and the peril of this system. Someone with privileged information made a fortune. But that same fortune serves as a red flag—a public signal that something unusual happened. Researchers, journalists, and regulators can investigate.

As prediction markets grow, tools like this leaderboard analyzer become essential. **Who's betting on what? When did they enter? What do unusual patterns suggest?**

The future is being priced right now. Let's build better tools to read those signals.

---

*Interested in prediction markets, trading analysis, or building with Claude Code? Connect with me on [Twitter/LinkedIn] or drop a comment below.*

---

**Code and Resources:**
- GitHub Repository: [PolymarketAnalyzer](https://github.com/yourusername/PolymarketAnalyzer)
- Polymarket API: [https://docs.polymarket.com](https://docs.polymarket.com)
- Streamlit Documentation: [https://docs.streamlit.io](https://docs.streamlit.io)
- Claude Code: [https://claude.com/claude-code](https://claude.com/claude-code)
