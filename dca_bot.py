import sqlite3
import json
import logging
import time
import os
from dotenv import load_dotenv
from datetime import datetime
from pybit.unified_trading import HTTP
from database import get_next_deal_number, save_trade, get_current_price

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("dca_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load configuration
try:
    with open("config.json") as f:
        DCA_CONFIG = json.load(f)
except Exception as e:
    logger.error(f"Failed to load config: {e}")
    # Provide default configuration as fallback
    DCA_CONFIG = {
        "base_order": 30,
        "safety_order": 60,
        "price_deviation": 0.005,
        "safety_order_volume_scale": 2,
        "safety_order_step_scale": 2,
        "max_safety_orders": 6,
        "take_profit_percent": 0.01
    }

# Load environment variables from .env file
load_dotenv()

# Initialize API client - using testnet by default
api_key = os.environ.get("BYBIT_API_KEY")
api_secret = os.environ.get("BYBIT_API_SECRET")

if not api_key or not api_secret:
    logger.error("API key or secret missing")
    session = None
else:
    session = HTTP(testnet=True, api_key=api_key, api_secret=api_secret)

def execute_dca_trade(pair):
    """
    Execute a DCA trade for the given trading pair.
    
    Args:
        pair (str): Trading pair symbol (e.g., "BTCUSDT")
        
    Returns:
        dict: Trade details and status
    """
    logger.info(f"Executing DCA trade for {pair}")
    
    if not session:
        error_msg = "API client not initialized"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    
    try:
        # Get configuration parameters
        base_order_size = DCA_CONFIG["base_order"]
        safety_order_size = DCA_CONFIG["safety_order"]
        price_deviation = DCA_CONFIG["price_deviation"]
        volume_scale = DCA_CONFIG["safety_order_volume_scale"]
        step_scale = DCA_CONFIG["safety_order_step_scale"]
        max_safety_orders = DCA_CONFIG["max_safety_orders"]
        take_profit = DCA_CONFIG["take_profit_percent"]
        
        # Place base order (market order)
        try:
            order = session.place_order(
                category="spot", 
                symbol=pair, 
                side="Buy", 
                order_type="Market", 
                qty=base_order_size
            )
            logger.info(f"Base order placed: {json.dumps(order)}")
        except Exception as e:
            logger.error(f"Failed to place base order: {e}")
            return {"success": False, "error": f"Failed to place base order: {str(e)}"}
        
        # Get current price
        current_price = get_current_price(pair)
        logger.info(f"Current price for {pair}: {current_price}")
        
        # Calculate and place safety orders
        safety_orders = []
        for i in range(max_safety_orders):
            # Calculate price deviation for this safety order
            step = price_deviation * (step_scale ** i)
            order_price = round(current_price * (1 - step), 4)
            
            # Calculate size for this safety order
            order_size = safety_order_size * (volume_scale ** i)
            
            safety_orders.append({
                "price": order_price,
                "size": order_size,
                "index": i + 1
            })
            
            # Place limit order
            try:
                order = session.place_order(
                    category="spot", 
                    symbol=pair, 
                    side="Buy", 
                    order_type="Limit", 
                    qty=order_size, 
                    price=order_price
                )
                logger.info(f"Safety order {i+1} placed at {order_price}: {json.dumps(order)}")
            except Exception as e:
                logger.error(f"Failed to place safety order {i+1}: {e}")
                # Continue with other orders even if one fails
        
        # Save trade details to database
        save_trade(pair, base_order_size, safety_orders, take_profit)
        
        # Return success
        return {
            "success": True,
            "pair": pair,
            "base_order": base_order_size,
            "safety_orders": len(safety_orders),
            "take_profit": take_profit,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to execute DCA trade: {e}", exc_info=True)
        return {"success": False, "error": str(e)}