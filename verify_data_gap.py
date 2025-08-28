#!/usr/bin/env python3
"""
Verify data availability and identify gaps between August 4-14, 2025
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

def verify_data_gap():
    """Verify data availability and identify gaps"""
    print("🔍 Verifying Data Availability and Gaps...")
    
    api_key = get_api_key_from_secrets()
    if not api_key:
        print("❌ No API key found!")
        return
    
    client = Client(api_key=api_key)
    
    # Get a comprehensive sample of runs
    print("📊 Fetching runs (this may take a moment)...")
    runs = client.list_runs(project_name="evaluators", limit=5000)
    runs_list = list(runs)
    
    print(f"✅ Fetched {len(runs_list)} runs")
    
    # Define the full range we want to check
    target_dates = []
    for i in range(1, 32):  # August 1-31
        target_dates.append(f"2025-08-{i:02d}")
    
    print(f"🎯 Checking data availability for: {target_dates}")
    
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
    
    print(f"\n📊 Results for August 2025:")
    print(f"   - Found data for dates: {sorted(found_dates)}")
    print(f"   - Missing dates: {sorted(set(target_dates) - found_dates)}")
    print(f"   - Total detailed_similarity_evaluator runs: {detailed_similarity_runs}")
    
    # Check specifically for the gap
    gap_dates = []
    for i in range(4, 15):  # August 4-14
        gap_dates.append(f"2025-08-{i:02d}")
    
    gap_found = [date for date in gap_dates if date in found_dates]
    gap_missing = [date for date in gap_dates if date not in found_dates]
    
    print(f"\n🎯 SPECIFIC GAP ANALYSIS (August 4-14):")
    print(f"   - Dates WITH data: {gap_found}")
    print(f"   - Dates MISSING data: {gap_missing}")
    
    if not gap_found:
        print(f"   ❌ CONFIRMED: NO DATA between August 4-14, 2025")
    else:
        print(f"   ⚠️  PARTIAL DATA: Some dates have data, others don't")
    
    # Show all experiments in the date range
    if found_dates:
        print(f"\n📅 All experiments found in August 2025:")
        for experiment, count in sorted(experiments.items()):
            date_str = extract_date_from_experiment(experiment)
            if date_str in target_dates:
                print(f"   {date_str}: {experiment} ({count} runs)")
    
    # Check what data exists before and after the gap
    print(f"\n📅 Data before gap (August 1-3):")
    early_dates = [f"2025-08-{i:02d}" for i in range(1, 4)]
    early_found = [date for date in early_dates if date in found_dates]
    print(f"   - Found: {early_found}")
    
    print(f"\n📅 Data after gap (August 15+):")
    late_dates = [f"2025-08-{i:02d}" for i in range(15, 32)]
    late_found = [date for date in late_dates if date in found_dates]
    print(f"   - Found: {late_found}")

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
    verify_data_gap()
