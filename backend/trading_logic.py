import httpx
import pandas as pd
import asyncio 
from web3 import Web3
import logging
import random # For synthetic data generation

from config import (
    WEB3_PROVIDER_URL,
    PEPE_WETH_POOL_ADDRESS,
    WETH_ADDRESS,
    PEPE_ADDRESS,
    UNISWAP_ROUTER_ADDRESS,
    SHORT_SMA_WINDOW,
    LONG_SMA_WINDOW,
    RSI_WINDOW,
    RSI_OVERSOLD,
    RSI_OVERBOUGHT,
    NUM_HOURS_DATA,
    WALLET_ADDRESS # For balance checks
)

# Configure logging
logger = logging.getLogger(__name__)

# Web3 setup (initialize w3 globally, but contracts only when w3 is connected)
w3 = None
try:
    w3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER_URL))
    if not w3.is_connected():
        logger.error("Web3 is not connected to Ethereum node. Check WEB3_PROVIDER_URL in .env")
        w3 = None # Ensure w3 is None if not connected
except Exception as e:
    logger.error(f"Failed to connect to Web3 provider: {e}")
    w3 = None # Set w3 to None if connection fails

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
    return w3.eth.contract(address=WETH_ADDRESS, abi=ERC20_ABI) if w3 else None

def get_pepe_contract():
    return w3.eth.contract(address=PEPE_ADDRESS, abi=ERC20_ABI) if w3 else None

def get_uniswap_router_contract():
    return w3.eth.contract(address=w3.to_checksum_address(UNISWAP_ROUTER_ADDRESS), abi=UNISWAP_ROUTER_ABI) if w3 else None

def get_uniswap_v3_pool_contract(pool_address: str):
    return w3.eth.contract(address=w3.to_checksum_address(pool_address), abi=UNISWAP_V3_POOL_ABI) if w3 else None

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
    if not w3 or not w3.is_connected():
        logger.error("Web3 not connected, cannot get Uniswap V3 price.")
        return 0.0
    try:
        pool_contract = get_uniswap_v3_pool_contract(pool_address)
        slot0 = pool_contract.functions.slot0().call()
        sqrtPriceX96 = slot0[0]
        # Price is (sqrtPriceX96 / 2**96)**2
        # For WETH/PEPE, if WETH is token0 and PEPE is token1, price is token1/token0
        # So, PEPE price in WETH
        price = (sqrtPriceX96 / (2**96))**2
        logger.info(f"Fetched current Uniswap V3 price: {price}")
        return price
    except Exception as e:
        logger.error(f"Error getting current Uniswap V3 price for {pool_address}: {e}")
        return 0.0

async def get_historical_uniswap_v3_prices(pool_address: str, num_hours: int, current_price: float) -> pd.DataFrame:
    """Attempts to get historical prices from Uniswap V3 by querying past blocks.
    If unable to fetch enough real data, generates synthetic data.
    """
    if not w3 or not w3.is_connected():
        logger.error("Web3 not connected, cannot get historical Uniswap V3 prices. Generating synthetic data.")
        return generate_synthetic_historical_data(num_hours, current_price)

    prices = []
    timestamps = []
    try:
        current_block = w3.eth.block_number
        logger.info(f"Attempting to fetch historical data from block {current_block} backwards for {num_hours} hours.")
        blocks_per_hour = 240 # Approximate blocks per hour for Ethereum mainnet

        for i in range(num_hours):
            block_number = current_block - (i * blocks_per_hour)
            if block_number < 0: 
                logger.info("Reached genesis block or negative block number, stopping historical data fetch.")
                break
            try:
                pool_contract = get_uniswap_v3_pool_contract(pool_address)
                slot0 = pool_contract.functions.slot0().call(block_identifier=block_number)
                sqrtPriceX96 = slot0[0]
                price = (sqrtPriceX96 / (2**96))**2
                block_info = w3.eth.get_block(block_number)
                timestamp = block_info['timestamp']
                prices.append(price)
                timestamps.append(timestamp)
                logger.debug(f"Fetched price {price} at block {block_number} (timestamp {timestamp})")
                await asyncio.sleep(0.05) # Small delay to avoid hitting RPC rate limits
            except Exception as e:
                logger.warning(f"Could not fetch historical price for block {block_number}: {e}")
                # Continue even if some blocks fail

        df = pd.DataFrame({'timestamp': timestamps, 'close': prices})
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True) # Ensure chronological order
            logger.info(f"Successfully fetched {len(df)} historical data points from blockchain.")
            return df
        else:
            logger.warning("No historical data points fetched from blockchain. Generating synthetic data.")
            return generate_synthetic_historical_data(num_hours, current_price)
    except Exception as e:
        logger.error(f"An error occurred during historical data fetching from blockchain: {e}. Generating synthetic data.")
        return generate_synthetic_historical_data(num_hours, current_price)

