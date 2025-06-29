#!/usr/bin/env python3

import os
import sys
from dotenv import load_dotenv
from web3 import Web3

# Load environment variables
load_dotenv()

def test_web3_connection():
    print("Testing Web3 connection...")
    
    # Check environment variables
    web3_url = os.getenv('WEB3_PROVIDER_URL')
    print(f"WEB3_PROVIDER_URL: {web3_url}")
    
    if not web3_url:
        print("ERROR: WEB3_PROVIDER_URL not found in environment variables")
        return False
    
    try:
        # Create Web3 instance
        web3 = Web3(Web3.HTTPProvider(web3_url))
        
        # Test connection
        if web3.is_connected():
            print("✅ Web3 connection successful!")
            
            # Get latest block
            latest_block = web3.eth.block_number
            print(f"Latest block number: {latest_block}")
            
            return True
        else:
            print("❌ Web3 connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Error connecting to Web3: {e}")
        return False

if __name__ == "__main__":
    success = test_web3_connection()
    sys.exit(0 if success else 1) 