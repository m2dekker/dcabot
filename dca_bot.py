import sqlite3
import json
import logging
import time
import os
from dotenv import load_dotenv
from datetime import datetime
from pybit.unified_trading import HTTP
from database import get_next_deal_number, save_trade, get_current_price, update_trade_status, update_trade_take_profit, get_trade_by_id

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

def calculate_average_entry_price(base_order_size, base_price, filled_safety_orders):
    """
    Calculate the average entry price based on filled orders
    
    Args:
        base_order_size (float): Size of the base order
        base_price (float): Price of the base order
        filled_safety_orders (list): List of filled safety orders with price and size
        
    Returns:
        float: Average entry price
    """
    total_quantity = base_order_size
    total_cost = base_order_size * base_price
    
    for order in filled_safety_orders:
        size = order['size']
        price = order['price']
        total_quantity += size
        total_cost += size * price
    
    # Calculate weighted average price
    if total_quantity > 0:
        return total_cost / total_quantity
    return base_price

def calculate_take_profit_price(avg_entry_price, take_profit_percent):
    """
    Calculate the take profit price based on average entry price
    
    Args:
        avg_entry_price (float): Average entry price
        take_profit_percent (float): Take profit percentage
        
    Returns:
        float: Take profit price
    """
    return avg_entry_price * (1 + take_profit_percent)

def check_order_status(order_id):
    """
    Check the status of an order
    
    Args:
        order_id (str): Order ID to check
        
    Returns:
        dict: Order details including status
    """
    if not session:
        return {"success": False, "error": "API client not initialized"}
    
    try:
        response = session.get_order_history(
            category="spot",
            orderId=order_id
        )
        
        if response["retCode"] == 0 and "list" in response["result"]:
            orders = response["result"]["list"]
            if orders:
                return {"success": True, "order": orders[0]}
        
        return {"success": False, "error": "Order not found"}
    except Exception as e:
        logger.error(f"Failed to check order status: {e}")
        return {"success": False, "error": str(e)}

def update_trade_take_profit_target(trade_id):
    """
    Update the take profit target for a trade based on filled safety orders
    
    Args:
        trade_id (int): Trade ID
        
    Returns:
        bool: Success or failure
    """
    try:
        # Get trade details
        trade = get_trade_by_id(trade_id)
        if not trade:
            logger.error(f"Trade {trade_id} not found")
            return False
        
        # Extract trade info
        _, deal_number, pair, base_order, safety_orders_json, current_take_profit, status, created_at = trade
        
        if status != "open":
            logger.info(f"Trade {trade_id} is not open, skipping take profit update")
            return False
        
        # Get current market price for the base order
        base_price = get_current_price(pair)
        
        # Parse safety orders
        safety_orders = json.loads(safety_orders_json)
        
        # Check which safety orders are filled
        filled_safety_orders = []
        for so in safety_orders:
            # Here we should check if the safety order is filled
            # In a real implementation, you would store the order IDs and check them
            # For this example, we'll assume safety orders with price higher than current price are filled
            current_price = get_current_price(pair)
            if so["price"] >= current_price:
                filled_safety_orders.append(so)
                logger.info(f"Safety order {so['index']} considered filled at price {so['price']}")
        
        # Calculate new average entry price
        avg_entry_price = calculate_average_entry_price(
            base_order,
            base_price,
            filled_safety_orders
        )
        
        # Calculate new take profit price
        take_profit_percent = DCA_CONFIG["take_profit_percent"]
        new_take_profit_price = calculate_take_profit_price(avg_entry_price, take_profit_percent)
        
        # Update trade with new take profit target
        update_trade_take_profit(trade_id, new_take_profit_price)
        
        logger.info(f"Updated take profit for trade {trade_id}: {new_take_profit_price}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to update take profit target: {e}")
        return False

