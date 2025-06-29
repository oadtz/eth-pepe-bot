import logging
import asyncio
from typing import Optional, Tuple
from web3 import Web3
from eth_account import Account
from datetime import datetime, timedelta
from config import (
    WALLET_ADDRESS,
    PRIVATE_KEY,
    PEPE_ADDRESS,
    WETH_ADDRESS,
    UNISWAP_ROUTER_ADDRESS,
    SLIPPAGE_TOLERANCE,
    GAS_LIMIT_MULTIPLIER,
    MAX_GAS_PRICE_GWEI,
    PEPE_WETH_POOL_ADDRESS,
    PEPE_WETH_POOL_1PERCENT,
    PEPE_WETH_POOL_005PERCENT
)
from trading_logic import get_w3, get_eth_balance, get_token_balance

logger = logging.getLogger(__name__)

# Uniswap V2 Router ABI (for swapExactETHForTokens like Uniswap interface)
UNISWAP_V2_ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForTokens",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

# PEPE ABI for getting decimals
PEPE_ABI = [
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "spender", "type": "address"}, {"name": "value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
]

# WETH ABI for wrapping/unwrapping ETH
WETH_ABI = [
    {"constant": False, "inputs": [], "name": "deposit", "outputs": [], "type": "function"},
    {"constant": False, "inputs": [{"name": "wad", "type": "uint256"}], "name": "withdraw", "outputs": [], "type": "function"},
    {"constant": True, "inputs": [{"name": "owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "spender", "type": "address"}, {"name": "value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
]

class LiveTrader:
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager
        self.account = None
        self.router_contract = None
        self.weth_contract = None
        self.pepe_contract = None
        
        if not get_w3().is_connected():
            raise ValueError("Web3 is not connected")
        
        # Initialize contracts
        self._initialize_contracts()
        
        # Initialize account if private key is provided
        if PRIVATE_KEY:
            self.account = Account.from_key(PRIVATE_KEY)
            logger.info(f"Account initialized: {self.account.address}")
        else:
            logger.warning("No private key provided - live trading disabled")
    
    def _initialize_contracts(self):
        """Initialize Web3 contract instances."""
        try:
            self.router_contract = get_w3().eth.contract(
                address=get_w3().to_checksum_address(UNISWAP_ROUTER_ADDRESS),
                abi=UNISWAP_V2_ROUTER_ABI
            )
            self.weth_contract = get_w3().eth.contract(
                address=get_w3().to_checksum_address(WETH_ADDRESS),
                abi=WETH_ABI
            )
            self.pepe_contract = get_w3().eth.contract(
                address=get_w3().to_checksum_address(PEPE_ADDRESS),
                abi=PEPE_ABI  # Using PEPE ABI for ERC20 functions
            )
            logger.info("Contracts initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize contracts: {e}")
            raise
    
    async def execute_buy_order(self, eth_amount: float, current_price: float) -> Tuple[bool, str]:
        """
        Execute a buy order (ETH -> PEPE)
        Returns (success, message)
        """
        if not self.account:
            return False, "No account configured for live trading"
        
        try:
            # Validate the trade
            is_valid, error_msg = await self.risk_manager.validate_trade_signal("BUY", eth_amount, current_price)
            if not is_valid:
                return False, error_msg
            
            # REDUCE TRADE SIZE for better execution - use only 50% of available ETH
            available_eth = await get_eth_balance(self.account.address)
            safe_eth_amount = min(eth_amount, available_eth * 0.5)  # Use max 50% of available ETH
            
            if safe_eth_amount < 0.001:  # Minimum 0.001 ETH (reduced from 0.002)
                return False, f"Insufficient ETH for trade: {safe_eth_amount} ETH"
            
            # Calculate minimum PEPE to receive (MetaMask-style slippage protection)
            expected_pepe = safe_eth_amount / current_price
            # Use 2% slippage tolerance (more reasonable than 1% or 10%)
            min_pepe_amount = expected_pepe * 0.98  # 2% slippage tolerance
            
            # CRITICAL FIX: Ensure minimum amount is never 0 or too small
            if min_pepe_amount <= 0:
                min_pepe_amount = expected_pepe * 0.95  # At least 95% of expected amount
                logger.warning(f"Minimum amount was 0, setting to 95% of expected: {min_pepe_amount:.0f}")
            
            # ADDITIONAL SAFETY: Check if the trade amount is too small for the pool
            if safe_eth_amount < 0.001:  # Very small trades often fail
                logger.warning(f"Trade amount {safe_eth_amount} ETH is very small and may fail")
                return False, f"Trade amount too small for reliable execution: {safe_eth_amount} ETH"
            
            # Get PEPE decimals for correct amount conversion
            try:
                pepe_decimals = self.pepe_contract.functions.decimals().call()
                logger.info(f"PEPE token decimals: {pepe_decimals}")
            except Exception as e:
                logger.warning(f"Could not get PEPE decimals, assuming 18: {e}")
                pepe_decimals = 18
            
            # Convert to PEPE's actual decimals
            min_pepe_wei = int(min_pepe_amount * (10 ** pepe_decimals))
            
            logger.info(f"Attempting BUY: {safe_eth_amount:.6f} ETH -> Expected: {expected_pepe:.0f} PEPE, Min: {min_pepe_amount:.0f} PEPE")
            logger.info(f"Current price: {current_price:.2e}, Slippage tolerance: {SLIPPAGE_TOLERANCE}")
            logger.info(f"PEPE decimals: {pepe_decimals}, Min amount in wei: {min_pepe_wei}")
            
            # Get current nonce
            nonce = get_w3().eth.get_transaction_count(self.account.address)
            
            # Get gas price
            gas_price = get_w3().eth.gas_price
            gas_price_gwei = get_w3().from_wei(gas_price, 'gwei')
            
            if gas_price_gwei > MAX_GAS_PRICE_GWEI:
                return False, f"Gas price too high: {gas_price_gwei} gwei"
            
            # Build the swap transaction
            deadline = int((datetime.now() + timedelta(minutes=20)).timestamp())
            
            # Use swapExactETHForTokens like Uniswap interface does (more reliable)
            swap_params = {
                'amountOutMin': min_pepe_wei,  # Minimum tokens to receive
                'path': [WETH_ADDRESS, PEPE_ADDRESS],  # ETH -> WETH -> PEPE path
                'to': self.account.address,  # Recipient
                'deadline': deadline
            }
            
            logger.info(f"Swap params - Path: ETH->WETH->PEPE, AmountIn: {get_w3().to_wei(safe_eth_amount, 'ether')}, AmountOutMin: {min_pepe_wei}")
            
            # Build transaction using swapExactETHForTokens
            transaction = self.router_contract.functions.swapExactETHForTokens(
                swap_params['amountOutMin'],
                swap_params['path'],
                swap_params['to'],
                swap_params['deadline']
            ).build_transaction({
                'from': self.account.address,
                'value': get_w3().to_wei(safe_eth_amount, 'ether'),  # Send ETH with transaction
                'gasPrice': gas_price,
                'nonce': nonce
            })
            
            # Estimate gas like MetaMask does
            try:
                estimated_gas = self.router_contract.functions.swapExactETHForTokens(
                    swap_params['amountOutMin'],
                    swap_params['path'],
                    swap_params['to'],
                    swap_params['deadline']
                ).estimate_gas({
                    'from': self.account.address,
                    'value': get_w3().to_wei(safe_eth_amount, 'ether')
                })
                # Add 20% buffer for safety
                transaction['gas'] = int(estimated_gas * 1.2)
                logger.info(f"Estimated gas: {estimated_gas}, Using: {transaction['gas']}")
            except Exception as gas_error:
                logger.warning(f"Gas estimation failed, using default: {gas_error}")
                transaction['gas'] = 300000  # Fallback to default
            
            # Sign and send transaction
            signed_txn = self.account.sign_transaction(transaction)
            raw_transaction = signed_txn.rawTransaction if hasattr(signed_txn, 'rawTransaction') else signed_txn.raw_transaction
            tx_hash = get_w3().eth.send_raw_transaction(raw_transaction)
            
            logger.info(f"Transaction sent: {tx_hash.hex()}")
            
            # Wait for transaction confirmation
            receipt = get_w3().eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if receipt.status == 1:
                # Check if the swap actually occurred by looking for transfer events
                swap_occurred = False
                for log in receipt.logs:
                    # Look for Transfer events to PEPE address
                    # Transfer event signature: 0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
                    if len(log.topics) > 0 and log.topics[0].hex() == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef':
                        # This is a Transfer event - check if it's to our address
                        if len(log.topics) >= 3:
                            # topics[1] = from address, topics[2] = to address
                            to_address = '0x' + log.topics[2].hex()[-40:]  # Remove padding
                            if to_address.lower() == self.account.address.lower():
                                swap_occurred = True
                                logger.info(f"Found Transfer event to our address: {to_address}")
                                break
                
                if swap_occurred:
                    logger.info(f"BUY order executed successfully: {tx_hash.hex()}")
                    self.risk_manager.update_trade_metrics(safe_eth_amount)
                    return True, f"Buy order executed: {tx_hash.hex()}"
                else:
                    # Additional check: verify PEPE balance increased
                    try:
                        await asyncio.sleep(2)  # Wait a bit for blockchain to update
                        new_pepe_balance = await get_token_balance(PEPE_ADDRESS, self.account.address)
                        if new_pepe_balance > 0:
                            logger.info(f"BUY order executed successfully (balance check): {tx_hash.hex()}")
                            logger.info(f"PEPE balance: {new_pepe_balance}")
                            self.risk_manager.update_trade_metrics(safe_eth_amount)
                            return True, f"Buy order executed: {tx_hash.hex()}"
                    except Exception as balance_error:
                        logger.warning(f"Balance check failed: {balance_error}")
                    
                    logger.error(f"Transaction succeeded but NO SWAP OCCURRED: {tx_hash.hex()}")
                    logger.error(f"Gas used: {receipt.gasUsed}, Logs: {len(receipt.logs)}")
                    return False, f"Transaction succeeded but swap failed - no PEPE received: {tx_hash.hex()}"
            else:
                return False, f"Transaction failed: {tx_hash.hex()}"
                
        except Exception as e:
            logger.error(f"Error executing buy order: {e}")
            return False, f"Buy order failed: {str(e)}"
    
    async def execute_sell_order(self, pepe_amount: float, current_price: float) -> Tuple[bool, str]:
        """
        Execute a sell order (PEPE -> ETH)
        Returns (success, message)
        """
        if not self.account:
            return False, "No account configured for live trading"
        
        try:
            # Calculate ETH value for validation
            eth_value = pepe_amount * current_price
            
            # Validate the trade
            is_valid, error_msg = await self.risk_manager.validate_trade_signal("SELL", eth_value, current_price)
            if not is_valid:
                return False, error_msg
            
            # Calculate minimum ETH to receive (with slippage protection)
            min_eth_amount = eth_value * (1 - SLIPPAGE_TOLERANCE)
            
            # Get current nonce
            nonce = get_w3().eth.get_transaction_count(self.account.address)
            
            # Get gas price
            gas_price = get_w3().eth.gas_price
            gas_price_gwei = get_w3().from_wei(gas_price, 'gwei')
            
            if gas_price_gwei > MAX_GAS_PRICE_GWEI:
                return False, f"Gas price too high: {gas_price_gwei} gwei"
            
            # First, approve PEPE spending
            approve_txn = self.pepe_contract.functions.approve(
                UNISWAP_ROUTER_ADDRESS,
                get_w3().to_wei(pepe_amount, 'ether')
            ).build_transaction({
                'from': self.account.address,
                'gas': 100000,
                'gasPrice': gas_price,
                'nonce': nonce
            })
            
            signed_approve = self.account.sign_transaction(approve_txn)
            # Fix for newer Web3.py versions
            raw_approve = signed_approve.rawTransaction if hasattr(signed_approve, 'rawTransaction') else signed_approve.raw_transaction
            approve_hash = get_w3().eth.send_raw_transaction(raw_approve)
            get_w3().eth.wait_for_transaction_receipt(approve_hash, timeout=300)
            
            # Build the swap transaction using Uniswap V2 router
            deadline = int((datetime.now() + timedelta(minutes=20)).timestamp())
            
            # Use swapExactTokensForTokens for PEPE -> ETH (Uniswap V2)
            swap_params = {
                'amountIn': get_w3().to_wei(pepe_amount, 'ether'),
                'amountOutMin': get_w3().to_wei(min_eth_amount, 'ether'),
                'path': [PEPE_ADDRESS, WETH_ADDRESS],  # PEPE -> WETH path
                'to': self.account.address,
                'deadline': deadline
            }
            
            # Build transaction using Uniswap V2 router
            transaction = self.router_contract.functions.swapExactTokensForTokens(
                swap_params['amountIn'],
                swap_params['amountOutMin'],
                swap_params['path'],
                swap_params['to'],
                swap_params['deadline']
            ).build_transaction({
                'from': self.account.address,
                'value': 0,  # No ETH sent for token->token swap
                'gas': 300000,
                'gasPrice': gas_price,
                'nonce': nonce + 1
            })
            
            # Sign and send transaction
            signed_txn = self.account.sign_transaction(transaction)
            raw_transaction = signed_txn.rawTransaction if hasattr(signed_txn, 'rawTransaction') else signed_txn.raw_transaction
            tx_hash = get_w3().eth.send_raw_transaction(raw_transaction)
            
            # Wait for transaction confirmation
            receipt = get_w3().eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if receipt.status == 1:
                logger.info(f"SELL order executed successfully: {tx_hash.hex()}")
                self.risk_manager.update_trade_metrics(eth_value)
                return True, f"Sell order executed: {tx_hash.hex()}"
            else:
                return False, f"Transaction failed: {tx_hash.hex()}"
                
        except Exception as e:
            logger.error(f"Error executing sell order: {e}")
            return False, f"Sell order failed: {str(e)}"
    
    async def get_transaction_status(self, tx_hash: str) -> str:
        """Get the status of a transaction."""
        try:
            receipt = get_w3().eth.get_transaction_receipt(tx_hash)
            if receipt is None:
                return "pending"
            return "confirmed" if receipt.status == 1 else "failed"
        except Exception as e:
            logger.error(f"Error getting transaction status: {e}")
            return "unknown"

    async def check_pool_liquidity(self, pool_address: str) -> bool:
        """Check if a pool has sufficient liquidity for trading."""
        try:
            pool_contract = get_w3().eth.contract(
                address=get_w3().to_checksum_address(pool_address),
                abi=[{"inputs":[],"name":"slot0","outputs":[{"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"},{"internalType":"int24","name":"tick","type":"int24"},{"internalType":"uint16","name":"observationIndex","type":"uint16"},{"internalType":"uint16","name":"observationCardinality","type":"uint16"},{"internalType":"uint16","name":"observationCardinalityNext","type":"uint16"},{"internalType":"uint8","name":"feeProtocol","type":"uint8"},{"internalType":"bool","name":"unlocked","type":"bool"}],"stateMutability":"view","type":"function"}]
            )
            
            slot0 = pool_contract.functions.slot0().call()
            sqrtPriceX96 = slot0[0]
            
            # If we can get a price, the pool has some liquidity
            if sqrtPriceX96 > 0:
                return True
            return False
        except Exception as e:
            logger.warning(f"Error checking pool liquidity for {pool_address}: {e}")
            return False

    async def get_best_pool(self) -> str:
        """Get the best pool with sufficient liquidity."""
        pools = [
            (PEPE_WETH_POOL_ADDRESS, 3000),      # 0.3% fee
            (PEPE_WETH_POOL_1PERCENT, 10000),    # 1% fee
            (PEPE_WETH_POOL_005PERCENT, 500)     # 0.05% fee
        ]
        
        for pool_addr, fee in pools:
            if await self.check_pool_liquidity(pool_addr):
                logger.info(f"Selected pool {pool_addr} with fee {fee}")
                return pool_addr, fee
        
        # Fallback to default pool
        logger.warning("No pool with sufficient liquidity found, using default")
        return PEPE_WETH_POOL_ADDRESS, 3000 