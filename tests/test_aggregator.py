"""Tests for the simulated SundaeSwap aggregator.

Run on bare stdlib python3:  python3 -m unittest discover -s tests -v
"""
import re
import subprocess
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aggregator  # noqa: E402

# Kyle's verified Cardano donation address (MEMORY.md, character-for-character)
DONATION = ("addr1q8hnl6vl5a6k3rw3n5g3jtte696zcl76kfatzv7gpswa9r0dj7fma"
            "6klq55y4ffm7tf0em09udnyhuk4ah92pl5x9jpqjae44v")
BECH32_CHARSET = set("qpzry9x8gf2tvdw0s3jn54khce6mua7l")


class QuoteMathTests(unittest.TestCase):
    def test_best_route_ada_usdc(self):
        quotes = aggregator.aggregate("ADA", "USDC", Decimal("1000"))
        best = quotes[0]
        # Minswap has the widest spread factor (0.998): 1000*.5*.998=.499k
        self.assertEqual(best["dex"], "Minswap")
        self.assertEqual(best["price"], Decimal("499.000"))
        self.assertEqual(best["fee"], Decimal("1.497"))
        self.assertEqual(best["net_out"], Decimal("497.503"))

    def test_sorted_descending_and_all_dexes(self):
        quotes = aggregator.aggregate("ADA", "USDC", Decimal("100"))
        nets = [q["net_out"] for q in quotes]
        self.assertEqual(nets, sorted(nets, reverse=True))
        self.assertEqual({q["dex"] for q in quotes}, set(aggregator.DEXES))

    def test_decimal_end_to_end_no_floats(self):
        for q in aggregator.aggregate("ADA", "USDC", Decimal("10")):
            for key in ("amount_in", "price", "fee", "net_out", "min_out"):
                self.assertIsInstance(q[key], Decimal, key)
            self.assertTrue(q["simulated"])

    def test_slippage_min_out(self):
        q = aggregator.fetch_quote("Minswap", "ADA", "USDC",
                                   Decimal("1000"), slippage_bps=100)
        # net 497.503 * (1 - 100/10000) = 497.503 * 0.99
        self.assertEqual(q["min_out"], Decimal("492.527970"))
        q0 = aggregator.fetch_quote("Minswap", "ADA", "USDC",
                                    Decimal("1000"), slippage_bps=0)
        self.assertEqual(q0["min_out"], q0["net_out"])

    def test_cardano_only_dexes(self):
        # Jupiter is a Solana aggregator; it must never reappear.
        self.assertNotIn("Jupiter", aggregator.DEXES)
        for dex in ("SundaeSwap", "Minswap", "WingRiders", "VyFinance"):
            self.assertIn(dex, aggregator.DEXES)


