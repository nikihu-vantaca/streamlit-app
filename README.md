# Ticket Evaluation Dashboard

A comprehensive Streamlit dashboard for analyzing ticket evaluation data from LangSmith, with the same data structure and analysis capabilities as the `create_daily_breakdown_spreadsheet.py` script.

## Features

### 📈 Overview Dashboard Tab
- **Key Metrics**: Total tickets, quality percentages, and performance indicators
- **Interactive Charts**: Quality distribution over time, ticket type distribution
- **Detailed Analysis**: Breakdown by ticket type with quality metrics
- **Real-time Data**: Sync with LangSmith to get latest evaluation data

### 📊 Daily Breakdown Analysis Tab
- **Comprehensive Breakdown**: Same data structure as `create_daily_breakdown_spreadsheet.py`
- **Interactive Visualizations**: Daily breakdown charts by ticket type and quality
- **Data Export**: Download as CSV or complete Excel spreadsheet with multiple sheets
- **Summary Statistics**: Overall metrics by ticket type and quality

## Data Structure

The dashboard provides the same detailed breakdown as the spreadsheet script:

- **Daily Breakdown**: Date, ticket type, quality, count, percentages
- **Summary Data**: Overall statistics by ticket type and quality
- **Pivot Tables**: Analysis by date and type, date and quality

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure LangSmith API key in `.streamlit/secrets.toml`:
```toml
[langsmith]
api_key = "your_api_key_here"
```

3. Run the dashboard:
```bash
streamlit run streamlit_app.py
```

## Usage

1. **Data Sync**: Use the sidebar to sync latest data from LangSmith
2. **Date Range**: Select custom date ranges for analysis
3. **Overview**: View high-level metrics and trends in the first tab
4. **Detailed Analysis**: Access comprehensive breakdowns in the second tab
5. **Export**: Download data as CSV or Excel files

## Database

The dashboard uses SQLite (`ticket_data.db`) to store evaluation data locally, with automatic date validation and cleanup functionality.

## Requirements

- Python 3.7+
- Streamlit
- Pandas
- Plotly
- LangSmith
- OpenPyXL (for Excel export)

## File Structure

- `streamlit_app.py` - Main dashboard application
- `create_daily_breakdown_spreadsheet.py` - Original spreadsheet script
- `database.py` - Database utilities
- `requirements.txt` - Python dependencies
- `.streamlit/secrets.toml` - Configuration (create this file)
