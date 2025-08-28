#!/usr/bin/env python3
"""
Check what's actually stored in the database
"""

import sqlite3
from datetime import datetime

def check_database_contents():
    """Check what's stored in the database"""
    print("🔍 Checking Database Contents...")
    
    try:
        conn = sqlite3.connect('ticket_data.db')
        
        # Check if table exists
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"📋 Tables in database: {tables}")
        
        if ('ticket_evaluations',) in tables:
            # Check total records
            cursor.execute('SELECT COUNT(*) FROM ticket_evaluations')
            total_records = cursor.fetchone()[0]
            print(f"📊 Total records: {total_records}")
            
            # Check records by date
            cursor.execute('''
                SELECT date, COUNT(*) as count 
                FROM ticket_evaluations 
                GROUP BY date 
                ORDER BY date
            ''')
            date_counts = cursor.fetchall()
            
            print(f"\n📅 Records by date:")
            for date, count in date_counts:
                print(f"  {date}: {count} records")
            
            # Check specifically for August 4-14
            august_4_14_dates = [f"2025-08-{i:02d}" for i in range(4, 15)]
            print(f"\n🎯 Checking August 4-14 specifically:")
            
            for date in august_4_14_dates:
                cursor.execute('SELECT COUNT(*) FROM ticket_evaluations WHERE date = ?', (date,))
                count = cursor.fetchone()[0]
                print(f"  {date}: {count} records")
            
            # Check sample records
            print(f"\n📋 Sample records:")
            cursor.execute('''
                SELECT date, ticket_id, evaluation_key, ticket_type, quality, comment 
                FROM ticket_evaluations 
                ORDER BY date DESC, ticket_id DESC 
                LIMIT 10
            ''')
            sample_records = cursor.fetchall()
            
            for record in sample_records:
                print(f"  {record[0]} | Ticket {record[1]} | Key: {record[2]} | Type: {record[3]} | Quality: {record[4]} | Comment: {record[5][:50]}...")
            
            # Check evaluation_key distribution
            print(f"\n🔑 Evaluation key distribution:")
            cursor.execute('''
                SELECT evaluation_key, COUNT(*) as count 
                FROM ticket_evaluations 
                GROUP BY evaluation_key 
                ORDER BY count DESC
            ''')
            key_counts = cursor.fetchall()
            
            for key, count in key_counts:
                print(f"  {key}: {count} records")
            
        else:
            print("❌ No ticket_evaluations table found!")
            
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")

if __name__ == "__main__":
    check_database_contents()