class ValidationTests(unittest.TestCase):
    def test_rejects_non_positive_and_non_finite(self):
        for bad in ("0", "-50", "NaN", "Infinity", "-Infinity"):
            with self.assertRaises(ValueError, msg=bad):
                aggregator.aggregate("ADA", "USDC", Decimal(bad))

    def test_rejects_same_token_case_insensitive(self):
        with self.assertRaises(ValueError):
            aggregator.aggregate("ada", "ADA", Decimal("100"))

    def test_rejects_bad_symbols_and_slippage(self):
        for args in [("", "USDC"), ("ADA", "  "), ("A DA", "USDC"),
                     ("ADA!", "USDC")]:
            with self.assertRaises(ValueError, msg=str(args)):
                aggregator.aggregate(args[0], args[1], Decimal("1"))
        for bps in (-1, 1001):
            with self.assertRaises(ValueError):
                aggregator.aggregate("ADA", "USDC", Decimal("1"),
                                     slippage_bps=bps)

    def test_cli_rejects_same_token_and_negative(self):
        for argv in (["--from", "ADA", "--to", "ADA", "--amount", "100"],
                     ["--from", "ADA", "--to", "USDC", "--amount", "-5"],
                     ["--from", "ADA", "--to", "USDC", "--amount", "abc"]):
            proc = subprocess.run(
                [sys.executable, str(ROOT / "aggregator.py"), *argv],
                capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2, argv)
            self.assertIn("error", (proc.stderr + proc.stdout).lower())

    def test_cli_output_is_labelled_simulated(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "aggregator.py"),
             "--from", "ADA", "--to", "USDC", "--amount", "1000"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("SIMULATED", proc.stdout)
        self.assertIn("Minswap", proc.stdout)
        self.assertIn("min received", proc.stdout)

    def test_fetch_quote_validates_like_aggregate(self):
        # fetch_quote used to compute blindly: same-token, negative and
        # NaN quotes came back as if real, an Infinity amount crashed
        # with decimal.InvalidOperation (not the ValueError contract),
        # and 99999 bps slippage returned a negative min_out.
        bad_calls = [
            (("Minswap", "ADA", "ADA", Decimal("100")), {}),
            (("Minswap", "ADA", "USDC", Decimal("-50")), {}),
            (("Minswap", "ADA", "USDC", Decimal("0")), {}),
            (("Minswap", "ADA", "USDC", Decimal("NaN")), {}),
            (("Minswap", "ADA", "USDC", Decimal("Infinity")), {}),
            (("Minswap", "ADA", "USDC", Decimal("100")),
             {"slippage_bps": 99999}),
            (("Minswap", "ADA", "USDC", Decimal("100")),
             {"slippage_bps": -500}),
        ]
        for args, kwargs in bad_calls:
            with self.assertRaises(ValueError, msg=str((args, kwargs))):
                aggregator.fetch_quote(*args, **kwargs)

    def test_fetch_quote_rejects_unknown_dex(self):
        # An unknown or mis-cased DEX used to get a 1.0 spread, which
        # out-quotes every real DEX in the list.
        for dex in ("FakeDEX", "minswap", "MINswap", "", "Sundae"):
            with self.assertRaises(ValueError, msg=dex):
                aggregator.fetch_quote(dex, "ADA", "USDC", Decimal("1000"))

    def test_fetch_quote_normalizes_tokens(self):
        # Lowercase symbols must find the ADA->USDC base rate, not the
        # generic fallback (the pre-normalization behaviour).
        q = aggregator.fetch_quote("Minswap", "ada", "usdc",
                                   Decimal("1000"))
        self.assertEqual(q["price"], Decimal("499.000"))
        self.assertEqual(q["from_token"], "ADA")
        self.assertEqual(q["to_token"], "USDC")

    def test_rejects_non_integer_slippage(self):
        # Floats poisoned the exact Decimal maths with binary noise
        # (33.3 bps -> a 28-digit min_out), a string crashed with an
        # uncaught TypeError, and True was silently read as 1 bp. The
        # CLI already enforces int via argparse; the library now does
        # the same, with ValueError.
        for bps in (50.5, 33.3, "50", True, Decimal("50")):
            with self.assertRaises(ValueError, msg=repr(bps)):
                aggregator.aggregate("ADA", "USDC", Decimal("1"),
                                     slippage_bps=bps)
            with self.assertRaises(ValueError, msg=repr(bps)):
                aggregator.fetch_quote("Minswap", "ADA", "USDC",
                                       Decimal("1"), slippage_bps=bps)

    def test_rejects_unicode_symbols(self):
        # str.isalnum() accepted these; the web UI's /^[A-Z0-9]+$/
        # rejects them. Both surfaces now apply the ASCII rule.
        for tok in ("ADÄ", "ＡＤＡ", "ADA²", "ADA①"):
            with self.assertRaises(ValueError, msg=tok):
                aggregator.aggregate(tok, "USDC", Decimal("1"))

    def test_cli_rejects_fractional_slippage(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "aggregator.py"),
             "--from", "ADA", "--to", "USDC", "--amount", "100",
             "--slippage-bps", "50.5"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)


class RepoHygieneTests(unittest.TestCase):
    def test_readme_flags_exist_in_cli(self):
        readme = (ROOT / "README.md").read_text()
        help_out = subprocess.run(
            [sys.executable, str(ROOT / "aggregator.py"), "--help"],
            capture_output=True, text=True).stdout
        for flag in sorted(set(re.findall(r"--[a-z][a-z\-]+", readme))):
            self.assertIn(flag, help_out, flag)
        self.assertIn("not live prices", readme.lower())
        self.assertIn("@kshot9000", readme)
        self.assertIn(DONATION, readme)

    def test_requirements_has_no_unused_deps(self):
        lines = [ln.strip() for ln in
                 (ROOT / "requirements.txt").read_text().splitlines()
                 if ln.strip() and not ln.strip().startswith("#")]
        self.assertEqual(lines, [])

    def test_donation_address_bech32_charset(self):
        payload = DONATION[len("addr1"):]
        self.assertTrue(set(payload) <= BECH32_CHARSET)

    def test_web_ui_shares_model_and_validates(self):
        html = (ROOT / "index.html").read_text()
        self.assertIn('name="viewport"', html)
        self.assertIn("Simulated quotes", html)
        self.assertNotIn("Jupiter", html)
        self.assertIn("computeQuotes", html)
        self.assertIn("must differ", html)
        self.assertIn("greater than zero", html)
        self.assertIn(DONATION, html)
        self.assertIn("@kshot9000", html)
        # The web spreads must match the Python model exactly.
        for dex, spread in aggregator.SPREADS.items():
            self.assertIn(f'"{dex}":{spread}', html, dex)

    def test_web_ui_integer_slippage_and_overflow_guard(self):
        html = (ROOT / "index.html").read_text()
        # Integer bps, matching the CLI's type=int and the library.
        self.assertIn("Number.isInteger", html)
        self.assertIn("whole number of basis points", html)
        # Huge amounts used to render Infinity min-received (ADA->USDC)
        # or NaN rows in arbitrary order (Inf - Inf on the generic
        # pair); the UI must refuse instead of rendering them.
        self.assertIn("too large to quote", html)


if __name__ == "__main__":
    unittest.main()
