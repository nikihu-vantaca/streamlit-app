#!/usr/bin/env python3
"""
Check for evaluation data between August 4-15, 2025
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

def check_august_4_to_15_data():
    """Check for evaluation data between August 4-15, 2025"""
    print("🔍 Checking for Evaluation Data (August 4-15, 2025)...")
    
    api_key = get_api_key_from_secrets()
    if not api_key:
        print("❌ No API key found!")
        return
    
    client = Client(api_key=api_key)
    
    # Get a larger sample of runs to check for data in our target range
    print("📊 Fetching runs (this may take a moment)...")
    runs = client.list_runs(project_name="evaluators", limit=3000)
    runs_list = list(runs)
    
    print(f"✅ Fetched {len(runs_list)} runs")
    
    # Define target date range
    target_dates = []
    for i in range(4, 16):  # August 4-15
        target_dates.append(f"2025-08-{i:02d}")
    
    print(f"🎯 Looking for data on dates: {target_dates}")
    
    # Analyze experiments and find matches
    experiments = {}
    found_dates = set()
    detailed_similarity_runs = 0
    
    for run in runs_list:
        if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
            experiment = run.metadata.get("experiment")
            if experiment:
                experiments[experiment] = experiments.get(experiment, 0) + 1
                
                # Extract date from experiment name
                date_str = extract_date_from_experiment(experiment)
                if date_str in target_dates:
                    found_dates.add(date_str)
                    if getattr(run, 'name', None) == "detailed_similarity_evaluator":
                        detailed_similarity_runs += 1
                        print(f"   ✅ Found detailed_similarity_evaluator run for {date_str}: {experiment}")
    
    print(f"\n📊 Results for August 4-15, 2025:")
    print(f"   - Found data for dates: {sorted(found_dates)}")
    print(f"   - Missing dates: {sorted(set(target_dates) - found_dates)}")
    print(f"   - Total detailed_similarity_evaluator runs in range: {detailed_similarity_runs}")
    
    # Show all experiments in the date range
    if found_dates:
        print(f"\n📅 Experiments found in August 4-15, 2025:")
        for experiment, count in sorted(experiments.items()):
            date_str = extract_date_from_experiment(experiment)
            if date_str in target_dates:
                print(f"   {date_str}: {experiment} ({count} runs)")
    
    # Check if there's any data before August 4
    print(f"\n🔍 Checking for data before August 4, 2025...")
    early_august_dates = []
    for i in range(1, 4):  # August 1-3
        early_august_dates.append(f"2025-08-{i:02d}")
    
    early_found = set()
    for run in runs_list:
        if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
            experiment = run.metadata.get("experiment")
            if experiment:
                date_str = extract_date_from_experiment(experiment)
                if date_str in early_august_dates:
                    early_found.add(date_str)
                    print(f"   ✅ Found data for {date_str}: {experiment}")
    
    if early_found:
        print(f"   - Found data for early August dates: {sorted(early_found)}")
    else:
        print(f"   - No data found for early August dates: {early_august_dates}")

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

if __name__ == "__main__":
    check_august_4_to_15_data()
