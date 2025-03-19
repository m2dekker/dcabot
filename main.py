from fastapi import FastAPI, Request, HTTPException, Depends, Header, Path
from pydantic import BaseModel
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import os
import uvicorn
import secrets
import json
import logging
from typing import Optional, List, Dict, Any

from dca_bot import (
    execute_dca_trade, 
    check_and_place_take_profit_order, 
    calculate_take_profit_price,
    update_trade_take_profit_target
)
from database import (
    get_open_trades, 
    get_trade_by_id, 
    update_trade_take_profit, 
    update_trade_status,
    get_trade_orders
)
from pybit.unified_trading import HTTP

# Add this near the top of your file
API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

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

# Generate a random API key if not provided
API_KEY = os.environ.get("WEBHOOK_API_KEY") or secrets.token_hex(16)
logger.info(f"API Key: {API_KEY}")  # Log during startup, remove in production

# Add this function to validate the API key
async def get_api_key(api_key: str = Header(None, alias=API_KEY_NAME)):
    if api_key is None:
        raise HTTPException(status_code=401, detail="API Key missing")
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key

app = FastAPI(
    title="DCA Trading Bot",
    description="A Dollar Cost Averaging trading bot for cryptocurrency",
    version="1.0.0"
)

# Add CORS middleware to allow requests from web browsers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/ui")
async def ui_redirect():
    return RedirectResponse(url="/static/index.html")

# Pydantic models for request/response validation
class TradeRequest(BaseModel):
    pair: str
    
class TakeProfitUpdate(BaseModel):
    take_profit_percent: float

class TakeProfitManualUpdate(BaseModel):
    take_profit_price: float

class StatusResponse(BaseModel):
    status: str
    version: str
    supported_pairs: List[str]

# List of supported trading pairs
SUPPORTED_PAIRS = ["ETHUSDT", "BNBUSDT"]

@app.get("/", response_model=StatusResponse)
async def root():
    """Get API status and information."""
    return {
        "status": "running",
        "version": "1.0.0",
        "supported_pairs": SUPPORTED_PAIRS
    }

@app.post("/webhook")
async def webhook(request: Request, api_key: str = Depends(get_api_key)):
    """Process trading webhook from external sources."""
    try:
        data = await request.json()
        pair = data.get("pair")
        
        if not pair:
            raise HTTPException(status_code=400, detail="Pair not provided")
            
        if pair not in SUPPORTED_PAIRS:
            logger.warning(f"Received webhook for unsupported pair: {pair}")
            raise HTTPException(status_code=400, detail=f"Unsupported pair. Supported pairs: {', '.join(SUPPORTED_PAIRS)}")

        logger.info(f"Received webhook for {pair}")
        result = execute_dca_trade(pair)
        return {"message": "Trade executed", "success": True, "details": result}
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/trades")
async def get_trades():
    """Get all open trades."""
    trades = get_open_trades()
    return {"trades": trades}

# NEW ENDPOINTS FOR TAKE PROFIT MANAGEMENT

