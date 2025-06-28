# 🚀 Aggressive Trading Configuration Guide

## Overview

This guide provides configuration settings for **high-risk, high-reward** trading with the ETH/PEPE bot. These settings are designed for traders who can afford to lose their entire investment and want maximum profit potential.

## ⚠️ RISK WARNING

**AGGRESSIVE TRADING INVOLVES EXTREME RISK**

- You can lose 100% of your investment
- High-frequency trading increases gas costs
- Market volatility can cause rapid losses
- Only use money you can afford to lose completely

## 🎯 Aggressive Configuration Settings

### Core Trading Parameters

```env
# Trade Size & Frequency
MAX_TRADE_SIZE_ETH=0.5          # 0.5 ETH per trade (vs 0.1 conservative)
TRADE_PERCENTAGE=0.25           # 25% of balance per trade (vs 10% conservative)
MAX_DAILY_TRADES=50             # 50 trades per day (vs 10 conservative)
MAX_DAILY_VOLUME_ETH=10.0       # 10 ETH daily volume (vs 1.0 conservative)

# Risk Tolerance
EMERGENCY_STOP_LOSS=0.20        # 20% loss tolerance (vs 5% conservative)
SLIPPAGE_TOLERANCE=0.05         # 5% slippage (vs 2% conservative)

# Execution Speed
GAS_LIMIT_MULTIPLIER=1.1        # Faster execution (vs 1.2 conservative)
MAX_GAS_PRICE_GWEI=200          # Higher gas tolerance (vs 100 conservative)
```

### Technical Indicators (Aggressive)

```env
# Faster Response Times
SHORT_SMA_WINDOW=5              # 5-period SMA (vs 10 conservative)
LONG_SMA_WINDOW=15              # 15-period SMA (vs 30 conservative)
RSI_WINDOW=7                    # 7-period RSI (vs 14 conservative)
NUM_HOURS_DATA=30               # 30 hours data (vs 60 conservative)

# More Sensitive Triggers
RSI_OVERSOLD=25                 # Buy at RSI 25 (vs 30 conservative)
RSI_OVERBOUGHT=75               # Sell at RSI 75 (vs 70 conservative)
```

### Recovery Settings

```env
EMERGENCY_STOP_RECOVERY_ENABLED=true
EMERGENCY_STOP_RECOVERY_THRESHOLD=0.05    # 5% recovery needed
EMERGENCY_STOP_RECOVERY_WAIT_HOURS=2      # 2 hours wait (vs 24 conservative)
```

## 📊 Expected Performance Characteristics

### Advantages

- **Higher Profit Potential**: Larger trades = bigger gains
- **Faster Response**: Quicker signal generation and execution
- **More Opportunities**: 50 trades/day vs 10 trades/day
- **Quick Recovery**: 2-hour recovery vs 24-hour wait

### Risks

- **Higher Losses**: 20% stop loss vs 5% conservative
- **Increased Gas Costs**: More frequent trading
- **Slippage Impact**: 5% tolerance vs 2% conservative
- **Market Noise**: Sensitive indicators may trigger false signals

## 🎛️ Configuration Tiers

### Tier 1: Moderate Aggressive (Recommended Start)

```env
MAX_TRADE_SIZE_ETH=0.25
TRADE_PERCENTAGE=0.15
MAX_DAILY_TRADES=25
EMERGENCY_STOP_LOSS=0.15
```

### Tier 2: High Aggressive (Current Settings)

```env
MAX_TRADE_SIZE_ETH=0.5
TRADE_PERCENTAGE=0.25
MAX_DAILY_TRADES=50
EMERGENCY_STOP_LOSS=0.20
```

### Tier 3: Extreme Aggressive (Maximum Risk)

```env
MAX_TRADE_SIZE_ETH=1.0
TRADE_PERCENTAGE=0.5
MAX_DAILY_TRADES=100
EMERGENCY_STOP_LOSS=0.30
EMERGENCY_STOP_RECOVERY_WAIT_HOURS=1
```

## 🔧 Implementation Steps

### 1. Update Your .env File

```bash
# Copy the aggressive configuration
cp env.example .env

# Edit with your wallet details
nano .env
```

### 2. Test in Simulation Mode First

```env
LIVE_TRADING_ENABLED=false
INITIAL_ETH_BALANCE=1.0
```

### 3. Monitor Performance

```bash
# Watch bot behavior
docker-compose logs -f backend

# Check database for trade history
sqlite3 backend/data/simulated_trades.db
```

### 4. Gradual Live Trading

