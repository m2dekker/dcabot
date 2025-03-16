from fastapi import FastAPI, Request, HTTPException, Depends
from pydantic import BaseModel
import json
import logging
from typing import Optional, List
import os
import uvicorn
from dca_bot import execute_dca_trade
from database import get_open_trades

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

app = FastAPI(
    title="DCA Trading Bot",
    description="A Dollar Cost Averaging trading bot for cryptocurrency",
    version="1.0.0"
)

class TradeRequest(BaseModel):
    pair: str
    
class StatusResponse(BaseModel):
    status: str
    version: str
    supported_pairs: List[str]

# List of supported trading pairs
SUPPORTED_PAIRS = ["HBARUSDT", "HYPEUSDT"]

@app.get("/", response_model=StatusResponse)
async def root():
    """Get API status and information."""
    return {
        "status": "running",
        "version": "1.0.0",
        "supported_pairs": SUPPORTED_PAIRS
    }

@app.post("/webhook")
async def webhook(request: Request):
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

if __name__ == "__main__":
    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 8000))
    
    # Log startup information
    logger.info(f"Starting DCA Bot on port {port}")
    logger.info(f"Supported pairs: {SUPPORTED_PAIRS}")
    
    # Start the server
    uvicorn.run(app, host="0.0.0.0", port=port)