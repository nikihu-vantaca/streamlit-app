#!/usr/bin/env python3
"""
Sync all grouped evaluation experiments into the Streamlit database
"""

import sqlite3
import toml
import json
from datetime import datetime
from langsmith import Client
from collections import defaultdict

def get_api_key():
    """Get API key from secrets.toml"""
    try:
        secrets = toml.load(".streamlit/secrets.toml")
        return secrets["langsmith"]["api_key"]
    except:
        return None

def sync_grouped_evaluations():
    """Sync all grouped evaluation experiments into the database"""
    print("🔄 Syncing Grouped Evaluation Experiments to Database")
    print("=" * 80)
    
    # Initialize client
    api_key = get_api_key()
    if not api_key:
        print("❌ No API key found")
        return
    
    client = Client(api_key=api_key)
    
    # Connect to database
    db_path = 'ticket_data.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get runs from August 1-31 to capture all grouped experiments
    start_date = datetime(2025, 8, 1)
    end_date = datetime(2025, 8, 31, 23, 59, 59)
    
    print(f"📅 Fetching runs from {start_date.date()} to {end_date.date()}")
    
    # Fetch runs with a large limit to get all grouped experiments
    all_runs = []
    max_runs = 20000
    
    try:
        print(f"📊 Fetching up to {max_runs} runs...")
        
        runs = client.list_runs(
            project_name="evaluators",
            start_time=start_date,
            end_time=end_date,
            limit=max_runs
        )
        
        all_runs = list(runs)
        print(f"📊 Total runs fetched: {len(all_runs)}")
        
        # Process and sync grouped evaluation runs
        sync_grouped_runs(all_runs, conn, cursor)
        
    except Exception as e:
        print(f"❌ Error fetching runs: {e}")
    finally:
        conn.close()

