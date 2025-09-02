#!/usr/bin/env python3
"""
Safe debug script that handles rate limits and investigates missing dates
"""

import os
import toml
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from langsmith import Client
import re
import time

def get_api_key():
    api_key = os.getenv('LANGSMITH_API_KEY')
    if api_key:
        return api_key
    try:
        secrets = toml.load('.streamlit/secrets.toml')
        return secrets['langsmith']['api_key']
    except:
        pass
    return None

def analyze_existing_databases():
    """First analyze what we have in existing databases"""
    print("=== ANALYZING EXISTING DATABASES ===")
    
    missing_dates = [
        "2025-08-15", "2025-08-16", "2025-08-17",
        "2025-08-23", "2025-08-24", "2025-08-25", "2025-08-26", "2025-08-27"
    ]
    
    db_files = [
        'comprehensive_evaluation.db',
        'comprehensive_merged_evaluation.db', 
        'final_evaluation.db',
        'ticket_data.db'
    ]
    
    for db_file in db_files:
        if not os.path.exists(db_file):
            continue
            
        print(f"\n--- {db_file} ---")
        conn = sqlite3.connect(db_file)
        
        try:
            # Check table structure
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"Tables: {tables}")
            
            # Check evaluations table (might be named differently)
            eval_table = None
            if 'evaluations' in tables:
                eval_table = 'evaluations'
            elif 'ticket_evaluations' in tables:
                eval_table = 'ticket_evaluations'
            
            if eval_table:
                # Get all August dates
                august_df = pd.read_sql_query(f'''
                    SELECT date, COUNT(*) as count
                    FROM {eval_table}
                    WHERE date LIKE '2025-08-%'
                    GROUP BY date
                    ORDER BY date
                ''', conn)
                
                print(f"August dates in {eval_table}:")
                if not august_df.empty:
                    for _, row in august_df.iterrows():
                        status = "MISSING" if row['date'] in missing_dates else "FOUND"
                        print(f"  {row['date']}: {row['count']} evaluations [{status}]")
                    
                    # Check for missing dates specifically
                    found_dates = set(august_df['date'].tolist())
                    missing_in_db = [d for d in missing_dates if d not in found_dates]
                    
                    if missing_in_db:
                        print(f"Missing in this database: {missing_in_db}")
                    else:
                        print("All target dates found in this database!")
                else:
                    print("  No August data found")
                
                # Get experiment names for August dates
                if eval_table == 'evaluations':
                    exp_df = pd.read_sql_query(f'''
                        SELECT date, experiment_name, COUNT(*) as count
                        FROM {eval_table}
                        WHERE date LIKE '2025-08-%'
                        GROUP BY date, experiment_name
                        ORDER BY date, experiment_name
                    ''', conn)
                else:
                    exp_df = pd.read_sql_query(f'''
                        SELECT date, experiment_name, COUNT(*) as count
                        FROM {eval_table}
                        WHERE date LIKE '2025-08-%' AND experiment_name IS NOT NULL
                        GROUP BY date, experiment_name
                        ORDER BY date, experiment_name
                    ''', conn)
                
                if not exp_df.empty:
                    print(f"\nExperiment names by date:")
                    for _, row in exp_df.iterrows():
                        print(f"  {row['date']}: {row['experiment_name']} ({row['count']} evaluations)")
            
        except Exception as e:
            print(f"Error analyzing {db_file}: {e}")
        
        conn.close()

