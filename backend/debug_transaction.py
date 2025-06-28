#!/usr/bin/env python3

import asyncio
from web3 import Web3
from config import WEB3_PROVIDER_URL
from trading_logic import get_w3

async def debug_transaction():
    """Debug the failed transaction to see what happened."""
    w3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER_URL))
    
    if not w3.is_connected():
        print("Web3 not connected")
        return
    
    tx_hash = "0x9f2a35d22d91f7ed10ca63734915c0894dc1fba7e83dd16b3dcf1cb229a28d24"
    
    try:
        # Get transaction receipt
        receipt = get_w3().eth.get_transaction_receipt(tx_hash)
        print(f"Transaction Status: {'Success' if receipt.status == 1 else 'Failed'}")
        print(f"Gas Used: {receipt.gasUsed}")
        print(f"Block Number: {receipt.blockNumber}")
        
        # Get transaction details
        tx = get_w3().eth.get_transaction(tx_hash)
        print(f"From: {tx['from']}")
        print(f"To: {tx['to']}")
        print(f"Value: {get_w3().from_wei(tx['value'], 'ether')} ETH")
        print(f"Gas Price: {get_w3().from_wei(tx['gasPrice'], 'gwei')} gwei")
        
        # Check for logs (events)
        print(f"\nLogs count: {len(receipt.logs)}")
        for i, log in enumerate(receipt.logs):
            print(f"Log {i}: {log}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_transaction()) 