def sync_grouped_runs(runs_list, conn, cursor):
    """Process and sync grouped evaluation runs to database"""
    print(f"\n🔍 Processing {len(runs_list)} runs for grouped evaluations...")
    
    # Track experiments by date and type
    experiments_by_date = defaultdict(lambda: defaultdict(list))
    
    # First pass: collect all grouped experiments
    for run in runs_list:
        if not run.outputs or run.name != "detailed_similarity_evaluator":
            continue
            
        experiment = None
        if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
            experiment = run.metadata.get("experiment")
        
        if not experiment:
            continue
        
        # Only process grouped evaluation experiments
        exp_type = None
        if "implementation-evaluation-" in experiment:
            exp_type = "implementation"
        elif "homeowner-pay-evaluation-" in experiment:
            exp_type = "homeowner"
        elif "management-pay-evaluation-" in experiment:
            exp_type = "management"
        else:
            # Skip zendesk-evaluation experiments
            continue
        
        # Extract date from experiment name
        # Format: implementation-evaluation-2025-08-15-6e065ee8
        try:
            date_part = experiment.split('-')[3:6]  # ['2025', '08', '15']
            if len(date_part) == 3:
                exp_date = f"{date_part[0]}-{date_part[1]}-{date_part[2]}"
                experiments_by_date[exp_date][exp_type].append({
                    'experiment': experiment,
                    'run': run,
                    'start_time': run.start_time
                })
        except:
            continue
    
    # Get latest experiments for each date and type
    latest_experiments = {}
    
    print(f"\n📅 Finding latest experiments for each date and type:")
    print("-" * 60)
    
    for date in sorted(experiments_by_date.keys()):
        print(f"\n{date}:")
        latest_experiments[date] = {}
        
        for exp_type in ['implementation', 'homeowner', 'management']:
            if exp_type in experiments_by_date[date]:
                # Sort by start_time and get the latest
                runs_for_type = experiments_by_date[date][exp_type]
                runs_for_type.sort(key=lambda x: x['start_time'] if x['start_time'] else datetime.min, reverse=True)
                
                latest_run = runs_for_type[0]
                latest_experiments[date][exp_type] = latest_run['experiment']
                
                print(f"  {exp_type}: {latest_run['experiment']} ({len(runs_for_type)} total runs for this type)")
            else:
                print(f"  {exp_type}: No experiments found")
    
    # Sync latest experiments to database
    print(f"\n💾 Syncing latest experiments to database:")
    print("-" * 60)
    
    total_synced = 0
    ticket_id_counter = 1000000  # Start with a high number to avoid conflicts
    
    for date in sorted(latest_experiments.keys()):
        print(f"\n📅 {date}:")
        
        for exp_type in ['implementation', 'homeowner', 'management']:
            if exp_type in latest_experiments[date]:
                experiment = latest_experiments[date][exp_type]
                print(f"  Syncing {exp_type}: {experiment}")
                
                # Process runs for this experiment
                synced_count = 0
                for run in runs_list:
                    if run.name != "detailed_similarity_evaluator" or not run.outputs:
                        continue
                    
                    # Check if this run is from the target experiment
                    run_experiment = None
                    if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
                        run_experiment = run.metadata.get("experiment")
                    
                    if run_experiment != experiment:
                        continue
                    
                    # Process evaluation output
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
                    
                    # Extract evaluation details
                    quality = result.get("quality")
                    comment = result.get("comment")
                    
                    # Determine quality category
                    quality_category = None
                    if quality == "copy_paste":
                        quality_category = "copy_paste"
                    elif quality == "low_quality":
                        quality_category = "low_quality"
                    elif quality == "high_quality":
                        quality_category = "high_quality"
                    elif comment == "empty_bot_answer":
                        quality_category = "skipped"
                    elif comment and "management_company_ticket" in comment:
                        quality_category = "skipped"
                    elif comment and "empty_human_answer" in comment:
                        quality_category = "skipped"
                    else:
                        quality_category = "unknown"
                    
                    # Generate unique ticket_id
                    ticket_id = ticket_id_counter
                    ticket_id_counter += 1
                    
                    # Insert into database (matching actual schema)
                    try:
                        cursor.execute('''
                            INSERT OR REPLACE INTO ticket_evaluations 
                            (ticket_id, date, ticket_type, quality, comment, evaluation_key, experiment_name, start_time)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            ticket_id,
                            date,
                            exp_type,
                            quality_category,
                            comment,
                            'detailed_similarity_evaluator',
                            experiment,
                            run.start_time.isoformat() if run.start_time else None
                        ))
                        synced_count += 1
                    except Exception as e:
                        print(f"    Error inserting record: {e}")
                
                print(f"    Synced {synced_count} records")
                total_synced += synced_count
    
    # Commit changes
    conn.commit()
    
    print(f"\n✅ Sync Complete!")
    print(f"📊 Total records synced: {total_synced}")
    
    # Verify sync
    print(f"\n🔍 Verifying sync results:")
    print("-" * 60)
    
    cursor.execute('''
        SELECT ticket_type, COUNT(*) as count
        FROM ticket_evaluations 
        WHERE date >= '2025-08-15' AND date <= '2025-08-28'
        AND experiment_name LIKE '%-evaluation-%'
        GROUP BY ticket_type
        ORDER BY ticket_type
    ''')
    
    results = cursor.fetchall()
    for ticket_type, count in results:
        print(f"  {ticket_type}: {count} tickets")
    
    # Show breakdown by date
    print(f"\n📅 Breakdown by date:")
    print("-" * 60)
    
    cursor.execute('''
        SELECT date, ticket_type, COUNT(*) as count
        FROM ticket_evaluations 
        WHERE date >= '2025-08-15' AND date <= '2025-08-28'
        AND experiment_name LIKE '%-evaluation-%'
        GROUP BY date, ticket_type
        ORDER BY date, ticket_type
    ''')
    
    date_results = cursor.fetchall()
    current_date = None
    for date, ticket_type, count in date_results:
        if date != current_date:
            print(f"\n{date}:")
            current_date = date
        print(f"  {ticket_type}: {count} tickets")

if __name__ == "__main__":
    sync_grouped_evaluations()