def safe_fetch_with_timeout_handling(api_key, target_dates, max_retries=3):
    """Safely fetch data with proper timeout and rate limit handling"""
    print(f"\n=== SAFE FETCH FOR SPECIFIC DATES ===")
    print(f"Target dates: {target_dates}")
    
    if not target_dates:
        print("No target dates to fetch - all data already exists!")
        return {}
    
    try:
        client = Client(api_key=api_key)
        
        findings = {}
        
        for i, date_str in enumerate(target_dates):
            print(f"\nInvestigating {date_str} ({i+1}/{len(target_dates)})...")
            
            # Multiple retry attempts with increasing delays
            for retry in range(max_retries):
                try:
                    # Define time window for this date
                    start_of_day = datetime.strptime(f"{date_str} 00:00:00", "%Y-%m-%d %H:%M:%S")
                    end_of_day = datetime.strptime(f"{date_str} 23:59:59", "%Y-%m-%d %H:%M:%S")
                    
                    # Progressive delay based on retry count
                    if retry > 0:
                        delay = 10 * (2 ** retry)  # 10, 20, 40 seconds
                        print(f"  Retry {retry + 1}/{max_retries} after {delay}s delay...")
                        time.sleep(delay)
                    else:
                        time.sleep(5)  # Standard delay
                    
                    # Fetch runs for this specific date with timeout
                    print(f"  Fetching runs for {date_str}...")
                    
                    runs = client.list_runs(
                        project_name="evaluators",
                        start_time=start_of_day,
                        end_time=end_of_day,
                        limit=500
                    )
                    
                    # Convert to list with timeout handling
                    runs_list = []
                    run_count = 0
                    fetch_start_time = time.time()
                    timeout_seconds = 30  # 30 second timeout per date
                    
                    for run in runs:
                        if time.time() - fetch_start_time > timeout_seconds:
                            print(f"    Timeout reached after {timeout_seconds}s, got {run_count} runs")
                            break
                        runs_list.append(run)
                        run_count += 1
                    
                    print(f"  Retrieved {len(runs_list)} runs for {date_str}")
                    
                    # Analyze runs for this date
                    date_analysis = analyze_runs_for_date(runs_list, date_str)
                    findings[date_str] = date_analysis
                    
                    # Success - break retry loop
                    break
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    print(f"  Error on attempt {retry + 1}: {e}")
                    
                    if "rate limit" in error_msg or "429" in error_msg:
                        if retry < max_retries - 1:
                            wait_time = 60 * (retry + 1)  # 60, 120, 180 seconds
                            print(f"  Rate limit hit, waiting {wait_time} seconds before retry...")
                            time.sleep(wait_time)
                            continue
                        else:
                            print(f"  Rate limit persists after {max_retries} retries, skipping {date_str}")
                            break
                    
                    elif "timeout" in error_msg or "timed out" in error_msg:
                        if retry < max_retries - 1:
                            print(f"  Timeout occurred, retrying with longer delay...")
                            continue
                        else:
                            print(f"  Timeout persists after {max_retries} retries, skipping {date_str}")
                            break
                    
                    elif "connection" in error_msg or "network" in error_msg:
                        if retry < max_retries - 1:
                            print(f"  Network error, retrying...")
                            continue
                        else:
                            print(f"  Network issues persist, skipping {date_str}")
                            break
                    
                    else:
                        print(f"  Unknown error, skipping {date_str}: {e}")
                        break
        
        return findings
        
    except Exception as e:
        print(f"Fatal error in safe fetch: {e}")
        return {}

def analyze_runs_for_date(runs_list, date_str):
    """Analyze runs for a specific date"""
    date_analysis = {
        'total_runs': len(runs_list),
        'detailed_eval_runs': 0,
        'detailed_with_outputs': 0,
        'experiments': set(),
        'sample_experiments': []
    }
    
    for run in runs_list:
        if run.name == "detailed_similarity_evaluator":
            date_analysis['detailed_eval_runs'] += 1
            
            if run.outputs:
                date_analysis['detailed_with_outputs'] += 1
            
            # Get experiment name
            experiment = None
            if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
                experiment = run.metadata.get("experiment")
            
            if experiment:
                date_analysis['experiments'].add(experiment)
                if len(date_analysis['sample_experiments']) < 5:
                    date_analysis['sample_experiments'].append({
                        'experiment': experiment,
                        'has_outputs': bool(run.outputs),
                        'run_id': str(getattr(run, 'id', 'No ID'))
                    })
    
    print(f"  Analysis for {date_str}:")
    print(f"    Total runs: {date_analysis['total_runs']}")
    print(f"    Detailed evaluator runs: {date_analysis['detailed_eval_runs']}")
    print(f"    With outputs: {date_analysis['detailed_with_outputs']}")
    print(f"    Unique experiments: {len(date_analysis['experiments'])}")
    
    if date_analysis['experiments']:
        print(f"    Experiment names:")
        for exp in sorted(date_analysis['experiments']):
            # Check if experiment name contains the date
            if date_str.replace('-', '') in exp or date_str in exp:
                print(f"      ✓ {exp}")
            else:
                print(f"      ? {exp} (date mismatch?)")
    
    return date_analysis

def store_findings_to_database(findings, db_path='merged_evaluation.db'):
    """Store findings about available data to the database for future reference"""
    if not findings:
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create a findings table to track what data is available but not yet processed
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            total_runs INTEGER,
            detailed_eval_runs INTEGER,
            detailed_with_outputs INTEGER,
            unique_experiments INTEGER,
            experiment_names TEXT,
            analysis_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date)
        )
    ''')
    
    for date_str, analysis in findings.items():
        experiment_names = ', '.join(sorted(analysis['experiments']))
        
        cursor.execute('''
            INSERT OR REPLACE INTO data_findings 
            (date, total_runs, detailed_eval_runs, detailed_with_outputs, unique_experiments, experiment_names)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            date_str,
            analysis['total_runs'],
            analysis['detailed_eval_runs'],
            analysis['detailed_with_outputs'],
            len(analysis['experiments']),
            experiment_names
        ))
    
    conn.commit()
    conn.close()
    
    print(f"\nStored findings for {len(findings)} dates in merged_evaluation.db")

