#!/usr/bin/env python3
"""
Check for historical evaluation data before August 2025
"""

import os
import toml
from langsmith import Client
import re
from datetime import datetime

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

def check_all_historical_data():
    """Check for any evaluation data before August 2025"""
    print("🔍 Checking for Historical Evaluation Data...")
    
    api_key = get_api_key_from_secrets()
    if not api_key:
        print("❌ No API key found!")
        return
    
    client = Client(api_key=api_key)
    
    # Get a larger sample of runs to check for historical data
    print("📊 Fetching runs (this may take a moment)...")
    runs = client.list_runs(project_name="evaluators", limit=2000)
    runs_list = list(runs)
    
    print(f"✅ Fetched {len(runs_list)} runs")
    
    # Analyze all experiments
    experiments = {}
    detailed_similarity_runs = 0
    
    for run in runs_list:
        if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
            experiment = run.metadata.get("experiment")
            if experiment:
                experiments[experiment] = experiments.get(experiment, 0) + 1
                
                if getattr(run, 'name', None) == "detailed_similarity_evaluator":
                    detailed_similarity_runs += 1
    
    print(f"\n📊 Found {len(experiments)} unique experiments")
    print(f"📊 Found {detailed_similarity_runs} detailed_similarity_evaluator runs")
    
    # Extract dates from experiments
    experiment_dates = []
    for experiment in experiments.keys():
        # Try different date patterns
        date_patterns = [
            r"zendesk-evaluation-(\d{4}-\d{2}-\d{2})",
            r"implementation-evaluation-(\d{4}-\d{2}-\d{2})",
            r"homeowner-pay-evaluation-(\d{4}-\d{2}-\d{2})",
            r"management-pay-evaluation-(\d{4}-\d{2}-\d{2})",
            r"evaluation-(\d{4}-\d{2}-\d{2})",
            r"(\d{4}-\d{2}-\d{2})"  # Generic date pattern
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, experiment)
            if match:
                date_str = match.group(1)
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    experiment_dates.append((date_str, date_obj, experiment))
                    break
                except ValueError:
                    continue
    
    if not experiment_dates:
        print("❌ No dates found in experiment names")
        return
    
    # Sort by date
    experiment_dates.sort(key=lambda x: x[1])
    
    print(f"\n📅 Experiment Timeline:")
    for date_str, date_obj, experiment in experiment_dates:
        count = experiments[experiment]
        print(f"   {date_str}: {experiment} ({count} runs)")
    
    # Check for July 2025 data specifically
    july_2025_data = [d for d in experiment_dates if d[1].year == 2025 and d[1].month == 7]
    
    if july_2025_data:
        print(f"\n✅ Found {len(july_2025_data)} experiments in July 2025:")
        for date_str, date_obj, experiment in july_2025_data:
            count = experiments[experiment]
            print(f"   {date_str}: {experiment} ({count} runs)")
    else:
        print(f"\n❌ No data found in July 2025")
        print("   This explains why there's no data starting from July 25!")
    
    # Check for any data before August 2025
    pre_august_data = [d for d in experiment_dates if d[1] < datetime(2025, 8, 1)]
    
    if pre_august_data:
        print(f"\n✅ Found {len(pre_august_data)} experiments before August 2025:")
        for date_str, date_obj, experiment in pre_august_data:
            count = experiments[experiment]
            print(f"   {date_str}: {experiment} ({count} runs)")
    else:
        print(f"\n❌ No data found before August 2025")
        print("   All evaluation data starts from August 26, 2025")

if __name__ == "__main__":
    check_all_historical_data()
