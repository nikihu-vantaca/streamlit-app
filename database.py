import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import json
from langsmith import Client
import re
from collections import defaultdict

class TicketDatabase:
    def __init__(self, db_path='ticket_data.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create main table for ticket evaluations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticket_id INTEGER NOT NULL,
                ticket_type TEXT DEFAULT 'homeowner',
                quality TEXT,
                comment TEXT,
                evaluation_key TEXT,
                experiment_name TEXT,
                start_time TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, ticket_id)
            )
        ''')
        
        # Check if evaluation_key column exists, if not add it
        cursor.execute("PRAGMA table_info(ticket_evaluations)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'evaluation_key' not in columns:
            print("Adding evaluation_key column to existing database...")
            cursor.execute('ALTER TABLE ticket_evaluations ADD COLUMN evaluation_key TEXT')
        
        # Create index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_date_ticket 
            ON ticket_evaluations(date, ticket_id)
        ''')
        
        conn.commit()
        conn.close()
    
    def fetch_and_store_latest_data(self, api_key, project_name="evaluators"):
        """Fetch latest data from LangSmith and store in database"""
        try:
            client = Client(api_key=api_key)
            # Use a larger limit to get more historical data, but handle rate limiting
            try:
                runs = client.list_runs(project_name=project_name, limit=10000)
            except Exception as e:
                if "rate limit" in str(e).lower() or "429" in str(e):
                    print("Rate limit hit, trying with smaller limit...")
                    runs = client.list_runs(project_name=project_name, limit=2000)
                else:
                    raise e
            
            # Get the latest timestamp we have in our database
            latest_timestamp = self.get_latest_timestamp()
            
            # Collect latest runs by (date, ticket_id)
            latest_runs = {}
            
            for run in runs:
                # Extract experiment name and date
                experiment = None
                if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
                    experiment = run.metadata.get("experiment")
                
                if not experiment:
                    continue
                
                # Determine date from experiment name
                date_str = self.extract_date_from_experiment(experiment)
                if not date_str:
                    continue
                
                # Only process detailed_similarity_evaluator runs
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
                    comment = result.get("comment")
                    evaluation_key = result.get("key", "")
                    
                    # Extract ticket_id
                    ticket_id = self.extract_ticket_id(run, result)
                    if ticket_id is None:
                        continue
                    
                    # Determine ticket type based on date and experiment
                    ticket_type = self.determine_ticket_type(date_str, experiment, evaluation_key, comment)
                    
                    # Extract start_time
                    start_time = getattr(run, "start_time", None)
                    if isinstance(start_time, str):
                        start_time_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    else:
                        start_time_dt = start_time
                    
                    # Check if this run is newer than what we have
                    if start_time_dt and latest_timestamp and start_time_dt <= latest_timestamp:
                        continue
                    
                    key = (date_str, ticket_id)
                    if ticket_id is not None and (key not in latest_runs or start_time_dt > latest_runs[key][0]):
                        latest_runs[key] = (start_time_dt, date_str, ticket_id, quality, comment, experiment, start_time, ticket_type, evaluation_key)
            
            # Store new/updated data
            if latest_runs:
                self.store_evaluations(latest_runs)
                return len(latest_runs)
            return 0
            
        except Exception as e:
            print(f"Error fetching data: {str(e)}")
            return 0
    
    def extract_date_from_experiment(self, experiment):
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
    
    def extract_ticket_id(self, run, result):
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
    
    def determine_ticket_type(self, date_str, experiment, evaluation_key, comment):
        """Determine ticket type based on date and experiment"""
        date_dt = datetime.strptime(date_str, "%Y-%m-%d")
        cutoff_date = datetime(2025, 8, 15)
        
        if date_dt < cutoff_date:
            # Pre-August 15, 2025: Use ungrouped logic
            return self.determine_ticket_type_ungrouped(evaluation_key, comment)
        else:
            # Post-August 15, 2025: Use grouped logic
            return self.determine_ticket_type_grouped(experiment)
    
    def determine_ticket_type_ungrouped(self, evaluation_key, comment):
        """Determine ticket type for pre-August 15, 2025 (ungrouped system)"""
        # Based on get_evaluation_ungrouped.py logic
        if "management_ticket_evaluation" in evaluation_key or "management" in comment.lower():
            return "management"
        else:
            return "homeowner"
    
    def determine_ticket_type_grouped(self, experiment):
        """Determine ticket type for post-August 15, 2025 (grouped system)"""
        # Based on get_evaluation_grouped.py logic
        if "implementation-evaluation-" in experiment:
            return "implementation"
        elif "homeowner-pay-evaluation-" in experiment:
            return "homeowner"
        elif "management-pay-evaluation-" in experiment:
            return "management"
        else:
            return "homeowner"  # default
    
    def get_latest_timestamp(self):
        """Get the latest start_time from the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(start_time) FROM ticket_evaluations')
        result = cursor.fetchone()
        conn.close()
        
        if result[0]:
            return datetime.fromisoformat(result[0].replace("Z", "+00:00"))
        return None
    
    def store_evaluations(self, evaluations):
        """Store evaluation data in the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for (start_time_dt, date_str, ticket_id, quality, comment, experiment, start_time, ticket_type, evaluation_key) in evaluations.values():
            cursor.execute('''
                INSERT OR REPLACE INTO ticket_evaluations 
                (date, ticket_id, ticket_type, quality, comment, evaluation_key, experiment_name, start_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (date_str, ticket_id, ticket_type, quality, comment, evaluation_key, experiment, start_time))
        
        conn.commit()
        conn.close()
    
    def get_data_for_range(self, date_range="2_weeks"):
        """Get data for the specified date range"""
        end_date = datetime.now()
        if date_range == "2_weeks":
            start_date = end_date - timedelta(days=14)
        elif date_range == "4_weeks":
            start_date = end_date - timedelta(days=28)
        else:  # all_data
            start_date = datetime(2025, 7, 1)  # Start from July 1, 2025 (when evaluation data actually starts)
        
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        conn = sqlite3.connect(self.db_path)
        query = f'''
            SELECT date, ticket_id, quality, comment, experiment_name, ticket_type, evaluation_key
            FROM ticket_evaluations 
            WHERE date >= ? AND date <= ?
            ORDER BY date, ticket_id
        '''
        df = pd.read_sql_query(query, conn, params=(start_date_str, end_date_str))
        conn.close()
        
        return self.process_dataframe(df, start_date, end_date)
    
    def process_dataframe(self, df, start_date, end_date):
        """Process raw dataframe into daily aggregated data"""
        # Initialize daily data structure
        daily_data = {}
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            daily_data[date_str] = {
                'date': date_str,
                'copy_paste_count': 0,
                'low_quality_count': 0,
                'skipped_count': 0,
                'management_company_ticket_count': 0,
                'implementation_ticket_count': 0,
                'total_evaluated': 0,
                'total_tickets': 0,
                'experiment_name': f"evaluation-{date_str}",
                'low_quality_tickets': []
            }
            current_date += timedelta(days=1)
        
        # Process the data
        for _, row in df.iterrows():
            date_str = row['date']
            if date_str in daily_data:
                daily_data[date_str]['total_tickets'] += 1
                
                quality = row['quality']
                comment = row['comment']
                ticket_id = row['ticket_id']
                ticket_type = row.get('ticket_type', 'homeowner')
                evaluation_key = row.get('evaluation_key', '')
                
                # Handle different ticket types based on date
                date_dt = datetime.strptime(date_str, "%Y-%m-%d")
                cutoff_date = datetime(2025, 8, 15)
                
                if date_dt < cutoff_date:
                    # Pre-August 15, 2025: Use ungrouped logic
                    self.process_ungrouped_ticket(daily_data[date_str], ticket_type, quality, comment, ticket_id, evaluation_key)
                else:
                    # Post-August 15, 2025: Use grouped logic
                    self.process_grouped_ticket(daily_data[date_str], ticket_type, quality, comment, ticket_id)
        
        # Convert to DataFrame
        result_df = pd.DataFrame(list(daily_data.values()))
        result_df['date'] = pd.to_datetime(result_df['date'])
        result_df = result_df.sort_values('date')
        
        return result_df, daily_data
    
    def process_ungrouped_ticket(self, day_data, ticket_type, quality, comment, ticket_id, evaluation_key):
        """Process ticket for pre-August 15, 2025 (ungrouped system)"""
        # Handle management tickets - EXCLUDE from evaluation counts
        if ticket_type == 'management' or evaluation_key == 'management_ticket_evaluation':
            day_data['management_company_ticket_count'] += 1
            return
        
        # Handle homeowner tickets (bot_evaluation key) - ONLY these count as "evaluated"
        if evaluation_key == 'bot_evaluation':
            # Check for skipped tickets first
            if comment == "empty_bot_answer":
                day_data['skipped_count'] += 1
                return
            
            # All non-skipped bot_evaluation tickets count as evaluated
            day_data['total_evaluated'] += 1
            
            # Now categorize the quality
            if quality == "copy_paste":
                day_data['copy_paste_count'] += 1
            elif quality == "low_quality":
                day_data['low_quality_count'] += 1
                day_data['low_quality_tickets'].append(ticket_id)
    
    def process_grouped_ticket(self, day_data, ticket_type, quality, comment, ticket_id):
        """Process ticket for post-August 15, 2025 (grouped system)"""
        # All tickets count as evaluated in the grouped system
        day_data['total_evaluated'] += 1
        
        # Track by ticket type
        if ticket_type == 'implementation':
            day_data['implementation_ticket_count'] += 1
        elif ticket_type == 'management':
            day_data['management_company_ticket_count'] += 1
        
        # Check for skipped tickets
        if comment == "empty_bot_answer" or "management_company_ticket" in comment or "empty_human_answer" in comment:
            day_data['skipped_count'] += 1
            return
        
        # Categorize quality
        if quality == "copy_paste":
            day_data['copy_paste_count'] += 1
        elif quality == "low_quality":
            day_data['low_quality_count'] += 1
            day_data['low_quality_tickets'].append(ticket_id)
    
    def get_low_quality_tickets(self, date_range="2_weeks"):
        """Get all low quality tickets for the specified date range"""
        end_date = datetime.now()
        if date_range == "2_weeks":
            start_date = end_date - timedelta(days=14)
        elif date_range == "4_weeks":
            start_date = end_date - timedelta(days=28)
        else:  # all_data
            start_date = datetime(2025, 8, 4)  # Start from August 4, 2025 (when evaluation data actually starts)
        
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        conn = sqlite3.connect(self.db_path)
        query = f'''
            SELECT date, ticket_id, ticket_type
            FROM ticket_evaluations 
            WHERE date >= ? AND date <= ? AND quality = 'low_quality'
            ORDER BY date, ticket_id
        '''
        df = pd.read_sql_query(query, conn, params=(start_date_str, end_date_str))
        conn.close()
        
        return df.to_dict('records')
    
    def debug_database_contents(self):
        """Debug method to check current database contents"""
        conn = sqlite3.connect(self.db_path)
        
        print("=== DATABASE DEBUG INFO ===")
        
        # Check total records
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM ticket_evaluations')
        total_records = cursor.fetchone()[0]
        print(f"Total records: {total_records}")
        
        # Check by evaluation_key
        cursor.execute('''
            SELECT evaluation_key, ticket_type, COUNT(*) 
            FROM ticket_evaluations 
            GROUP BY evaluation_key, ticket_type
        ''')
        print("\nBreakdown by evaluation_key and ticket_type:")
        for row in cursor.fetchall():
            print(f"  Key: {row[0]}, Type: {row[1]}, Count: {row[2]}")
        
        # Check recent records
        cursor.execute('''
            SELECT date, ticket_id, evaluation_key, ticket_type, quality, comment 
            FROM ticket_evaluations 
            ORDER BY date DESC, ticket_id DESC 
            LIMIT 10
        ''')
        print("\nSample recent records:")
        for row in cursor.fetchall():
            print(f"  {row[0]} | Ticket {row[1]} | Key: {row[2]} | Type: {row[3]} | Quality: {row[4]} | Comment: {row[5][:50]}...")
        
        conn.close()
    
    def force_migrate_data(self):
        """Force migration of existing data - call this manually if needed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        print("=== FORCING DATA MIGRATION ===")
        
        # Show current state
        cursor.execute('''
            SELECT evaluation_key, ticket_type, COUNT(*) 
            FROM ticket_evaluations 
            GROUP BY evaluation_key, ticket_type
        ''')
        print("Before migration:")
        for row in cursor.fetchall():
            print(f"  Key: {row[0]}, Type: {row[1]}, Count: {row[2]}")
        
        # Update management tickets
        cursor.execute('''
            UPDATE ticket_evaluations 
            SET ticket_type = 'management' 
            WHERE evaluation_key = 'management_ticket_evaluation'
        ''')
        mgmt_updated = cursor.rowcount
        
        # Update homeowner tickets  
        cursor.execute('''
            UPDATE ticket_evaluations 
            SET ticket_type = 'homeowner' 
            WHERE evaluation_key = 'bot_evaluation'
        ''')
        homeowner_updated = cursor.rowcount
        
        conn.commit()
        
        print(f"\nUpdated {mgmt_updated} management tickets")
        print(f"Updated {homeowner_updated} homeowner tickets")
        
        # Show new state
        cursor.execute('''
            SELECT evaluation_key, ticket_type, COUNT(*) 
            FROM ticket_evaluations 
            GROUP BY evaluation_key, ticket_type
        ''')
        print("\nAfter migration:")
        for row in cursor.fetchall():
            print(f"  Key: {row[0]}, Type: {row[1]}, Count: {row[2]}")
            
        conn.close()
        print("=== MIGRATION COMPLETED ===")
        return mgmt_updated + homeowner_updated