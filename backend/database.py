from sqlalchemy import create_engine, Column, Float, String, DateTime, Boolean, Text, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, UTC # Import UTC
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = "sqlite:///./data/simulated_trades.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class SimulatedTrade(Base):
    __tablename__ = "simulated_trades"

    id = Column(String, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC)) # Use timezone-aware UTC
    signal = Column(String, index=True)
    eth_amount = Column(Float)
    pepe_amount = Column(Float)
    eth_balance_after = Column(Float)
    pepe_balance_after = Column(Float)
    price_at_trade = Column(Float)
    profit_loss_eth = Column(Float)

class LiveTrade(Base):
    __tablename__ = "live_trades"

    id = Column(String, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))
    signal = Column(String, index=True)
    eth_amount = Column(Float)
    pepe_amount = Column(Float)
    price_at_trade = Column(Float)
    transaction_hash = Column(String, index=True)
    gas_used = Column(Float)
    gas_price_gwei = Column(Float)
    status = Column(String)  # pending, confirmed, failed
    error_message = Column(Text, nullable=True)
    slippage_tolerance = Column(Float)
    amount_out_minimum = Column(Float)

class PortfolioState(Base):
    __tablename__ = "portfolio_state"

    id = Column(String, primary_key=True, index=True, default="current_state")
    eth_balance = Column(Float)
    pepe_balance = Column(Float)
    last_updated = Column(DateTime, default=lambda: datetime.now(UTC)) # Use timezone-aware UTC

class TradingSession(Base):
    __tablename__ = "trading_sessions"

    id = Column(String, primary_key=True, index=True)
    start_time = Column(DateTime, default=lambda: datetime.now(UTC))
    end_time = Column(DateTime, nullable=True)
    mode = Column(String)  # simulation, live
    initial_eth_balance = Column(Float)
    final_eth_balance = Column(Float, nullable=True)
    total_trades = Column(Integer, default=0)
    successful_trades = Column(Integer, default=0)
    failed_trades = Column(Integer, default=0)
    total_volume_eth = Column(Float, default=0.0)
    total_gas_used_eth = Column(Float, default=0.0)
    emergency_stop_triggered = Column(Boolean, default=False)

class RiskEvent(Base):
    __tablename__ = "risk_events"

    id = Column(String, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))
    event_type = Column(String)  # stop_loss, gas_limit, balance_check, etc.
    severity = Column(String)  # low, medium, high, critical
    description = Column(Text)
    action_taken = Column(String)
    trade_id = Column(String, nullable=True)

def init_db(initial_eth_balance=None):
    """Initialize the database with initial portfolio state."""
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    
    # Create initial portfolio state
    db = SessionLocal()
    try:
        # Check if initial state already exists
        existing_state = db.query(PortfolioState).filter(PortfolioState.id == "current_state").first()
        if existing_state:
            logger.info("Database already initialized with portfolio state.")
            return
        
        # Create initial portfolio state
        # Note: initial_eth_balance should always be provided from real wallet balance
        if initial_eth_balance is None:
            logger.warning("No initial ETH balance provided - this should not happen in live trading")
            initial_eth_balance = 0.0
        
        initial_state = PortfolioState(
            id="current_state",
            eth_balance=initial_eth_balance,
            pepe_balance=0.0,
            timestamp=datetime.now(UTC)
        )
        db.add(initial_state)
        db.commit()
        logger.info(f"Initial portfolio state created with {initial_eth_balance:.6f} ETH.")
    finally:
        db.close()
