# DCA Trading Bot

A Dollar Cost Averaging (DCA) trading bot for cryptocurrency that automatically places base and safety orders based on a configured strategy..

## Features

- Webhook endpoint to trigger DCA trades
- Configurable DCA strategy parameters
- Trade history storage in SQLite database
- CLI interface for managing trades and configuration
- Docker support for easy deployment

## Quick Start

### Using Docker

1. Clone this repository:
   ```
   git clone <repository-url>
   cd dca-bot
   ```

2. Build and start the application:
   ```
   docker-compose up -d
   ```

3. Access the CLI interface:
   ```
   docker attach dca-bot-cli
   ```

### Without Docker

1. Clone this repository:
   ```
   git clone <repository-url>
   cd dca-bot
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   python main.py
   ```

4. In a separate terminal, run the CLI:
   ```
   python cli.py
   ```

## Configuration

Edit the `config.json` file to configure your DCA strategy:

```json
{
    "base_order": 30,
    "safety_order": 60,
    "price_deviation": 0.005,
    "safety_order_volume_scale": 2,
    "safety_order_step_scale": 2,
    "max_safety_orders": 6,
    "take_profit_percent": 0.01
}
```

## Usage

### Web API

The bot exposes a webhook endpoint that can be triggered to start a DCA trade:

```
POST /webhook
{
    "pair": "HBARUSDT"
}
```

Currently supported pairs:
- HBARUSDT
- HYPEUSDT

### CLI Interface

The CLI interface provides the following options:

1. View Trade History - List all trades in the database
2. View Trade Details - Show detailed information for a specific trade
3. View Configuration - Display the current bot configuration
4. Update Configuration - Modify the bot configuration
5. Clear Screen - Clear the terminal screen
6. Exit - Exit the CLI

## Architecture

- `main.py` - FastAPI application that exposes the webhook endpoint
- `dca_bot.py` - Implementation of the DCA strategy
- `database.py` - Database operations
- `cli.py` - Command-line interface
- `config.json` - Bot configuration

## Development

This project uses the PyBit library to interact with the Bybit API. By default, it runs in testnet mode.

To contribute:

1. Fork the repository
2. Create a new branch
3. Make your changes
4. Submit a pull request

## License

[MIT License](LICENSE)
