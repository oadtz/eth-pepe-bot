import asyncio
import logging
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
import uuid
from decimal import Decimal

from trading_logic import get_trading_signal, get_eth_balance, get_token_balance, get_w3
from config import (
    WALLET_ADDRESS,
    PRIVATE_KEY,
    PEPE_ADDRESS,
    WETH_ADDRESS,
    LIVE_TRADING_ENABLED,
    TRADE_PERCENTAGE,
    EMERGENCY_STOP_RECOVERY_ENABLED,
    EMERGENCY_STOP_RECOVERY_THRESHOLD,
    EMERGENCY_STOP_RECOVERY_WAIT_HOURS
)
from database import init_db, SessionLocal, SimulatedTrade, PortfolioState, LiveTrade, TradingSession, RiskEvent
from risk_management import RiskManager
from live_trading import LiveTrader

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variables for session tracking
current_session = None
risk_manager = None
live_trader = None

def convert_to_float(value):
    """Convert decimal or other numeric types to float."""
    if isinstance(value, Decimal):
        return float(value)
    elif value is None:
        return 0.0
    else:
        return float(value)

async def execute_simulated_trade(signal: str, current_pepe_price_eth: float, db: Session):
    """Executes a simulated trade based on the signal and updates balances in DB."""
    current_state = db.query(PortfolioState).filter(PortfolioState.id == "current_state").first()
    if not current_state:
        logger.error("Portfolio state not found in DB. Cannot execute trade.")
        return

    eth_balance_simulated = current_state.eth_balance
    pepe_balance_simulated = current_state.pepe_balance

    if current_pepe_price_eth == 0:
        logger.warning("Current PEPE price is zero, cannot execute simulated trade.")
        return

    eth_amount_traded = 0.0
    pepe_amount_traded = 0.0

    if signal == "BUY":
        eth_to_spend = eth_balance_simulated * TRADE_PERCENTAGE
        if eth_to_spend > 0:
            pepe_received = eth_to_spend / current_pepe_price_eth
            current_state.eth_balance -= eth_to_spend
            current_state.pepe_balance += pepe_received
            eth_amount_traded = eth_to_spend
            pepe_amount_traded = pepe_received
            logger.info(f"SIMULATED BUY: Spent {eth_to_spend:.6f} ETH, Received {pepe_received:.6f} PEPE")
    elif signal == "SELL":
        pepe_to_sell = pepe_balance_simulated * TRADE_PERCENTAGE
        if pepe_to_sell > 0:
            eth_received = pepe_to_sell * current_pepe_price_eth
            current_state.pepe_balance -= pepe_to_sell
            current_state.eth_balance += eth_received
            eth_amount_traded = eth_received
            pepe_amount_traded = pepe_to_sell
            logger.info(f"SIMULATED SELL: Sold {pepe_to_sell:.6f} PEPE, Received {eth_received:.6f} ETH")

    # Save updated simulated balances to DB
    current_state.last_updated = datetime.now(timezone.utc)
    db.add(current_state)
    db.commit()
    db.refresh(current_state)

    # Log trade to DB
    if signal in ["BUY", "SELL"] and (eth_amount_traded > 0 or pepe_amount_traded > 0):
        trade_log = SimulatedTrade(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            signal=signal,
            eth_amount=eth_amount_traded if signal == "BUY" else -eth_amount_traded, # Positive for buy, negative for sell
            pepe_amount=pepe_amount_traded if signal == "BUY" else -pepe_amount_traded, # Positive for buy, negative for sell
            eth_balance_after=current_state.eth_balance,
            pepe_balance_after=current_state.pepe_balance,
            price_at_trade=current_pepe_price_eth,
            profit_loss_eth=0.0 # This will be calculated based on trade history later
        )
        db.add(trade_log)
        db.commit()
        db.refresh(trade_log)

