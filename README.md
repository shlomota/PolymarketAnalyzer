# Polymarket Leaderboard Analyzer

Streamlit app to analyze big trades and top performers on Polymarket markets.

## Features

- 🔍 **Search markets by name** or enter condition ID directly
- 💰 **Filter by minimum trade value** (default $1,000)
- 📊 **Multiple leaderboards**:
  - By total P&L (profit/loss)
  - By total amount spent
- 📈 **View sample big trades** with timestamps and prices
- 🔗 **Direct links to trader profiles** on Polymarket
- 📅 **Date range and statistics** for trade activity

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Run the Streamlit app
streamlit run streamlit_app.py
```

The app will open in your browser at `http://localhost:8501`

## How to Use

1. **Search for a market**:
   - Use "Search by Name" to find markets (e.g., "Maduro", "Venezuela")
   - Or paste a Condition ID directly if you have it

2. **Set filters**:
   - Minimum trade value (default $1,000)
   - Assumed resolution (Yes or No)

3. **Click "Analyze"** to see:
   - Leaderboard of top traders
   - Total gains and losses
   - Sample big trades
   - Direct links to trader profiles

## Finding Condition IDs

Condition IDs are the unique identifiers for markets on Polymarket:

- **From URL**: Look at market URL: `polymarket.com/event/slug` → fetch via API
- **From browser**: Open DevTools → Network tab → look for API calls
- **Or just use the name search!** The app will find it for you

## Example Markets

Try these searches:
- "Maduro out by January 31, 2026"
- "US forces in Venezuela"
- "Trump" (for Trump-related markets)

## Profile Links

Trader profiles link to: `https://polymarket.com/@{wallet_address}`

## Data Limitations

- API returns trades with cash value >= filter amount
- Historical data may be limited (typically last 10-14 days for $1k+ trades)
- For full historical analysis, lower the minimum trade value
