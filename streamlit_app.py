import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta
import json
import io
import csv
from langsmith import Client
import re
from collections import defaultdict
from database import TicketDatabase

# Debug: Print to verify code is updated
print("🚀 Streamlit app loaded - Updated version v2.1!")

# Version: 2.1 - Fixed evaluation logic and database migration

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

# Initialize database
@st.cache_resource
def get_database():
    return TicketDatabase()

def create_quality_bar_chart(df):
    """Create bar chart for copy_paste and low_quality counts"""
    # Ensure data is sorted chronologically
    df_sorted = df.sort_values('date')
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df_sorted['date'],
        y=df_sorted['copy_paste_count'],
        name='Copy Paste',
        marker_color='#2176A5'  # blue
    ))
    
    fig.add_trace(go.Bar(
        x=df_sorted['date'],
        y=df_sorted['low_quality_count'],
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
    # Ensure data is sorted chronologically
    df_sorted = df.sort_values('date')
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df_sorted['date'],
        y=df_sorted['total_tickets'],
        name='Total Tickets',
        marker_color='#2176A5'  # blue
    ))
    
    fig.add_trace(go.Bar(
        x=df_sorted['date'],
        y=df_sorted['total_evaluated'],
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
    # Ensure data is sorted chronologically
    df_sorted = df.sort_values('date')
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df_sorted['date'],
        y=df_sorted['skipped_count'],
        name='Skipped Tickets',
        marker_color='#2176A5'  # blue
    ))
    
    fig.add_trace(go.Bar(
        x=df_sorted['date'],
        y=df_sorted['management_company_ticket_count'],
        name='Management Company Tickets',
        marker_color='#6BB643'  # green
    ))
    
    fig.update_layout(
        title='Daily Skipped vs Management Company Tickets',
        xaxis_title='Date',
        yaxis_title='Count',
        barmode='group',
        height=500
    )
    
    return fig


def create_weekly_percentage_chart(df):
    """Create line chart showing weekly percentages for evaluated and copy-paste tickets"""
    # Group by week and calculate percentages
    df_weekly = df.copy()
    df_weekly['week'] = df_weekly['date'].dt.to_period('W').dt.start_time
    df_weekly['week_label'] = df_weekly['week'].dt.strftime('Week of %-m/%-d')
    
    weekly_stats = df_weekly.groupby('week_label').agg({
        'total_tickets': 'sum',
        'total_evaluated': 'sum',
        'copy_paste_count': 'sum'
    }).reset_index()
    
    # Calculate percentages
    weekly_stats['evaluated_pct'] = (weekly_stats['total_evaluated'] / weekly_stats['total_tickets'] * 100).round(1)
    weekly_stats['copy_paste_pct'] = (weekly_stats['copy_paste_count'] / weekly_stats['total_evaluated'] * 100).round(1)
    
    # Sort by actual week start date to ensure chronological order
    df_weekly_temp = df_weekly[['week', 'week_label']].drop_duplicates()
    week_order = df_weekly_temp.sort_values('week')['week_label'].tolist()
    
    # Reorder the weekly_stats DataFrame based on chronological week order
    weekly_stats['week_order'] = weekly_stats['week_label'].map({week: i for i, week in enumerate(week_order)})
    weekly_stats = weekly_stats.sort_values('week_order').drop('week_order', axis=1)
    
    # Create the line chart
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=weekly_stats['week_label'],
        y=weekly_stats['evaluated_pct'],
        mode='lines+markers',
        name='Evaluated Ticket %',
        line=dict(color='#2176A5', width=3),
        marker=dict(size=8),
        connectgaps=True
    ))
    
    fig.add_trace(go.Scatter(
        x=weekly_stats['week_label'],
        y=weekly_stats['copy_paste_pct'],
        mode='lines+markers',
        name='Copy/Paste %',
        line=dict(color='#6BB643', width=3), 
        marker=dict(size=8),
        connectgaps=True
    ))
    
    fig.update_layout(
        title='Evaluated vs. Copy-Paste Tickets (% by Week)',
        xaxis_title='Week',
        yaxis_title='Percentage (%)',
        height=500,
        yaxis=dict(
            range=[0, 100],
            tickmode='linear',
            tick0=0,
            dtick=10,
            gridcolor='lightgray'
        ),
        xaxis=dict(
            gridcolor='lightgray'
        ),
        plot_bgcolor='white',
        hovermode='x unified'
    )
    
    return fig

def create_summary_metrics(df):
    """Create summary metrics for the entire period"""
    total_copy_paste = df['copy_paste_count'].sum()
    total_low_quality = df['low_quality_count'].sum()
    total_evaluated = df['total_evaluated'].sum()
    total_tickets = df['total_tickets'].sum()
    total_skipped = df['skipped_count'].sum()
    total_management = df['management_company_ticket_count'].sum()
    total_implementation = df['implementation_ticket_count'].sum() if 'implementation_ticket_count' in df.columns else 0
    
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
        'total_implementation': total_implementation,
        'copy_paste_pct': copy_paste_pct,
        'low_quality_pct': low_quality_pct,
        'evaluation_rate': evaluation_rate
    }

