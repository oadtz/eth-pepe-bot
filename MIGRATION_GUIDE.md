# ETH/PEPE Trading Bot - Migration Guide: Simulation to Live Trading

## ⚠️ CRITICAL WARNINGS

**LIVE TRADING INVOLVES REAL MONEY AND SUBSTANTIAL RISK**

- You can lose all funds invested
- Cryptocurrency markets are highly volatile
- Technical failures can result in financial losses
- Gas fees and slippage can significantly impact profitability
- Smart contract risks exist (though Uniswap V3 is well-audited)

**NEVER USE MORE MONEY THAN YOU CAN AFFORD TO LOSE**

## Pre-Migration Checklist

### 1. Security Assessment

- [ ] Private key is stored securely (not in plain text)
- [ ] Using a dedicated trading wallet (not your main wallet)
- [ ] Hardware wallet integration considered
- [ ] Environment variables are properly secured
- [ ] `.env` file is in `.gitignore`

### 2. Technical Preparation

- [ ] Bot has been tested extensively in simulation mode
- [ ] All risk management features are configured
- [ ] Emergency stop procedures are understood
- [ ] Monitoring and alerting systems are in place
- [ ] Backup and recovery procedures are ready

### 3. Financial Preparation

- [ ] Only using funds you can afford to lose
- [ ] Starting with small amounts (0.01-0.1 ETH)
- [ ] Understanding of gas fees and their impact
- [ ] Clear profit/loss tracking system
- [ ] Stop-loss limits are set appropriately

## Step-by-Step Migration Process

### Phase 1: Enhanced Simulation Testing

1. **Update Configuration**

   ```bash
   # Copy the example environment file
   cp env.example .env

   # Edit .env with your settings
   nano .env
   ```

2. **Configure Risk Parameters**

   ```env
   # Start with very conservative settings
   LIVE_TRADING_ENABLED=false
   MAX_TRADE_SIZE_ETH=0.01
   EMERGENCY_STOP_LOSS=0.02
   MAX_DAILY_TRADES=5
   MAX_DAILY_VOLUME_ETH=0.1
   ```

3. **Test Enhanced Features**

   ```bash
   # Run the bot with new risk management
   docker-compose up --build

   # Monitor logs for risk events and validation
   docker-compose logs -f backend
   ```

### Phase 2: Testnet Deployment

1. **Configure for Testnet**

   ```env
   # Use Goerli or Sepolia testnet
   WEB3_PROVIDER_URL=https://goerli.infura.io/v3/YOUR_PROJECT_ID

   # Use testnet tokens
   PEPE_ADDRESS=0xTestnetPepeAddress
   WETH_ADDRESS=0xTestnetWethAddress
   ```

2. **Get Testnet Funds**

   - Use faucets to get testnet ETH
   - Test with small amounts first

3. **Enable Live Trading on Testnet**

   ```env
   LIVE_TRADING_ENABLED=true
   MAX_TRADE_SIZE_ETH=0.001
   ```

4. **Monitor Testnet Performance**
   - Verify all transactions execute correctly
   - Check risk management triggers
   - Validate portfolio tracking

### Phase 3: Mainnet Preparation

1. **Final Security Review**

   - [ ] Private key security verified
   - [ ] All risk limits reviewed
   - [ ] Emergency procedures tested
   - [ ] Monitoring systems active

2. **Update Configuration for Mainnet**

   ```env
   WEB3_PROVIDER_URL=https://mainnet.infura.io/v3/YOUR_PROJECT_ID
   LIVE_TRADING_ENABLED=true

   # Conservative mainnet settings
   MAX_TRADE_SIZE_ETH=0.01
   EMERGENCY_STOP_LOSS=0.05
   MAX_DAILY_TRADES=3
   MAX_DAILY_VOLUME_ETH=0.05
   ```

3. **Deploy with Minimal Funds**
   - Start with 0.01-0.05 ETH
   - Monitor first few trades closely
   - Verify all systems working correctly

### Phase 4: Gradual Scaling

1. **Increase Trade Sizes Gradually**

   ```env
   # Week 1: Very small
   MAX_TRADE_SIZE_ETH=0.01

   # Week 2: Small increase
   MAX_TRADE_SIZE_ETH=0.02

   # Week 3: Moderate
   MAX_TRADE_SIZE_ETH=0.05
   ```

2. **Monitor Performance Metrics**

   - Success rate of trades
   - Gas costs vs. profits
   - Risk management effectiveness
   - Portfolio performance

3. **Adjust Parameters Based on Results**
   - Fine-tune technical indicators
   - Optimize risk parameters
   - Adjust trading frequency

## Risk Management Features

