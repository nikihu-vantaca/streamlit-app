# Zendesk Support Agent Performance Dashboard

This Streamlit dashboard analyzes ticket evaluation data from LangSmith, supporting two different evaluation systems:

## API Key Setup

### For Streamlit Cloud (Production)
1. Go to your Streamlit Cloud dashboard
2. Navigate to your app's settings
3. Add a secret with key `api_key` and your LangSmith API key as the value

### For Local Development
1. Create a `.env` file in the project root
2. Add your API key: `LANGSMITH_API_KEY=your_actual_api_key_here`
3. Or set the environment variable: `export LANGSMITH_API_KEY=your_actual_api_key_here`

### For Standalone Scripts
The evaluation scripts (`get_evaluation_ungrouped.py` and `get_evaluation_grouped.py`) will automatically use the API key from:
1. Environment variable `LANGSMITH_API_KEY`
2. `.env` file (if present)

## Evaluation Systems

### Pre-August 15, 2025 (Ungrouped)
- Uses `zendesk-evaluation-2025-XX-XX` experiments
- Categorizes tickets as "homeowner" or "management" based on evaluation key
- Management tickets are excluded from evaluation counts

### Post-August 15, 2025 (Grouped)
- Uses separate experiments:
  - `implementation-evaluation-2025-XX-XX`
  - `homeowner-pay-evaluation-2025-XX-XX`
  - `management-pay-evaluation-2025-XX-XX`
- All tickets count as evaluated
- Tracks implementation tickets separately

## Usage

1. **Streamlit Dashboard**: Run `streamlit run streamlit_app.py`
2. **Ungrouped Analysis**: Run `python get_evaluation_ungrouped.py`
3. **Grouped Analysis**: Run `python get_evaluation_grouped.py`

## Features

- Real-time data syncing from LangSmith
- SQLite database for data persistence
- Interactive charts and metrics
- Export functionality (CSV, JSON)
- Date range filtering (2 weeks, 4 weeks, all data)
- Separate tracking for different ticket types
