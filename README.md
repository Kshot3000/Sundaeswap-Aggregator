# SundaeSwap DEX Aggregator — Simulated Quotes

A lightweight **simulated** DEX aggregator for Cardano that compares
modelled quotes across SundaeSwap, Minswap, WingRiders, and VyFinance
to demonstrate best-price routing, fee estimation, and slippage
protection.

> ⚠️ **These are not live prices.** Every rate comes from fixed model
> constants in `aggregator.py` (`BASE_RATES` / `SPREADS`) so the maths
> can be exercised offline. Never trade on this output — check a live
> DEX for a real quote.

## Features
- Simulated quote aggregation from multiple Cardano DEXs
- Best price routing over the simulated quotes
- Fee estimation (0.3% simulated swap fee) and a minimum-received
  figure from a configurable slippage tolerance (`--slippage-bps`)
- Input validation on every surface (CLI, library functions, and web
  UI): positive finite amounts, distinct ASCII token symbols, integer
  slippage within 0–1000 bps — a single-quote `fetch_quote` call is
  validated exactly like a full `aggregate`, including the DEX name
- Simple CLI and web UI sharing the same model

## Usage
```bash
python aggregator.py --from ADA --to USDC --amount 1000
python aggregator.py --from ADA --to USDC --amount 1000 --slippage-bps 100
```
No third-party packages are needed — the CLI runs on the Python
standard library alone (see `requirements.txt`).

## Web UI
Open `index.html` in a browser for interactive simulated quotes.

## Limitations
- Quotes are simulated from fixed constants; no DEX or price API is
  called, in the CLI or the web UI.
- Only ADA→USDC has its own model rate; every other pair uses the
  generic fallback rate. Neither is market data.
- The web UI computes in floating point and refuses amounts whose
  quote would overflow it; the CLI's Decimal maths has no such limit.

## Tests
```bash
python3 -m unittest discover -s tests -v
```
Covers the quote maths (exact `Decimal` end-to-end), validation,
slippage/min-received, the Cardano-only DEX list, CLI flags matching
this README, and the web UI's shared quote logic.

## Donate
Cardano donation address:
`addr1q8hnl6vl5a6k3rw3n5g3jtte696zcl76kfatzv7gpswa9r0dj7fma6klq55y4ffm7tf0em09udnyhuk4ah92pl5x9jpqjae44v`

Built by [@kshot9000](https://x.com/kshot9000) · [github.com/Kshot3000](https://github.com/Kshot3000)

## License
MIT