### Automatic Safety Measures

1. **Trade Size Limits**

   - Maximum trade size per transaction
   - Daily volume limits
   - Daily trade count limits

2. **Price Protection**

   - Slippage tolerance (default 2%)
   - Gas price limits
   - Transaction deadline enforcement

3. **Emergency Stops**

   - Portfolio loss percentage triggers
   - Failed transaction limits
   - System error detection

4. **Balance Validation**
   - Pre-trade balance checks
   - Insufficient funds protection
   - Gas cost estimation

### Manual Safety Procedures

1. **Emergency Stop Commands**

   ```bash
   # Stop the bot immediately
   docker-compose down

   # Or kill the process
   pkill -f "python.*main.py"
   ```

2. **Monitoring Commands**

   ```bash
   # Check bot status
   docker-compose ps

   # View recent logs
   docker-compose logs --tail=100 backend

   # Check database
   sqlite3 backend/data/simulated_trades.db
   ```

## Monitoring and Alerting

### Essential Metrics to Track

1. **Performance Metrics**

   - Total trades executed
   - Success/failure rate
   - Average gas costs
   - Portfolio value changes

2. **Risk Metrics**

   - Daily volume used
   - Risk events triggered
   - Emergency stops activated
   - Balance validation failures

3. **System Metrics**
   - Web3 connection status
   - Database health
   - Memory usage
   - Error rates

### Recommended Monitoring Tools

1. **Log Monitoring**

   ```bash
   # Real-time log monitoring
   docker-compose logs -f backend | grep -E "(ERROR|CRITICAL|LIVE)"
   ```

2. **Database Queries**

   ```sql
   -- Check recent trades
   SELECT * FROM live_trades ORDER BY timestamp DESC LIMIT 10;

   -- Check risk events
   SELECT * FROM risk_events ORDER BY timestamp DESC LIMIT 10;

   -- Portfolio performance
   SELECT * FROM trading_sessions ORDER BY start_time DESC LIMIT 5;
   ```

3. **External Monitoring**
   - Set up email/SMS alerts for critical events
   - Use monitoring services (UptimeRobot, etc.)
   - Implement Telegram/Discord notifications

## Troubleshooting Common Issues

### Connection Issues

```bash
# Check Web3 connection
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  YOUR_WEB3_PROVIDER_URL
```

### Gas Issues

- Increase `MAX_GAS_PRICE_GWEI` if transactions are failing
- Check current gas prices on Etherscan
- Consider using gas price estimation services

### Balance Issues

- Verify wallet has sufficient ETH for gas
- Check token approvals for PEPE
- Validate token decimals and amounts

### Transaction Failures

- Check transaction hash on Etherscan
- Verify slippage tolerance is appropriate
- Ensure sufficient liquidity in pool

## Post-Migration Best Practices

### Regular Maintenance

1. **Daily Checks**

   - Review bot performance
   - Check for any risk events
   - Verify portfolio balances
   - Monitor gas costs

2. **Weekly Reviews**

   - Analyze trading patterns
   - Adjust parameters if needed
   - Backup database
   - Update dependencies

3. **Monthly Assessments**
   - Comprehensive performance review
   - Risk parameter optimization
   - Strategy effectiveness evaluation
   - Security audit

### Continuous Improvement

1. **Strategy Optimization**

   - Backtest parameter changes
   - Implement new indicators
   - Optimize trade timing
   - Reduce gas costs

2. **Risk Management Enhancement**

   - Add new safety checks
   - Implement dynamic limits
   - Improve error handling
   - Add more monitoring

3. **System Upgrades**
   - Update dependencies regularly
   - Implement new features
   - Improve monitoring
   - Enhance security

## Emergency Procedures

### Immediate Actions

1. **Stop Trading**

   ```bash
   docker-compose down
   ```

2. **Check Balances**

   - Verify wallet balances on Etherscan
   - Check for pending transactions
   - Review recent trade history

3. **Assess Damage**
   - Calculate losses
   - Identify cause of issue
   - Document what happened

### Recovery Steps

1. **Fix Issues**

   - Address root cause
   - Update configuration
   - Test fixes thoroughly

2. **Restart Safely**

   - Start with simulation mode
   - Test on testnet
   - Gradually re-enable live trading

3. **Learn and Improve**
   - Update procedures
   - Enhance monitoring
   - Improve risk management

## Conclusion

Migration from simulation to live trading is a significant step that requires careful preparation, testing, and ongoing monitoring. Always prioritize safety and start small. The bot includes comprehensive risk management features, but they are not a substitute for careful oversight and responsible trading practices.

**Remember: The goal is consistent, profitable trading, not maximum returns at any cost.**
