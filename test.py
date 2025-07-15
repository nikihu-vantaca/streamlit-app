from langsmith import Client
import json
import re
from datetime import datetime

API_KEY = "YOUR_API_KEY_HERE"
PROJECT_NAME = "evaluators"
TARGET_DATE = "2025-07-10"

client = Client(api_key=API_KEY)
runs = client.list_runs(project_name=PROJECT_NAME)

low_quality_ticket_ids = []

for run in runs:
    # Extract experiment name and date
    experiment = None
    if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
        experiment = run.metadata.get("experiment")
    if not experiment:
        continue
    # Check if it's a zendesk evaluation experiment for the target date
    if not experiment.startswith(f"zendesk-evaluation-{TARGET_DATE}"):
        continue
    # Process detailed_similarity_evaluator runs
    if getattr(run, "name", None) == "detailed_similarity_evaluator" and getattr(run, "outputs", None):
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
        # print(result)
        if quality == "low_quality":
            ticket_id = None
            if hasattr(run, "inputs") and run.inputs:
                if isinstance(run.inputs, dict):
                    # Direct ticket_id
                    if 'ticket_id' in run.inputs:
                        ticket_id = run.inputs['ticket_id']
                    # Nested under 'x'
                    elif 'x' in run.inputs and isinstance(run.inputs['x'], dict):
                        ticket_id = run.inputs['x'].get('ticket_id')
                    # Nested under 'run' > 'inputs' > 'x'
                    elif 'run' in run.inputs and isinstance(run.inputs['run'], dict):
                        run_inputs = run.inputs['run'].get('inputs', {})
                        if 'x' in run_inputs and isinstance(run_inputs['x'], dict):
                            ticket_id = run_inputs['x'].get('ticket_id')
            if ticket_id is None:
                ticket_id = result.get('ticket_id')
            if ticket_id is not None:
                low_quality_ticket_ids.append(ticket_id)
            if len(low_quality_ticket_ids) >= 10:
                break

print("Low quality ticket IDs for 2025-07-14:")
for tid in low_quality_ticket_ids:
    print(tid)
