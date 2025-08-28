# get evaluation of separated groups 
from langsmith import Client
import json
import time
from datetime import datetime, timedelta, timezone

client = Client(api_key="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")

# Configuration matching van_zendesk_langsmith implementation
project_name = "evaluators"

# Get runs with pagination to avoid rate limits
print(f"Fetching runs from project '{project_name}'...")

# Start with a larger batch to get more comprehensive results
runs_list = []
try:
    # Get runs in larger batches
    runs = client.list_runs(project_name=project_name, limit=1000)
    runs_list = list(runs)
    print(f"Successfully fetched {len(runs_list)} runs (limited to 1000 to avoid rate limits)")
except Exception as e:
    print(f"Error fetching runs: {e}")
    print("Trying with smaller limit...")
    try:
        runs = client.list_runs(project_name=project_name, limit=500)
        runs_list = list(runs)
        print(f"Successfully fetched {len(runs_list)} runs (limited to 500)")
    except Exception as e2:
        print(f"Error fetching runs with limit 500: {e2}")
        exit(1)

# Analysis counters matching the implementation
implementation_stats = {
    "total": 0,
    "copy_paste": 0,
    "low_quality": 0,
    "skipped": 0,
    "high_quality": 0,
    "scores": []
}

homeowner_stats = {
    "total": 0,
    "copy_paste": 0,
    "low_quality": 0,
    "skipped": 0,
    "high_quality": 0,
    "scores": []
}

management_stats = {
    "total": 0,
    "copy_paste": 0,
    "low_quality": 0,
    "skipped": 0,
    "high_quality": 0,
    "scores": []
}

# Debug: Let's see what types of runs exist
print("\nDEBUGGING: Examining all run types...")
run_names = {}
for run in runs_list:
    name = run.name
    if name not in run_names:
        run_names[name] = 0
    run_names[name] += 1

print("Run types found:")
for name, count in sorted(run_names.items()):
    print(f"  - {name}: {count} runs")

# Debug: Let's see all experiments found
print("\nDEBUGGING: All experiments found:")
all_experiments = {}
for run in runs_list:
    if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
        experiment = run.metadata.get("experiment")
        if experiment:
            if experiment not in all_experiments:
                all_experiments[experiment] = 0
            all_experiments[experiment] += 1

print("All experiments found:")
for experiment, count in sorted(all_experiments.items()):
    print(f"  - {experiment}: {count} runs")

