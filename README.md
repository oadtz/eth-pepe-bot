# ETH/PEPE Trading Bot (Simulated - Backend Only)

This project implements a simulated cryptocurrency trading bot for the ETH/PEPE pair. It focuses on robust backend logic for signal generation, simulated trade execution, and performance tracking. The bot operates as a continuous process, providing useful information directly to the console.

**IMPORTANT SECURITY WARNING:**
This project is designed as a **simulation and prototype**. While it demonstrates how to interact with blockchain data and construct transactions, it **DOES NOT** include secure implementation for signing and sending live transactions using your private key. Directly handling private keys in code for live trading carries **EXTREME FINANCIAL RISK**. If you intend to use this for live trading, you **MUST** implement robust security measures, conduct thorough audits, and understand the inherent risks involved. The developer of this tool is not responsible for any financial losses incurred.

## Features

*   **Fully Automated Simulated Trading:** Executes simulated buy/sell orders based on trading signals in a continuous loop.
*   **Persistent Portfolio:** Simulated ETH and PEPE balances, along with trade history, are stored in a SQLite database, ensuring data persists across restarts.
*   **Advanced Technical Indicators:** Implements Simple Moving Average (SMA) Crossover, Relative Strength Index (RSI), and Moving Average Convergence Divergence (MACD) for signal generation.
*   **Direct Uniswap V3 Data:** Fetches current and attempts to fetch historical price data for the ETH/PEPE pair directly from the Uniswap V3 smart contracts on the Ethereum blockchain using `web3.py`.
    *   **Note on Historical Data:** Fetching extensive historical OHLCV data directly from the blockchain can be very slow and prone to RPC node rate limits. A synthetic data fallback is implemented if real historical data cannot be fetched.
*   **Configurable:** Key parameters (wallet addresses, API URLs, trading windows) are managed via a `config.py` file and `.env` for sensitive data.
*   **Comprehensive Logging:** Provides detailed information about bot activity, signals, simulated trades, and portfolio metrics directly to the console.

## Project Structure

```
eth-pepe-bot/
├── .env                  # Environment variables (sensitive data)
├── backend/              # Python backend
│   ├── main.py           # Main bot loop, simulated trade execution
│   ├── config.py         # Centralized configuration for the bot
│   ├── trading_logic.py  # Core trading logic, indicator calculations, Web3 interaction
│   ├── database.py       # SQLAlchemy models and database initialization
│   ├── requirements.txt  # Python dependencies
│   └── Dockerfile        # Dockerfile for the backend service
└── docker-compose.yml    # Docker Compose configuration for the backend service
```

## Prerequisites

Before you begin, ensure you have the following installed:

*   **Docker Desktop:** Includes Docker Engine and Docker Compose.
*   **An Ethereum Node Provider URL:** (e.g., Infura, Alchemy) for `web3.py` to connect to the blockchain. You'll need to sign up for a free account and get your project ID.

## Setup

1.  **Navigate to the Project Root Directory:**
    ```bash
    cd /Users/oadtz/Code/eth-pepe-bot
    ```

2.  **Configure `.env` File:**
    Create or open the `.env` file in the root of the `eth-pepe-bot` directory and add your sensitive information. **Replace the placeholder values with your actual data.**

    ```dotenv
    # .env
    WALLET_ADDRESS=0xYourEthereumWalletAddressHere
    PRIVATE_KEY=your_private_key_here_without_0x_prefix
    WEB3_PROVIDER_URL=https://mainnet.infura.io/v3/YOUR_INFURA_PROJECT_ID
    ```
    *   `WALLET_ADDRESS`: Your Ethereum wallet address.
    *   `PRIVATE_KEY`: Your wallet's private key (used for *simulated* transaction construction, **not for live signing/sending in this prototype**).
    *   `WEB3_PROVIDER_URL`: The URL of your Ethereum node provider (e.g., Infura, Alchemy).

3.  **Build and Run with Docker Compose:**
    From the project root directory, run the following command to build the Docker image and start the backend service:

    ```bash
    docker-compose up --build
    ```
    *   The `--build` flag ensures that Docker images are rebuilt if there are any changes in the `Dockerfile` or source code.

## Usage

Once Docker Compose has successfully started the backend service, the bot will begin its operation automatically. All output, including trading signals, simulated trades, and portfolio metrics, will be displayed directly in your terminal where `docker-compose up` is running.

To stop the bot, simply press `Ctrl+C` in your terminal.

## Disclaimer

This project is for educational and demonstrative purposes only. It is a **simulated trading bot** and should not be used for live trading without significant further development, security enhancements, and a thorough understanding of the risks involved. Cryptocurrency trading is highly volatile and can result in substantial financial losses. Always exercise caution and consult with financial professionals.
