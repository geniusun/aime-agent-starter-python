"""
Trading strategies for the AIME prediction market.

Each strategy function takes a market dict and returns either:
  - A trade dict: {"position": "YES"|"NO", "amount": float, "reasoning": str, "confidence": float}
  - None to skip the market

Market dict fields (from API):
  - id, title, description
  - yes_price (0.0-1.0), no_price (0.0-1.0)
  - volume, status
"""

import random


def contrarian(market, amount=5.0):
    """
    Bet against the crowd.

    When the market is heavily skewed one way, bet the other.
    Buy YES when price < 0.3 (crowd says unlikely, we disagree).
    Buy NO when price > 0.7 (crowd says likely, we disagree).
    Skip when price is near 0.5 (no clear mispricing).
    """
    yes_price = market.get("yes_price", 0.5)
    title = market.get("title", "Unknown")

    if yes_price < 0.30:
        confidence = 1.0 - yes_price  # more confident when price is lower
        return {
            "position": "YES",
            "amount": amount,
            "reasoning": f"Contrarian: '{title}' YES price at {yes_price:.2f} looks undervalued. Market may be overreacting to the downside.",
            "confidence": round(confidence, 2),
        }

    if yes_price > 0.70:
        confidence = yes_price  # more confident when price is higher
        return {
            "position": "NO",
            "amount": amount,
            "reasoning": f"Contrarian: '{title}' YES price at {yes_price:.2f} looks overvalued. Market may be overreacting to the upside.",
            "confidence": round(confidence, 2),
        }

    # Price is in the 0.3-0.7 range — no strong signal.
    return None


def momentum(market, amount=5.0):
    """
    Follow the crowd.

    If the market leans one way, ride the trend.
    Buy YES when price > 0.55 (crowd says likely, we agree).
    Buy NO when price < 0.45 (crowd says unlikely, we agree).
    Skip when price is near 0.5 (no clear trend).
    """
    yes_price = market.get("yes_price", 0.5)
    title = market.get("title", "Unknown")

    if yes_price > 0.55:
        confidence = yes_price
        return {
            "position": "YES",
            "amount": amount,
            "reasoning": f"Momentum: '{title}' trending YES at {yes_price:.2f}. Following the crowd consensus.",
            "confidence": round(confidence, 2),
        }

    if yes_price < 0.45:
        confidence = 1.0 - yes_price
        return {
            "position": "NO",
            "amount": amount,
            "reasoning": f"Momentum: '{title}' trending NO at {yes_price:.2f}. Following the crowd consensus.",
            "confidence": round(confidence, 2),
        }

    return None


def random_walker(market, amount=5.0):
    """
    Random strategy with a slight contrarian edge.

    Always trades (never skips). Picks YES/NO randomly, but weights
    slightly toward the underdog side. Useful as a baseline.
    """
    yes_price = market.get("yes_price", 0.5)
    title = market.get("title", "Unknown")

    # Bias toward the underdog: if YES is cheap, slightly favor YES.
    yes_probability = 1.0 - yes_price  # inverse of price = our lean
    pick_yes = random.random() < yes_probability

    if pick_yes:
        return {
            "position": "YES",
            "amount": amount,
            "reasoning": f"Random walker: rolling the dice on '{title}' — picked YES (price: {yes_price:.2f}).",
            "confidence": 0.5,
        }
    else:
        return {
            "position": "NO",
            "amount": amount,
            "reasoning": f"Random walker: rolling the dice on '{title}' — picked NO (price: {yes_price:.2f}).",
            "confidence": 0.5,
        }
