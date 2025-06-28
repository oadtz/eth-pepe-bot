# Project TODO: ETH/PEPE Trading Bot (Simulated)

This document outlines the current status of the ETH/PEPE Trading Bot project and lists future work, improvements, and critical considerations.

## Project Overview

This project implements a simulated cryptocurrency trading bot for the ETH/PEPE pair. It features a backend that generates trading signals based on technical indicators and tracks a simulated portfolio, and a frontend (React TypeScript) for monitoring. The entire application is containerized using Docker and Docker Compose.

**IMPORTANT NOTE:** This bot is currently in **simulation mode**. It does not execute real trades with real funds. The primary goal is to develop and test the trading logic and monitoring capabilities safely.

## Current State & Achieved Milestones

### Backend (Python)
*   **Core Logic:** Implements SMA Crossover, RSI, and MACD indicators for signal generation.
*   **Data Fetching:** Fetches current price data directly from Uniswap V3 smart contracts using `web3.py`.
*   **Historical Data:** Attempts to fetch historical price data directly from the blockchain. Includes a **synthetic data fallback** if real historical data cannot be reliably obtained (due to RPC node limitations like `header not found` errors or rate limits).
*   **Persistence:** Uses SQLite (via SQLAlchemy) to store simulated portfolio balances and a log of simulated trades, ensuring data persists across restarts.
*   **Logging:** Comprehensive logging to the console for monitoring bot activity, signals, and simulated portfolio updates.
*   **Configuration:** Centralized configuration in `config.py` with sensitive data loaded from `.env`.
*   **Containerization:** Dockerized for easy setup and deployment.

### Frontend (React TypeScript)
*   **UI Dashboard:** Displays bot status, current trading signal, simulated ETH/PEPE balances, portfolio value, and profit/loss.
*   **Start/Stop Control:** Buttons to start and stop the bot's simulated operation.
*   **Configuration Display:** Fetches and displays current backend configuration parameters.
*   **Containerization:** Dockerized and served by Nginx.

### Deployment
*   **Docker Compose:** Orchestrates both backend and frontend services for single-command setup and execution.

## Key Challenges & Decisions Made

*   **Historical Data from RPCs:** Direct on-chain queries for extensive historical OHLCV data are highly resource-intensive and prone to RPC node rate limits (especially with free providers). A synthetic data fallback was implemented to ensure the bot can always run and demonstrate indicator calculations.
*   **No Live Trading Implementation:** Due to the extreme security risks associated with handling private keys and executing real transactions, this project explicitly **does not** include code for signing or sending live trades. This remains a critical area for user-implemented, highly secure development if moving beyond simulation.

## Future Work & TODOs

### High Priority

*   **Display Real Wallet Balances:** Modify the backend to fetch and display *actual* ETH and PEPE balances from the `WALLET_ADDRESS` on the blockchain. This will provide real-time insight into the user's actual holdings, while the trading logic remains simulated.

### Medium Priority

*   **Implement Actual Live Trading (User Responsibility & Extreme Caution Required):**
    *   **Secure Private Key Management:** Research and implement highly secure methods for private key handling (e.g., hardware wallets, secure enclaves, KMS). **This is the most critical and risky step.**
    *   **Transaction Construction & Signing:** Implement `web3.py` logic to construct and sign real Uniswap swap transactions.
    *   **Gas Management:** Implement dynamic gas price estimation and strategies to ensure timely and cost-effective transaction execution.
    *   **Slippage Control:** Add robust slippage protection to live trades.
    *   **Transaction Monitoring:** Implement on-chain monitoring to confirm trade execution status.
*   **More Sophisticated Trading Indicators & Strategies:**
    *   Integrate additional indicators (e.g., Bollinger Bands, Volume Profile).
    *   Develop more complex multi-indicator strategies.
    *   Implement a backtesting framework to evaluate strategy performance on historical data.
*   **Dynamic Trading Parameters & Optimization:**
    *   Add a UI in the frontend to allow users to adjust trading parameters (SMA windows, RSI thresholds, trade percentage) dynamically.
    *   Implement a basic optimization routine to find optimal parameters for the simulated strategy.

### Low Priority / Enhancements

*   **Error Notifications and Alerting:** Set up email, Telegram, or Discord notifications for critical bot events (e.g., failed data fetches, significant simulated P/L changes).
*   **Enhanced Frontend Visualizations:**
    *   Add interactive charts (e.g., candlestick charts with indicators overlay) using charting libraries (e.g., Chart.js, D3.js).
    *   Display a detailed table of simulated trade history.
*   **Improve Historical Data Fetching:** If real historical data is crucial for advanced strategies, explore reliable (potentially paid) archival RPC nodes or dedicated blockchain data providers.

