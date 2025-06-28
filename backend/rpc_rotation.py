"""
RPC Rotation Module
Handles automatic switching between multiple RPC providers to avoid rate limits
"""

import logging
import asyncio
from typing import Optional, List
from web3 import Web3
from web3.exceptions import Web3Exception, TimeExhausted
from config import RPC_PROVIDERS

logger = logging.getLogger(__name__)

class RPCRotation:
    def __init__(self):
        self.providers = RPC_PROVIDERS
        self.current_index = 0
        self.failed_providers = set()
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        
    def get_current_provider(self) -> str:
        """Get the current RPC provider URL."""
        return self.providers[self.current_index]
    
    def rotate_provider(self):
        """Rotate to the next available RPC provider."""
        self.current_index = (self.current_index + 1) % len(self.providers)
        logger.info(f"Rotated to RPC provider {self.current_index + 1}/{len(self.providers)}: {self.get_current_provider()}")
    
    def mark_provider_failed(self, provider_url: str):
        """Mark a provider as failed (rate limited or down)."""
        if provider_url in self.providers:
            self.failed_providers.add(provider_url)
            logger.warning(f"Marked RPC provider as failed: {provider_url}")
            
            # If current provider failed, rotate to next
            if provider_url == self.get_current_provider():
                self.rotate_provider()
    
    def reset_failed_providers(self):
        """Reset failed providers list (called periodically)."""
        if self.failed_providers:
            logger.info(f"Resetting {len(self.failed_providers)} failed RPC providers")
            self.failed_providers.clear()
    
    async def execute_with_rotation(self, func, *args, **kwargs):
        """
        Execute a function with automatic RPC rotation on failures.
        
        Args:
            func: Function to execute (should accept web3 instance)
            *args, **kwargs: Arguments to pass to func
            
        Returns:
            Result of func execution
            
        Raises:
            Exception: If all providers fail
        """
        last_error = None
        
        for attempt in range(self.max_retries * len(self.providers)):
            try:
                # Create Web3 instance with current provider
                provider_url = self.get_current_provider()
                web3 = Web3(Web3.HTTPProvider(provider_url))
                
                if not web3.is_connected():
                    raise Web3Exception(f"Failed to connect to {provider_url}")
                
                # Execute the function
                result = func(web3, *args, **kwargs)
                
                # If we get here, the call succeeded
                logger.debug(f"Successfully executed with provider {self.current_index + 1}")
                return result
                
            except (Web3Exception, TimeExhausted, Exception) as e:
                last_error = e
                error_msg = str(e).lower()
                
                # Check if it's a rate limit error
                is_rate_limit = any(phrase in error_msg for phrase in [
                    '429', 'too many requests', 'rate limit', 'quota exceeded'
                ])
                
                if is_rate_limit:
                    logger.warning(f"Rate limit hit on provider {self.current_index + 1}: {provider_url}")
                    self.mark_provider_failed(provider_url)
                else:
                    logger.warning(f"Provider {self.current_index + 1} failed: {e}")
                    self.mark_provider_failed(provider_url)
                
                # Wait before retry
                await asyncio.sleep(self.retry_delay)
        
        # All providers failed
        logger.error(f"All RPC providers failed after {self.max_retries * len(self.providers)} attempts")
        raise last_error or Exception("All RPC providers failed")

# Global RPC rotation instance
rpc_rotation = RPCRotation()

def get_web3_with_rotation() -> Web3:
    """Get a Web3 instance with the current RPC provider."""
    provider_url = rpc_rotation.get_current_provider()
    return Web3(Web3.HTTPProvider(provider_url))

async def execute_rpc_call(func, *args, **kwargs):
    """Execute an RPC call with automatic rotation."""
    return await rpc_rotation.execute_with_rotation(func, *args, **kwargs) 