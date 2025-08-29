#!/usr/bin/env python3
"""
Create a detailed daily breakdown spreadsheet that matches LangSmith data exactly
"""

import sqlite3
import csv
from datetime import datetime
import toml
from langsmith import Client
import json

def get_api_key():
    """Get API key from Streamlit secrets"""
    try:
        # Read from .streamlit/secrets.toml
        secrets = toml.load('.streamlit/secrets.toml')
        return secrets['langsmith']['api_key']
    except:
        return None

def get_latest_runs_data():
    """Get only the latest runs for each experiment type per day - matching LangSmith data"""
    conn = sqlite3.connect('ticket_data.db')
    cursor = conn.cursor()
    
    # Use the same logic as the Streamlit app to get latest runs only
    latest_runs_query = '''
        SELECT 
            date,
            ticket_type,
            quality,
            comment,
            experiment_name,
            COUNT(*) as count
        FROM ticket_evaluations 
        WHERE date LIKE '____-__-__'
        AND experiment_name IS NOT NULL
        AND experiment_name NOT LIKE 'zendesk-evaluation%'
        AND experiment_name IN (
            -- Get the most recent experiment name for each date and ticket type
            SELECT experiment_name
            FROM ticket_evaluations e2
            WHERE e2.date = ticket_evaluations.date 
            AND e2.ticket_type = ticket_evaluations.ticket_type
            AND e2.experiment_name IS NOT NULL
            AND e2.experiment_name NOT LIKE 'zendesk-evaluation%'
            ORDER BY e2.start_time DESC
            LIMIT 1
        )
        GROUP BY date, ticket_type, quality, comment, experiment_name
        ORDER BY date, ticket_type, quality
    '''
    
    cursor.execute(latest_runs_query)
    rows = cursor.fetchall()
    conn.close()
    
    return rows

def standardize_quality_labels(rows):
    """Standardize quality labels across ticket types"""
    standardized_rows = []
    
    for row in rows:
        date, ticket_type, quality, comment, experiment_name, count = row
        
        # Standardize homeowner "copy_paste" to "high_quality" to match other ticket types
        if ticket_type == 'homeowner' and quality == 'copy_paste':
            quality = 'high_quality'
        
        standardized_rows.append((date, ticket_type, quality, comment, experiment_name, count))
    
    return standardized_rows

def create_detailed_breakdown_spreadsheet():
    """Create a comprehensive daily breakdown spreadsheet"""
    print("📊 Creating detailed daily breakdown spreadsheet...")
    
    # Get the filtered data (latest runs only)
    rows = get_latest_runs_data()
    
    if not rows:
        print("❌ No data found in database")
        return None
    
    # Standardize quality labels
    rows = standardize_quality_labels(rows)
    
    # Convert to dictionary for easier processing
    data_by_date = {}
    for row in rows:
        date, ticket_type, quality, comment, experiment_name, count = row
        
        if date not in data_by_date:
            data_by_date[date] = {}
        
        if ticket_type not in data_by_date[date]:
            data_by_date[date][ticket_type] = {}
        
        if quality not in data_by_date[date][ticket_type]:
            data_by_date[date][ticket_type][quality] = 0
        
        data_by_date[date][ticket_type][quality] += count
    
    # Create breakdown data
    breakdown_data = []
    summary_data = []
    
    # Process each date
    for date in sorted(data_by_date.keys()):
        date_data = data_by_date[date]
        total_tickets = sum(sum(quality_counts.values()) for quality_counts in date_data.values())
        
        # Process each ticket type
        for ticket_type in ['implementation', 'homeowner', 'management']:
            if ticket_type in date_data:
                type_data = date_data[ticket_type]
                type_total = sum(type_data.values())
                
                # Process each quality
                for quality in ['high_quality', 'low_quality', 'copy_paste', 'skipped', 'unknown']:
                    quality_count = type_data.get(quality, 0)
                    
                    if quality_count > 0:
                        breakdown_data.append({
                            'Date': date,
                            'Ticket_Type': ticket_type.title(),
                            'Quality': quality.replace('_', ' ').title(),
                            'Count': quality_count,
                            'Percentage_of_Type': round((quality_count / type_total) * 100, 1),
                            'Percentage_of_Total': round((quality_count / total_tickets) * 100, 1),
                            'Total_Type_Tickets': type_total,
                            'Total_Daily_Tickets': total_tickets
                        })
                
                # Handle None quality values
                none_quality_count = type_data.get(None, 0)
                if none_quality_count > 0:
                    breakdown_data.append({
                        'Date': date,
                        'Ticket_Type': ticket_type.title(),
                        'Quality': 'None',
                        'Count': none_quality_count,
                        'Percentage_of_Type': round((none_quality_count / type_total) * 100, 1),
                        'Percentage_of_Total': round((none_quality_count / total_tickets) * 100, 1),
                        'Total_Type_Tickets': type_total,
                        'Total_Daily_Tickets': total_tickets
                    })
        
        # Add summary row for this date
        breakdown_data.append({
            'Date': date,
            'Ticket_Type': 'TOTAL',
            'Quality': 'ALL',
            'Count': total_tickets,
            'Percentage_of_Type': 100.0,
            'Percentage_of_Total': 100.0,
            'Total_Type_Tickets': total_tickets,
            'Total_Daily_Tickets': total_tickets
        })
    
    # Create overall summary
    overall_by_type = {}
    overall_by_quality = {}
    
    for row in rows:
        date, ticket_type, quality, comment, experiment_name, count = row
        
        # By ticket type
        if ticket_type not in overall_by_type:
            overall_by_type[ticket_type] = 0
        overall_by_type[ticket_type] += count
        
        # By quality
        if quality not in overall_by_quality:
            overall_by_quality[quality] = 0
        overall_by_quality[quality] += count
    
    total_overall = sum(overall_by_type.values())
    
    # Add summary data
    for ticket_type, count in overall_by_type.items():
        summary_data.append({
            'Summary_Type': 'By_Ticket_Type',
            'Category': ticket_type.title(),
            'Total_Count': count,
            'Percentage': round((count / total_overall) * 100, 1)
        })
    
    for quality, count in overall_by_quality.items():
        if quality is not None:
            summary_data.append({
                'Summary_Type': 'By_Quality',
                'Category': quality.replace('_', ' ').title(),
                'Total_Count': count,
                'Percentage': round((count / total_overall) * 100, 1)
            })
        else:
            summary_data.append({
                'Summary_Type': 'By_Quality',
                'Category': 'None',
                'Total_Count': count,
                'Percentage': round((count / total_overall) * 100, 1)
            })
    
    return breakdown_data, summary_data

