#!/usr/bin/env python3
"""
Debug pagination issue with LangSmith API calls
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

def debug_pagination():
    """Debug pagination issue"""
    print("🔍 Debugging Pagination Issue...")
    
    api_key = get_api_key_from_secrets()
    if not api_key:
        print("❌ No API key found!")
        return
    
    client = Client(api_key=api_key)
    
    # Test different limits
    limits = [100, 500, 1000, 2000, 5000]
    
    for limit in limits:
        print(f"\n📊 Testing with limit={limit}")
        
        runs = client.list_runs(project_name="evaluators", limit=limit)
        runs_list = list(runs)
        
        print(f"  Total runs fetched: {len(runs_list)}")
        
        # Check for August 4-14 data
        august_4_14_count = 0
        for run in runs_list:
            if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
                experiment = run.metadata.get("experiment")
                if experiment and experiment.startswith("zendesk-evaluation-2025-08-"):
                    # Check if it's August 4-14
                    match = re.search(r"zendesk-evaluation-2025-08-(\d{2})", experiment)
                    if match:
                        day = int(match.group(1))
                        if 4 <= day <= 14:
                            august_4_14_count += 1
        
        print(f"  August 4-14 runs found: {august_4_14_count}")
        
        if august_4_14_count > 0:
            print(f"  ✅ Found data with limit={limit}")
            break
    
    # Test without limit
    print(f"\n📊 Testing without limit parameter")
    runs = client.list_runs(project_name="evaluators")
    runs_list = list(runs)
    
    print(f"  Total runs fetched: {len(runs_list)}")
    
    # Check for August 4-14 data
    august_4_14_count = 0
    august_4_14_experiments = set()
    
    for run in runs_list:
        if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
            experiment = run.metadata.get("experiment")
            if experiment and experiment.startswith("zendesk-evaluation-2025-08-"):
                # Check if it's August 4-14
                match = re.search(r"zendesk-evaluation-2025-08-(\d{2})", experiment)
                if match:
                    day = int(match.group(1))
                    if 4 <= day <= 14:
                        august_4_14_count += 1
                        august_4_14_experiments.add(experiment)
    
    print(f"  August 4-14 runs found: {august_4_14_count}")
    print(f"  August 4-14 experiments: {sorted(august_4_14_experiments)}")
    
    # Check the date range of all experiments
    print(f"\n📅 Checking date range of all experiments...")
    all_dates = set()
    
    for run in runs_list:
        if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
            experiment = run.metadata.get("experiment")
            if experiment and experiment.startswith("zendesk-evaluation-2025-"):
                match = re.search(r"zendesk-evaluation-(\d{4}-\d{2}-\d{2})", experiment)
                if match:
                    all_dates.add(match.group(1))
    
    august_dates = [date for date in sorted(all_dates) if date.startswith("2025-08-")]
    print(f"  All August dates found: {august_dates}")

if __name__ == "__main__":
    debug_pagination()
