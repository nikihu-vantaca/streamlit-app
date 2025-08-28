#!/usr/bin/env python3
"""
Manual database sync script to initialize database and fetch data from LangSmith
"""

import os
import toml
import sqlite3
from database import TicketDatabase
import time

def get_api_key_from_secrets():
    """Get API key from .streamlit/secrets.toml file"""
    try:
        secrets_path = ".streamlit/secrets.toml"
        if os.path.exists(secrets_path):
            secrets = toml.load(secrets_path)
            return secrets.get("langsmith", {}).get("api_key", "")
    except Exception as e:
        print(f"Error reading secrets file: {e}")
    return ""

def manual_sync():
    """Manually sync data from LangSmith to database"""
    print("🔄 Manual Database Sync Starting...")
    
    # Get API key
    api_key = get_api_key_from_secrets()
    if not api_key:
        print("❌ No API key found!")
        print("   Make sure you have a .streamlit/secrets.toml file with your LangSmith API key")
        return
    
    print(f"✅ API key found: {api_key[:10]}...")
    
    # Initialize database
    print("\n📊 Initializing database...")
    db = TicketDatabase()
    
    # Check if database is empty
    try:
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        conn.close()
        
        if not tables:
            print("   Database is empty - no tables found")
        else:
            print(f"   Found tables: {tables}")
            
            # Check if ticket_evaluations table has data
            conn = sqlite3.connect(db.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ticket_evaluations")
            count = cursor.fetchone()[0]
            conn.close()
            print(f"   ticket_evaluations table has {count} records")
            
    except Exception as e:
        print(f"   Error checking database: {e}")
    
    # Sync data from LangSmith
    print("\n🔄 Syncing data from LangSmith...")
    print("   This may take a few minutes and could hit rate limits...")
    
    try:
        new_records = db.fetch_and_store_latest_data(api_key)
        print(f"✅ Sync completed! Added {new_records} new records")
        
        # Check final database state
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ticket_evaluations")
        total_records = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT date, COUNT(*) as count 
            FROM ticket_evaluations 
            GROUP BY date 
            ORDER BY date
        ''')
        date_counts = cursor.fetchall()
        conn.close()
        
        print(f"\n📊 Final Database State:")
        print(f"   Total records: {total_records}")
        print(f"   Records by date:")
        for date, count in date_counts:
            print(f"     {date}: {count} records")
            
    except Exception as e:
        print(f"❌ Sync failed: {e}")
        print("\n💡 If you hit rate limits, try again in a few minutes")
        print("   Or try syncing from the Streamlit app directly")

if __name__ == "__main__":
    manual_sync()