def save_csv_files(breakdown_data, summary_data):
    """Save the data as CSV files"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save breakdown data
    breakdown_filename = f"corrected_daily_breakdown_{timestamp}.csv"
    with open(breakdown_filename, 'w', newline='', encoding='utf-8') as csvfile:
        if breakdown_data:
            fieldnames = breakdown_data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(breakdown_data)
    
    # Save summary data
    summary_filename = f"corrected_summary_{timestamp}.csv"
    with open(summary_filename, 'w', newline='', encoding='utf-8') as csvfile:
        if summary_data:
            fieldnames = summary_data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(summary_data)
    
    print(f"✅ Saved breakdown data: {breakdown_filename}")
    print(f"✅ Saved summary data: {summary_filename}")
    
    return breakdown_filename, summary_filename

def upload_to_langsmith(breakdown_data, summary_data):
    """Upload the data to LangSmith as a dataset"""
    api_key = get_api_key()
    if not api_key:
        print("❌ No API key found. Please check your configuration.")
        return False
    
    try:
        client = Client(api_key=api_key)
        
        # Create dataset name with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dataset_name = f"corrected_daily_breakdown_{timestamp}"
        
        print(f"📤 Uploading to LangSmith dataset: {dataset_name}")
        
        # Create dataset
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description="Corrected daily ticket evaluation breakdown with latest runs only"
        )
        
        # Upload breakdown data
        for record in breakdown_data:
            client.create_example(
                dataset_id=dataset.id,
                inputs={
                    "date": record['Date'],
                    "ticket_type": record['Ticket_Type'],
                    "quality": record['Quality'],
                    "count": record['Count'],
                    "percentage_of_type": record['Percentage_of_Type'],
                    "percentage_of_total": record['Percentage_of_Total'],
                    "total_type_tickets": record['Total_Type_Tickets'],
                    "total_daily_tickets": record['Total_Daily_Tickets']
                },
                outputs={
                    "record_type": "corrected_daily_breakdown"
                }
            )
        
        # Upload summary data
        for record in summary_data:
            client.create_example(
                dataset_id=dataset.id,
                inputs={
                    "summary_type": record['Summary_Type'],
                    "category": record['Category'],
                    "total_count": record['Total_Count'],
                    "percentage": record['Percentage']
                },
                outputs={
                    "record_type": "corrected_summary"
                }
            )
        
        print(f"✅ Successfully uploaded {len(breakdown_data)} breakdown records and {len(summary_data)} summary records")
        print(f"🔗 Dataset URL: https://smith.langchain.com/datasets/{dataset.id}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error uploading to LangSmith: {e}")
        return False

def print_implementation_quality_explanation():
    """Print explanation of implementation ticket quality differences"""
    print("\n📋 IMPLEMENTATION TICKET QUALITY EXPLANATION:")
    print("=" * 60)
    print("• 'Unknown': The AI couldn't determine if the ticket was high or low quality")
    print("• 'None': No quality assessment was made (e.g., skipped evaluation)")
    print("• 'High Quality': Ticket meets quality standards")
    print("• 'Low Quality': Ticket doesn't meet quality standards")
    print("• 'Skipped': Evaluation was intentionally skipped")

def main():
    """Main function to create and upload the corrected spreadsheet"""
    print("🚀 Starting CORRECTED daily breakdown spreadsheet creation...")
    print("📊 This version filters for latest runs only (matching LangSmith data)")
    
    # Create the breakdown data
    result = create_detailed_breakdown_spreadsheet()
    
    if result is None:
        return
    
    breakdown_data, summary_data = result
    
    print(f"📊 Created breakdown with {len(breakdown_data)} records")
    print(f"📈 Created summary with {len(summary_data)} records")
    
    # Save locally as CSV
    breakdown_file, summary_file = save_csv_files(breakdown_data, summary_data)
    
    # Upload to LangSmith
    success = upload_to_langsmith(breakdown_data, summary_data)
    
    if success:
        print("🎉 Successfully created and uploaded CORRECTED daily breakdown spreadsheet!")
    else:
        print("⚠️ Created local CSV files but failed to upload to LangSmith")
    
    # Show sample of the data
    print("\n📋 Sample of corrected daily breakdown data:")
    for i, record in enumerate(breakdown_data[:5]):
        print(f"  {record}")
    
    print("\n📋 Sample of corrected summary data:")
    for i, record in enumerate(summary_data[:5]):
        print(f"  {record}")
    
    # Print explanation
    print_implementation_quality_explanation()

if __name__ == "__main__":
    main()
