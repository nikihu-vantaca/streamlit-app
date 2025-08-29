#!/usr/bin/env python3
"""
Create a detailed daily breakdown spreadsheet and upload to LangSmith
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import toml
from langsmith import Client
import json
import os

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
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    return df

def create_detailed_breakdown_spreadsheet():
    """Create a comprehensive daily breakdown spreadsheet"""
    print("📊 Creating detailed daily breakdown spreadsheet...")
    
    # Get the raw data
    df = get_daily_breakdown_data()
    
    if df.empty:
        print("❌ No data found in database")
        return None
    
    # Create a comprehensive breakdown
    breakdown_data = []
    
    # Get unique dates
    dates = sorted(df['date'].unique())
    
    for date in dates:
        date_data = df[df['date'] == date]
        
        # Overall summary for this date
        total_tickets = date_data['count'].sum()
        
        # Breakdown by ticket type
        for ticket_type in ['implementation', 'homeowner', 'management']:
            type_data = date_data[date_data['ticket_type'] == ticket_type]
            type_total = type_data['count'].sum()
            
            if type_total > 0:
                # Quality breakdown for this ticket type
                for quality in ['high_quality', 'low_quality', 'copy_paste', 'skipped', 'unknown']:
                    quality_data = type_data[type_data['quality'] == quality]
                    quality_count = quality_data['count'].sum()
                    
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
    
    # Create DataFrame
    breakdown_df = pd.DataFrame(breakdown_data)
    
    # Add additional summary sheets
    summary_data = []
    
    # Overall summary by ticket type
    overall_by_type = df.groupby('ticket_type')['count'].sum().reset_index()
    for _, row in overall_by_type.iterrows():
        summary_data.append({
            'Summary_Type': 'By_Ticket_Type',
            'Category': row['ticket_type'].title(),
            'Total_Count': row['count'],
            'Percentage': round((row['count'] / overall_by_type['count'].sum()) * 100, 1)
        })
    
    # Overall summary by quality
    overall_by_quality = df.groupby('quality')['count'].sum().reset_index()
    for _, row in overall_by_quality.iterrows():
        summary_data.append({
            'Summary_Type': 'By_Quality',
            'Category': row['quality'].replace('_', ' ').title(),
            'Total_Count': row['count'],
            'Percentage': round((row['count'] / overall_by_quality['count'].sum()) * 100, 1)
        })
    
    summary_df = pd.DataFrame(summary_data)
    
    return breakdown_df, summary_df

def upload_to_langsmith(breakdown_df, summary_df):
    """Upload the spreadsheet data to LangSmith as a dataset"""
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
        
        # Convert DataFrames to records for upload
        breakdown_records = breakdown_df.to_dict('records')
        summary_records = summary_df.to_dict('records')
        
        # Create dataset
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description="Daily ticket evaluation breakdown with detailed quality metrics"
        )
        
        # Upload breakdown data
        for record in breakdown_records:
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
        for record in summary_records:
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
        
        print(f"✅ Successfully uploaded {len(breakdown_records)} breakdown records and {len(summary_records)} summary records")
        print(f"🔗 Dataset URL: https://smith.langchain.com/datasets/{dataset.id}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error uploading to LangSmith: {e}")
        return False

def save_local_spreadsheet(breakdown_df, summary_df):
    """Save the spreadsheet locally as Excel file"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"daily_breakdown_{timestamp}.xlsx"
    
    try:
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Write breakdown data
            breakdown_df.to_excel(writer, sheet_name='Daily_Breakdown', index=False)
            
            # Write summary data
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Create pivot tables for better analysis
            # Pivot by date and ticket type
            pivot_type = breakdown_df[breakdown_df['Ticket_Type'] != 'TOTAL'].pivot_table(
                index='Date', 
                columns='Ticket_Type', 
                values='Count', 
                aggfunc='sum',
                fill_value=0
            )
            pivot_type.to_excel(writer, sheet_name='Pivot_By_Type')
            
            # Pivot by date and quality
            pivot_quality = breakdown_df[breakdown_df['Ticket_Type'] != 'TOTAL'].pivot_table(
                index='Date', 
                columns='Quality', 
                values='Count', 
                aggfunc='sum',
                fill_value=0
            )
            pivot_quality.to_excel(writer, sheet_name='Pivot_By_Quality')
        
        print(f"✅ Saved local spreadsheet: {filename}")
        return filename
        
    except Exception as e:
        print(f"❌ Error saving local spreadsheet: {e}")
        return None

def main():
    """Main function to create and upload the spreadsheet"""
    print("🚀 Starting daily breakdown spreadsheet creation...")
    
    # Create the breakdown data
    result = create_detailed_breakdown_spreadsheet()
    
    if result is None:
        return
    
    breakdown_df, summary_df = result
    
    print(f"📊 Created breakdown with {len(breakdown_df)} records")
    print(f"📈 Created summary with {len(summary_df)} records")
    
    # Save locally
    local_file = save_local_spreadsheet(breakdown_df, summary_df)
    
    # Upload to LangSmith
    success = upload_to_langsmith(breakdown_df, summary_df)
    
    if success:
        print("🎉 Successfully created and uploaded daily breakdown spreadsheet!")
    else:
        print("⚠️ Created local spreadsheet but failed to upload to LangSmith")
    
    # Show sample of the data
    print("\n📋 Sample of daily breakdown data:")
    print(breakdown_df.head(10))
    
    print("\n📋 Sample of summary data:")
    print(summary_df.head(10))

if __name__ == "__main__":
    main()
