import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
from langsmith import Client
import re

# Page configuration
st.set_page_config(
    page_title="Zendesk SupportAgent Performance Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.main-header {
    font-size: 2.5rem;
    font-weight: bold;
    color: #1f77b4;
    text-align: center;
    margin-bottom: 2rem;
}
.metric-container {
    background-color: #f0f2f6;
    padding: 1rem;
    border-radius: 10px;
    margin: 0.5rem 0;
}
.sidebar-header {
    font-size: 1.5rem;
    font-weight: bold;
    color: #1f77b4;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)  # Cache for 1 hour for hourly refresh
def fetch_langsmith_data(api_key, project_name="evaluators"):
    """Fetch and process LangSmith data for the past 2 weeks"""
    try:
        client = Client(api_key=api_key)
        runs = client.list_runs(project_name=project_name)
        
        # Generate date range for past 2 weeks
        end_date = datetime.now()
        start_date = end_date - timedelta(days=14)
        
        # Initialize data structure
        daily_data = {}
        
        # Create entries for all dates in range (fill with 0s for missing days)
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            daily_data[date_str] = {
                'date': date_str,
                'copy_paste_count': 0,
                'low_quality_count': 0,
                'skipped_count': 0,
                'management_company_ticket_count': 0,
                'total_evaluated': 0,
                'total_tickets': 0,
                'experiment_name': f"zendesk-evaluation-{date_str}"
            }
            current_date += timedelta(days=1)
        
        # Process runs
        for run in runs:
            # Extract experiment name and date
            experiment = None
            if hasattr(run, "metadata") and run.metadata and isinstance(run.metadata, dict):
                experiment = run.metadata.get("experiment")
            
            if not experiment:
                continue
                
            # Check if it's a zendesk evaluation experiment
            if not experiment.startswith("zendesk-evaluation-2025-07-"):
                continue
                
            # Extract date from experiment name
            date_match = re.search(r"zendesk-evaluation-(\d{4}-\d{2}-\d{2})", experiment)
            if not date_match:
                continue
                
            date_str = date_match.group(1)
            
            # Skip if date is outside our range
            if date_str not in daily_data:
                continue
            
            # Process detailed_similarity_evaluator runs
            if run.name == "detailed_similarity_evaluator" and run.outputs:
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
                
                daily_data[date_str]['total_tickets'] += 1
                
                quality = result.get("quality")
                comment = result.get("comment")
                
                if quality == "copy_paste":
                    daily_data[date_str]['copy_paste_count'] += 1
                    daily_data[date_str]['total_evaluated'] += 1
                elif quality == "low_quality":
                    daily_data[date_str]['low_quality_count'] += 1
                    daily_data[date_str]['total_evaluated'] += 1
                elif comment == "empty_bot_answer":
                    daily_data[date_str]['skipped_count'] += 1
                elif comment == "management_company_ticket":
                    daily_data[date_str]['management_company_ticket_count'] += 1
                else:
                    # Other evaluated tickets
                    daily_data[date_str]['total_evaluated'] += 1
        
        # Convert to DataFrame
        df = pd.DataFrame(list(daily_data.values()))
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        return df, daily_data
        
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        return None, None

def create_quality_bar_chart(df):
    """Create bar chart for copy_paste and low_quality counts"""
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df['date'].dt.strftime('%Y-%m-%d'),
        y=df['copy_paste_count'],
        name='Copy Paste',
        marker_color='#ff7f0e'
    ))
    
    fig.add_trace(go.Bar(
        x=df['date'].dt.strftime('%Y-%m-%d'),
        y=df['low_quality_count'],
        name='Low Quality',
        marker_color='#d62728'
    ))
    
    fig.update_layout(
        title='Daily Copy Paste vs Low Quality Tickets',
        xaxis_title='Date',
        yaxis_title='Count',
        barmode='group',
        height=500,
        xaxis=dict(
            type='category',
            tickmode='array',
            tickvals=[d.strftime('%Y-%m-%d') for d in df['date']],
            ticktext=[d.strftime('%Y-%m-%d') for d in df['date']]
        )
    )
    
    return fig


def create_total_tickets_chart(df):
    """Create bar chart for total evaluated vs total tickets"""
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df['date'].dt.strftime('%Y-%m-%d'),
        y=df['total_tickets'],
        name='Total Tickets',
        marker_color='#1f77b4'
    ))
    
    fig.add_trace(go.Bar(
        x=df['date'].dt.strftime('%Y-%m-%d'),
        y=df['total_evaluated'],
        name='Evaluated Tickets',
        marker_color='#2ca02c'
    ))
    
    fig.update_layout(
        title='Daily Total Tickets vs Evaluated Tickets',
        xaxis_title='Date',
        yaxis_title='Count',
        barmode='group',
        height=500,
        xaxis=dict(
            type='category',
            tickmode='array',
            tickvals=[d.strftime('%Y-%m-%d') for d in df['date']],
            ticktext=[d.strftime('%Y-%m-%d') for d in df['date']]
        )
    )
    
    return fig


def create_skipped_management_chart(df):
    """Create bar chart for skipped and management company tickets"""
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df['date'].dt.strftime('%Y-%m-%d'),
        y=df['skipped_count'],
        name='Skipped Tickets',
        marker_color='#9467bd'
    ))
    
    fig.add_trace(go.Bar(
        x=df['date'].dt.strftime('%Y-%m-%d'),
        y=df['management_company_ticket_count'],
        name='Management Company Tickets',
        marker_color='#8c564b'
    ))
    
    fig.update_layout(
        title='Daily Skipped vs Management Company Tickets',
        xaxis_title='Date',
        yaxis_title='Count',
        barmode='group',
        height=500,
        xaxis=dict(
            type='category',
            tickmode='array',
            tickvals=[d.strftime('%Y-%m-%d') for d in df['date']],
            ticktext=[d.strftime('%Y-%m-%d') for d in df['date']]
        )
    )
    
    return fig

