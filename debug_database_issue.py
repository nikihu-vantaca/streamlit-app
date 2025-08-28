#!/usr/bin/env python3
"""
Debug why database isn't showing data for August 4-14 despite data existing in LangSmith
"""

import os
import toml
from langsmith import Client
import re
from datetime import datetime
import json

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

def debug_august_4_14_data():
    """Debug why August 4-14 data isn't showing up"""
    print("🔍 Debugging August 4-14 Data Processing...")
    
    api_key = get_api_key_from_secrets()
    if not api_key:
        print("❌ No API key found!")
        return
    
    client = Client(api_key=api_key)
    
    # Focus on August 4-14 data
    target_dates = [f"2025-08-{i:02d}" for i in range(4, 15)]
    
    print(f"🎯 Analyzing data for: {target_dates}")
    
    # Get runs for these specific dates
    runs = client.list_runs(project_name="evaluators", limit=2000)
    runs_list = list(runs)
    
    print(f"✅ Fetched {len(runs_list)} total runs")
    
    # Filter runs for our target dates
    target_runs = []
    for run in runs_list:
        if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
            experiment = run.metadata.get("experiment")
            if experiment:
                date_str = extract_date_from_experiment(experiment)
                if date_str in target_dates:
                    target_runs.append(run)
    
    print(f"📊 Found {len(target_runs)} runs for August 4-14")
    
    # Analyze detailed_similarity_evaluator runs specifically
    detailed_runs = []
    for run in target_runs:
        if getattr(run, 'name', None) == "detailed_similarity_evaluator":
            detailed_runs.append(run)
    
    print(f"🔍 Found {len(detailed_runs)} detailed_similarity_evaluator runs")
    
    # Sample a few runs to see their structure
    if detailed_runs:
        print(f"\n📋 Sample run analysis:")
        for i, run in enumerate(detailed_runs[:3]):  # Look at first 3 runs
            print(f"\n--- Run {i+1} ---")
            print(f"  ID: {getattr(run, 'id', 'N/A')}")
            print(f"  Name: {getattr(run, 'name', 'N/A')}")
            print(f"  Experiment: {run.metadata.get('experiment', 'N/A')}")
            print(f"  Start Time: {getattr(run, 'start_time', 'N/A')}")
            
            # Check inputs
            if hasattr(run, 'inputs') and run.inputs:
                print(f"  Inputs: {run.inputs}")
            
            # Check outputs
            if hasattr(run, 'outputs') and run.outputs:
                print(f"  Outputs: {run.outputs}")
                
                # Try to parse outputs
                if isinstance(run.outputs, str):
                    try:
                        parsed_output = json.loads(run.outputs)
                        print(f"  Parsed Output: {parsed_output}")
                        
                        # Check for ticket_id
                        ticket_id = extract_ticket_id_from_run(run, parsed_output)
                        print(f"  Extracted Ticket ID: {ticket_id}")
                        
                        # Check for quality and comment
                        quality = parsed_output.get('quality')
                        comment = parsed_output.get('comment')
                        evaluation_key = parsed_output.get('key', '')
                        print(f"  Quality: {quality}")
                        print(f"  Comment: {comment}")
                        print(f"  Evaluation Key: {evaluation_key}")
                        
                    except json.JSONDecodeError:
                        print(f"  Could not parse outputs as JSON")
                elif isinstance(run.outputs, dict):
                    print(f"  Output Dict: {run.outputs}")
                    
                    # Check for ticket_id
                    ticket_id = extract_ticket_id_from_run(run, run.outputs)
                    print(f"  Extracted Ticket ID: {ticket_id}")
                    
                    # Check for quality and comment
                    quality = run.outputs.get('quality')
                    comment = run.outputs.get('comment')
                    evaluation_key = run.outputs.get('key', '')
                    print(f"  Quality: {quality}")
                    print(f"  Comment: {comment}")
                    print(f"  Evaluation Key: {evaluation_key}")
    
    # Check if there are any issues with the data structure
    print(f"\n🔍 Checking for potential issues:")
    
    # Count runs by date
    runs_by_date = {}
    for run in detailed_runs:
        experiment = run.metadata.get("experiment")
        date_str = extract_date_from_experiment(experiment)
        if date_str:
            runs_by_date[date_str] = runs_by_date.get(date_str, 0) + 1
    
    print(f"📅 Runs by date:")
    for date in target_dates:
        count = runs_by_date.get(date, 0)
        print(f"  {date}: {count} runs")

def extract_date_from_experiment(experiment):
    """Extract date from experiment name"""
    if experiment.startswith("zendesk-evaluation-2025-"):
        match = re.search(r"zendesk-evaluation-(\d{4}-\d{2}-\d{2})", experiment)
        if match:
            return match.group(1)
    return None

def extract_ticket_id_from_run(run, result):
    """Extract ticket_id from run inputs or result"""
    # Try to get from run inputs first
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
    
    # Fallback to result
    return result.get('ticket_id')

if __name__ == "__main__":
    debug_august_4_14_data()
