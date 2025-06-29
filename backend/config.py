# backend/config.py

import os
from dotenv import load_dotenv

load_dotenv()

# --- Web3 Configuration ---
# RPC providers with rotation for rate limit handling
# Primary provider is optional - public providers are reliable
RPC_PROVIDERS = [
    os.getenv("WEB3_PROVIDER_URL"),  # Your primary provider (Infura/Alchemy/etc) - OPTIONAL
    "https://cloudflare-eth.com",    # Cloudflare public RPC
    "https://rpc.ankr.com/eth",      # Ankr public RPC
    "https://eth.llamarpc.com",      # LlamaRPC public
    "https://ethereum.publicnode.com", # PublicNode
    "https://1rpc.io/eth",           # 1RPC public
]

# Filter out None values (if WEB3_PROVIDER_URL is not set)
RPC_PROVIDERS = [provider for provider in RPC_PROVIDERS if provider]

if not RPC_PROVIDERS:
    raise ValueError("No RPC providers configured. Please set WEB3_PROVIDER_URL in .env file or use public providers")

# Current RPC index for rotation
_current_rpc_index = 0

# --- Wallet Configuration (Sensitive - Handle with Extreme Care) ---
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

# --- Live Trading Configuration ---
LIVE_TRADING_ENABLED = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"
MAX_TRADE_SIZE_ETH = float(os.getenv("MAX_TRADE_SIZE_ETH", "0.01"))
EMERGENCY_STOP_LOSS = float(os.getenv("EMERGENCY_STOP_LOSS", "0.20"))
GAS_LIMIT_MULTIPLIER = float(os.getenv("GAS_LIMIT_MULTIPLIER", "1.1"))
SLIPPAGE_TOLERANCE = float(os.getenv("SLIPPAGE_TOLERANCE", "0.02"))
MAX_DAILY_TRADES = int(os.getenv("MAX_DAILY_TRADES", "50"))
MAX_DAILY_VOLUME_ETH = float(os.getenv("MAX_DAILY_VOLUME_ETH", "10.0"))
MAX_GAS_PRICE_GWEI = int(os.getenv("MAX_GAS_PRICE_GWEI", "200"))

# --- Emergency Stop Recovery Configuration ---
EMERGENCY_STOP_RECOVERY_ENABLED = os.getenv("EMERGENCY_STOP_RECOVERY_ENABLED", "true").lower() == "true"
EMERGENCY_STOP_RECOVERY_THRESHOLD = float(os.getenv("EMERGENCY_STOP_RECOVERY_THRESHOLD", "0.05"))
EMERGENCY_STOP_RECOVERY_WAIT_HOURS = int(os.getenv("EMERGENCY_STOP_RECOVERY_WAIT_HOURS", "2"))

# --- Uniswap Subgraph Configuration (Removed - Using CoinGecko) ---
# UNISWAP_SUBGRAPH_URL is no longer needed

# PEPE/WETH Pool Addresses (multiple fee tiers for better liquidity)
PEPE_WETH_POOL_ADDRESS = "0x11950d141ecb863f01007add7d1a342041227b58" # Uniswap V3 PEPE/WETH 0.3% fee tier (MAIN POOL)
PEPE_WETH_POOL_1PERCENT = "0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8" # 1% fee tier 
PEPE_WETH_POOL_005PERCENT = "0x4e68ccd3e89f51c3074ca5072bbac773960dfa36" # 0.05% fee tier

UNISWAP_ROUTER_ADDRESS = '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D' # Uniswap V2 Router

# --- Token Addresses (Mainnet) ---
WETH_ADDRESS = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
PEPE_ADDRESS = '0x6982508145454Ce325dDbE47a25d4ec3d2311933' # Corrected PEPE address

# --- Trading Logic Parameters (ULTRA AGGRESSIVE DAY TRADING) ---
SHORT_SMA_WINDOW = 3      # Ultra-fast 3-period SMA (was 5)
LONG_SMA_WINDOW = 8       # Fast 8-period SMA (was 15)
RSI_WINDOW = 5            # Fast 5-period RSI (was 7)
RSI_OVERSOLD = 35         # Buy at RSI 35 (was 25 - less restrictive)
RSI_OVERBOUGHT = 65       # Sell at RSI 65 (was 75 - less restrictive)
NUM_HOURS_DATA = 24       # 24 hours data (reduced from 72 for faster startup)

# --- Bot Trading Parameters ---
TRADE_PERCENTAGE = 0.15  # Increased from 0.05 to 0.15 (15% of balance instead of 5%)

# Note: INITIAL_ETH_BALANCE removed - bot always fetches real wallet balance on startup

# --- FastAPI/CORS Configuration (Removed) ---
# CORS_ORIGINS = [
#     "http://localhost",
#     "http://localhost:80", # For frontend served by Nginx
#     "http://localhost:8000",
#     "http://127.0.0.1:8000",
#     "file:///Users/oadtz/Code/eth-pepe-bot/frontend/index.html" # Still keep for direct file access during dev
# ]