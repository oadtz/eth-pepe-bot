# backend/config.py

import os
from dotenv import load_dotenv

load_dotenv()

# --- Web3 Configuration ---
WEB3_PROVIDER_URL = os.getenv("WEB3_PROVIDER_URL")
if not WEB3_PROVIDER_URL:
    raise ValueError("WEB3_PROVIDER_URL not found in .env file")

# --- Wallet Configuration (Sensitive - Handle with Extreme Care) ---
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

# --- Live Trading Configuration ---
LIVE_TRADING_ENABLED = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"
MAX_TRADE_SIZE_ETH = float(os.getenv("MAX_TRADE_SIZE_ETH", "0.5"))
EMERGENCY_STOP_LOSS = float(os.getenv("EMERGENCY_STOP_LOSS", "0.20"))
GAS_LIMIT_MULTIPLIER = float(os.getenv("GAS_LIMIT_MULTIPLIER", "1.1"))
SLIPPAGE_TOLERANCE = float(os.getenv("SLIPPAGE_TOLERANCE", "0.05"))
MAX_DAILY_TRADES = int(os.getenv("MAX_DAILY_TRADES", "50"))
MAX_DAILY_VOLUME_ETH = float(os.getenv("MAX_DAILY_VOLUME_ETH", "10.0"))
MAX_GAS_PRICE_GWEI = int(os.getenv("MAX_GAS_PRICE_GWEI", "200"))

# --- Emergency Stop Recovery Configuration ---
EMERGENCY_STOP_RECOVERY_ENABLED = os.getenv("EMERGENCY_STOP_RECOVERY_ENABLED", "true").lower() == "true"
EMERGENCY_STOP_RECOVERY_THRESHOLD = float(os.getenv("EMERGENCY_STOP_RECOVERY_THRESHOLD", "0.05"))
EMERGENCY_STOP_RECOVERY_WAIT_HOURS = int(os.getenv("EMERGENCY_STOP_RECOVERY_WAIT_HOURS", "2"))

# --- Uniswap Subgraph Configuration (Removed - Using CoinGecko) ---
# UNISWAP_SUBGRAPH_URL is no longer needed
PEPE_WETH_POOL_ADDRESS = "0x11950d141ecb863f01007add7d1a342041227b58" # Uniswap V3 PEPE/WETH 0.3% fee tier
UNISWAP_ROUTER_ADDRESS = '0xE592427A0AEce92De3Edee1F18F0157Cc0fEf9f2' # Uniswap V3 Router 2

# --- Token Addresses (Mainnet) ---
WETH_ADDRESS = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
PEPE_ADDRESS = '0x6982508145454Ce325dDbE47a25d4ec3d2311933' # Corrected PEPE address

# --- Trading Logic Parameters (ULTRA AGGRESSIVE DAY TRADING) ---
SHORT_SMA_WINDOW = 3      # Ultra-fast 3-period SMA (was 5)
LONG_SMA_WINDOW = 8       # Fast 8-period SMA (was 15)
RSI_WINDOW = 5            # Fast 5-period RSI (was 7)
RSI_OVERSOLD = 35         # Buy at RSI 35 (was 25 - less restrictive)
RSI_OVERBOUGHT = 65       # Sell at RSI 65 (was 75 - less restrictive)
NUM_HOURS_DATA = 24       # 24 hours data (was 30 - faster response)

# --- Bot Simulation Parameters ---
INITIAL_ETH_BALANCE = 0.019532
TRADE_PERCENTAGE = 0.25

# --- FastAPI/CORS Configuration (Removed) ---
# CORS_ORIGINS = [
#     "http://localhost",
#     "http://localhost:80", # For frontend served by Nginx
#     "http://localhost:8000",
#     "http://127.0.0.1:8000",
#     "file:///Users/oadtz/Code/eth-pepe-bot/frontend/index.html" # Still keep for direct file access during dev
# ]