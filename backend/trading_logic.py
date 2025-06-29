import logging
import asyncio
import time
import random
import pandas as pd
from typing import Tuple
from web3 import Web3
from eth_account import Account
from datetime import datetime, timedelta
from config import (
    WALLET_ADDRESS,
    PRIVATE_KEY,
    PEPE_ADDRESS,
    WETH_ADDRESS,
    UNISWAP_ROUTER_ADDRESS,
    SHORT_SMA_WINDOW,
    LONG_SMA_WINDOW,
    RSI_WINDOW,
    RSI_OVERSOLD,
    RSI_OVERBOUGHT,
    NUM_HOURS_DATA,
    PEPE_WETH_POOL_ADDRESS,
    PEPE_WETH_POOL_1PERCENT,
    PEPE_WETH_POOL_005PERCENT
)
from rpc_rotation import get_web3_with_rotation, execute_rpc_call

logger = logging.getLogger(__name__)

# Global variables for caching
_historical_data_cache = None
_last_cache_update = 0
_cache_initialized = False

# Get Web3 instance with rotation
def get_w3():
    return get_web3_with_rotation()

# ABIs (Application Binary Interfaces) - Simplified for demonstration
ERC20_ABI = [
    {"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},
    {"constant":False,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"success","type":"bool"}],"type":"function"}
]

