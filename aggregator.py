"""
SundaeSwap DEX Aggregator
Aggregates quotes from multiple Cardano DEXs and selects best price.
"""

import argparse
from decimal import Decimal
from typing import List, Dict

# Mock DEX adapters - replace with real API calls
DEXES = ["SundaeSwap", "Minswap", "WingRiders", "Jupiter"]

def fetch_quote(dex: str, from_token: str, to_token: str, amount: Decimal) -> Dict:
    # Mock pricing with small random variation
    base_rate = Decimal("0.5") if from_token == "ADA" and to_token == "USDC" else Decimal("2.0")
    # Simulate DEX spread
    spread = {
        "SundaeSwap": Decimal("0.995"),
        "Minswap": Decimal("0.998"),
        "WingRiders": Decimal("0.992"),
        "Jupiter": Decimal("0.997"),
    }.get(dex, Decimal("1"))
    price = amount * base_rate * spread
    fee = price * Decimal("0.003")
    net = price - fee
    return {
        "dex": dex,
        "from_token": from_token,
        "to_token": to_token,
        "amount_in": float(amount),
        "price": float(price),
        "fee": float(fee),
        "net_out": float(net),
    }

def aggregate(from_token: str, to_token: str, amount: Decimal) -> List[Dict]:
    quotes = []
    for dex in DEXES:
        q = fetch_quote(dex, from_token, to_token, amount)
        quotes.append(q)
    # Sort by net_out descending
    quotes.sort(key=lambda x: x["net_out"], reverse=True)
    return quotes

def main():
    parser = argparse.ArgumentParser(description="DEX Aggregator")
    parser.add_argument("--from", dest="from_token", required=True)
    parser.add_argument("--to", dest="to_token", required=True)
    parser.add_argument("--amount", type=Decimal, required=True)
    args = parser.parse_args()

    quotes = aggregate(args.from_token, args.to_token, args.amount)
    print(f"Quotes for {args.amount} {args.from_token} -> {args.to_token}:")
    for q in quotes:
        print(f"{q['dex']}: net out {q['net_out']:.6f} {q['to_token']}  fee {q['fee']:.6f}")
    best = quotes[0]
    print(f"\nBest route: {best['dex']} with {best['net_out']:.6f} {best['to_token']}")

if __name__ == "__main__":
    main()