def generate_synthetic_historical_data(num_hours: int, current_price: float) -> pd.DataFrame:
    """Generates a simple synthetic historical price dataset."""
    logger.info(f"Generating {num_hours} hours of synthetic historical data.")
    prices = []
    timestamps = []
    # Generate prices that fluctuate around the current price
    for i in range(num_hours):
        # Simple random walk around the current price
        price = current_price * (1 + (random.random() - 0.5) * 0.02) # +/- 1% fluctuation
        prices.append(price)
        timestamps.append(int(time.time()) - (num_hours - 1 - i) * 3600) # Hourly timestamps

    df = pd.DataFrame({'timestamp': timestamps, 'close': prices})
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True) # Ensure chronological order
    return df

async def get_trading_signal() -> tuple[str, float]:
    """Calculates the trading signal based on SMA, RSI, and MACD indicators using Uniswap V3 data."""
    current_pepe_price_eth = await get_current_uniswap_v3_price(PEPE_WETH_POOL_ADDRESS)

    # Fetch historical data, with fallback to synthetic data
    df = await get_historical_uniswap_v3_prices(PEPE_WETH_POOL_ADDRESS, NUM_HOURS_DATA, current_pepe_price_eth)

    # Determine the minimum required data points for all indicators
    min_data_points = max(SHORT_SMA_WINDOW, LONG_SMA_WINDOW, RSI_WINDOW, 26) # 26 is for MACD slow period

    if df.empty or len(df) < min_data_points:
        logger.warning("Not enough data (real or synthetic) to calculate signals. Returning HOLD.")
        return "HOLD", current_pepe_price_eth

    df['short_sma'] = calculate_sma(df['close'], SHORT_SMA_WINDOW)
    df['long_sma'] = calculate_sma(df['close'], LONG_SMA_WINDOW)
    df['rsi'] = calculate_rsi(df['close'], RSI_WINDOW)
    df['macd'], df['signal_line'], df['histogram'] = calculate_macd(df['close'])

    # Drop NaN values that result from indicator calculations
    df.dropna(inplace=True)

    if df.empty:
        logger.warning("Dataframe is empty after dropping NaNs from indicator calculations. Returning HOLD.")
        return "HOLD", current_pepe_price_eth

    last_row = df.iloc[-1]
    previous_row = df.iloc[-2] if len(df) > 1 else None

    signal = "HOLD"
    if previous_row is not None:
        # === AGGRESSIVE DAY TRADING SIGNALS ===
        
        # 1. SMA Crossover Signals (Primary)
        sma_buy_signal = previous_row['short_sma'] <= previous_row['long_sma'] and last_row['short_sma'] > last_row['long_sma']
        sma_sell_signal = previous_row['short_sma'] >= previous_row['long_sma'] and last_row['short_sma'] < last_row['long_sma']
        
        # 2. RSI Signals (Secondary - more sensitive for day trading)
        rsi_buy_condition = last_row['rsi'] < RSI_OVERBOUGHT  # Buy when RSI < 75 (less restrictive)
        rsi_sell_condition = last_row['rsi'] > RSI_OVERSOLD   # Sell when RSI > 25 (less restrictive)
        
        # 3. MACD Signals (Additional momentum confirmation)
        macd_buy_signal = last_row['macd'] > last_row['signal_line'] and previous_row['macd'] <= previous_row['signal_line']
        macd_sell_signal = last_row['macd'] < last_row['signal_line'] and previous_row['macd'] >= previous_row['signal_line']
        
        # 4. Price Momentum Signals (Additional day trading triggers)
        price_momentum_buy = last_row['close'] > previous_row['close'] * 1.001  # 0.1% price increase
        price_momentum_sell = last_row['close'] < previous_row['close'] * 0.999  # 0.1% price decrease
        
        # === AGGRESSIVE SIGNAL COMBINATIONS ===
        
        # BUY Signals (any of these combinations):
        buy_signals = [
            # Primary: SMA crossover + RSI
            sma_buy_signal and rsi_buy_condition,
            # Secondary: MACD crossover + RSI
            macd_buy_signal and rsi_buy_condition,
            # Tertiary: SMA crossover + price momentum
            sma_buy_signal and price_momentum_buy,
            # Quaternary: Strong RSI oversold + price momentum
            last_row['rsi'] < 30 and price_momentum_buy,
            # Quinary: MACD crossover + price momentum
            macd_buy_signal and price_momentum_buy
        ]
        
        # SELL Signals (any of these combinations):
        sell_signals = [
            # Primary: SMA crossover + RSI
            sma_sell_signal and rsi_sell_condition,
            # Secondary: MACD crossover + RSI
            macd_sell_signal and rsi_sell_condition,
            # Tertiary: SMA crossover + price momentum
            sma_sell_signal and price_momentum_sell,
            # Quaternary: Strong RSI overbought + price momentum
            last_row['rsi'] > 70 and price_momentum_sell,
            # Quinary: MACD crossover + price momentum
            macd_sell_signal and price_momentum_sell
        ]
        
        # Determine final signal
        if any(buy_signals):
            signal = "BUY"
            logger.info(f"BUY signal triggered - SMA: {sma_buy_signal}, RSI: {rsi_buy_condition}, MACD: {macd_buy_signal}, Momentum: {price_momentum_buy}")
        elif any(sell_signals):
            signal = "SELL"
            logger.info(f"SELL signal triggered - SMA: {sma_sell_signal}, RSI: {rsi_sell_condition}, MACD: {macd_sell_signal}, Momentum: {price_momentum_sell}")
        else:
            signal = "HOLD"
            logger.debug(f"HOLD - No signals met. RSI: {last_row['rsi']:.2f}, MACD: {last_row['macd']:.6f}, Price: {last_row['close']:.6f}")

    return signal, current_pepe_price_eth