async def execute_live_trade(signal: str, current_pepe_price_eth: float, db: Session):
    """Executes a live trade on the blockchain."""
    global live_trader, risk_manager, current_session
    
    if not live_trader:
        logger.error("Live trader not initialized")
        return
    
    try:
        # Check current PEPE balance for position management
        current_pepe_balance = await get_token_balance(PEPE_ADDRESS, WALLET_ADDRESS)
        
        # Calculate trade amount
        if signal == "BUY":
            # POSITION MANAGEMENT: Don't buy if already holding significant PEPE
            if current_pepe_balance > 0:
                logger.info(f"BUY signal ignored: Already holding {current_pepe_balance:.0f} PEPE tokens")
                return
            
            eth_amount = await get_eth_balance(WALLET_ADDRESS)
            trade_amount = eth_amount * TRADE_PERCENTAGE
            
            # Execute buy order
            success, message = await live_trader.execute_buy_order(trade_amount, current_pepe_price_eth)
            
            if success:
                logger.info(f"LIVE BUY executed: {message}")
                # Update session metrics
                if current_session:
                    current_session.total_trades += 1
                    current_session.successful_trades += 1
                    current_session.total_volume_eth += trade_amount
                    db.add(current_session)
                    db.commit()
            else:
                logger.error(f"LIVE BUY failed: {message}")
                if current_session:
                    current_session.total_trades += 1
                    current_session.failed_trades += 1
                    db.add(current_session)
                    db.commit()
                
                # Log risk event
                risk_event = RiskEvent(
                    id=str(uuid.uuid4()),
                    event_type="trade_failure",
                    severity="high",
                    description=f"Buy order failed: {message}",
                    action_taken="none"
                )
                db.add(risk_event)
                db.commit()
                
        elif signal == "SELL":
            pepe_balance = await get_token_balance(PEPE_ADDRESS, WALLET_ADDRESS)
            
            # Check if we have PEPE to sell
            if pepe_balance <= 0:
                logger.warning(f"SELL signal ignored: No PEPE balance to sell (balance: {pepe_balance})")
                return
            
            trade_amount = pepe_balance  # AGGRESSIVE SELL: Sell 100% of PEPE tokens
            
            # Execute sell order
            success, message = await live_trader.execute_sell_order(trade_amount, current_pepe_price_eth)
            
            if success:
                logger.info(f"LIVE SELL executed: {message}")
                # Update session metrics
                if current_session:
                    current_session.total_trades += 1
                    current_session.successful_trades += 1
                    current_session.total_volume_eth += (trade_amount * current_pepe_price_eth)
                    db.add(current_session)
                    db.commit()
            else:
                logger.error(f"LIVE SELL failed: {message}")
                if current_session:
                    current_session.total_trades += 1
                    current_session.failed_trades += 1
                    db.add(current_session)
                    db.commit()
                
                # Log risk event
                risk_event = RiskEvent(
                    id=str(uuid.uuid4()),
                    event_type="trade_failure",
                    severity="high",
                    description=f"Sell order failed: {message}",
                    action_taken="none"
                )
                db.add(risk_event)
                db.commit()
                
    except Exception as e:
        logger.error(f"Error executing live trade: {e}")
        # Log risk event
        risk_event = RiskEvent(
            id=str(uuid.uuid4()),
            event_type="system_error",
            severity="critical",
            description=f"Live trade execution error: {str(e)}",
            action_taken="none"
        )
        db.add(risk_event)
        db.commit()

async def initialize_live_trading():
    """Initialize live trading components."""
    global risk_manager, live_trader, current_session
    
    # Wait for Web3 to be connected (with retry)
    max_retries = 10
    retry_count = 0
    
    while retry_count < max_retries:
        if get_w3() and get_w3().is_connected():
            break
        logger.info(f"Waiting for Web3 connection... (attempt {retry_count + 1}/{max_retries})")
        await asyncio.sleep(3)
        retry_count += 1
    
    if not get_w3() or not get_w3().is_connected():
        logger.error("Web3 not connected after retries - cannot initialize live trading")
        return False
    
    try:
        # Initialize risk manager
        risk_manager = RiskManager()
        risk_manager.live_trading_enabled = True  # Set to True since we're initializing live trading
        
        # Initialize live trader
        live_trader = LiveTrader(risk_manager)
        
        # Create trading session
        db = SessionLocal()
        try:
            current_session = TradingSession(
                id=str(uuid.uuid4()),
                mode="live",
                initial_eth_balance=await get_eth_balance(WALLET_ADDRESS)
            )
            db.add(current_session)
            db.commit()
            logger.info(f"Live trading initialized. Mode: {current_session.mode}")
            return True
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to initialize live trading: {e}")
        return False

