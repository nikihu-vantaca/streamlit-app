import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
from langsmith import Client
import re
from collections import defaultdict

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
                'experiment_name': f"zendesk-evaluation-{date_str}",
                'low_quality_tickets': []
            }
            current_date += timedelta(days=1)
        
        # Step 1: Collect latest runs by (date, ticket_id)
        latest_runs = {}  # key: (date_str, ticket_id), value: (start_time, run, result, quality, comment)
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
                # Only proceed if result is set
                quality = result.get("quality")
                comment = result.get("comment")
                # Robust ticket_id extraction (matches test.py)
                ticket_id = None
                if hasattr(run, "inputs") and run.inputs:
                    if isinstance(run.inputs, dict):
                        if 'ticket_id' in run.inputs:
                            ticket_id = run.inputs['ticket_id']
                        elif 'x' in run.inputs and isinstance(run.inputs['x'], dict):
                            ticket_id = run.inputs['x'].get('ticket_id')
                        elif 'run' in run.inputs and isinstance(run.inputs['run'], dict):
                            run_inputs = run.inputs['run'].get('inputs', {})
                            if 'x' in run_inputs and isinstance(run_inputs['x'], dict):
                                ticket_id = run_inputs['x'].get('ticket_id')
                if ticket_id is None:
                    ticket_id = result.get('ticket_id')
                # Extract start_time
                start_time = getattr(run, "start_time", None)
                if isinstance(start_time, str):
                    start_time_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                else:
                    start_time_dt = start_time  # If already a datetime
                key = (date_str, ticket_id)
                # Only keep the latest run for each (date, ticket_id)
                if ticket_id is not None and (key not in latest_runs or start_time_dt > latest_runs[key][0]):
                    latest_runs[key] = (start_time_dt, run, result, quality, comment)
        # Step 2: Process only the latest runs
        for (date_str, ticket_id), (start_time_dt, run, result, quality, comment) in latest_runs.items():
            daily_data[date_str]['total_tickets'] += 1
            if quality == "copy_paste":
                daily_data[date_str]['copy_paste_count'] += 1
                daily_data[date_str]['total_evaluated'] += 1
            elif quality == "low_quality":
                daily_data[date_str]['low_quality_count'] += 1
                daily_data[date_str]['total_evaluated'] += 1
                daily_data[date_str]['low_quality_tickets'].append(ticket_id)
            elif comment == "empty_bot_answer":
                daily_data[date_str]['skipped_count'] += 1
            elif comment == "management_company_ticket":
                daily_data[date_str]['management_company_ticket_count'] += 1
            else:
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
        x=df['date'],
        y=df['copy_paste_count'],
        name='Copy Paste',
        marker_color='#2176A5'  # blue
    ))
    
    fig.add_trace(go.Bar(
        x=df['date'],
        y=df['low_quality_count'],
        name='Low Quality',
        marker_color='#6BB643'  # green
    ))
    
    fig.update_layout(
        title='Daily Copy Paste vs Low Quality Tickets',
        xaxis_title='Date',
        yaxis_title='Count',
        barmode='group',
        height=500
    )
    
    return fig


def create_total_tickets_chart(df):
    """Create bar chart for total evaluated vs total tickets"""
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df['date'],
        y=df['total_tickets'],
        name='Total Tickets',
        marker_color='#2176A5'  # blue
    ))
    
    fig.add_trace(go.Bar(
        x=df['date'],
        y=df['total_evaluated'],
        name='Evaluated Tickets',
        marker_color='#6BB643'  # green
    ))
    
    fig.update_layout(
        title='Daily Total Tickets vs Evaluated Tickets',
        xaxis_title='Date',
        yaxis_title='Count',
        barmode='group',
        height=500
    )
    
    return fig


def create_skipped_management_chart(df):
    """Create bar chart for skipped and management company tickets"""
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df['date'],
        y=df['skipped_count'],
        name='Missed Tickets',
        marker_color='#2176A5'  # blue
    ))
    
    fig.add_trace(go.Bar(
        x=df['date'],
        y=df['management_company_ticket_count'],
        name='Management Company Tickets',
        marker_color='#6BB643'  # green
    ))
    
    fig.update_layout(
        title='Daily Missed vs Management Company Tickets',
        xaxis_title='Date',
        yaxis_title='Count',
        barmode='group',
        height=500
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
            "Missed Tickets",
            f"{metrics['total_skipped']:,}",
            help="Missed tickets due to service downtime"
        )
    
    with col6:
        st.metric(
            "Management Company Tickets",
            f"{metrics['total_management']:,}",
            help="Skipped management company tickets"
        )
    
    # Pie charts for evaluation and copy-paste rates
    st.subheader("🥧 Evaluation & Quality Breakdown")
    pie1_col, pie2_col = st.columns(2)
    with pie1_col:
        evaluated = metrics['total_evaluated']
        skipped = metrics['total_skipped']
        mgt_company = metrics['total_management']
        other = metrics['total_tickets'] - (evaluated + skipped + mgt_company)
        fig_eval = go.Figure(data=[go.Pie(
            labels=["Evaluated", "Management Company", "Missed", "Other"],
            values=[evaluated, mgt_company, skipped, other],
            hole=0.4,
            marker_colors=["#6BB643", "#2176A5", "#E4572E", "#D3D3D3"]
        )])
        fig_eval.update_layout(title="% Ticket Outcomes", height=350)
        st.plotly_chart(fig_eval, use_container_width=True)
    with pie2_col:
        copy_paste = metrics['total_copy_paste']
        other_eval = metrics['total_evaluated'] - metrics['total_copy_paste']
        fig_cp = go.Figure(data=[go.Pie(
            labels=["Copy-Pasted", "Other Evaluated"],
            values=[copy_paste, other_eval],
            hole=0.4,
            marker_colors=["#6BB643", "#2176A5"]
        )])
        fig_cp.update_layout(title="% Copy-Pasted of Evaluated", height=350)
        st.plotly_chart(fig_cp, use_container_width=True)

    
    
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
    
    col1, col2, col3 = st.columns(3)
    
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
    
    with col3:
        low_quality_tickets = []
        for date_str, day in daily_data.items():
            if 'low_quality_tickets' in day:
                for ticket in day['low_quality_tickets']:
                    low_quality_tickets.append({
                        'Date': date_str,
                        'Ticket ID': ticket
                    })
        if low_quality_tickets:
            import io
            import csv
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=['Date', 'Ticket ID'])
            writer.writeheader()
            writer.writerows(low_quality_tickets)
            st.download_button(
                label="📥 Download Low Quality Tickets CSV",
                data=output.getvalue(),
                file_name=f"low_quality_tickets_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No low quality tickets found for this period.")

if __name__ == "__main__":
    main()