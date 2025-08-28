#!/usr/bin/env python3
"""
Simple debug script to test data fetching and see what's happening with evaluation data
"""

import os
import sys
from datetime import datetime, timedelta
from langsmith import Client
import json
import re
import toml

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

def test_api_connection():
    """Test if we can connect to LangSmith API"""
    print("🔍 Testing API Connection...")
    
    # Try multiple sources for API key
    api_key = get_api_key_from_secrets()
    if not api_key:
        api_key = os.getenv("LANGSMITH_API_KEY", "")
    
    if not api_key:
        print("❌ No API key found!")
        print("   Check .streamlit/secrets.toml or set LANGSMITH_API_KEY environment variable")
        return False
    
    print(f"✅ API key found: {api_key[:10]}...")
    
    try:
        client = Client(api_key=api_key)
        # Try to list projects to test connection
        projects = list(client.list_projects())
        print(f"✅ API connection successful! Found {len(projects)} projects")
        return True, api_key
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        return False, None

def test_runs_fetching(api_key):
    """Test fetching runs from the evaluators project"""
    print("\n🔍 Testing Runs Fetching...")
    
    client = Client(api_key=api_key)
    
    try:
        # Fetch runs from evaluators project
        runs = client.list_runs(project_name="evaluators", limit=100)
        runs_list = list(runs)
        print(f"✅ Successfully fetched {len(runs_list)} runs from evaluators project")
        
        if len(runs_list) == 0:
            print("⚠️  No runs found in evaluators project")
            return False
            
        return runs_list
    except Exception as e:
        print(f"❌ Failed to fetch runs: {e}")
        return False

def analyze_experiments(runs_list):
    """Analyze what experiments are available"""
    print("\n🔍 Analyzing Experiments...")
    
    experiments = {}
    run_types = {}
    
    for run in runs_list:
        # Count run types
        run_name = getattr(run, 'name', 'unknown')
        run_types[run_name] = run_types.get(run_name, 0) + 1
        
        # Count experiments
        if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
            experiment = run.metadata.get("experiment")
            if experiment:
                experiments[experiment] = experiments.get(experiment, 0) + 1
    
    print(f"📊 Found {len(run_types)} run types:")
    for run_type, count in sorted(run_types.items()):
        print(f"   - {run_type}: {count} runs")
    
    print(f"\n📊 Found {len(experiments)} experiments:")
    for experiment, count in sorted(experiments.items()):
        print(f"   - {experiment}: {count} runs")
    
    return experiments

def extract_date_from_experiment(experiment):
    """Extract date from experiment name based on the evaluation system"""
    # For pre-August 15, 2025: zendesk-evaluation-2025-07-XX format
    if experiment.startswith("zendesk-evaluation-2025-"):
        match = re.search(r"zendesk-evaluation-(\d{4}-\d{2}-\d{2})", experiment)
        if match:
            return match.group(1)
    
    # For post-August 15, 2025: implementation-evaluation-2025-XX-XX format
    elif "implementation-evaluation-" in experiment:
        match = re.search(r"implementation-evaluation-(\d{4}-\d{2}-\d{2})", experiment)
        if match:
            return match.group(1)
    
    # For post-August 15, 2025: homeowner-pay-evaluation-2025-XX-XX format
    elif "homeowner-pay-evaluation-" in experiment:
        match = re.search(r"homeowner-pay-evaluation-(\d{4}-\d{2}-\d{2})", experiment)
        if match:
            return match.group(1)
    
    # For post-August 15, 2025: management-pay-evaluation-2025-XX-XX format
    elif "management-pay-evaluation-" in experiment:
        match = re.search(r"management-pay-evaluation-(\d{4}-\d{2}-\d{2})", experiment)
        if match:
            return match.group(1)
    
    return None

def test_specific_date_range(api_key):
    """Test fetching data for specific date range around 2025-07-25"""
    print("\n🔍 Testing Specific Date Range (2025-07-20 to 2025-07-30)...")
    
    client = Client(api_key=api_key)
    
    # Get more runs to find data in our date range
    runs = client.list_runs(project_name="evaluators", limit=1000)
    runs_list = list(runs)
    
    target_dates = []
    for i in range(20, 31):  # July 20-30
        target_dates.append(f"2025-07-{i:02d}")
    
    print(f"🎯 Looking for data on dates: {target_dates}")
    
    found_dates = set()
    detailed_similarity_runs = 0
    
    for run in runs_list:
        if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
            experiment = run.metadata.get("experiment")
            if experiment:
                date_str = extract_date_from_experiment(experiment)
                if date_str in target_dates:
                    found_dates.add(date_str)
                    if getattr(run, 'name', None) == "detailed_similarity_evaluator":
                        detailed_similarity_runs += 1
                        print(f"   ✅ Found detailed_similarity_evaluator run for {date_str}")
    
    print(f"\n📊 Results:")
    print(f"   - Found data for dates: {sorted(found_dates)}")
    print(f"   - Missing dates: {sorted(set(target_dates) - found_dates)}")
    print(f"   - Total detailed_similarity_evaluator runs in range: {detailed_similarity_runs}")

def test_database_connection():
    """Test database connection and data"""
    print("\n🔍 Testing Database Connection...")
    
    try:
        from database import TicketDatabase
        db = TicketDatabase()
        
        # Test getting data for different ranges
        print("📊 Testing database data retrieval:")
        
        for date_range in ["2_weeks", "4_weeks", "all_data"]:
            try:
                df, daily_data = db.get_data_for_range(date_range)
                if df is not None and not df.empty:
                    print(f"   ✅ {date_range}: {len(df)} rows, date range: {df['date'].min()} to {df['date'].max()}")
                else:
                    print(f"   ❌ {date_range}: No data found")
            except Exception as e:
                print(f"   ❌ {date_range}: Error - {e}")
        
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def main():
    """Run all debug tests"""
    print("🚀 Starting Debug Tests...")
    print("=" * 50)
    
    # Test 1: API Connection
    success, api_key = test_api_connection()
    if not success:
        print("❌ Stopping tests due to API connection failure")
        return
    
    # Test 2: Runs Fetching
    runs_list = test_runs_fetching(api_key)
    if runs_list is False:
        print("❌ Stopping tests due to runs fetching failure")
        return
    
    # Test 3: Analyze Experiments
    experiments = analyze_experiments(runs_list)
    
    # Test 4: Specific Date Range
    test_specific_date_range(api_key)
    
    # Test 5: Database Connection
    test_database_connection()
    
    print("\n" + "=" * 50)
    print("🏁 Debug Tests Complete!")

if __name__ == "__main__":
    main()