def safe_fetch_with_rate_limit_handling(api_key, target_dates):
    """Legacy function name - now calls the improved version"""
    return safe_fetch_with_timeout_handling(api_key, target_dates)

def analyze_experiment_patterns():
    """Analyze experiment patterns in existing comprehensive database"""
    print(f"\n=== ANALYZING EXPERIMENT PATTERNS ===")
    
    db_file = 'comprehensive_evaluation.db'
    if not os.path.exists(db_file):
        print(f"Comprehensive database not found")
        return
    
    conn = sqlite3.connect(db_file)
    
    # Get all experiment names
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    if 'latest_experiments' in tables:
        exp_df = pd.read_sql_query('''
            SELECT date, experiment_type, experiment_name
            FROM latest_experiments
            ORDER BY date, experiment_type
        ''', conn)
        
        print("All experiments in database:")
        for _, row in exp_df.iterrows():
            print(f"  {row['date']} | {row['experiment_type']} | {row['experiment_name']}")
        
        # Look for patterns
        all_experiments = exp_df['experiment_name'].tolist()
        
        print(f"\nExperiment naming patterns:")
        patterns = {
            'zendesk': [],
            'implementation': [],
            'homeowner': [],
            'management': [],
            'other': []
        }
        
        for exp in all_experiments:
            if 'zendesk-evaluation' in exp:
                patterns['zendesk'].append(exp)
            elif 'implementation-evaluation' in exp:
                patterns['implementation'].append(exp)
            elif 'homeowner-pay-evaluation' in exp:
                patterns['homeowner'].append(exp)
            elif 'management-pay-evaluation' in exp:
                patterns['management'].append(exp)
            else:
                patterns['other'].append(exp)
        
        for pattern_type, exps in patterns.items():
            if exps:
                print(f"\n{pattern_type.upper()} experiments ({len(exps)}):")
                for exp in sorted(exps)[:5]:  # Show first 5
                    print(f"  {exp}")
                if len(exps) > 5:
                    print(f"  ... and {len(exps) - 5} more")
    
    conn.close()

def main():
    """Main function with rate limit handling"""
    print("=== SAFE MISSING DATES INVESTIGATION ===")
    print("This script analyzes existing data first, then carefully fetches new data")
    
    # Step 1: Analyze existing databases
    analyze_existing_databases()
    
    # Step 2: Analyze experiment patterns
    analyze_experiment_patterns()
    
    # Step 3: Check if we need to fetch more data
    api_key = get_api_key()
    if not api_key:
        print("\nNo API key found - can only analyze existing databases")
        return
    
    print(f"\nAPI key found: {api_key[:10]}...")
    
    # Wait a bit to let rate limits reset
    print("Waiting 60 seconds for rate limits to reset...")
    time.sleep(60)
    
    missing_dates = [
        "2025-08-15", "2025-08-16", "2025-08-17",
        "2025-08-23", "2025-08-24", "2025-08-25", "2025-08-26", "2025-08-27"
    ]
    
    try:
        findings = safe_fetch_with_rate_limit_handling(api_key, missing_dates)
        
        if findings:
            print(f"\n=== CONCLUSIONS ===")
            
            dates_with_data = []
            dates_no_runs = []
            dates_no_outputs = []
            dates_no_experiments = []
            
            for date_str, analysis in findings.items():
                if analysis['detailed_eval_runs'] == 0:
                    dates_no_runs.append(date_str)
                elif analysis['detailed_with_outputs'] == 0:
                    dates_no_outputs.append(date_str)
                elif len(analysis['experiments']) == 0:
                    dates_no_experiments.append(date_str)
                else:
                    dates_with_data.append(date_str)
            
            print(f"Dates with processable data: {dates_with_data}")
            print(f"Dates with no detailed evaluator runs: {dates_no_runs}")
            print(f"Dates with runs but no outputs: {dates_no_outputs}")
            print(f"Dates with outputs but no experiment metadata: {dates_no_experiments}")
            
            if dates_with_data:
                print(f"\nRecommendation: The missing dates DO have evaluation data available")
                print(f"The issue is likely in the processing logic or database insertion")
            elif dates_no_outputs:
                print(f"\nRecommendation: Evaluation runs exist but are not completed yet")
                print(f"Wait for evaluations to finish or check evaluation status in LangSmith")
            elif dates_no_runs:
                print(f"\nRecommendation: No evaluation runs were created for these dates")
                print(f"Check if evaluation system was running on these dates")
        
    except Exception as e:
        print(f"Rate limit still active or other error: {e}")
        print("Recommendation: Wait longer for rate limits to reset, then try again")