async def get_eth_balance(address: str) -> float:
    """Gets the ETH balance for a given address."""
    if not w3 or not w3.is_connected():
        logger.error("Web3 not connected, cannot get ETH balance.")
        return 0.0
    try:
        balance_wei = w3.eth.get_balance(w3.to_checksum_address(address))
        return w3.from_wei(balance_wei, 'ether')
    except Exception as e:
        logger.error(f"Error getting ETH balance for {address}: {e}")
        return 0.0

async def get_token_balance(token_address: str, address: str) -> float:
    """Gets the balance of a specific ERC-20 token for a given address."""
    if not w3 or not w3.is_connected():
        logger.error("Web3 not connected, cannot get token balance.")
        return 0.0
    try:
        token_contract = w3.eth.contract(address=w3.to_checksum_address(token_address), abi=ERC20_ABI)
        balance_wei = token_contract.functions.balanceOf(w3.to_checksum_address(address)).call()
        # You'll need to get the token's decimals to convert from wei
        # For simplicity, assuming 18 decimals for now (like ETH)
        return w3.from_wei(balance_wei, 'ether')
    except Exception as e:
        logger.error(f"Error getting token balance for {address}: {e}")
        return 0.0

async def construct_simulated_swap_transaction(amount_in: float, path: list[str], to_address: str, deadline: int, is_buy: bool):
    """Constructs a transaction object, but DOES NOT sign or send it. For demonstration only."""
    # Ensure contracts are initialized before use
    uniswap_router_contract = get_uniswap_router_contract()
    if not w3 or not w3.is_connected() or not uniswap_router_contract:
        logger.error("Web3 not connected or Uniswap router contract not initialized, cannot construct transaction.")
        return None

    try:
        # Get current gas price
        gas_price = w3.eth.gas_price

        # Build the transaction
        if is_buy: # ETH to PEPE
            # For Uniswap V3, you'd typically use swapExactInputSingle or swapExactInputMultihop
            # This is a simplified representation for demonstration.
            # The actual path for V3 involves pool fees.
            # For simplicity, using a generic swapExactTokensForTokens from V2 router ABI for conceptual understanding.
            # You would need the correct V3 router ABI and function for actual V3 swaps.
            tx = uniswap_router_contract.functions.swapExactTokensForTokens(
                w3.to_wei(amount_in, 'ether'), # amountIn (ETH)
                0, # amountOutMin (slippage control, set to 0 for simulation)
                [w3.to_checksum_address(p) for p in path], # Ensure path addresses are checksummed
                w3.to_checksum_address(to_address),
                deadline
            ).build_transaction({
                'from': w3.to_checksum_address(to_address),
                'gas': 300000, # Estimate gas or use a higher value for simulation
                'gasPrice': gas_price,
                'nonce': w3.eth.get_transaction_count(w3.to_checksum_address(to_address))
            })
        else: # PEPE to ETH
            tx = uniswap_router_contract.functions.swapExactTokensForTokens(
                w3.to_wei(amount_in, 'ether'), # amountIn (PEPE, assuming 18 decimals)
                0, # amountOutMin
                [w3.to_checksum_address(p) for p in path], # Ensure path addresses are checksummed
                w3.to_checksum_address(to_address),
                deadline
            ).build_transaction({
                'from': w3.to_checksum_address(to_address),
                'gas': 300000, # Estimate gas or use a higher value for simulation
                'gasPrice': gas_price,
                'nonce': w3.eth.get_transaction_count(w3.to_checksum_address(to_address))
            })

        logger.info("--- Constructed Simulated Transaction (NOT SIGNED/SENT) ---")
        logger.info(tx)
        logger.info("--------------------------------------------------------")
        return tx
    except Exception as e:
        logger.error(f"Error constructing simulated swap transaction: {e}")
        return None