# Find the three specific evaluation experiments
def find_specific_evaluation_experiments(runs):
    """Find the three specific evaluation experiments: implementation, homeowner, and management"""
    experiments = {
        "implementation": [],
        "homeowner": [],
        "management": []
    }
    
    for run in runs:
        # Check all runs, not just detailed_similarity_evaluator
        if not run.outputs:
            continue
            
        experiment = None
        if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
            experiment = run.metadata.get("experiment")
        
        if not experiment:
            continue
            
        # Categorize experiments by type
        if "implementation-evaluation-" in experiment:
            experiments["implementation"].append((experiment, run.start_time))
        elif "homeowner-pay-evaluation-" in experiment:
            experiments["homeowner"].append((experiment, run.start_time))
        elif "management-pay-evaluation-" in experiment:
            experiments["management"].append((experiment, run.start_time))
    
    # Get the most recent experiment of each type
    most_recent = {}
    for exp_type, exp_list in experiments.items():
        if exp_list:
            # Sort by start_time (most recent first) and take the first one
            exp_list.sort(key=lambda x: x[1] if x[1] else datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            most_recent[exp_type] = exp_list[0][0]
        else:
            most_recent[exp_type] = None
    
    return most_recent

# Find the specific evaluation experiments
specific_experiments = find_specific_evaluation_experiments(runs_list)

print("\nFinding specific evaluation experiments...")
print("Specific experiments found:")
for exp_type, experiment in specific_experiments.items():
    if experiment:
        print(f"  - {exp_type.capitalize()}: {experiment}")
    else:
        print(f"  - {exp_type.capitalize()}: No experiments found")
print("-" * 80)

# Analyze each specific experiment
print("Analyzing specific evaluation experiments...")

for exp_type, experiment in specific_experiments.items():
    if not experiment:
        print(f"No {exp_type} experiment found, skipping...")
        continue
    
    print(f"\nAnalyzing {exp_type} experiment: {experiment}")
    
    # Get stats for this experiment type
    if exp_type == "implementation":
        stats = implementation_stats
    elif exp_type == "homeowner":
        stats = homeowner_stats
    elif exp_type == "management":
        stats = management_stats
    else:
        continue
    
    # Count runs for this experiment
    experiment_runs = 0
    
    for run in runs_list:
        # Only process detailed_similarity_evaluator runs with outputs
        if run.name != "detailed_similarity_evaluator" or not run.outputs:
            continue
        
        # Check if this run is from the target experiment
        run_experiment = None
        if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
            run_experiment = run.metadata.get("experiment")
        
        # Skip if not from the target experiment
        if run_experiment != experiment:
            continue
        
        experiment_runs += 1
        
        # Process the evaluation output
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
        
        stats["total"] += 1
        
        # Extract evaluation details
        quality = result.get("quality")
        comment = result.get("comment")
        score = result.get("score")
        
        # Categorize based on quality and comments
        if quality == "copy_paste":
            stats["copy_paste"] += 1
        elif quality == "low_quality":
            stats["low_quality"] += 1
        elif quality == "high_quality":
            stats["high_quality"] += 1
        elif comment == "empty_bot_answer":
            stats["skipped"] += 1
        elif comment and "management_company_ticket" in comment:
            stats["skipped"] += 1
        elif comment and "empty_human_answer" in comment:
            stats["skipped"] += 1
        
        # Collect scores for analysis
        if score is not None:
            stats["scores"].append(score)
    
    print(f"  Found {experiment_runs} runs for {exp_type} experiment")

# Print comprehensive analysis
print("\n" + "=" * 80)
print("EVALUATION ANALYSIS RESULTS")
print("=" * 80)

# Implementation tickets analysis
print(f"\nIMPLEMENTATION TICKETS ({implementation_stats['total']} total)")
print("-" * 40)
if implementation_stats['total'] > 0:
    print(f"Copy-paste responses: {implementation_stats['copy_paste']} ({100 * implementation_stats['copy_paste'] / implementation_stats['total']:.1f}%)")
    print(f"Low quality responses: {implementation_stats['low_quality']} ({100 * implementation_stats['low_quality'] / implementation_stats['total']:.1f}%)")
    print(f"High quality responses: {implementation_stats['high_quality']} ({100 * implementation_stats['high_quality'] / implementation_stats['total']:.1f}%)")
    print(f"Skipped tickets: {implementation_stats['skipped']} ({100 * implementation_stats['skipped'] / implementation_stats['total']:.1f}%)")
    if implementation_stats['scores']:
        avg_score = sum(implementation_stats['scores']) / len(implementation_stats['scores'])
        print(f"Average score: {avg_score:.2f}/10")
        print(f"Score range: {min(implementation_stats['scores']):.2f} - {max(implementation_stats['scores']):.2f}")
else:
    print("No implementation tickets evaluated")

# Homeowner tickets analysis
print(f"\nHOMEOWNER TICKETS ({homeowner_stats['total']} total)")
print("-" * 40)
if homeowner_stats['total'] > 0:
    print(f"Copy-paste responses: {homeowner_stats['copy_paste']} ({100 * homeowner_stats['copy_paste'] / homeowner_stats['total']:.1f}%)")
    print(f"Low quality responses: {homeowner_stats['low_quality']} ({100 * homeowner_stats['low_quality'] / homeowner_stats['total']:.1f}%)")
    print(f"High quality responses: {homeowner_stats['high_quality']} ({100 * homeowner_stats['high_quality'] / homeowner_stats['total']:.1f}%)")
    print(f"Skipped tickets: {homeowner_stats['skipped']} ({100 * homeowner_stats['skipped'] / homeowner_stats['total']:.1f}%)")
    if homeowner_stats['scores']:
        avg_score = sum(homeowner_stats['scores']) / len(homeowner_stats['scores'])
        print(f"Average score: {avg_score:.2f}/10")
        print(f"Score range: {min(homeowner_stats['scores']):.2f} - {max(homeowner_stats['scores']):.2f}")
else:
    print("No homeowner tickets evaluated")

# Management tickets analysis
print(f"\nMANAGEMENT TICKETS ({management_stats['total']} total)")
print("-" * 40)
if management_stats['total'] > 0:
    print(f"Copy-paste responses: {management_stats['copy_paste']} ({100 * management_stats['copy_paste'] / management_stats['total']:.1f}%)")
    print(f"Low quality responses: {management_stats['low_quality']} ({100 * management_stats['low_quality'] / management_stats['total']:.1f}%)")
    print(f"High quality responses: {management_stats['high_quality']} ({100 * management_stats['high_quality'] / management_stats['total']:.1f}%)")
    print(f"Skipped tickets: {management_stats['skipped']} ({100 * management_stats['skipped'] / management_stats['total']:.1f}%)")
    if management_stats['scores']:
        avg_score = sum(management_stats['scores']) / len(management_stats['scores'])
        print(f"Average score: {avg_score:.2f}/10")
        print(f"Score range: {min(management_stats['scores']):.2f} - {max(management_stats['scores']):.2f}")
else:
    print("No management tickets evaluated")

# Overall summary
total_tickets = implementation_stats['total'] + homeowner_stats['total'] + management_stats['total']
total_copy_paste = implementation_stats['copy_paste'] + homeowner_stats['copy_paste'] + management_stats['copy_paste']
total_low_quality = implementation_stats['low_quality'] + homeowner_stats['low_quality'] + management_stats['low_quality']
total_skipped = implementation_stats['skipped'] + homeowner_stats['skipped'] + management_stats['skipped']

print(f"\nOVERALL SUMMARY ({total_tickets} total tickets)")
print("=" * 80)
if total_tickets > 0:
    print(f"Total copy-paste responses: {total_copy_paste} ({100 * total_copy_paste / total_tickets:.1f}%)")
    print(f"Total low quality responses: {total_low_quality} ({100 * total_low_quality / total_tickets:.1f}%)")
    print(f"Total skipped tickets: {total_skipped} ({100 * total_skipped / total_tickets:.1f}%)")
    
    # Distribution by ticket type
    print(f"\nDistribution by ticket type:")
    print(f"  Implementation: {implementation_stats['total']} ({100 * implementation_stats['total'] / total_tickets:.1f}%)")
    print(f"  Homeowner: {homeowner_stats['total']} ({100 * homeowner_stats['total'] / total_tickets:.1f}%)")
    print(f"  Management: {management_stats['total']} ({100 * management_stats['total'] / total_tickets:.1f}%)")
    
    # Overall average score
    all_scores = implementation_stats['scores'] + homeowner_stats['scores'] + management_stats['scores']
    if all_scores:
        overall_avg = sum(all_scores) / len(all_scores)
        print(f"\nOverall average score: {overall_avg:.2f}/10")
else:
    print("No tickets were evaluated in the specific experiments")
