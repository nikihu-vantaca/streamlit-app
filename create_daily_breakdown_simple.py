#!/usr/bin/env python3
"""
Create a detailed daily breakdown spreadsheet (CSV version)
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

def get_daily_breakdown_data():
    """Get detailed daily breakdown data from database"""
    conn = sqlite3.connect('ticket_data.db')
    cursor = conn.cursor()
    
    # Get all data with valid dates
    query = '''
        SELECT 
            date,
            ticket_type,
            quality,
            comment,
            experiment_name,
            COUNT(*) as count
        FROM ticket_evaluations 
        WHERE date LIKE '____-__-__'
        GROUP BY date, ticket_type, quality, comment, experiment_name
        ORDER BY date, ticket_type, quality
    '''
    
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    return rows

def create_detailed_breakdown_spreadsheet():
    """Create a comprehensive daily breakdown spreadsheet"""
    print("📊 Creating detailed daily breakdown spreadsheet...")
    
    # Get the raw data
    rows = get_daily_breakdown_data()
    
    if not rows:
        print("❌ No data found in database")
        return None
    
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
    breakdown_filename = f"daily_breakdown_{timestamp}.csv"
    with open(breakdown_filename, 'w', newline='', encoding='utf-8') as csvfile:
        if breakdown_data:
            fieldnames = breakdown_data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(breakdown_data)
    
    # Save summary data
    summary_filename = f"summary_{timestamp}.csv"
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
        dataset_name = f"daily_breakdown_{timestamp}"
        
        print(f"📤 Uploading to LangSmith dataset: {dataset_name}")
        
        # Create dataset
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description="Daily ticket evaluation breakdown with detailed quality metrics"
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
                    "record_type": "daily_breakdown"
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
                    "record_type": "summary"
                }
            )
        
        print(f"✅ Successfully uploaded {len(breakdown_data)} breakdown records and {len(summary_data)} summary records")
        print(f"🔗 Dataset URL: https://smith.langchain.com/datasets/{dataset.id}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error uploading to LangSmith: {e}")
        return False

def main():
    """Main function to create and upload the spreadsheet"""
    print("🚀 Starting daily breakdown spreadsheet creation...")
    
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
        print("🎉 Successfully created and uploaded daily breakdown spreadsheet!")
    else:
        print("⚠️ Created local CSV files but failed to upload to LangSmith")
    
    # Show sample of the data
    print("\n📋 Sample of daily breakdown data:")
    for i, record in enumerate(breakdown_data[:5]):
        print(f"  {record}")
    
    print("\n📋 Sample of summary data:")
    for i, record in enumerate(summary_data[:5]):
        print(f"  {record}")

if __name__ == "__main__":
    main()
