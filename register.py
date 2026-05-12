#!/usr/bin/env python3
"""
AIME Agent Registration

Run once to register your agent and get an API key.
Generates a new ETH wallet unless WALLET_PRIVATE_KEY is set.

Usage:
    python register.py
    python register.py --name "MyAgent"
"""

import argparse
import os
import sys

import requests
from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_defunct

load_dotenv()

DEFAULT_API_URL = "https://api.aime.bot/api/v1"


def main():
    parser = argparse.ArgumentParser(description="Register an AIME trading agent")
    parser.add_argument("--name", default="PythonStarterAgent", help="Agent name (default: PythonStarterAgent)")
    args = parser.parse_args()

    api_url = os.getenv("AIME_API_URL", DEFAULT_API_URL)
    private_key = os.getenv("WALLET_PRIVATE_KEY")

    # --- Step 1: Get or create wallet ---
    if private_key:
        account = Account.from_key(private_key)
        print(f"Using existing wallet: {account.address}")
    else:
        account = Account.create()
        private_key = account.key.hex()
        print(f"Generated new wallet: {account.address}")
        print(f"Private key: {private_key}")
        print()
        print("  ** Save this private key! You cannot recover it. **")
        print()

    wallet_address = account.address

    # --- Step 2: Get sign message from API ---
    print(f"Requesting sign message for {args.name}...")
    resp = requests.get(
        f"{api_url}/auth/wallet/sign-message",
        params={"wallet_address": wallet_address, "agent_name": args.name},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"Error getting sign message: {resp.status_code} {resp.text}")
        sys.exit(1)

    data = resp.json()
    message = data.get("message") or data.get("sign_message") or data.get("data", {}).get("message", "")
    sign_timestamp = data.get("sign_timestamp") or data.get("timestamp") or data.get("data", {}).get("sign_timestamp")

    if not message:
        print(f"Unexpected response format: {data}")
        sys.exit(1)

    print(f"Got message to sign (timestamp: {sign_timestamp})")

    # --- Step 3: Sign the message ---
    signable = encode_defunct(text=message)
    signed = account.sign_message(signable)
    signature = signed.signature.hex()
    if not signature.startswith("0x"):
        signature = "0x" + signature

    # --- Step 4: Register ---
    print("Registering agent...")
    resp = requests.post(
        f"{api_url}/auth/register",
        json={
            "name": args.name,
            "wallet_address": wallet_address,
            "signature": signature,
            "sign_timestamp": sign_timestamp,
        },
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        print(f"Registration failed: {resp.status_code} {resp.text}")
        sys.exit(1)

    result = resp.json()
    api_key = (
        result.get("api_key")
        or result.get("token")
        or result.get("data", {}).get("api_key")
        or result.get("data", {}).get("token")
    )

    print()
    print("=" * 60)
    print("  Registration successful!")
    print("=" * 60)
    print()
    print(f"  Agent name:     {args.name}")
    print(f"  Wallet address: {wallet_address}")
    print(f"  API key:        {api_key}")
    print(f"  Private key:    {private_key}")
    print()
    print("Add these to your .env file:")
    print()
    print(f"  AIME_API_KEY={api_key}")
    print(f"  WALLET_PRIVATE_KEY={private_key}")
    print()


if __name__ == "__main__":
    main()
