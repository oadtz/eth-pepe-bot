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
    MAX_GAS_PRICE_GWEI
)

logger = logging.getLogger(__name__)

# Uniswap V3 Router ABI (simplified for swapExactInputSingle)
UNISWAP_V3_ROUTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "address", "name": "recipient", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
                ],
                "internalType": "struct ISwapRouter.ExactInputSingleParams",
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "exactInputSingle",
        "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    }
]

# WETH ABI for wrapping/unwrapping ETH
WETH_ABI = [
    {"constant": False, "inputs": [], "name": "deposit", "outputs": [], "type": "function"},
    {"constant": False, "inputs": [{"name": "wad", "type": "uint256"}], "name": "withdraw", "outputs": [], "type": "function"},
    {"constant": True, "inputs": [{"name": "owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "spender", "type": "address"}, {"name": "value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
]

class LiveTrader:
    def __init__(self, w3: Web3, risk_manager):
        self.w3 = w3
        self.risk_manager = risk_manager
        self.account = None
        self.router_contract = None
        self.weth_contract = None
        self.pepe_contract = None
        
        if not w3.is_connected():
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
            self.router_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(UNISWAP_ROUTER_ADDRESS),
                abi=UNISWAP_V3_ROUTER_ABI
            )
            self.weth_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(WETH_ADDRESS),
                abi=WETH_ABI
            )
            self.pepe_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(PEPE_ADDRESS),
                abi=WETH_ABI  # Using same ABI for ERC20 functions
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
            
            # Calculate minimum PEPE to receive (with slippage protection)
            min_pepe_amount = (eth_amount / current_price) * (1 - SLIPPAGE_TOLERANCE)
            
            # Get current nonce
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            
            # Get gas price
            gas_price = self.w3.eth.gas_price
            gas_price_gwei = self.w3.from_wei(gas_price, 'gwei')
            
            if gas_price_gwei > MAX_GAS_PRICE_GWEI:
                return False, f"Gas price too high: {gas_price_gwei} gwei"
            
            # Build the swap transaction
            deadline = int((datetime.now() + timedelta(minutes=20)).timestamp())
            
            swap_params = {
                'tokenIn': WETH_ADDRESS,
                'tokenOut': PEPE_ADDRESS,
                'fee': 3000,  # 0.3% fee tier
                'recipient': self.account.address,
                'deadline': deadline,
                'amountIn': self.w3.to_wei(eth_amount, 'ether'),
                'amountOutMinimum': self.w3.to_wei(min_pepe_amount, 'ether'),
                'sqrtPriceLimitX96': 0
            }
            
            # Build transaction
            transaction = self.router_contract.functions.exactInputSingle(swap_params).build_transaction({
                'from': self.account.address,
                'value': self.w3.to_wei(eth_amount, 'ether'),  # Send ETH with transaction
                'gas': 300000,
                'gasPrice': gas_price,
                'nonce': nonce
            })
            
            # Sign and send transaction
            signed_txn = self.account.sign_transaction(transaction)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if receipt.status == 1:
                logger.info(f"BUY order executed successfully: {tx_hash.hex()}")
                self.risk_manager.update_trade_metrics(eth_amount)
                return True, f"Buy order executed: {tx_hash.hex()}"
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
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            
            # Get gas price
            gas_price = self.w3.eth.gas_price
            gas_price_gwei = self.w3.from_wei(gas_price, 'gwei')
            
            if gas_price_gwei > MAX_GAS_PRICE_GWEI:
                return False, f"Gas price too high: {gas_price_gwei} gwei"
            
            # First, approve PEPE spending
            approve_txn = self.pepe_contract.functions.approve(
                UNISWAP_ROUTER_ADDRESS,
                self.w3.to_wei(pepe_amount, 'ether')
            ).build_transaction({
                'from': self.account.address,
                'gas': 100000,
                'gasPrice': gas_price,
                'nonce': nonce
            })
            
            signed_approve = self.account.sign_transaction(approve_txn)
            approve_hash = self.w3.eth.send_raw_transaction(signed_approve.rawTransaction)
            self.w3.eth.wait_for_transaction_receipt(approve_hash, timeout=300)
            
            # Build the swap transaction
            deadline = int((datetime.now() + timedelta(minutes=20)).timestamp())
            
            swap_params = {
                'tokenIn': PEPE_ADDRESS,
                'tokenOut': WETH_ADDRESS,
                'fee': 3000,  # 0.3% fee tier
                'recipient': self.account.address,
                'deadline': deadline,
                'amountIn': self.w3.to_wei(pepe_amount, 'ether'),
                'amountOutMinimum': self.w3.to_wei(min_eth_amount, 'ether'),
                'sqrtPriceLimitX96': 0
            }
            
            # Build transaction
            transaction = self.router_contract.functions.exactInputSingle(swap_params).build_transaction({
                'from': self.account.address,
                'value': 0,  # No ETH sent for token->token swap
                'gas': 300000,
                'gasPrice': gas_price,
                'nonce': nonce + 1
            })
            
            # Sign and send transaction
            signed_txn = self.account.sign_transaction(transaction)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
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
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            if receipt is None:
                return "pending"
            return "confirmed" if receipt.status == 1 else "failed"
        except Exception as e:
            logger.error(f"Error getting transaction status: {e}")
            return "unknown" 