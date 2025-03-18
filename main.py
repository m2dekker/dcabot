from fastapi import FastAPI, Request, HTTPException, Depends, Header
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
from typing import Optional, List

from dca_bot import execute_dca_trade
from database import get_open_trades
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

class TradeRequest(BaseModel):
    pair: str
    
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