#!/usr/bin/env python3

import asyncio
from web3 import Web3
from config import (
    WEB3_PROVIDER_URL,
    PEPE_WETH_POOL_ADDRESS,
    UNISWAP_ROUTER_ADDRESS,
    WETH_ADDRESS,
    PEPE_ADDRESS
)
from trading_logic import get_w3

async def verify_addresses():
    """Verify all addresses are correct."""
    if not get_w3().is_connected():
        print("❌ Web3 not connected")
        return
    
    print("🔍 VERIFYING ADDRESSES...")
    print("=" * 50)
    
    # Official addresses from Uniswap and token contracts
    OFFICIAL_ADDRESSES = {
        "Uniswap V3 Router": "0xE592427A0AEce92De3Edee1F18F0157Cc0fEf9f2",
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "PEPE": "0x6982508145454Ce325dDbE47a25d4ec3d2311933",
        "PEPE/WETH Pool (0.3%)": "0x11950d141ecb863f01007add7d1a342041227b58"
    }
    
    # Check each address
    for name, official_addr in OFFICIAL_ADDRESSES.items():
        config_addr = None
        
        if "Router" in name:
            config_addr = UNISWAP_ROUTER_ADDRESS
        elif "WETH" in name:
            config_addr = WETH_ADDRESS
        elif "PEPE" in name and "Pool" not in name:
            config_addr = PEPE_ADDRESS
        elif "Pool" in name:
            config_addr = PEPE_WETH_POOL_ADDRESS
        
        if config_addr:
            # Normalize addresses for comparison
            official_normalized = get_w3().to_checksum_address(official_addr)
            config_normalized = get_w3().to_checksum_address(config_addr)
            
            if official_normalized == config_normalized:
                print(f"✅ {name}: CORRECT")
                print(f"   {config_normalized}")
            else:
                print(f"❌ {name}: MISMATCH!")
                print(f"   Expected: {official_normalized}")
                print(f"   Config:   {config_normalized}")
        else:
            print(f"⚠️  {name}: Not found in config")
        
        print()
    
    # Additional verification - check if contracts exist
    print("🔍 VERIFYING CONTRACT EXISTENCE...")
    print("=" * 50)
    
    for name, addr in OFFICIAL_ADDRESSES.items():
        try:
            # Try to get contract code
            code = get_w3().eth.get_code(get_w3().to_checksum_address(addr))
            if code and code != b'':
                print(f"✅ {name}: Contract exists")
            else:
                print(f"❌ {name}: No contract code found")
        except Exception as e:
            print(f"❌ {name}: Error checking contract - {e}")
    
    # Check PEPE/WETH pool specifically
    print("\n🔍 VERIFYING PEPE/WETH POOL...")
    print("=" * 50)
    
    try:
        # Try to get pool data
        pool_contract = get_w3().eth.contract(
            address=get_w3().to_checksum_address(PEPE_WETH_POOL_ADDRESS),
            abi=[{"inputs":[],"name":"slot0","outputs":[{"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"},{"internalType":"int24","name":"tick","type":"int24"},{"internalType":"uint16","name":"observationIndex","type":"uint16"},{"internalType":"uint16","name":"observationCardinality","type":"uint16"},{"internalType":"uint16","name":"observationCardinalityNext","type":"uint16"},{"internalType":"uint8","name":"feeProtocol","type":"uint8"},{"internalType":"bool","name":"unlocked","type":"bool"}],"stateMutability":"view","type":"function"}]
        )
        
        slot0 = pool_contract.functions.slot0().call()
        sqrtPriceX96 = slot0[0]
        price = (sqrtPriceX96 / (2**96))**2
        print(f"✅ PEPE/WETH Pool: Working (Price: {price:.2e})")
    except Exception as e:
        print(f"❌ PEPE/WETH Pool: Error - {e}")

if __name__ == "__main__":
    asyncio.run(verify_addresses()) 