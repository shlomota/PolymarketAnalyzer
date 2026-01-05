#!/usr/bin/env python3
"""
Test if Polymarket API has a hard limit on pagination
"""

import requests
import json

condition_id = "0xbb8bfdef9052b2709557a6f8f28b23551e3134bfb86eca800211e2191703ee65"
base_url = "https://data-api.polymarket.com/trades"

# Test different offsets around 1000
test_offsets = [990, 1000, 1001, 1010, 1500, 2000]

print("Testing API pagination limits...")
print(f"{'='*100}\n")

results = {}

for offset in test_offsets:
    url = f"{base_url}?market={condition_id}&limit=5&offset={offset}"
    print(f"Fetching offset={offset}...")

    response = requests.get(url)
    response.raise_for_status()
    trades = response.json()

    if trades:
        # Get transaction hashes to compare
        tx_hashes = [t['transactionHash'] for t in trades]
        timestamps = [t['timestamp'] for t in trades]
        results[offset] = {
            'count': len(trades),
            'tx_hashes': tx_hashes,
            'first_timestamp': timestamps[0] if timestamps else None,
            'last_timestamp': timestamps[-1] if timestamps else None
        }
        print(f"  ✓ Got {len(trades)} trades")
        print(f"    First tx: {tx_hashes[0][:16]}...")
        print(f"    Last tx:  {tx_hashes[-1][:16]}...")
    else:
        results[offset] = {'count': 0, 'tx_hashes': [], 'first_timestamp': None, 'last_timestamp': None}
        print(f"  ✗ No trades returned")
    print()

# Compare results
print(f"{'='*100}\n")
print("COMPARISON:")
print(f"{'='*100}\n")

for i in range(len(test_offsets) - 1):
    offset1 = test_offsets[i]
    offset2 = test_offsets[i + 1]

    hashes1 = set(results[offset1]['tx_hashes'])
    hashes2 = set(results[offset2]['tx_hashes'])

    if hashes1 == hashes2 and len(hashes1) > 0:
        print(f"⚠️  offset={offset1} and offset={offset2} return IDENTICAL trades")
        print(f"    This suggests API limit at offset ~{offset1}")
    elif hashes1 & hashes2:  # Some overlap
        overlap = len(hashes1 & hashes2)
        print(f"ℹ️  offset={offset1} and offset={offset2} have {overlap}/{min(len(hashes1), len(hashes2))} overlapping trades")
    else:
        print(f"✓ offset={offset1} and offset={offset2} return DIFFERENT trades")
    print()

print(f"{'='*100}\n")
print("CONCLUSION:")
if results[1000]['tx_hashes'] == results[1001]['tx_hashes'] and len(results[1000]['tx_hashes']) > 0:
    print("⚠️  API appears to have a HARD LIMIT around offset=1000")
    print("    Pagination stops working beyond this point")
    print("\nThis means we can only access ~1000 most recent trades via this endpoint")
else:
    print("✓ No hard limit detected at offset=1000")
    print("  API pagination appears to be working normally")