def check_merged_database():
    """Check what dates exist in merged_evaluation.db"""
    print("=== CHECKING MERGED_EVALUATION.DB ===")
    
    missing_dates = [
        "2025-08-15", "2025-08-16", "2025-08-17", 
        "2025-08-23", "2025-08-24", "2025-08-25", "2025-08-26", "2025-08-27"
    ]
    
    db_file = 'merged_evaluation.db'
    if not os.path.exists(db_file):
        print(f"Database {db_file} not found!")
        print("Please run the migration script first to create merged_evaluation.db")
        return []
    
    print(f"\n--- {db_file} ---")
    conn = sqlite3.connect(db_file)
    
    try:
        # Get all August 2025 dates
        df = pd.read_sql_query('''
            SELECT date, COUNT(*) as count
            FROM evaluations
            WHERE date LIKE '2025-08-%'
            GROUP BY date
            ORDER BY date
        ''', conn)
        
        if not df.empty:
            found_dates = set(df['date'].tolist())
            missing_in_db = [d for d in missing_dates if d not in found_dates]
            found_missing_dates = [d for d in missing_dates if d in found_dates]
            
            print(f"Total August dates in database: {len(df)}")
            print(f"Target dates already found: {len(found_missing_dates)}")
            print(f"Target dates still missing: {len(missing_in_db)}")
            
            if found_missing_dates:
                print(f"Already have data for: {found_missing_dates}")
            
            if missing_in_db:
                print(f"Still missing: {missing_in_db}")
            
            print("\nAll August dates in merged database:")
            for _, row in df.iterrows():
                status = "TARGET-MISSING" if row['date'] in missing_dates else "FOUND"
                print(f"  {row['date']}: {row['count']} evaluations [{status}]")
            
            return missing_in_db
        else:
            print("No August data found in merged database")
            return missing_dates
    
    except Exception as e:
        print(f"Error checking merged database: {e}")
        return missing_dates
    
    finally:
        conn.close()

def quick_database_date_check():
    """Quick check of what dates exist in databases without API calls"""
    print("=== QUICK DATABASE DATE CHECK ===")
    
    missing_dates = [
        "2025-08-15", "2025-08-16", "2025-08-17", 
        "2025-08-23", "2025-08-24", "2025-08-25", "2025-08-26", "2025-08-27"
    ]
    
    # Check merged database first
    still_missing = check_merged_database()
    
    # Also check other databases for reference
    db_files = [
        ('comprehensive_evaluation.db', 'evaluations'),
        ('comprehensive_merged_evaluation.db', 'evaluations'),
        ('ticket_data.db', 'ticket_evaluations'),
        ('final_evaluation.db', 'evaluations')
    ]
    
    for db_file, table_name in db_files:
        if not os.path.exists(db_file):
            continue
        
        print(f"\n--- {db_file} ---")
        conn = sqlite3.connect(db_file)
        
        try:
            # Get all August 2025 dates
            df = pd.read_sql_query(f'''
                SELECT date, COUNT(*) as count
                FROM {table_name}
                WHERE date LIKE '2025-08-%'
                GROUP BY date
                ORDER BY date
            ''', conn)
            
            if not df.empty:
                found_dates = set(df['date'].tolist())
                missing_in_this_db = [d for d in missing_dates if d not in found_dates]
                found_missing_dates = [d for d in missing_dates if d in found_dates]
                
                print(f"August dates: {len(df)} total")
                print(f"Missing target dates in this DB: {len(missing_in_this_db)}")
                print(f"Found target dates in this DB: {len(found_missing_dates)}")
                
                if found_missing_dates:
                    print(f"FOUND target dates: {found_missing_dates}")
                
                if missing_in_this_db:
                    print(f"MISSING target dates: {missing_in_this_db}")
                
                # Show all August dates for context
                print("All August dates in this database:")
                for _, row in df.iterrows():
                    status = "TARGET" if row['date'] in missing_dates else ""
                    print(f"  {row['date']}: {row['count']} {status}")
            else:
                print("No August data found")
        
        except Exception as e:
            print(f"Error checking {db_file}: {e}")
        
        conn.close()

if __name__ == "__main__":
    # First do a quick check without API calls
    quick_database_date_check()
    
    # Then analyze existing databases
    analyze_existing_databases()
    
    # Finally try to fetch more data if needed (with rate limit handling)
    print(f"\nTo fetch more data, wait for rate limits to reset and run again")
    print(f"Or run: main() to attempt careful fetching with delays")