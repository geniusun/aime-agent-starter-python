#!/usr/bin/env python3
"""
AIME Trading Agent

Fetches active markets, applies a strategy, and places trades in a loop.

Usage:
    python agent.py
    python agent.py --strategy momentum --amount 10 --interval 120
"""

import argparse
import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv

import strategies

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_URL = os.getenv("AIME_API_URL", "https://backend-production-3dc9.up.railway.app/api/v1")
API_KEY = os.getenv("AIME_API_KEY", "")

STRATEGY_MAP = {
    "contrarian": strategies.contrarian,
    "momentum": strategies.momentum,
    "random_walker": strategies.random_walker,
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("aime-agent")

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def api_get(path, params=None, auth=False):
    """GET request to the AIME API."""
    headers = {"X-API-Key": API_KEY} if auth else {}
    resp = requests.get(f"{API_URL}{path}", params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def api_post(path, body, auth=True):
    """POST request to the AIME API."""
    headers = {"X-API-Key": API_KEY} if auth else {}
    resp = requests.post(f"{API_URL}{path}", json=body, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_markets(limit=20):
    """Return a list of active markets."""
    data = api_get("/markets", params={"status": "active", "limit": limit})
    # Handle both {markets: [...]} and [{...}] response shapes
    if isinstance(data, list):
        return data
    return data.get("markets") or data.get("data") or []


def get_balance():
    """Return the agent's current balance."""
    data = api_get("/balance", auth=True)
    if isinstance(data, dict):
        return data.get("balance") or data.get("data", {}).get("balance")
    return data


def get_positions():
    """Return the agent's open positions."""
    data = api_get("/positions", auth=True)
    if isinstance(data, list):
        return data
    return data.get("positions") or data.get("data") or []


def place_trade(market_id, position, amount, reasoning, confidence):
    """Place a trade on a market. Returns the API response."""
    body = {
        "position": position,
        "amount": amount,
        "reasoning": reasoning,
        "confidence": confidence,
    }
    return api_post(f"/markets/{market_id}/trade", body)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def run_once(strategy_fn, amount):
    """Run one cycle: fetch markets, evaluate, trade."""
    log.info("Fetching active markets...")
    markets = fetch_markets()
    log.info("Found %d active markets", len(markets))

    if not markets:
        log.info("No active markets. Waiting for next cycle.")
        return

    # Show balance
    try:
        balance = get_balance()
        log.info("Current balance: %s", balance)
    except Exception as e:
        log.warning("Could not fetch balance: %s", e)

    trades_made = 0
    for market in markets:
        market_id = market.get("id")
        title = market.get("title", "???")
        yes_price = market.get("yes_price", "?")

        log.info("  Market: %s (YES: %s)", title[:60], yes_price)

        # Ask the strategy what to do
        signal = strategy_fn(market, amount=amount)

        if signal is None:
            log.info("    -> Skip (no signal)")
            continue

        # Place the trade
        try:
            result = place_trade(
                market_id=market_id,
                position=signal["position"],
                amount=signal["amount"],
                reasoning=signal["reasoning"],
                confidence=signal["confidence"],
            )
            log.info(
                "    -> TRADE %s $%.1f (confidence: %.0f%%) — %s",
                signal["position"],
                signal["amount"],
                signal["confidence"] * 100,
                result,
            )
            trades_made += 1
        except requests.HTTPError as e:
            log.error("    -> Trade failed: %s %s", e.response.status_code, e.response.text)
        except Exception as e:
            log.error("    -> Trade failed: %s", e)

    log.info("Cycle complete. Placed %d trades.", trades_made)


def main():
    parser = argparse.ArgumentParser(description="AIME trading agent")
    parser.add_argument(
        "--strategy",
        choices=list(STRATEGY_MAP.keys()),
        default="contrarian",
        help="Trading strategy (default: contrarian)",
    )
    parser.add_argument("--amount", type=float, default=5.0, help="Trade size in dollars (default: 5.0)")
    parser.add_argument("--interval", type=int, default=60, help="Seconds between cycles (default: 60)")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()

    if not API_KEY:
        print("Error: AIME_API_KEY not set. Run register.py first, then add the key to .env")
        sys.exit(1)

    strategy_fn = STRATEGY_MAP[args.strategy]
    log.info("Starting AIME agent — strategy: %s, amount: $%.1f, interval: %ds", args.strategy, args.amount, args.interval)

    if args.once:
        run_once(strategy_fn, args.amount)
        return

    # Continuous loop
    while True:
        try:
            run_once(strategy_fn, args.amount)
        except KeyboardInterrupt:
            log.info("Shutting down.")
            break
        except Exception as e:
            log.error("Cycle error: %s", e)

        log.info("Sleeping %ds until next cycle...", args.interval)
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            log.info("Shutting down.")
            break


if __name__ == "__main__":
    main()
