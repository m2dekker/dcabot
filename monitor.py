import logging
import time
import threading
from dca_bot import monitor_safety_orders

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("monitor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting DCA Bot Monitor")
    
    # Start the safety order monitoring in a separate thread
    monitor_thread = threading.Thread(target=monitor_safety_orders)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Monitor stopped by user")
    except Exception as e:
        logger.error(f"Monitor stopped due to error: {e}")

if __name__ == "__main__":
    main()