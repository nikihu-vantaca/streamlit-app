#!/usr/bin/env python3
"""
Simple database sync script without pandas dependency
"""

import os
import toml
import sqlite3
import json
from datetime import datetime
from langsmith import Client
import re

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

def init_database():
    """Initialize the database with required tables"""
    db_path = 'ticket_data.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create main table for ticket evaluations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            ticket_id INTEGER NOT NULL,
            ticket_type TEXT DEFAULT 'homeowner',
            quality TEXT,
            comment TEXT,
            evaluation_key TEXT,
            experiment_name TEXT,
            start_time TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, ticket_id)
        )
    ''')
    
    # Check if evaluation_key column exists, if not add it
    cursor.execute("PRAGMA table_info(ticket_evaluations)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'evaluation_key' not in columns:
        print("Adding evaluation_key column to existing database...")
        cursor.execute('ALTER TABLE ticket_evaluations ADD COLUMN evaluation_key TEXT')
    
    # Create index for faster queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_date_ticket 
        ON ticket_evaluations(date, ticket_id)
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")

def extract_date_from_experiment(experiment):
    """Extract date from experiment name"""
    if experiment.startswith("zendesk-evaluation-2025-"):
        match = re.search(r"zendesk-evaluation-(\d{4}-\d{2}-\d{2})", experiment)
        if match:
            return match.group(1)
    elif "implementation-evaluation-" in experiment:
        match = re.search(r"implementation-evaluation-(\d{4}-\d{2}-\d{2})", experiment)
        if match:
            return match.group(1)
    elif "homeowner-pay-evaluation-" in experiment:
        match = re.search(r"homeowner-pay-evaluation-(\d{4}-\d{2}-\d{2})", experiment)
        if match:
            return match.group(1)
    elif "management-pay-evaluation-" in experiment:
        match = re.search(r"management-pay-evaluation-(\d{4}-\d{2}-\d{2})", experiment)
        if match:
            return match.group(1)
    return None

def extract_ticket_id(run, result):
    """Extract ticket_id from run inputs or result"""
    if hasattr(run, "inputs") and run.inputs:
        if isinstance(run.inputs, dict):
            if 'ticket_id' in run.inputs:
                return run.inputs['ticket_id']
            elif 'x' in run.inputs and isinstance(run.inputs['x'], dict):
                return run.inputs['x'].get('ticket_id')
            elif 'run' in run.inputs and isinstance(run.inputs['run'], dict):
                run_inputs = run.inputs['run'].get('inputs', {})
                if 'x' in run_inputs and isinstance(run_inputs['x'], dict):
                    return run_inputs['x'].get('ticket_id')
    return result.get('ticket_id')

def sync_data():
    """Sync data from LangSmith to database"""
    print("🔄 Starting data sync...")
    
    # Get API key
    api_key = get_api_key_from_secrets()
    if not api_key:
        print("❌ No API key found!")
        return
    
    # Initialize database
    init_database()
    
    # Connect to LangSmith
    client = Client(api_key=api_key)
    
    # Fetch runs with rate limiting protection
    try:
        print("📊 Fetching runs from LangSmith...")
        runs = client.list_runs(project_name="evaluators", limit=5000)
        runs_list = list(runs)
        print(f"✅ Fetched {len(runs_list)} runs")
    except Exception as e:
        if "rate limit" in str(e).lower() or "429" in str(e):
            print("⚠️  Rate limit hit, trying with smaller limit...")
            runs = client.list_runs(project_name="evaluators", limit=1000)
            runs_list = list(runs)
            print(f"✅ Fetched {len(runs_list)} runs (limited)")
        else:
            print(f"❌ Error fetching runs: {e}")
            return
    
    # Process runs
    db_path = 'ticket_data.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    processed_count = 0
    detailed_runs = 0
    
    for run in runs_list:
        # Extract experiment name and date
        experiment = None
        if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
            experiment = run.metadata.get("experiment")
        
        if not experiment:
            continue
        
        # Determine date from experiment name
        date_str = extract_date_from_experiment(experiment)
        if not date_str:
            continue
        
        # Only process detailed_similarity_evaluator runs
        if getattr(run, "name", None) == "detailed_similarity_evaluator" and getattr(run, "outputs", None):
            detailed_runs += 1
            
            output = run.outputs
            if isinstance(output, dict):
                result = output
            elif isinstance(output, str):
                try:
                    result = json.loads(output)
                except Exception:
                    continue
            else:
                continue
            
            quality = result.get("quality")
            comment = result.get("comment")
            evaluation_key = result.get("key", "")
            
            # Extract ticket_id
            ticket_id = extract_ticket_id(run, result)
            if ticket_id is None:
                continue
            
            # Determine ticket type (simplified)
            ticket_type = "homeowner"  # default
            if "management_ticket_evaluation" in evaluation_key or (comment and "management" in comment.lower()):
                ticket_type = "management"
            
            # Extract start_time
            start_time = getattr(run, "start_time", None)
            
            # Store in database
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO ticket_evaluations 
                    (date, ticket_id, ticket_type, quality, comment, evaluation_key, experiment_name, start_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (date_str, ticket_id, ticket_type, quality, comment, evaluation_key, experiment, start_time))
                processed_count += 1
            except Exception as e:
                print(f"Error storing record: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"✅ Sync completed!")
    print(f"   Processed {processed_count} records")
    print(f"   Found {detailed_runs} detailed_similarity_evaluator runs")
    
    # Show summary
    conn = sqlite3.connect(db_path)
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
    
    print(f"\n📊 Database Summary:")
    print(f"   Total records: {total_records}")
    print(f"   Records by date:")
    for date, count in date_counts:
        print(f"     {date}: {count} records")

if __name__ == "__main__":
    sync_data()
