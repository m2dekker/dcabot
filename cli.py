import sqlite3
import json
import sys
import os
from datetime import datetime

# Set up the database directory (same as in database.py)
DB_DIR = "/app/data"
DB_PATH = os.path.join(DB_DIR, "dca_bot.db")

def view_trade_history():
    """Display all trades in the database"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, deal_number, pair, base_order, status, created_at FROM trades ORDER BY id DESC")
        rows = cursor.fetchall()
        
        if not rows:
            print("\nNo trades found in the database.")
            return
            
        print("\nTrade History:")
        print(f"{'ID':<5} {'Deal':<5} {'Pair':<10} {'Base Order':<12} {'Status':<10} {'Date':<20}")
        print("-" * 65)
        
        for row in rows:
            id, deal, pair, base, status, created = row
            # Format datetime if it's a string
            if isinstance(created, str):
                created = created[:19]  # Trim milliseconds if present
            print(f"{id:<5} {deal:<5} {pair:<10} {base:<12.2f} {status:<10} {created}")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def view_trade_details(trade_id):
    """Display detailed information for a specific trade"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
        trade = cursor.fetchone()
        
        if not trade:
            print(f"\nTrade with ID {trade_id} not found.")
            return
            
        id, deal, pair, base, safety_orders, take_profit, status, created = trade
        safety_orders = json.loads(safety_orders)
        
        print(f"\nTrade Details (ID: {id}):")
        print(f"Deal Number: {deal}")
        print(f"Pair: {pair}")
        print(f"Base Order: {base}")
        print(f"Take Profit: {take_profit}%")
        print(f"Status: {status}")
        print(f"Created: {created}")
        
        print("\nSafety Orders:")
        if isinstance(safety_orders, list):
            if len(safety_orders) > 0 and isinstance(safety_orders[0], dict):
                for so in safety_orders:
                    print(f"  Order #{so['index']}: Price {so['price']}, Size {so['size']}")
            else:
                for i, (price, size) in enumerate(safety_orders):
                    print(f"  Order #{i+1}: Price {price}, Size {size}")
        else:
            print("  No safety orders found or invalid format")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def view_config():
    """Display the current bot configuration"""
    try:
        with open("/app/config.json") as f:
            config = json.load(f)
            
        print("\nCurrent Bot Configuration:")
        for key, value in config.items():
            print(f"{key}: {value}")
            
    except FileNotFoundError:
        print("\nConfig file not found. Please create a config.json file.")
    except json.JSONDecodeError:
        print("\nInvalid JSON in config file.")
    except Exception as e:
        print(f"\nError reading config: {e}")

def update_config():
    """Update the bot configuration"""
    try:
        # Load current config
        with open("/app/config.json") as f:
            config = json.load(f)
            
        print("\nUpdate Configuration (press Enter to keep current value):")
        for key, value in config.items():
            new_value = input(f"{key} ({value}): ")
            if new_value.strip():
                try:
                    # Try to convert string to number if applicable
                    if isinstance(value, int):
                        config[key] = int(new_value)
                    elif isinstance(value, float):
                        config[key] = float(new_value)
                    else:
                        config[key] = new_value
                except ValueError:
                    print(f"Invalid value for {key}, keeping original")
        
        # Save updated config
        with open("/app/config.json", "w") as f:
            json.dump(config, f, indent=4)
            
        print("\nConfiguration updated successfully!")
        
    except FileNotFoundError:
        print("\nConfig file not found. Creating a new one...")
        default_config = {
            "base_order": 30,
            "safety_order": 60,
            "price_deviation": 0.005,
            "safety_order_volume_scale": 2,
            "safety_order_step_scale": 2,
            "max_safety_orders": 6,
            "take_profit_percent": 0.01
        }
        with open("/app/config.json", "w") as f:
            json.dump(default_config, f, indent=4)
        print("Default configuration created!")
    except Exception as e:
        print(f"\nError updating config: {e}")

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def main_menu():
    """Display and handle the main menu"""
    while True:
        print("\nDCA Bot CLI Menu")
        print("=" * 20)
        print("1. View Trade History")
        print("2. View Trade Details")
        print("3. View Configuration")
        print("4. Update Configuration")
        print("5. Clear Screen")
        print("6. Exit")
        
        choice = input("\nSelect an option: ")
        
        if choice == "1":
            view_trade_history()
        elif choice == "2":
            trade_id = input("Enter trade ID: ")
            if trade_id.isdigit():
                view_trade_details(int(trade_id))
            else:
                print("Invalid trade ID")
        elif choice == "3":
            view_config()
        elif choice == "4":
            update_config()
        elif choice == "5":
            clear_screen()
        elif choice == "6":
            print("\nExiting DCA Bot CLI. Goodbye!")
            break
        else:
            print("\nInvalid option. Please try again.")

if __name__ == "__main__":
    # Make sure the database directory exists
    os.makedirs(DB_DIR, exist_ok=True)
    
    print("DCA Bot CLI - Management Interface")
    main_menu()