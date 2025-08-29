#!/usr/bin/env python3
"""
Test script to get August 19-21 data specifically
"""

import os
import toml
import sqlite3
import json
from datetime import datetime
from langsmith import Client
import re
import pandas as pd

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

def determine_ticket_type(date_str, experiment, evaluation_key, comment):
    """Determine ticket type based on date and experiment"""
    date_dt = datetime.strptime(date_str, "%Y-%m-%d")
    cutoff_date = datetime(2025, 8, 15)
    
    if date_dt < cutoff_date:
        # Pre-August 15, 2025: Use ungrouped logic
        if "management_ticket_evaluation" in evaluation_key or (comment and "management" in comment.lower()):
            return "management"
        else:
            return "homeowner"
    else:
        # Post-August 15, 2025: Use grouped logic
        if "implementation-evaluation-" in experiment:
            return "implementation"
        elif "homeowner-pay-evaluation-" in experiment:
            return "homeowner"
        elif "management-pay-evaluation-" in experiment:
            return "management"
        else:
            return "homeowner"  # default

def fetch_august_19_21_data():
    """Fetch data specifically for August 19-21"""
    print("🔄 Starting August 19-21 data fetch...")
    
    # Get API key
    api_key = get_api_key_from_secrets()
    if not api_key:
        print("❌ No API key found!")
        return
    
    # Initialize database
    init_database()
    
    # Connect to LangSmith
    client = Client(api_key=api_key)
    
    # Target dates
    target_dates = ['2025-08-19', '2025-08-20', '2025-08-21']
    
    # Store data by date and experiment
    data_by_date = {}
    for date in target_dates:
        data_by_date[date] = {}
    
    try:
        print("📊 Fetching runs from LangSmith...")
        # Use smaller limit to avoid rate limits
        runs = client.list_runs(project_name="evaluators", limit=1000)
        runs_list = list(runs)
        print(f"✅ Fetched {len(runs_list)} runs")
    except Exception as e:
        print(f"❌ Error fetching runs: {e}")
        return
    
    # Process runs
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
        if not date_str or date_str not in target_dates:
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
            
            # Determine ticket type
            ticket_type = determine_ticket_type(date_str, experiment, evaluation_key, comment)
            
            # Extract start_time
            start_time = getattr(run, "start_time", None)
            
            # Store in memory by date and experiment
            if experiment not in data_by_date[date_str]:
                data_by_date[date_str][experiment] = []
            
            data_by_date[date_str][experiment].append({
                'ticket_id': ticket_id,
                'ticket_type': ticket_type,
                'quality': quality,
                'comment': comment,
                'evaluation_key': evaluation_key,
                'start_time': start_time
            })
            
            processed_count += 1
    
    print(f"✅ Processing completed!")
    print(f"   Processed {processed_count} records")
    print(f"   Found {detailed_runs} detailed_similarity_evaluator runs")
    
    # Now store in database
    db_path = 'ticket_data.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    stored_count = 0
    for date_str, experiments in data_by_date.items():
        for experiment, tickets in experiments.items():
            for ticket in tickets:
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO ticket_evaluations 
                        (date, ticket_id, ticket_type, quality, comment, evaluation_key, experiment_name, start_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (date_str, ticket['ticket_id'], ticket['ticket_type'], 
                          ticket['quality'], ticket['comment'], ticket['evaluation_key'], 
                          experiment, ticket['start_time']))
                    stored_count += 1
                except Exception as e:
                    print(f"Error storing record: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"✅ Stored {stored_count} records in database")
    
    # Show summary by date
    print(f"\n📊 Summary by date:")
    for date_str in target_dates:
        if date_str in data_by_date:
            total_tickets = sum(len(tickets) for tickets in data_by_date[date_str].values())
            print(f"  {date_str}: {total_tickets} total tickets")
            
            # Show breakdown by experiment
            for experiment, tickets in data_by_date[date_str].items():
                ticket_types = {}
                for ticket in tickets:
                    ticket_type = ticket['ticket_type']
                    if ticket_type not in ticket_types:
                        ticket_types[ticket_type] = 0
                    ticket_types[ticket_type] += 1
                
                print(f"    {experiment}: {dict(ticket_types)}")
    
    return data_by_date

def create_breakdown_for_august_19_21():
    """Create detailed breakdown for August 19-21"""
    print("\n📊 Creating detailed breakdown for August 19-21...")
    
    db_path = 'ticket_data.db'
    conn = sqlite3.connect(db_path)
    
    # Get data for August 19-21
    query = '''
        SELECT 
            date,
            ticket_type,
            quality,
            comment,
            experiment_name,
            COUNT(*) as count
        FROM ticket_evaluations 
        WHERE date IN ('2025-08-19', '2025-08-20', '2025-08-21')
        AND experiment_name IS NOT NULL
        GROUP BY date, ticket_type, quality, comment, experiment_name
        ORDER BY date, ticket_type, quality
    '''
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print("❌ No data found for August 19-21")
        return
    
    print(f"✅ Found {len(df)} records")
    
    # Create breakdown
    breakdown_data = []
    for _, row in df.iterrows():
        breakdown_data.append({
            'Date': row['date'],
            'Ticket_Type': row['ticket_type'],
            'Quality': row['quality'],
            'Comment': row['comment'],
            'Experiment_Name': row['experiment_name'],
            'Count': row['count']
        })
    
    # Convert to DataFrame and save
    breakdown_df = pd.DataFrame(breakdown_data)
    
    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"august_19_21_breakdown_{timestamp}.csv"
    breakdown_df.to_csv(filename, index=False)
    print(f"✅ Saved breakdown to {filename}")
    
    # Show summary
    print(f"\n📋 Breakdown Summary:")
    for date in ['2025-08-19', '2025-08-20', '2025-08-21']:
        date_data = breakdown_df[breakdown_df['Date'] == date]
        if not date_data.empty:
            total_count = date_data['Count'].sum()
            print(f"  {date}: {total_count} total tickets")
            
            # Show by ticket type
            for ticket_type in date_data['Ticket_Type'].unique():
                type_data = date_data[date_data['Ticket_Type'] == ticket_type]
                type_count = type_data['Count'].sum()
                print(f"    {ticket_type}: {type_count} tickets")
    
    return breakdown_df

if __name__ == "__main__":
    # First fetch the data
    data = fetch_august_19_21_data()
    
    # Then create the breakdown
    if data:
        breakdown = create_breakdown_for_august_19_21()