async def main_bot_loop():
    logger.info("Starting bot main loop...")
    
    # Get initial wallet balance for profit/loss calculations
    initial_eth_balance = convert_to_float(await get_eth_balance(WALLET_ADDRESS))
    logger.info(f"Initial ETH balance detected: {initial_eth_balance:.6f} ETH")
    
    # Initialize database with actual wallet balance
    init_db(initial_eth_balance)

    # Track if live trading is actually enabled
    live_trading_active = LIVE_TRADING_ENABLED
    emergency_stop_triggered = False
    emergency_stop_time = None
    emergency_stop_portfolio_value = None

    # Initialize live trading if enabled
    if live_trading_active:
        if not await initialize_live_trading():
            logger.error("Failed to initialize live trading. Falling back to simulation mode.")
            live_trading_active = False

    # Get a DB session for the loop
    db = SessionLocal()
    try:
        while True:
            logger.info("--- Bot Cycle Start ---")
            signal = "HOLD"
            current_pepe_price_eth = 0.0

            try:
                signal, current_pepe_price_eth = await get_trading_signal()
                
                # Execute trade based on mode and emergency stop status
                if live_trading_active and not emergency_stop_triggered and signal in ["BUY", "SELL"]:
                    # Check if Web3 is connected before attempting live trade
                    if get_w3() and get_w3().is_connected():
                        await execute_live_trade(signal, current_pepe_price_eth, db)
                    else:
                        logger.warning("Web3 not connected - skipping live trade, falling back to simulation")
                        await execute_simulated_trade(signal, current_pepe_price_eth, db)
                elif signal in ["BUY", "SELL"] and not emergency_stop_triggered:
                    await execute_simulated_trade(signal, current_pepe_price_eth, db)
                elif emergency_stop_triggered and signal in ["BUY", "SELL"]:
                    logger.warning(f"EMERGENCY STOP ACTIVE - Skipping {signal} signal")
                    
            except Exception as e:
                logger.error(f"Error during bot cycle: {e}")
                signal = "ERROR"

            # Fetch and log current metrics
            current_state = db.query(PortfolioState).filter(PortfolioState.id == "current_state").first()
            if current_state:
                # Fetch actual wallet balances
                actual_eth_balance = convert_to_float(await get_eth_balance(WALLET_ADDRESS))
                actual_pepe_balance = convert_to_float(await get_token_balance(PEPE_ADDRESS, WALLET_ADDRESS))

                # Calculate portfolio values
                if live_trading_active:
                    # Use actual balances for live trading
                    current_portfolio_value_eth = actual_eth_balance + (actual_pepe_balance * current_pepe_price_eth)
                    profit_loss_eth = current_portfolio_value_eth - initial_eth_balance
                else:
                    # Use simulated balances for simulation mode
                    current_portfolio_value_eth = current_state.eth_balance + (current_state.pepe_balance * current_pepe_price_eth)
                    profit_loss_eth = current_portfolio_value_eth - initial_eth_balance

                logger.info(f"Current Signal: {signal}")
                logger.info(f"Actual ETH Balance: {actual_eth_balance:.6f}")
                logger.info(f"Actual PEPE Balance: {actual_pepe_balance:.6f}")
                logger.info(f"Portfolio Value (ETH): {current_portfolio_value_eth:.6f}")
                logger.info(f"Profit/Loss (ETH): {profit_loss_eth:.6f}")
                logger.info(f"Trading Mode: {'LIVE' if live_trading_active else 'SIMULATION'}")
                if emergency_stop_triggered:
                    logger.warning("EMERGENCY STOP ACTIVE - Trading paused")
                
                # Check emergency stop loss
                if live_trading_active and risk_manager and not emergency_stop_triggered:
                    if await risk_manager.emergency_stop_check(current_portfolio_value_eth, initial_eth_balance):
                        logger.critical("EMERGENCY STOP LOSS TRIGGERED - PAUSING TRADING")
                        emergency_stop_triggered = True
                        emergency_stop_time = datetime.now(timezone.utc)
                        emergency_stop_portfolio_value = current_portfolio_value_eth
                        
                        # Update session with emergency stop
                        if current_session:
                            current_session.emergency_stop_triggered = True
                            db.add(current_session)
                            db.commit()
                        
                        # Log risk event
                        risk_event = RiskEvent(
                            id=str(uuid.uuid4()),
                            event_type="emergency_stop",
                            severity="critical",
                            description=f"Emergency stop loss triggered: {((initial_eth_balance - current_portfolio_value_eth) / initial_eth_balance * 100):.2f}% loss",
                            action_taken="trading_paused"
                        )
                        db.add(risk_event)
                        db.commit()
                
                # Check for recovery conditions
                if emergency_stop_triggered and EMERGENCY_STOP_RECOVERY_ENABLED:
                    time_since_emergency_stop = datetime.now(timezone.utc) - emergency_stop_time
                    hours_since_emergency_stop = time_since_emergency_stop.total_seconds() / 3600
                    
                    # Check if enough time has passed and portfolio has recovered
                    if (hours_since_emergency_stop >= EMERGENCY_STOP_RECOVERY_WAIT_HOURS and 
                        emergency_stop_portfolio_value and 
                        current_portfolio_value_eth > emergency_stop_portfolio_value * (1 + EMERGENCY_STOP_RECOVERY_THRESHOLD)):
                        
                        logger.info("EMERGENCY STOP RECOVERY CONDITIONS MET - RESUMING TRADING")
                        emergency_stop_triggered = False
                        emergency_stop_time = None
                        emergency_stop_portfolio_value = None
                        
                        # Update session
                        if current_session:
                            current_session.emergency_stop_triggered = False
                            db.add(current_session)
                            db.commit()
                        
                        # Log recovery event
                        recovery_event = RiskEvent(
                            id=str(uuid.uuid4()),
                            event_type="emergency_stop_recovery",
                            severity="medium",
                            description=f"Emergency stop recovery: Portfolio recovered {((current_portfolio_value_eth - emergency_stop_portfolio_value) / emergency_stop_portfolio_value * 100):.2f}% after {hours_since_emergency_stop:.1f} hours",
                            action_taken="trading_resumed"
                        )
                        db.add(recovery_event)
                        db.commit()
                    elif hours_since_emergency_stop < EMERGENCY_STOP_RECOVERY_WAIT_HOURS:
                        remaining_hours = EMERGENCY_STOP_RECOVERY_WAIT_HOURS - hours_since_emergency_stop
                        logger.info(f"Emergency stop active - {remaining_hours:.1f} hours remaining before recovery check")
                    elif emergency_stop_portfolio_value:
                        recovery_needed = emergency_stop_portfolio_value * EMERGENCY_STOP_RECOVERY_THRESHOLD
                        current_recovery = current_portfolio_value_eth - emergency_stop_portfolio_value
                        logger.info(f"Emergency stop active - Need {recovery_needed:.6f} ETH recovery, current: {current_recovery:.6f} ETH")
                
            else:
                logger.error("Could not retrieve portfolio state for logging.")

            logger.info("--- Bot Cycle End ---")
            await asyncio.sleep(3) # Wait for 3 seconds before next cycle (ULTRA AGGRESSIVE DAY TRADING)

    finally:
        # End trading session
        if current_session:
            current_session.end_time = datetime.now(timezone.utc)
            current_session.final_eth_balance = convert_to_float(await get_eth_balance(WALLET_ADDRESS))
            db.add(current_session)
            db.commit()
            logger.info("Trading session ended")
        
        db.close()

if __name__ == "__main__":
    asyncio.run(main_bot_loop())