# Main app
def main():
    try:
        api_key = st.secrets["api_key"]
    except KeyError:
        st.error("LangSmith API key not found in secrets. Please configure it in Streamlit Cloud.")
        st.stop()
    
    st.markdown('<h1 class="main-header">Zendesk Support Agent Performance Dashboard</h1>', unsafe_allow_html=True)

    # Initialize database
    db = get_database()

    # Sidebar controls
    st.sidebar.markdown("### 🔄 Data Management")
    
    # Sync button to fetch latest data
    if st.sidebar.button("🔄 Sync Latest Data"):
        with st.spinner("Syncing latest data from LangSmith..."):
            new_records = db.fetch_and_store_latest_data(api_key)
            if new_records > 0:
                st.sidebar.success(f"✅ Synced {new_records} new records!")
            else:
                st.sidebar.info("✅ Database is up to date!")
        st.rerun()

    # Convert UTC to EDT (UTC-4)
    edt_time = datetime.now() - timedelta(hours=4)
    st.sidebar.markdown(f"**Last Updated (EDT):** {edt_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Date range selection
    date_range_options = ["2 Weeks", "4 Weeks", "All Data"]
    selected_date_range = st.sidebar.radio(
        "Select Date Range for Data:",
        date_range_options,
        index=0,
        help="Choose how far back to fetch data for analysis."
    )

    # Map user-friendly options to function parameters
    if selected_date_range == "2 Weeks":
        date_range_param = "2_weeks"
    elif selected_date_range == "4 Weeks":
        date_range_param = "4_weeks"
    else: # All Data
        date_range_param = "all_data"

    # Get data from database
    with st.spinner("Loading data from database..."):
        df, daily_data = db.get_data_for_range(date_range_param)
    
    if df is None or df.empty:
        st.warning("No data found for the selected date range. Try syncing data first!")
        return
    
    # Filter to only include data from July 2025 onwards
    july_2025_start = pd.to_datetime('2025-07-01')
    df = df[df['date'] >= july_2025_start].copy()
    
    if df.empty:
        st.warning("No data found from July 2025 onwards. Try syncing data first!")
        return
    
    # Ensure data is sorted chronologically
    df = df.sort_values('date')
    
    # Create summary metrics
    metrics = create_summary_metrics(df)
    
    # Display summary metrics
    st.subheader("📊 Summary")
    
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
            help="Management company tickets processed"
        )
    
    # Additional row for implementation tickets
    col7, col8, col9 = st.columns(3)
    
    with col7:
        st.metric(
            "Implementation Tickets",
            f"{metrics['total_implementation']:,}",
            help="Implementation tickets (post-August 15, 2025)"
        )
    
    # Pie charts for evaluation and copy-paste rates
    st.subheader("🥧 Evaluation & Quality Breakdown")
    pie1_col, pie2_col = st.columns(2)
    with pie1_col:
        evaluated = metrics['total_evaluated']
        skipped = metrics['total_skipped']
        mgt_company = metrics['total_management']
        implementation = metrics['total_implementation']
        other = metrics['total_tickets'] - (evaluated + skipped + mgt_company + implementation)
        fig_eval = go.Figure(data=[go.Pie(
            labels=["Evaluated", "Management Company", "Missed", "Implementation", "Other"],
            values=[evaluated, mgt_company, skipped, implementation, other],
            hole=0.4,
            marker_colors=["#6BB643", "#2176A5", "#E4572E", "#FFD700", "#D3D3D3"]
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
    
    # Weekly percentage chart
    st.plotly_chart(create_weekly_percentage_chart(df), use_container_width=True)
    
    # Data table
    st.subheader("📋 Daily Breakdown")
    
    # Format the dataframe for display and ensure chronological order
    display_df = df.copy()
    display_df = display_df.sort_values('date')  # Sort chronologically
    display_df['Date'] = display_df['date'].dt.strftime('%Y-%m-%d')
    # Handle columns that might not exist
    available_columns = ['Date', 'total_tickets', 'total_evaluated', 'copy_paste_count', 
                        'low_quality_count', 'skipped_count', 'management_company_ticket_count']
    
    if 'implementation_ticket_count' in display_df.columns:
        available_columns.append('implementation_ticket_count')
    
    display_df = display_df[available_columns]
    
    # Map column names
    column_mapping = {
        'Date': 'Date',
        'total_tickets': 'Total Tickets',
        'total_evaluated': 'Evaluated',
        'copy_paste_count': 'Copy Paste',
        'low_quality_count': 'Low Quality',
        'skipped_count': 'Skipped',
        'management_company_ticket_count': 'Management Co.',
        'implementation_ticket_count': 'Implementation'
    }
    
    display_df.columns = [column_mapping[col] for col in available_columns]
    
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
        low_quality_tickets = db.get_low_quality_tickets(date_range_param)
        if low_quality_tickets:
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=['Date', 'Ticket ID', 'Ticket Type'])
            writer.writeheader()
            # Convert database field names to CSV field names
            formatted_tickets = []
            for ticket in low_quality_tickets:
                formatted_tickets.append({
                    'Date': ticket['date'],
                    'Ticket ID': ticket['ticket_id'],
                    'Ticket Type': ticket.get('ticket_type', 'homeowner')
                })
            writer.writerows(formatted_tickets)
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