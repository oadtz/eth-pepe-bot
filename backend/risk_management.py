import logging
from typing import Optional, Tuple
from web3 import Web3
from datetime import datetime, timedelta
from config import (
    MAX_TRADE_SIZE_ETH,
    EMERGENCY_STOP_LOSS,
    GAS_LIMIT_MULTIPLIER,
    SLIPPAGE_TOLERANCE,
    WALLET_ADDRESS,
    PEPE_ADDRESS,
    WETH_ADDRESS,
    MAX_DAILY_TRADES,
    MAX_DAILY_VOLUME_ETH,
    MAX_GAS_PRICE_GWEI
)

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, w3: Web3):
        self.w3 = w3
        self.last_trade_time = None
        self.daily_trade_count = 0
        self.daily_volume_eth = 0.0
        self.reset_daily_counters()
    
    def reset_daily_counters(self):
        """Reset daily trading counters at midnight."""
        now = datetime.now()
        if self.last_trade_time is None or now.date() > self.last_trade_time.date():
            self.daily_trade_count = 0
            self.daily_volume_eth = 0.0
            logger.info("Daily trading counters reset")
    
    async def validate_trade_signal(self, signal: str, amount_eth: float, current_price: float) -> Tuple[bool, str]:
        """
        Comprehensive validation of a trade signal before execution.
        Returns (is_valid, error_message)
        """
        if not signal in ["BUY", "SELL"]:
            return False, f"Invalid signal: {signal}"
        
        # Check if live trading is enabled
        if not getattr(self, 'live_trading_enabled', False):
            return False, "Live trading is disabled"
        
        # Validate trade amount
        if amount_eth <= 0:
            return False, "Trade amount must be positive"
        
        if amount_eth > MAX_TRADE_SIZE_ETH:
            return False, f"Trade amount {amount_eth} ETH exceeds maximum {MAX_TRADE_SIZE_ETH} ETH"
        
        # Check wallet balance
        try:
            eth_balance = await self.get_eth_balance(WALLET_ADDRESS)
            if signal == "BUY" and amount_eth > eth_balance:
                return False, f"Insufficient ETH balance. Required: {amount_eth}, Available: {eth_balance}"
        except Exception as e:
            return False, f"Failed to check ETH balance: {e}"
        
        # Check token balance for sell orders
        if signal == "SELL":
            try:
                pepe_balance = await self.get_token_balance(PEPE_ADDRESS, WALLET_ADDRESS)
                pepe_amount = amount_eth / current_price
                if pepe_amount > pepe_balance:
                    return False, f"Insufficient PEPE balance. Required: {pepe_amount}, Available: {pepe_balance}"
            except Exception as e:
                return False, f"Failed to check PEPE balance: {e}"
        
        # Rate limiting checks (more lenient for aggressive trading)
        self.reset_daily_counters()
        if self.daily_trade_count >= MAX_DAILY_TRADES:
            return False, "Daily trade limit reached"
        
        if self.daily_volume_eth + amount_eth > MAX_DAILY_VOLUME_ETH:
            return False, "Daily volume limit would be exceeded"
        
        # Gas price validation (more lenient)
        try:
            gas_price = self.w3.eth.gas_price
            gas_price_gwei = self.w3.from_wei(gas_price, 'gwei')
            if gas_price_gwei > MAX_GAS_PRICE_GWEI:
                return False, f"Gas price too high: {gas_price_gwei} gwei"
        except Exception as e:
            return False, f"Failed to check gas price: {e}"
        
        # Price volatility check (disabled for aggressive trading)
        # if not await self.check_price_stability(current_price):
        #     return False, "Price volatility too high for safe trading"
        
        return True, "Trade validation passed"
    
    async def check_price_stability(self, current_price: float) -> bool:
        """Check if price is stable enough for trading."""
        # This would implement price volatility checks
        # For now, return True - implement based on your requirements
        return True
    
    async def get_eth_balance(self, address: str) -> float:
        """Get ETH balance for an address."""
        try:
            balance_wei = self.w3.eth.get_balance(self.w3.to_checksum_address(address))
            return self.w3.from_wei(balance_wei, 'ether')
        except Exception as e:
            logger.error(f"Error getting ETH balance: {e}")
            raise
    
    async def get_token_balance(self, token_address: str, address: str) -> float:
        """Get token balance for an address."""
        try:
            # Simplified ERC20 balance check
            erc20_abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
            token_contract = self.w3.eth.contract(address=self.w3.to_checksum_address(token_address), abi=erc20_abi)
            balance_wei = token_contract.functions.balanceOf(self.w3.to_checksum_address(address)).call()
            return self.w3.from_wei(balance_wei, 'ether')
        except Exception as e:
            logger.error(f"Error getting token balance: {e}")
            raise
    
    def update_trade_metrics(self, amount_eth: float):
        """Update trading metrics after a successful trade."""
        self.last_trade_time = datetime.now()
        self.daily_trade_count += 1
        self.daily_volume_eth += amount_eth
        logger.info(f"Trade metrics updated - Daily count: {self.daily_trade_count}, Volume: {self.daily_volume_eth} ETH")
    
    async def emergency_stop_check(self, portfolio_value: float, initial_value: float) -> bool:
        """Check if emergency stop loss has been triggered."""
        if initial_value <= 0:
            return False
        
        loss_percentage = (initial_value - portfolio_value) / initial_value
        if loss_percentage >= EMERGENCY_STOP_LOSS:
            logger.critical(f"EMERGENCY STOP LOSS TRIGGERED: {loss_percentage:.2%} loss")
            return True
        
        return False 