```env
# Start with small amounts
LIVE_TRADING_ENABLED=true
MAX_TRADE_SIZE_ETH=0.1  # Start small
```

## 📈 Performance Monitoring

### Key Metrics to Track

1. **Win Rate**: Target >60% for aggressive trading
2. **Average Profit per Trade**: Should exceed gas costs
3. **Maximum Drawdown**: Monitor against 20% stop loss
4. **Daily Volume**: Ensure within 10 ETH limit
5. **Recovery Success Rate**: Should be >80%

### Database Queries

```sql
-- Check recent performance
SELECT
    signal,
    COUNT(*) as trades,
    AVG(profit_loss_eth) as avg_profit,
    SUM(profit_loss_eth) as total_profit
FROM simulated_trades
WHERE timestamp > datetime('now', '-7 days')
GROUP BY signal;

-- Check emergency stops
SELECT * FROM risk_events
WHERE event_type = 'emergency_stop'
ORDER BY timestamp DESC;
```

## 🛡️ Risk Management Strategies

### 1. Portfolio Diversification

- Don't put all funds in one bot
- Consider multiple trading pairs
- Maintain emergency funds outside bot

### 2. Dynamic Adjustment

- Reduce trade size during high volatility
- Increase stop loss during strong trends
- Pause trading during major news events

### 3. Monitoring Alerts

```bash
# Set up monitoring for critical events
docker-compose logs -f backend | grep -E "(CRITICAL|EMERGENCY|ERROR)"
```

## 🚨 Emergency Procedures

### Immediate Actions

1. **Stop Trading**: `docker-compose down`
2. **Check Balances**: Verify wallet on Etherscan
3. **Assess Damage**: Calculate total losses
4. **Review Logs**: Identify what went wrong

### Recovery Actions

1. **Reduce Risk**: Lower trade sizes
2. **Adjust Parameters**: Increase stop loss
3. **Test Changes**: Use simulation mode
4. **Gradual Restart**: Start with small amounts

## 💡 Advanced Strategies

### 1. Market Condition Adaptation

```env
# Bull Market Settings
RSI_OVERSOLD=20
RSI_OVERBOUGHT=80
TRADE_PERCENTAGE=0.3

# Bear Market Settings
RSI_OVERSOLD=30
RSI_OVERBOUGHT=70
TRADE_PERCENTAGE=0.15
```

### 2. Time-Based Adjustments

```env
# High Activity Hours (UTC 14-22)
MAX_DAILY_TRADES=75
MAX_GAS_PRICE_GWEI=300

# Low Activity Hours (UTC 22-14)
MAX_DAILY_TRADES=25
MAX_GAS_PRICE_GWEI=150
```

### 3. Volatility-Based Settings

```env
# High Volatility
SLIPPAGE_TOLERANCE=0.08
EMERGENCY_STOP_LOSS=0.25

# Low Volatility
SLIPPAGE_TOLERANCE=0.03
EMERGENCY_STOP_LOSS=0.15
```

## 📊 Performance Benchmarks

### Conservative Bot (Baseline)

- Daily Trades: 10
- Trade Size: 0.1 ETH
- Stop Loss: 5%
- Expected Return: 2-5% monthly

### Aggressive Bot (Current)

- Daily Trades: 50
- Trade Size: 0.5 ETH
- Stop Loss: 20%
- Expected Return: 10-30% monthly

### Extreme Bot (Maximum Risk)

- Daily Trades: 100
- Trade Size: 1.0 ETH
- Stop Loss: 30%
- Expected Return: 20-50% monthly (or -50% to -80%)

## 🎯 Success Factors

1. **Market Timing**: Deploy during trending markets
2. **Liquidity**: Ensure sufficient PEPE/ETH liquidity
3. **Gas Management**: Monitor gas costs vs profits
4. **Risk Discipline**: Stick to stop losses
5. **Continuous Monitoring**: Watch for unusual patterns

## ⚡ Quick Start Commands

```bash
# Start with aggressive settings
docker-compose up --build

# Monitor in real-time
docker-compose logs -f backend

# Check current configuration
grep -E "(MAX_TRADE|EMERGENCY|TRADE_PERCENTAGE)" .env

# Emergency stop
docker-compose down
```

## 📞 Support & Monitoring

- **Logs**: `docker-compose logs -f backend`
- **Database**: `sqlite3 backend/data/simulated_trades.db`
- **Configuration**: Check `.env` file
- **Performance**: Monitor profit/loss in logs

**Remember: Aggressive trading can lead to significant losses. Only use funds you can afford to lose completely.**
