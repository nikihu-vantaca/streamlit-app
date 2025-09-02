#!/usr/bin/env python3
"""
Simple script to refresh data from LangSmith
Useful for scheduled data updates or manual data refresh
"""

from evaluation_database import EvaluationDatabase
from datetime import datetime, timedelta
import sys

def main():
    """Main function to refresh data"""
    print("🔄 LangSmith Data Refresh Script")
    print("=" * 40)
    
    # Initialize database
    db = EvaluationDatabase('merged_evaluation.db')
    
    # Get API key
    api_key = db.get_api_key()
    if not api_key:
        print("❌ No API key found!")
        print("Please set LANGSMITH_API_KEY environment variable or create .streamlit/secrets.toml")
        sys.exit(1)
    
    print("✅ API key found")
    
    # Set date range (last 7 days by default)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    print(f"📅 Fetching data from {start_date_str} to {end_date_str}")
    
    # Fetch and sync data
    print("🔄 Fetching data from LangSmith...")
    success = db.fetch_and_sync_data(api_key, start_date_str, end_date_str)
    
    if success:
        print("✅ Data refresh completed successfully!")
        
        # Show updated database contents
        print("\n📊 Updated Database Contents:")
        db.debug_database_contents()
        
    else:
        print("❌ Data refresh failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
