#!/usr/bin/env python3
"""
LangSmith Evaluation Dashboard
Streamlit application for visualizing evaluation data from LangSmith
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import sqlite3
from evaluation_database import EvaluationDatabase

# Page configuration
st.set_page_config(
    page_title="LangSmith Evaluation Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .stAlert {
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    """Load data from the database"""
    try:
        db = EvaluationDatabase('merged_evaluation.db')
        
        # Get various data views
        evaluation_summary = db.get_evaluation_summary()
        daily_breakdown = db.get_daily_breakdown()
        quality_distribution = db.get_quality_distribution()
        ticket_type_distribution = db.get_ticket_type_distribution()
        latest_experiments = db.get_latest_experiments_info()
        
        # Filter out zendesk experiments and evaluations from display
        if not latest_experiments.empty:
            latest_experiments = latest_experiments[~latest_experiments['experiment_name'].str.startswith('zendesk', na=False)]
        
        if not evaluation_summary.empty:
            evaluation_summary = evaluation_summary[~evaluation_summary['experiment_name'].str.startswith('zendesk', na=False)]
        
        return {
            'evaluation_summary': evaluation_summary,
            'daily_breakdown': daily_breakdown,
            'quality_distribution': quality_distribution,
            'ticket_type_distribution': ticket_type_distribution,
            'latest_experiments': latest_experiments
        }
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

def main():
    """Main dashboard function"""
    
    # Header
    st.markdown('<h1 class="main-header">📊 LangSmith Evaluation Dashboard</h1>', unsafe_allow_html=True)
    
    # Load data
    data = load_data()
    if data is None:
        st.error("Failed to load data. Please check your database connection.")
        return
    
    # Sidebar for filters
    st.sidebar.header("🔍 Filters")
    
    # Date range filter
    st.sidebar.subheader("Date Range")
    date_range = st.sidebar.date_input(
        "Select date range",
        value=(datetime.now() - timedelta(days=30), datetime.now()),
        max_value=datetime.now()
    )
    
    # Handle date range selection
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
    else:
        start_date_str = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        end_date_str = datetime.now().strftime('%Y-%m-%d')
    
    # Ticket type filter
    ticket_types = ['All'] + sorted(data['ticket_type_distribution']['ticket_type'].unique().tolist())
    selected_ticket_type = st.sidebar.selectbox("Ticket Type", ticket_types)
    
    # Apply filters
    if selected_ticket_type != 'All':
        filtered_daily = data['daily_breakdown'][data['daily_breakdown']['ticket_type'] == selected_ticket_type]
        filtered_summary = data['evaluation_summary'][data['evaluation_summary']['ticket_type'] == selected_ticket_type]
    else:
        filtered_daily = data['daily_breakdown']
        filtered_summary = data['evaluation_summary']
    
    # Filter by date range
    filtered_daily = filtered_daily[
        (filtered_daily['date'] >= start_date_str) & 
        (filtered_daily['date'] <= end_date_str)
    ]
    
    # Key Metrics Row
    st.subheader("📈 Key Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_evaluations = filtered_daily['total_evaluations'].sum()
        st.metric("Total Evaluations", f"{total_evaluations:,}")
    
    with col2:
        avg_score = filtered_daily['avg_score'].mean()
        st.metric("Average Score", f"{avg_score:.2f}" if pd.notna(avg_score) else "N/A")
    
    with col3:
        good_count = filtered_daily['good_count'].sum()
        st.metric("Good Quality", f"{good_count:,}")
    
    with col4:
        bad_ugly_count = filtered_daily['bad_count'].sum() + filtered_daily['ugly_count'].sum()
        st.metric("Bad/Ugly Quality", f"{bad_ugly_count:,}")
    
    # Charts Row 1
    st.subheader("📊 Quality Distribution Over Time")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Quality distribution pie chart
        quality_data = data['quality_distribution']
        if not quality_data.empty:
            fig_pie = px.pie(
                quality_data, 
                values='count', 
                names='quality',
                title="Overall Quality Distribution",
                color_discrete_map={
                    'good': '#2E8B57',
                    'bad': '#FF6B6B',
                    'ugly': '#8B0000'
                }
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        # Ticket type distribution
        ticket_data = data['ticket_type_distribution']
        if not ticket_data.empty:
            fig_bar = px.bar(
                ticket_data,
                x='ticket_type',
                y='count',
                title="Ticket Type Distribution",
                color='ticket_type'
            )
            st.plotly_chart(fig_bar, use_container_width=True)
    
    # Charts Row 2
    st.subheader("📅 Daily Trends")
    
    # Daily breakdown line chart
    if not filtered_daily.empty:
        # Prepare data for plotting
        plot_data = filtered_daily.melt(
            id_vars=['date', 'ticket_type'],
            value_vars=['good_count', 'bad_count', 'ugly_count'],
            var_name='quality',
            value_name='count'
        )
        
        # Clean up quality labels
        plot_data['quality'] = plot_data['quality'].str.replace('_count', '').str.title()
        
        fig_line = px.line(
            plot_data,
            x='date',
            y='count',
            color='quality',
            title=f"Daily Quality Trends ({start_date_str} to {end_date_str})",
            color_discrete_map={
                'Good': '#2E8B57',
                'Bad': '#FF6B6B',
                'Ugly': '#8B0000'
            }
        )
        fig_line.update_xaxes(title_text="Date")
        fig_line.update_yaxes(title_text="Number of Evaluations")
        st.plotly_chart(fig_line, use_container_width=True)
    
    # Charts Row 3
    st.subheader("🔬 Experiment Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Latest experiments table
        st.write("**Latest Experiments**")
        if not data['latest_experiments'].empty:
            # Format the data for display
            exp_display = data['latest_experiments'].copy()
            exp_display['date'] = pd.to_datetime(exp_display['date']).dt.strftime('%Y-%m-%d')
            exp_display['updated_at'] = pd.to_datetime(exp_display['updated_at']).dt.strftime('%Y-%m-%d %H:%M')
            
            st.dataframe(
                exp_display[['date', 'experiment_type', 'experiment_name', 'run_count']],
                use_container_width=True,
                hide_index=True
            )
    
    with col2:
        # Experiment type distribution
        if not data['latest_experiments'].empty:
            exp_type_counts = data['latest_experiments']['experiment_type'].value_counts()
            fig_exp = px.pie(
                values=exp_type_counts.values,
                names=exp_type_counts.index,
                title="Experiment Type Distribution"
            )
            st.plotly_chart(fig_exp, use_container_width=True)
    
    # Data Table Section
    st.subheader("📋 Detailed Data")
    
    # Evaluation summary table
    if not filtered_summary.empty:
        st.write("**Evaluation Summary by Date and Ticket Type**")
        
        # Format the data
        summary_display = filtered_summary.copy()
        summary_display['avg_score'] = summary_display['avg_score'].round(2)
        
        st.dataframe(
            summary_display,
            use_container_width=True,
            hide_index=True
        )
    
    # Sidebar - Data Refresh
    st.sidebar.header("🔄 Data Management")
    
    if st.sidebar.button("Refresh Data Cache"):
        st.cache_data.clear()
        st.rerun()
    
    # API Key status
    db = EvaluationDatabase()
    api_key = db.get_api_key()
    
    if api_key:
        st.sidebar.success("✅ API Key Found")
        if st.sidebar.button("Fetch New Data from LangSmith"):
            with st.spinner("Fetching data from LangSmith..."):
                # Get the latest date from the database to fetch only newer data
                latest_date = db.get_latest_date()
                if latest_date:
                    # Start fetching from the day after the latest data
                    fetch_start_date = (pd.to_datetime(latest_date) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
                    fetch_end_date = datetime.now().strftime('%Y-%m-%d')
                    st.info(f"Fetching data from {fetch_start_date} to {fetch_end_date}")
                    success = db.fetch_and_sync_data(api_key, fetch_start_date, fetch_end_date)
                else:
                    # Fallback to last 30 days if no data exists
                    success = db.fetch_and_sync_data(api_key, start_date_str, end_date_str)
                
                if success:
                    st.success("Data fetched successfully!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Failed to fetch data. Check the console for details.")
    else:
        st.sidebar.warning("⚠️ No API Key Found")
        st.sidebar.info("Set LANGSMITH_API_KEY environment variable or create .streamlit/secrets.toml")

if __name__ == "__main__":
    main()