def check_and_place_take_profit_order(trade_id):
    """
    Check if a take profit order should be placed and place it
    
    Args:
        trade_id (int): Trade ID
        
    Returns:
        dict: Result of the operation
    """
    if not session:
        return {"success": False, "error": "API client not initialized"}
    
    try:
        # Get trade details
        trade = get_trade_by_id(trade_id)
        if not trade:
            return {"success": False, "error": f"Trade {trade_id} not found"}
        
        # Extract trade info
        _, deal_number, pair, base_order, safety_orders_json, take_profit_percent, status, created_at = trade
        
        if status != "open":
            return {"success": False, "error": f"Trade {trade_id} is not open"}
        
        # Calculate total quantity from base order and filled safety orders
        safety_orders = json.loads(safety_orders_json)
        total_quantity = base_order
        
        # Add quantities from filled safety orders
        for so in safety_orders:
            # In real implementation, check if the safety order is filled first
            # For simplicity, we're assuming it's filled if price >= current price
            current_price = get_current_price(pair)
            if so["price"] >= current_price:
                total_quantity += so["size"]
        
        # Get current price and calculate take profit price
        current_price = get_current_price(pair)
        
        # Calculate average entry price
        # In real implementation, you should track the exact filled prices
        # For this example, we'll use the current price as the base price
        filled_safety_orders = [so for so in safety_orders if so["price"] >= current_price]
        avg_entry_price = calculate_average_entry_price(
            base_order,
            current_price,  # Using current price as a proxy for base price
            filled_safety_orders
        )
        
        take_profit_price = calculate_take_profit_price(avg_entry_price, take_profit_percent)
        
        # Place take profit order
        try:
            order = session.place_order(
                category="spot",
                symbol=pair,
                side="Sell",
                order_type="Limit",
                qty=total_quantity,
                price=take_profit_price,
                timeInForce="GoodTillCancel"
            )
            
            if order.get("retCode") == 0:
                logger.info(f"Take profit order placed for trade {trade_id}: {json.dumps(order)}")
                # Update trade status
                update_trade_status(trade_id, "take_profit_placed")
                return {"success": True, "order": order}
            else:
                logger.error(f"Failed to place take profit order: {order}")
                return {"success": False, "error": "Failed to place take profit order"}
                
        except Exception as e:
            logger.error(f"Failed to place take profit order: {e}")
            return {"success": False, "error": str(e)}
    
    except Exception as e:
        logger.error(f"Failed to check and place take profit order: {e}")
        return {"success": False, "error": str(e)}

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
        base_order_result = None
        try:
            base_order_result = session.place_order(
                category="spot", 
                symbol=pair, 
                side="Buy", 
                order_type="Market", 
                qty=base_order_size
            )
            logger.info(f"Base order placed: {json.dumps(base_order_result)}")
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
            
            # Skip if the price is already at or below the calculated safety order price
            current_market_price = get_current_price(pair)  # Get the latest price
            if order_price >= current_market_price:
                logger.warning(f"Safety order {i+1} price {order_price} is above or equal to current market price {current_market_price}. Skipping.")
                continue

            # Generate a unique client order ID for this safety order
            client_order_id = f"SO_{pair}_{i+1}_{int(time.time())}"
            
            # Place limit order with client order ID for later reference
            order_result = None
            try:
                order_result = session.place_order(
                    category="spot", 
                    symbol=pair, 
                    side="Buy", 
                    order_type="Limit", 
                    qty=order_size, 
                    price=order_price,
                    timeInForce="PostOnly",  # This ensures the order is placed as a limit order only
                    orderLinkId=client_order_id  # Use this to identify the order later
                )
                # Check the response to verify the order was placed as a limit order
                if order_result.get("retCode") == 0:  # Success code for Bybit API
                    order_id = order_result.get("result", {}).get("orderId")
                    logger.info(f"Safety order {i+1} placed at {order_price}: {json.dumps(order_result)}")
                    
                    # Add to safety orders list with order ID for tracking
                    safety_orders.append({
                        "price": order_price,
                        "size": order_size,
                        "index": i + 1,
                        "order_id": order_id,
                        "client_order_id": client_order_id,
                        "status": "open"
                    })
                else:
                    logger.error(f"Failed to place safety order {i+1}: {order_result}")
            except Exception as e:
                logger.error(f"Failed to place safety order {i+1}: {e}")
        
        # Calculate initial take profit price
        initial_take_profit_price = calculate_take_profit_price(current_price, take_profit)
        
        # Save trade details to database
        trade_id = save_trade(pair, base_order_size, safety_orders, take_profit, initial_take_profit_price)
        
        # Return success
        return {
            "success": True,
            "trade_id": trade_id,
            "pair": pair,
            "base_order": base_order_size,
            "safety_orders": len(safety_orders),
            "take_profit": take_profit,
            "take_profit_price": initial_take_profit_price,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to execute DCA trade: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

def monitor_safety_orders():
    """
    Periodically check the status of safety orders and update take profit targets
    """
    from database import get_open_trades
    
    logger.info("Starting safety order monitoring")
    
    while True:
        try:
            # Get all open trades
            open_trades = get_open_trades()
            
            for trade in open_trades:
                trade_id = trade[0]
                
                # Update take profit target based on filled safety orders
                update_trade_take_profit_target(trade_id)
                
                # Check if we should place a take profit order
                check_and_place_take_profit_order(trade_id)
                
            # Sleep before next check
            time.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Error in safety order monitoring: {e}")
            time.sleep(60)  # Sleep and retry