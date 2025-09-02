#!/usr/bin/env python3
"""
Evaluation Database Module for LangSmith Data Management
Handles data retrieval from LangSmith API and database operations
"""

import os
import toml
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from langsmith import Client
import time
import json
from typing import Optional, Dict, List, Any

class EvaluationDatabase:
    """Database manager for evaluation data from LangSmith"""
    
    def __init__(self, db_path: str = 'merged_evaluation.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create evaluations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticket_id INTEGER,
                ticket_type TEXT,
                quality TEXT,
                comment TEXT,
                score REAL,
                experiment_name TEXT,
                run_id TEXT,
                start_time TEXT,
                evaluation_key TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create latest_experiments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS latest_experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                experiment_type TEXT,
                experiment_name TEXT,
                start_time TEXT,
                run_count INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_evaluations_date ON evaluations(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_evaluations_ticket_type ON evaluations(ticket_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_evaluations_quality ON evaluations(quality)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_evaluations_experiment ON evaluations(experiment_name)')
        
        conn.commit()
        conn.close()
    
    def get_api_key(self) -> Optional[str]:
        """Get API key from various sources"""
        # Try environment variable first
        api_key = os.getenv('LANGSMITH_API_KEY')
        if api_key:
            return api_key
        
        # Try secrets.toml file
        try:
            secrets = toml.load('.streamlit/secrets.toml')
            return secrets['langsmith']['api_key']
        except:
            pass
        
        return None
    
    def fetch_and_sync_data(self, api_key: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> bool:
        """Fetch data from LangSmith and sync to database"""
        try:
            client = Client(api_key=api_key)
            
            # Set default date range if not provided
            if not start_date:
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            
            print(f"Fetching data from {start_date} to {end_date}")
            
            # Fetch runs for the date range
            start_time = datetime.strptime(f"{start_date} 00:00:00", "%Y-%m-%d %H:%M:%S")
            end_time = datetime.strptime(f"{end_date} 23:59:59", "%Y-%m-%d %H:%M:%S")
            
            runs = client.list_runs(
                project_name="evaluators",
                start_time=start_time,
                end_time=end_time,
                limit=1000
            )
            
            # Process runs and store in database
            evaluation_data = []
            experiment_data = []
            
            # Track experiments by date to only keep the last set of three
            experiments_by_date = {}
            
            for run in runs:
                if run.name == "detailed_similarity_evaluator" and run.outputs:
                    # Extract evaluation data
                    eval_data = self._extract_evaluation_data(run)
                    if eval_data:
                        evaluation_data.append(eval_data)
                    
                    # Extract experiment data
                    exp_data = self._extract_experiment_data(run)
                    if exp_data:
                        # Group experiments by date
                        date = exp_data['date']
                        if date not in experiments_by_date:
                            experiments_by_date[date] = []
                        experiments_by_date[date].append(exp_data)
                
                # Rate limiting
                time.sleep(0.1)
            
            # For each date, only keep the last set of three experiments (management-pay, homeowner-pay, implementation)
            for date, experiments in experiments_by_date.items():
                # Sort experiments by start time (most recent first)
                experiments.sort(key=lambda x: x['start_time'], reverse=True)
                
                # Keep only the most recent set of three experiments
                # Look for experiments starting with the expected prefixes
                kept_experiments = []
                seen_prefixes = set()
                
                for exp in experiments:
                    exp_name = exp['experiment_name']
                    prefix = None
                    
                    if exp_name.startswith('management-pay'):
                        prefix = 'management-pay'
                    elif exp_name.startswith('homeowner-pay'):
                        prefix = 'homeowner-pay'
                    elif exp_name.startswith('implementation'):
                        prefix = 'implementation'
                    
                    if prefix and prefix not in seen_prefixes:
                        seen_prefixes.add(prefix)
                        kept_experiments.append(exp)
                    
                    # Stop once we have all three
                    if len(kept_experiments) >= 3:
                        break
                
                # Replace the experiments list with only the kept ones
                experiments_by_date[date] = kept_experiments
            
            # Flatten the kept experiments
            final_experiments = []
            for experiments in experiments_by_date.values():
                final_experiments.extend(experiments)
            
            # Store data in database
            if evaluation_data:
                self._store_evaluations(evaluation_data)
            
            if final_experiments:
                self._store_experiments(final_experiments)
            
            print(f"Successfully processed {len(evaluation_data)} evaluations and {len(final_experiments)} experiments")
            return True
            
        except Exception as e:
            print(f"Error fetching data: {e}")
            return False
    
    def _extract_evaluation_data(self, run) -> Optional[Dict[str, Any]]:
        """Extract evaluation data from a run"""
        try:
            # Get outputs
            outputs = run.outputs
            if not outputs:
                return None
            
            # Extract ticket information
            ticket_id = None
            ticket_type = None
            
            if hasattr(run, 'inputs') and run.inputs:
                inputs = run.inputs
                if isinstance(inputs, dict):
                    # Try to extract ticket info from various possible locations
                    if 'ticket_id' in inputs:
                        ticket_id = inputs['ticket_id']
                    elif 'ticket' in inputs and isinstance(inputs['ticket'], dict):
                        ticket_id = inputs['ticket'].get('id')
                        ticket_type = inputs['ticket'].get('type')
            
            # Extract quality and comment from outputs
            quality = None
            comment = None
            score = None
            
            if isinstance(outputs, dict):
                if 'quality' in outputs:
                    quality = outputs['quality']
                    # Standardize quality naming
                    if quality == 'copy_paste':
                        quality = 'high_quality'
                if 'comment' in outputs:
                    comment = outputs['comment']
                if 'score' in outputs:
                    score = outputs['score']
            
            # Get experiment name
            experiment_name = None
            if hasattr(run, 'metadata') and run.metadata:
                experiment_name = run.metadata.get('experiment')
            
            # Skip zendesk evaluations
            if experiment_name and experiment_name.startswith('zendesk'):
                return None
            
            # Get date from start time
            date = run.start_time.strftime('%Y-%m-%d') if run.start_time else None
            
            return {
                'date': date,
                'ticket_id': ticket_id,
                'ticket_type': ticket_type,
                'quality': quality,
                'comment': comment,
                'score': score,
                'experiment_name': experiment_name,
                'run_id': str(run.id),
                'start_time': run.start_time.isoformat() if run.start_time else None,
                'evaluation_key': 'detailed_similarity_evaluator'
            }
            
        except Exception as e:
            print(f"Error extracting evaluation data: {e}")
            return None
    
    def _extract_experiment_data(self, run) -> Optional[Dict[str, Any]]:
        """Extract experiment data from a run"""
        try:
            if not hasattr(run, 'metadata') or not run.metadata:
                return None
            
            experiment_name = run.metadata.get('experiment')
            if not experiment_name:
                return None
            
            # Skip zendesk experiments
            if experiment_name.startswith('zendesk'):
                return None
            
            # Determine experiment type from name
            experiment_type = None
            if 'implementation' in experiment_name:
                experiment_type = 'implementation'
            elif 'homeowner' in experiment_name:
                experiment_type = 'homeowner'
            elif 'management' in experiment_name:
                experiment_type = 'management'
            
            date = run.start_time.strftime('%Y-%m-%d') if run.start_time else None
            
            return {
                'date': date,
                'experiment_type': experiment_type,
                'experiment_name': experiment_name,
                'start_time': run.start_time.isoformat() if run.start_time else None,
                'run_count': 1
            }
            
        except Exception as e:
            print(f"Error extracting experiment data: {e}")
            return None
    
    def _store_evaluations(self, evaluation_data: List[Dict[str, Any]]):
        """Store evaluation data in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for data in evaluation_data:
            cursor.execute('''
                INSERT OR REPLACE INTO evaluations 
                (date, ticket_id, ticket_type, quality, comment, score, experiment_name, run_id, start_time, evaluation_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['date'], data['ticket_id'], data['ticket_type'], data['quality'],
                data['comment'], data['score'], data['experiment_name'], data['run_id'],
                data['start_time'], data['evaluation_key']
            ))
        
        conn.commit()
        conn.close()
    
    def _store_experiments(self, experiment_data: List[Dict[str, Any]]):
        """Store experiment data in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for data in experiment_data:
            cursor.execute('''
                INSERT OR REPLACE INTO latest_experiments 
                (date, experiment_type, experiment_name, start_time, run_count)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                data['date'], data['experiment_type'], data['experiment_name'],
                data['start_time'], data['run_count']
            ))
        
        conn.commit()
        conn.close()
    
    def get_evaluation_summary(self) -> pd.DataFrame:
        """Get evaluation summary data"""
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT 
                date,
                ticket_type,
                quality,
                COUNT(*) as count,
                AVG(score) as avg_score
            FROM evaluations
            WHERE ticket_type IS NOT NULL AND quality IS NOT NULL
            GROUP BY date, ticket_type, quality
            ORDER BY date DESC, ticket_type, quality
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        return df
    
    def get_latest_experiments_info(self) -> pd.DataFrame:
        """Get latest experiments information"""
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT 
                date,
                experiment_type,
                experiment_name,
                run_count,
                updated_at
            FROM latest_experiments
            ORDER BY date DESC, experiment_type
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        return df
    
    def get_daily_breakdown(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """Get daily breakdown of evaluations"""
        conn = sqlite3.connect(self.db_path)
        
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        query = '''
            SELECT 
                date,
                ticket_type,
                COUNT(*) as total_evaluations,
                SUM(CASE WHEN quality = 'high_quality' THEN 1 ELSE 0 END) as good_count,
                SUM(CASE WHEN quality = 'low_quality' THEN 1 ELSE 0 END) as bad_count,
                SUM(CASE WHEN quality IN ('skipped', 'unknown') THEN 1 ELSE 0 END) as ugly_count,
                AVG(score) as avg_score
            FROM evaluations
            WHERE date BETWEEN ? AND ?
            GROUP BY date, ticket_type
            ORDER BY date DESC, ticket_type
        '''
        
        df = pd.read_sql_query(query, conn, params=[start_date, end_date])
        conn.close()
        
        return df
    
    def get_quality_distribution(self) -> pd.DataFrame:
        """Get quality distribution across all data"""
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT 
                quality,
                COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM evaluations WHERE quality IS NOT NULL), 2) as percentage
            FROM evaluations
            WHERE quality IS NOT NULL
            GROUP BY quality
            ORDER BY count DESC
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        return df
    
    def get_latest_date(self) -> Optional[str]:
        """Get the latest date from the database"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT MAX(date) FROM evaluations WHERE date IS NOT NULL')
            result = cursor.fetchone()
            return result[0] if result and result[0] else None
        finally:
            conn.close()
    
    def get_ticket_type_distribution(self) -> pd.DataFrame:
        """Get ticket type distribution"""
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT 
                ticket_type,
                COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM evaluations WHERE ticket_type IS NOT NULL), 2) as percentage
            FROM evaluations
            WHERE ticket_type IS NOT NULL
            GROUP BY ticket_type
            ORDER BY count DESC
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        return df
    
    def debug_database_contents(self):
        """Debug function to show database contents"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check evaluations table
        cursor.execute("SELECT COUNT(*) FROM evaluations")
        eval_count = cursor.fetchone()[0]
        print(f"Total evaluations: {eval_count}")
        
        # Check latest experiments table
        cursor.execute("SELECT COUNT(*) FROM latest_experiments")
        exp_count = cursor.fetchone()[0]
        print(f"Total experiments: {exp_count}")
        
        # Show recent dates
        cursor.execute("SELECT DISTINCT date FROM evaluations ORDER BY date DESC LIMIT 10")
        recent_dates = cursor.fetchall()
        print(f"Recent dates: {[d[0] for d in recent_dates]}")
        
        conn.close()