@app.get("/trades/{trade_id}")
async def get_trade_detail(trade_id: int = Path(..., description="The ID of the trade to get")):
    """Get detailed information about a specific trade."""
    trade = get_trade_by_id(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade with ID {trade_id} not found")
    
    # Convert trade tuple to dict for better readability
    trade_dict = {
        "id": trade[0],
        "deal_number": trade[1],
        "pair": trade[2],
        "base_order": trade[3],
        "safety_orders": json.loads(trade[4]),
        "take_profit": trade[5],
        "take_profit_price": trade[6] if len(trade) > 6 else None,
        "status": trade[7] if len(trade) > 7 else None,
        "created_at": trade[8] if len(trade) > 8 else None
    }
    
    # Get orders related to this trade
    orders = get_trade_orders(trade_id)
    
    return {"trade": trade_dict, "orders": orders}

@app.post("/trades/{trade_id}/take-profit")
async def update_take_profit(
    trade_id: int = Path(..., description="The ID of the trade to update"),
    take_profit: TakeProfitUpdate = None,
    api_key: str = Depends(get_api_key)
):
    """Update the take profit percentage for a trade and recalculate the take profit price."""
    trade = get_trade_by_id(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade with ID {trade_id} not found")
    
    if not take_profit:
        # If no take profit update is provided, just recalculate based on current settings
        result = update_trade_take_profit_target(trade_id)
        if result:
            return {"message": f"Take profit recalculated for trade {trade_id}", "success": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to recalculate take profit")
    
    # If a new take profit percentage is provided, update the trade
    try:
        # Update the take profit percentage in the database
        conn = None
        try:
            import sqlite3
            from datetime import datetime
            
            conn = sqlite3.connect("/app/data/dca_bot.db")
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE trades SET take_profit = ?, last_updated = ? WHERE id = ?", 
                (take_profit.take_profit_percent, datetime.now().isoformat(), trade_id)
            )
            conn.commit()
        finally:
            if conn:
                conn.close()
        
        # Recalculate the take profit price
        result = update_trade_take_profit_target(trade_id)
        if result:
            return {"message": f"Take profit updated for trade {trade_id}", "success": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to update take profit")
    except Exception as e:
        logger.error(f"Error updating take profit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trades/{trade_id}/take-profit/manual")
async def set_manual_take_profit(
    trade_id: int = Path(..., description="The ID of the trade to update"),
    take_profit: TakeProfitManualUpdate = None,
    api_key: str = Depends(get_api_key)
):
    """Manually set a specific take profit price for a trade."""
    trade = get_trade_by_id(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade with ID {trade_id} not found")
    
    if not take_profit:
        raise HTTPException(status_code=400, detail="Take profit price not provided")
    
    try:
        # Update the take profit price directly
        result = update_trade_take_profit(trade_id, take_profit.take_profit_price)
        if result:
            return {"message": f"Take profit price manually set for trade {trade_id}", "success": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to set take profit price")
    except Exception as e:
        logger.error(f"Error setting manual take profit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trades/{trade_id}/place-take-profit")
async def place_take_profit_order(
    trade_id: int = Path(..., description="The ID of the trade to place take profit for"),
    api_key: str = Depends(get_api_key)
):
    """Manually trigger placement of a take profit order for a trade."""
    trade = get_trade_by_id(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade with ID {trade_id} not found")
    
    # Check if the trade is in the correct state
    if trade[7] != "open":
        raise HTTPException(status_code=400, detail=f"Cannot place take profit order for trade with status {trade[7]}")
    
    try:
        # Place the take profit order
        result = check_and_place_take_profit_order(trade_id)
        if result.get("success"):
            return {"message": f"Take profit order placed for trade {trade_id}", "success": True, "order": result.get("order")}
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to place take profit order"))
    except Exception as e:
        logger.error(f"Error placing take profit order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trades/{trade_id}/cancel-take-profit")
async def cancel_take_profit_order(
    trade_id: int = Path(..., description="The ID of the trade to cancel take profit for"),
    api_key: str = Depends(get_api_key)
):
    """Cancel a take profit order for a trade."""
    trade = get_trade_by_id(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade with ID {trade_id} not found")
    
    # Check if the trade has a take profit order placed
    if trade[7] != "take_profit_placed":
        raise HTTPException(status_code=400, detail=f"No take profit order placed for trade with status {trade[7]}")
    
    try:
        # Initialize Bybit session
        api_key = os.environ.get("BYBIT_API_KEY")
        api_secret = os.environ.get("BYBIT_API_SECRET")
        
        if not api_key or not api_secret:
            raise HTTPException(status_code=500, detail="API key or secret missing")
        
        session = HTTP(testnet=True, api_key=api_key, api_secret=api_secret)
        
        # Get the take profit order ID
        # This is a simplification - in a real implementation, you'd store the order ID in the database
        # Here we're assuming we can get it from the orders table
        orders = get_trade_orders(trade_id)
        tp_order = None
        for order in orders:
            if order[4] == "take_profit":  # Assuming order_type is at index 4
                tp_order = order
                break
        
        if not tp_order:
            raise HTTPException(status_code=404, detail="Take profit order not found")
        
        # Cancel the order
        result = session.cancel_order(
            category="spot",
            symbol=trade[2],  # Pair is at index 2
            orderId=tp_order[2]  # Assuming order_id is at index 2
        )
        
        if result.get("retCode") == 0:
            # Update the trade status back to open
            update_trade_status(trade_id, "open")
            return {"message": f"Take profit order cancelled for trade {trade_id}", "success": True}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to cancel order: {result}")
    except Exception as e:
        logger.error(f"Error cancelling take profit order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/trades/take-profit/status")
async def get_take_profit_status(api_key: str = Depends(get_api_key)):
    """Get the status of all take profit orders."""
    try:
        # Get all open trades
        trades = get_open_trades()
        
        # Filter trades with take profit orders
        take_profit_trades = []
        for trade in trades:
            trade_dict = {
                "id": trade[0],
                "deal_number": trade[1],
                "pair": trade[2],
                "base_order": trade[3],
                "take_profit": trade[5],
                "take_profit_price": trade[6] if len(trade) > 6 else None,
                "status": trade[7] if len(trade) > 7 else None,
                "created_at": trade[8] if len(trade) > 8 else None
            }
            
            # Add the trade to the list if it has a take profit order
            if trade_dict["status"] == "take_profit_placed":
                take_profit_trades.append(trade_dict)
        
        return {"take_profit_trades": take_profit_trades}
    except Exception as e:
        logger.error(f"Error getting take profit status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Initialize Bybit session
api_key = os.environ.get("BYBIT_API_KEY")
api_secret = os.environ.get("BYBIT_API_SECRET")

if not api_key or not api_secret:
    logger.error("API key or secret missing")
    session = None
else:
    session = HTTP(testnet=True, api_key=api_key, api_secret=api_secret)

@app.get("/test-connection")
async def test_connection():
    """Test connection to Bybit API."""
    if not session:
        return {"status": "error", "message": "API client not initialized"}
    
    try:
        # Using the correct method for pybit
        result = session.get_wallet_balance(accountType="UNIFIED")
        return {"status": "success", "message": "Connected to Bybit API", "data": result}
    except Exception as e:
        logger.error(f"API connection test failed: {e}")
        return {"status": "error", "message": str(e)}
    
@app.get("/config")
async def get_config(api_key: str = Depends(get_api_key)):
    """Get the current bot configuration."""
    try:
        with open("config.json") as f:
            config = json.load(f)
        return {"config": config}
    except Exception as e:
        logger.error(f"Error reading config: {e}")
        raise HTTPException(status_code=500, detail=str(e))    

if __name__ == "__main__":
    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 8000))
    
    # Log startup information
    logger.info(f"Starting DCA Bot on port {port}")
    logger.info(f"Supported pairs: {SUPPORTED_PAIRS}")
    
    # Start the server
    uvicorn.run(app, host="0.0.0.0", port=port)