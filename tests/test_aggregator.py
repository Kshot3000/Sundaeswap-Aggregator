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


if __name__ == "__main__":
    unittest.main()