def create_summary_metrics(df):
    """Create summary metrics for the entire 2-week period"""
    total_copy_paste = df['copy_paste_count'].sum()
    total_low_quality = df['low_quality_count'].sum()
    total_evaluated = df['total_evaluated'].sum()
    total_tickets = df['total_tickets'].sum()
    total_skipped = df['skipped_count'].sum()
    total_management = df['management_company_ticket_count'].sum()
    
    # Calculate percentages
    copy_paste_pct = (total_copy_paste / total_evaluated * 100) if total_evaluated > 0 else 0
    low_quality_pct = (total_low_quality / total_evaluated * 100) if total_evaluated > 0 else 0
    evaluation_rate = (total_evaluated / total_tickets * 100) if total_tickets > 0 else 0
    
    return {
        'total_copy_paste': total_copy_paste,
        'total_low_quality': total_low_quality,
        'total_evaluated': total_evaluated,
        'total_tickets': total_tickets,
        'total_skipped': total_skipped,
        'total_management': total_management,
        'copy_paste_pct': copy_paste_pct,
        'low_quality_pct': low_quality_pct,
        'evaluation_rate': evaluation_rate
    }

# Main app
def main():
    try:
        api_key = st.secrets["langsmith"]["api_key"]
    except KeyError:
        st.error("LangSmith API key not found in secrets. Please configure it in Streamlit Cloud.")
        st.stop()
    st.markdown('<h1 class="main-header">Zendesk Support Agent Performance Dashboard</h1>', unsafe_allow_html=True)

    # --- Place your sidebar code here ---
    if st.sidebar.button("🔄 Refresh Data Now"):
        st.cache_data.clear()
        st.rerun()
        st.sidebar.success("Data refreshed!")

    # Convert UTC to EDT (UTC-4)
    edt_time = datetime.now() - timedelta(hours=4)
    st.sidebar.markdown(f"**Last Updated (EDT):** {edt_time.strftime('%Y-%m-%d %H:%M:%S')}")
    # --- End sidebar code ---

    # Now fetch data, etc.
    with st.spinner("Fetching data from LangSmith..."):
        df, daily_data = fetch_langsmith_data(api_key) # type: ignore
    
    if df is None:
        st.error("Failed to fetch data. Please check your API key and try again.")
        return
    
    # Create summary metrics
    metrics = create_summary_metrics(df)
    
    # Display summary metrics
    st.subheader("📊 2-Week Summary")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Total Tickets",
            f"{metrics['total_tickets']:,}",
            help="Total number of tickets processed"
        )
    
    with col2:
        st.metric(
            "Low Quality Responses",
            f"{metrics['total_low_quality']:,}",
            f"{metrics['low_quality_pct']:.1f}% of evaluated",
            help="Tickets identified as low quality responses"
        )
    
    with col3:
        st.metric(
            "Copy-Pasted Responses",
            f"{metrics['total_copy_paste']:,}",
            f"{metrics['copy_paste_pct']:.1f}% of evaluated",
            help="Tickets identified as copy-paste responses"
        )
    

    
    # Additional metrics row
    col4, col5, col6 = st.columns(3)

    with col4:
        st.metric(
            "Evaluated Tickets",
            f"{metrics['total_evaluated']:,}",
            f"{metrics['evaluation_rate']:.1f}% of total",
            help="Tickets that were successfully evaluated"
        )
        
    
    with col5:
        st.metric(
            "Skipped Tickets",
            f"{metrics['total_skipped']:,}",
            help="Skipped tickets due to service downtime"
        )
    
    with col6:
        st.metric(
            "Management Company Tickets",
            f"{metrics['total_management']:,}",
            help="Skipped management company tickets"
        )
    
    
    # Charts
    st.subheader("📈 Daily Trends")
    
    # Quality issues chart
    st.plotly_chart(create_quality_bar_chart(df), use_container_width=True)
    
    # Total vs evaluated tickets chart
    st.plotly_chart(create_total_tickets_chart(df), use_container_width=True)
    
    # Skipped and management tickets chart
    st.plotly_chart(create_skipped_management_chart(df), use_container_width=True)
    
    # Data table
    st.subheader("📋 Daily Breakdown")
    
    # Format the dataframe for display
    display_df = df.copy()
    display_df['Date'] = display_df['date'].dt.strftime('%Y-%m-%d')
    display_df = display_df[['Date', 'total_tickets', 'total_evaluated', 'copy_paste_count', 
                           'low_quality_count', 'skipped_count', 'management_company_ticket_count']]
    
    display_df.columns = ['Date', 'Total Tickets', 'Evaluated', 'Copy Paste', 
                         'Low Quality', 'Skipped', 'Management Co.']
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Export options
    st.subheader("💾 Export Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        csv_data = display_df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv_data,
            file_name=f"agent_performance_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    with col2:
        json_data = df.to_json(orient='records', date_format='iso', indent=2)
        st.download_button(
            label="📥 Download JSON",
            data=json_data,
            file_name=f"agent_performance_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json"
        )

if __name__ == "__main__":
    main()