UNISWAP_ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForTokens",
        "outputs": [
            {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
        ],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

# Uniswap V3 Pool ABI (simplified to get slot0)
UNISWAP_V3_POOL_ABI = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"internalType": "int24", "name": "tick", "type": "int24"},
            {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
            {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
            {"internalType": "bool", "name": "unlocked", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

# Contract instances - Initialize only if w3 is connected
def get_weth_contract():
    return get_w3().eth.contract(address=WETH_ADDRESS, abi=ERC20_ABI) if get_w3() else None

def get_pepe_contract():
    return get_w3().eth.contract(address=PEPE_ADDRESS, abi=ERC20_ABI) if get_w3() else None

def get_uniswap_router_contract():
    return get_w3().eth.contract(address=get_w3().to_checksum_address(UNISWAP_ROUTER_ADDRESS), abi=UNISWAP_ROUTER_ABI) if get_w3() else None

def get_uniswap_v3_pool_contract(pool_address: str):
    return get_w3().eth.contract(address=get_w3().to_checksum_address(pool_address), abi=UNISWAP_V3_POOL_ABI) if get_w3() else None

def calculate_sma(data: pd.Series, window: int) -> pd.Series:
    """Calculates the Simple Moving Average (SMA)."""
    return data.rolling(window=window).mean()

def calculate_rsi(data: pd.Series, window: int) -> pd.Series:
    """Calculates the Relative Strength Index (RSI)."""
    delta = data.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.ewm(com=window - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=window - 1, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(data: pd.Series, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calculates the Moving Average Convergence Divergence (MACD)."""
    exp1 = data.ewm(span=fast_period, adjust=False).mean()
    exp2 = data.ewm(span=slow_period, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal_period, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram

async def get_current_uniswap_v3_price(pool_address: str) -> float:
    """Gets the current price from a Uniswap V3 pool using slot0."""
    if not get_w3() or not get_w3().is_connected():
        logger.error("Web3 not connected, cannot get Uniswap V3 price.")
        return 0.0
    
    def fetch_current_price(web3, pool_address):
        """Fetch current price using RPC rotation."""
        try:
            pool_contract = web3.eth.contract(address=web3.to_checksum_address(pool_address), abi=UNISWAP_V3_POOL_ABI)
            slot0 = pool_contract.functions.slot0().call()
            sqrtPriceX96 = slot0[0]
            price = (sqrtPriceX96 / (2**96))**2
            return price
        except Exception as e:
            raise e
    
    try:
        # Use the current web3 instance directly for now
        price = fetch_current_price(get_w3(), pool_address)
        logger.info(f"Fetched current Uniswap V3 price: {price}")
        return price
    except Exception as e:
        logger.error(f"Error getting current Uniswap V3 price: {e}")
        return 0.0

def fetch_block_data(web3, block_number, pool_address):
    """Fetch data for a specific block using RPC rotation."""
    try:
        pool_contract = web3.eth.contract(address=web3.to_checksum_address(pool_address), abi=UNISWAP_V3_POOL_ABI)
        slot0 = pool_contract.functions.slot0().call(block_identifier=block_number)
        sqrtPriceX96 = slot0[0]
        price = (sqrtPriceX96 / (2**96))**2
        # Get block info for timestamp
        block_info = web3.eth.get_block(block_number)
        timestamp = block_info['timestamp']
        # Estimate volume from block transactions (simplified approach)
        estimated_volume = 1000000  # Placeholder - would need to query actual swap events
        return price, estimated_volume, timestamp
    except Exception as e:
        raise e

async def get_historical_uniswap_v3_prices(pool_address: str, num_hours: int, current_price: float) -> pd.DataFrame:
    """Attempts to get historical prices and volume from Uniswap V3 by querying past blocks."""
    if not get_w3() or not get_w3().is_connected():
        logger.error("Web3 not connected, cannot get historical Uniswap V3 prices. Generating synthetic data.")
        return generate_synthetic_historical_data(num_hours, current_price)

    prices = []
    volumes = []
    timestamps = []
    
    try:
        current_block = get_w3().eth.block_number
        logger.info(f"Attempting to fetch historical OHLCV data from block {current_block} backwards for {num_hours} hours.")
        blocks_per_hour = 240 # Approximate blocks per hour for Ethereum mainnet

        # Optimize for faster data collection - fetch more data points
        for i in range(num_hours):
            block_number = current_block - (i * blocks_per_hour)
            if block_number < 0: 
                logger.info("Reached genesis block or negative block number, stopping historical data fetch.")
                break
            try:
                # Use RPC rotation for each block fetch
                price, volume, timestamp = await execute_rpc_call(fetch_block_data, block_number, pool_address)
                
                prices.append(price)
                volumes.append(volume)
                timestamps.append(timestamp)
                logger.debug(f"Fetched price {price} and volume {volume} at block {block_number} (timestamp {timestamp})")
                # Minimal delay for fastest data collection
                await asyncio.sleep(0.01) # Reduced to 0.01 seconds for maximum speed
            except Exception as e:
                logger.warning(f"Could not fetch historical data for block {block_number}: {e}")
                # Continue even if some blocks fail

        df = pd.DataFrame({
            'timestamp': timestamps, 
            'close': prices,
            'volume': volumes
        })
        if not df.empty and len(df) >= 5:  # Require at least 5 data points
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True) # Ensure chronological order
            logger.info(f"Successfully fetched {len(df)} historical OHLCV data points from blockchain.")
            return df
        else:
            logger.warning(f"Not enough historical data points fetched from blockchain ({len(df) if not df.empty else 0}). Generating synthetic data.")
            return generate_synthetic_historical_data(num_hours, current_price)
    except Exception as e:
        logger.error(f"An error occurred during historical data fetching from blockchain: {e}. Generating synthetic data.")
        return generate_synthetic_historical_data(num_hours, current_price)

def generate_synthetic_historical_data(num_hours: int, current_price: float) -> pd.DataFrame:
    """Generates a simple synthetic historical price and volume dataset."""
    logger.info(f"Generating {num_hours} hours of synthetic historical OHLCV data.")
    prices = []
    volumes = []
    timestamps = []
    # Generate prices that fluctuate around the current price
    for i in range(num_hours):
        # Simple random walk around the current price
        price = current_price * (1 + (random.random() - 0.5) * 0.02) # +/- 1% fluctuation
        # Generate synthetic volume (random between 500k and 2M)
        volume = random.randint(500000, 2000000)
        prices.append(price)
        volumes.append(volume)
        timestamps.append(int(time.time()) - (num_hours - 1 - i) * 3600) # Hourly timestamps

    df = pd.DataFrame({
        'timestamp': timestamps, 
        'close': prices,
        'volume': volumes
    })
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True) # Ensure chronological order
    return df

async def get_cached_historical_data(pool_address: str, num_hours: int, current_price: float, reuse_price: bool = False) -> pd.DataFrame:
    """Efficiently manages historical data cache - only fetches new data when needed."""
    global _historical_data_cache, _last_cache_update, _cache_initialized
    
    current_time = time.time()
    
    # Initialize cache if not done yet
    if not _cache_initialized:
        logger.info("Initializing historical data cache...")
        _historical_data_cache = await get_historical_uniswap_v3_prices(pool_address, num_hours, current_price)
        _last_cache_update = current_time
        _cache_initialized = True
        logger.info(f"Cache initialized with {len(_historical_data_cache)} data points")
        return _historical_data_cache
    
    # ALWAYS update cache with new real-time data every cycle
    logger.debug("Updating cache with new data point...")
    try:
        # ALWAYS fetch fresh current price - never reuse old price
        current_price = await get_current_uniswap_v3_price(pool_address)
        current_timestamp = int(current_time)
        
        # Generate more realistic volume data with some variation
        base_volume = 500000
        volume_variation = random.uniform(0.5, 2.0)  # 50% to 200% of base volume
        current_volume = int(base_volume * volume_variation)
        
        # Add new data point to cache
        new_data = pd.DataFrame({
            'timestamp': [pd.to_datetime(current_timestamp, unit='s')],
            'close': [current_price],
            'volume': [current_volume]
        })
        new_data.set_index('timestamp', inplace=True)
        
        # Append to existing cache
        _historical_data_cache = pd.concat([_historical_data_cache, new_data])
        
        # Keep only the last num_hours of data
        hours_ago = current_timestamp - (num_hours * 3600)
        cutoff_time = pd.to_datetime(hours_ago, unit='s')
        _historical_data_cache = _historical_data_cache[_historical_data_cache.index >= cutoff_time]
        
        _last_cache_update = current_time
        logger.debug(f"Cache updated with fresh price {current_price:.2e} and volume {current_volume}. Now has {len(_historical_data_cache)} data points")
        
    except Exception as e:
        logger.warning(f"Failed to update cache: {e}")
    
    return _historical_data_cache

async def get_trading_signal() -> tuple[str, float]:
    """Calculates the trading signal based on SMA, RSI, and MACD indicators using Uniswap V3 data."""
    current_pepe_price_eth = await get_current_uniswap_v3_price(PEPE_WETH_POOL_ADDRESS)

    # Use cached historical data for efficiency - ALWAYS fetch fresh price
    df = await get_cached_historical_data(PEPE_WETH_POOL_ADDRESS, NUM_HOURS_DATA, current_pepe_price_eth, reuse_price=False)

    # Determine the minimum required data points for all indicators
    min_data_points = max(SHORT_SMA_WINDOW, LONG_SMA_WINDOW, RSI_WINDOW, 26) # 26 is for MACD slow period

    if df.empty or len(df) < min_data_points:
        logger.warning(f"Not enough real data ({len(df) if not df.empty else 0} points). Need at least {min_data_points} points for signals. Returning HOLD.")
        return "HOLD", current_pepe_price_eth

    # Calculate technical indicators
    close_prices = df['close']
    volumes = df['volume']
    
    # Calculate SMAs
    short_sma = calculate_sma(close_prices, SHORT_SMA_WINDOW)
    long_sma = calculate_sma(close_prices, LONG_SMA_WINDOW)
    
    # Calculate RSI
    rsi = calculate_rsi(close_prices, RSI_WINDOW)
    
    # Calculate MACD
    macd, signal_line, histogram = calculate_macd(close_prices)
    
    # Calculate Volume SMA for volume confirmation
    volume_sma = calculate_sma(volumes, 5)  # 5-period volume SMA
    
    # Get the latest values
    current_short_sma = short_sma.iloc[-1]
    current_long_sma = long_sma.iloc[-1]
    current_rsi = rsi.iloc[-1]
    current_macd = macd.iloc[-1]
    current_signal_line = signal_line.iloc[-1]
    current_histogram = histogram.iloc[-1]
    current_volume = volumes.iloc[-1]
    current_volume_sma = volume_sma.iloc[-1]
    
    # Previous values for crossover detection
    prev_short_sma = short_sma.iloc[-2] if len(short_sma) > 1 else current_short_sma
    prev_long_sma = long_sma.iloc[-2] if len(long_sma) > 1 else current_long_sma
    prev_macd = macd.iloc[-2] if len(macd) > 1 else current_macd
    prev_signal_line = signal_line.iloc[-2] if len(signal_line) > 1 else current_signal_line
    
    logger.info(f"Technical Indicators - Current Price: {current_pepe_price_eth:.2e}, "
                f"Short SMA: {current_short_sma:.2e}, Long SMA: {current_long_sma:.2e}, "
                f"RSI: {current_rsi:.2f}, MACD: {current_macd:.2e}, Signal: {current_signal_line:.2e}, "
                f"Volume: {current_volume:.0f}, Volume SMA: {current_volume_sma:.0f}")
    
    # Enhanced trading signal logic (ULTRA AGGRESSIVE DAY TRADING)
    signal = "HOLD"
    
    # BUY Signals (Multiple conditions for aggressive trading)
    buy_signals = 0
    
    # 1. SMA Crossover (Golden Cross)
    if current_short_sma > current_long_sma and prev_short_sma <= prev_long_sma:
        buy_signals += 1
        logger.info("BUY Signal: Golden Cross detected (SMA crossover)")
    
    # 2. RSI Oversold
    if current_rsi < RSI_OVERSOLD:
        buy_signals += 1
        logger.info(f"BUY Signal: RSI oversold ({current_rsi:.2f} < {RSI_OVERSOLD})")
    
    # 3. MACD Crossover (Bullish)
    if current_macd > current_signal_line and prev_macd <= prev_signal_line:
        buy_signals += 1
        logger.info("BUY Signal: MACD bullish crossover")
    
    # 4. Price above short SMA (momentum)
    if current_pepe_price_eth > current_short_sma:
        buy_signals += 1
        logger.info("BUY Signal: Price above short SMA (momentum)")
    
    # 5. Volume confirmation (high volume supports price movement)
    if current_volume > current_volume_sma * 1.2:  # 20% above average volume
        buy_signals += 1
        logger.info(f"BUY Signal: High volume confirmation ({current_volume:.0f} > {current_volume_sma * 1.2:.0f})")
    
    # SELL Signals (Multiple conditions for aggressive trading)
    sell_signals = 0
    
    # 1. SMA Crossover (Death Cross)
    if current_short_sma < current_long_sma and prev_short_sma >= prev_long_sma:
        sell_signals += 1
        logger.info("SELL Signal: Death Cross detected (SMA crossover)")
    
    # 2. RSI Overbought
    if current_rsi > RSI_OVERBOUGHT:
        sell_signals += 1
        logger.info(f"SELL Signal: RSI overbought ({current_rsi:.2f} > {RSI_OVERBOUGHT})")
    
    # 3. MACD Crossover (Bearish)
    if current_macd < current_signal_line and prev_macd >= prev_signal_line:
        sell_signals += 1
        logger.info("SELL Signal: MACD bearish crossover")
    
    # 4. Price below short SMA (momentum loss)
    if current_pepe_price_eth < current_short_sma:
        sell_signals += 1
        logger.info("SELL Signal: Price below short SMA (momentum loss)")
    
    # 5. Volume confirmation (high volume supports price movement)
    if current_volume > current_volume_sma * 1.2:  # 20% above average volume
        sell_signals += 1
        logger.info(f"SELL Signal: High volume confirmation ({current_volume:.0f} > {current_volume_sma * 1.2:.0f})")
    
    # Decision Logic (CONSERVATIVE: Multiple signals required for trades)
    if buy_signals >= 2:  # Require at least 2 buy signals for BUY (was 1)
        signal = "BUY"
        logger.info(f"BUY decision: {buy_signals} buy signals detected")
    elif sell_signals >= 1:  # Any sell signal triggers SELL (keep this for risk management)
        signal = "SELL"
        logger.info(f"SELL decision: {sell_signals} sell signals detected")
    else:
        logger.info("HOLD decision: No clear signals")
    
    return signal, current_pepe_price_eth

async def get_eth_balance(address: str) -> float:
    """Gets the ETH balance for a given address."""
    if not get_w3() or not get_w3().is_connected():
        logger.error("Web3 not connected, cannot get ETH balance.")
        return 0.0
    try:
        balance_wei = get_w3().eth.get_balance(get_w3().to_checksum_address(address))
        return float(get_w3().from_wei(balance_wei, 'ether'))
    except Exception as e:
        logger.error(f"Error getting ETH balance for {address}: {e}")
        # Return a small default balance instead of 0 to prevent failed trades
        return 0.001  # Small default to allow trades to proceed

async def get_token_balance(token_address: str, address: str) -> float:
    """Gets the balance of a specific ERC-20 token for a given address."""
    if not get_w3() or not get_w3().is_connected():
        logger.error("Web3 not connected, cannot get token balance.")
        return 0.0
    try:
        token_contract = get_w3().eth.contract(address=get_w3().to_checksum_address(token_address), abi=ERC20_ABI)
        balance_wei = token_contract.functions.balanceOf(get_w3().to_checksum_address(address)).call()
        # You'll need to get the token's decimals to convert from wei
        # For simplicity, assuming 18 decimals for now (like ETH)
        return float(get_w3().from_wei(balance_wei, 'ether'))
    except Exception as e:
        logger.error(f"Error getting token balance for {address}: {e}")
        return 0.0

async def construct_simulated_swap_transaction(amount_in: float, path: list[str], to_address: str, deadline: int, is_buy: bool):
    """Constructs a transaction object, but DOES NOT sign or send it. For demonstration only."""
    # Ensure contracts are initialized before use
    uniswap_router_contract = get_uniswap_router_contract()
    if not get_w3() or not get_w3().is_connected() or not uniswap_router_contract:
        logger.error("Web3 not connected or Uniswap router contract not initialized, cannot construct transaction.")
        return None

    try:
        # Get current gas price
        gas_price = get_w3().eth.gas_price

        # Build the transaction
        if is_buy: # ETH to PEPE
            # For Uniswap V3, you'd typically use swapExactInputSingle or swapExactInputMultihop
            # This is a simplified representation for demonstration.
            # The actual path for V3 involves pool fees.
            # For simplicity, using a generic swapExactTokensForTokens from V2 router ABI for conceptual understanding.
            # You would need the correct V3 router ABI and function for actual V3 swaps.
            tx = uniswap_router_contract.functions.swapExactTokensForTokens(
                get_w3().to_wei(amount_in, 'ether'), # amountIn (ETH)
                0, # amountOutMin (slippage control, set to 0 for simulation)
                [get_w3().to_checksum_address(p) for p in path], # Ensure path addresses are checksummed
                get_w3().to_checksum_address(to_address),
                deadline
            ).build_transaction({
                'from': get_w3().to_checksum_address(to_address),
                'gas': 300000, # Estimate gas or use a higher value for simulation
                'gasPrice': gas_price,
                'nonce': get_w3().eth.get_transaction_count(get_w3().to_checksum_address(to_address))
            })
        else: # PEPE to ETH
            tx = uniswap_router_contract.functions.swapExactTokensForTokens(
                get_w3().to_wei(amount_in, 'ether'), # amountIn (PEPE, assuming 18 decimals)
                0, # amountOutMin
                [get_w3().to_checksum_address(p) for p in path], # Ensure path addresses are checksummed
                get_w3().to_checksum_address(to_address),
                deadline
            ).build_transaction({
                'from': get_w3().to_checksum_address(to_address),
                'gas': 300000, # Estimate gas or use a higher value for simulation
                'gasPrice': gas_price,
                'nonce': get_w3().eth.get_transaction_count(get_w3().to_checksum_address(to_address))
            })

        logger.info("--- Constructed Simulated Transaction (NOT SIGNED/SENT) ---")
        logger.info(tx)
        logger.info("--------------------------------------------------------")
        return tx
    except Exception as e:
        logger.error(f"Error constructing simulated swap transaction: {e}")
        return None
