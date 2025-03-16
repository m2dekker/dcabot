import sqlite3
import json
import logging
import os

# Set up the database directory
DB_DIR = "/app/data"
DB_PATH = os.path.join(DB_DIR, "dca_bot.db")

def init_db():
    conn = None
    try:
        # Make sure the directory exists
        os.makedirs(DB_DIR, exist_ok=True)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        deal_number INTEGER,
                        pair TEXT,
                        base_order REAL,
                        safety_orders TEXT,
                        take_profit REAL,
                        status TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        logging.info(f"Database initialized at {DB_PATH}")
    except Exception as e:
        logging.error(f"Database initialization error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def save_trade(pair, base_order, safety_orders, take_profit):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO trades (deal_number, pair, base_order, safety_orders, take_profit, status) VALUES (?, ?, ?, ?, ?, ?)",
                    (get_next_deal_number(), pair, base_order, json.dumps(safety_orders), take_profit, "open"))
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error saving trade: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_current_price(pair):
    # This is a placeholder - in a real system, you'd call an external API
    # Consider implementing a proper API call to get the actual price
    import random
    # Simulated price between 0.04 and 0.06
    return 0.05 + random.uniform(-0.01, 0.01)

def get_next_deal_number():
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trades")
        count = cursor.fetchone()[0] + 1
        return count
    except Exception as e:
        logging.error(f"Error getting next deal number: {e}")
        return 1
    finally:
        if conn:
            conn.close()

def get_open_trades():
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE status = 'open'")
        rows = cursor.fetchall()
        return rows
    except Exception as e:
        logging.error(f"Error getting open trades: {e}")
        return []
    finally:
        if conn:
            conn.close()

# Initialize the database when the module is imported
init_db()