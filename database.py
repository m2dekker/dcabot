import sqlite3
import json
import logging
import os
from datetime import datetime

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
        
        # Update the trades table to include take_profit_price
        cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        deal_number INTEGER,
                        pair TEXT,
                        base_order REAL,
                        safety_orders TEXT,
                        take_profit REAL,
                        take_profit_price REAL,
                        status TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Add orders table to track individual orders
        cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trade_id INTEGER,
                        order_id TEXT,
                        client_order_id TEXT,
                        order_type TEXT,
                        price REAL,
                        size REAL,
                        status TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (trade_id) REFERENCES trades(id))''')
        
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

def save_trade(pair, base_order, safety_orders, take_profit, take_profit_price=None):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # If take_profit_price is not provided, set it to None
        if take_profit_price is None:
            take_profit_price = 0.0
        
        cursor.execute("""
            INSERT INTO trades (
                deal_number, pair, base_order, safety_orders, 
                take_profit, take_profit_price, status, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            get_next_deal_number(), pair, base_order, 
            json.dumps(safety_orders), take_profit, take_profit_price, 
            "open", datetime.now().isoformat()
        ))
        
        # Get the ID of the inserted trade
        trade_id = cursor.lastrowid
        
        # Insert safety orders into orders table
        for so in safety_orders:
            cursor.execute("""
                INSERT INTO orders (
                    trade_id, order_id, client_order_id, order_type, 
                    price, size, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id, so.get("order_id", ""), so.get("client_order_id", ""),
                "safety_order", so["price"], so["size"], so.get("status", "open")
            ))
        
        conn.commit()
        return trade_id
    except Exception as e:
        logging.error(f"Error saving trade: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_trade_status(trade_id, status):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE trades SET status = ?, last_updated = ? WHERE id = ?", 
            (status, datetime.now().isoformat(), trade_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error updating trade status: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_trade_take_profit(trade_id, take_profit_price):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE trades SET take_profit_price = ?, last_updated = ? WHERE id = ?", 
            (take_profit_price, datetime.now().isoformat(), trade_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error updating take profit: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_order_status(order_id, status):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE orders SET status = ? WHERE order_id = ?", 
            (status, order_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error updating order status: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_trade_by_id(trade_id):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
        trade = cursor.fetchone()
        return trade
    except Exception as e:
        logging.error(f"Error getting trade: {e}")
        return None
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
        cursor.execute("SELECT * FROM trades WHERE status = 'open' OR status = 'take_profit_placed'")
        rows = cursor.fetchall()
        return rows
    except Exception as e:
        logging.error(f"Error getting open trades: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_trade_orders(trade_id):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE trade_id = ?", (trade_id,))
        rows = cursor.fetchall()
        return rows
    except Exception as e:
        logging.error(f"Error getting trade orders: {e}")
        return []
    finally:
        if conn:
            conn.close()

# Initialize the database when the module is imported
init_db()