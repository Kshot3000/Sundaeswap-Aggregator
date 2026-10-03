"""
SundaeSwap DEX Aggregator — SIMULATED quotes.

Aggregates *simulated* quotes from Cardano DEXs and selects the best
price. This tool does NOT fetch live prices: every rate below is a
fixed, illustrative model (see BASE_RATES / SPREADS) so the routing,
fee and slippage maths can be exercised offline. Do not use its output
as a real quote — check a live DEX before trading.
"""

import argparse
from decimal import Decimal, InvalidOperation
from typing import Dict, List

# Cardano DEXs only. (Jupiter, present in an earlier version, is a
# Solana aggregator and has no Cardano pools — removed.)
DEXES = ["SundaeSwap", "Minswap", "WingRiders", "VyFinance"]

# Simulated per-DEX spread factors applied to the base rate.
SPREADS = {
    "SundaeSwap": Decimal("0.995"),
    "Minswap": Decimal("0.998"),
    "WingRiders": Decimal("0.992"),
    "VyFinance": Decimal("0.996"),
}

# Simulated base rates: ADA->USDC, and a generic fallback pair rate.
# These are model constants, not market data.
BASE_RATES = {
    ("ADA", "USDC"): Decimal("0.5"),
}
DEFAULT_BASE_RATE = Decimal("2.0")

FEE_RATE = Decimal("0.003")  # 0.3% simulated swap fee
DEFAULT_SLIPPAGE_BPS = 50  # 0.5%
MAX_SLIPPAGE_BPS = 1000  # 10%


def normalize_token(token: str) -> str:
    return (token or "").strip().upper()


def validate_inputs(from_token: str, to_token: str, amount: Decimal,
                    slippage_bps: int = DEFAULT_SLIPPAGE_BPS) -> None:
    """Raise ValueError unless the trade inputs are sane."""
    if not from_token or not to_token:
        raise ValueError("token symbols must not be empty")
    for token in (from_token, to_token):
        if not token.isalnum():
            raise ValueError(f"invalid token symbol: {token!r}")
    if from_token == to_token:
        raise ValueError("from and to tokens must differ "
                           "(a same-token swap has no quote)")
    if not isinstance(amount, Decimal) or not amount.is_finite():
        raise ValueError("amount must be a finite number")
    if amount <= 0:
        raise ValueError("amount must be greater than zero")
    if not (0 <= slippage_bps <= MAX_SLIPPAGE_BPS):
        raise ValueError(
            f"slippage must be between 0 and {MAX_SLIPPAGE_BPS} bps")


def fetch_quote(dex: str, from_token: str, to_token: str,
                amount: Decimal,
                slippage_bps: int = DEFAULT_SLIPPAGE_BPS) -> Dict:
    """One simulated quote. All money values stay Decimal end-to-end."""
    base_rate = BASE_RATES.get((from_token, to_token), DEFAULT_BASE_RATE)
    spread = SPREADS.get(dex, Decimal("1"))
    price = amount * base_rate * spread
    fee = price * FEE_RATE
    net = price - fee
    min_out = net * (Decimal(10000 - slippage_bps) / Decimal(10000))
    return {
        "dex": dex,
        "from_token": from_token,
        "to_token": to_token,
        "amount_in": amount,
        "price": price,
        "fee": fee,
        "net_out": net,
        "min_out": min_out,
        "slippage_bps": slippage_bps,
        "simulated": True,
    }


def aggregate(from_token: str, to_token: str, amount: Decimal,
              slippage_bps: int = DEFAULT_SLIPPAGE_BPS) -> List[Dict]:
    from_token = normalize_token(from_token)
    to_token = normalize_token(to_token)
    validate_inputs(from_token, to_token, amount, slippage_bps)
    quotes = [fetch_quote(dex, from_token, to_token, amount, slippage_bps)
              for dex in DEXES]
    quotes.sort(key=lambda x: x["net_out"], reverse=True)
    return quotes


def _decimal_arg(text: str) -> Decimal:
    try:
        return Decimal(text)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"invalid amount: {text!r}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="DEX Aggregator (simulated quotes — not live prices)")
    parser.add_argument("--from", dest="from_token", required=True)
    parser.add_argument("--to", dest="to_token", required=True)
    parser.add_argument("--amount", type=_decimal_arg, required=True)
    parser.add_argument("--slippage-bps", type=int,
                        default=DEFAULT_SLIPPAGE_BPS,
                        help="slippage tolerance in basis points for the "
                             "minimum-received figure (default 50 = 0.5%%)")
    args = parser.parse_args(argv)

    try:
        quotes = aggregate(args.from_token, args.to_token, args.amount,
                           args.slippage_bps)
    except ValueError as exc:
        parser.error(str(exc))

    print("SIMULATED quotes — fixed model rates, not live market prices.")
    print(f"Quotes for {args.amount} {quotes[0]['from_token']} "
          f"-> {quotes[0]['to_token']}:")
    for q in quotes:
        print(f"{q['dex']}: net out {q['net_out']:.6f} {q['to_token']}  "
              f"fee {q['fee']:.6f}  min received {q['min_out']:.6f} "
              f"(@ {q['slippage_bps']} bps slippage)")
    best = quotes[0]
    print(f"\nBest route: {best['dex']} with {best['net_out']:.6f} "
          f"{best['to_token']} (simulated)")


if __name__ == "__main__":
    main()
