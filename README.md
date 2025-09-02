# LangSmith Evaluation Dashboard

A Streamlit-based dashboard for visualizing and analyzing evaluation data from LangSmith. This application provides comprehensive insights into AI model evaluation results, including quality metrics, ticket type analysis, and experiment tracking.

## Features

- 📊 **Interactive Dashboard**: Beautiful, responsive Streamlit interface with real-time data visualization
- 📈 **Key Metrics**: Total evaluations, average scores, quality distribution, and more
- 📅 **Time Series Analysis**: Daily trends and patterns in evaluation quality
- 🔬 **Experiment Tracking**: Monitor and analyze different experiment types
- 🔍 **Advanced Filtering**: Filter by date range, ticket type, and quality
- 📋 **Detailed Data Tables**: Comprehensive data views with export capabilities
- 🔄 **Live Data Sync**: Fetch fresh data directly from LangSmith API

## Screenshots

The dashboard includes:
- Quality distribution pie charts
- Ticket type distribution bar charts
- Daily quality trends line charts
- Experiment analysis tables
- Interactive filters and date pickers

## Prerequisites

- Python 3.8 or higher
- LangSmith API key
- Access to LangSmith project "evaluators"

## Installation

1. **Clone or download this repository**
   ```bash
   cd streamlit-app-new
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up your LangSmith API key**

   **Option A: Environment Variable**
   ```bash
   export LANGSMITH_API_KEY="your_api_key_here"
   ```

   **Option B: Streamlit Secrets (Recommended for production)**
   
   Create a `.streamlit/secrets.toml` file:
   ```toml
   [langsmith]
   api_key = "your_api_key_here"
   ```

## Usage

### Starting the Dashboard

1. **Run the Streamlit app**
   ```bash
   streamlit run app.py
   ```

2. **Open your browser** and navigate to the URL shown in the terminal (usually `http://localhost:8501`)

### Using the Dashboard

1. **View Overview**: The main page shows key metrics and summary charts
2. **Apply Filters**: Use the sidebar to filter by date range and ticket type
3. **Explore Data**: Click through different sections to analyze specific aspects
4. **Refresh Data**: Use the sidebar buttons to refresh cached data or fetch new data from LangSmith

### Data Management

- **Refresh Cache**: Clears cached data and reloads from the database
- **Fetch New Data**: Retrieves fresh data from LangSmith API (requires API key)
- **Export**: Data tables can be copied or exported for further analysis

## Data Structure

The dashboard works with a SQLite database (`merged_evaluation.db`) containing:

### Tables

1. **evaluations**
   - `id`: Primary key
   - `date`: Evaluation date
   - `ticket_id`: Associated ticket identifier
   - `ticket_type`: Type of ticket (homeowner, implementation, etc.)
   - `quality`: Evaluation quality (good, bad, ugly)
   - `comment`: Evaluation comments
   - `score`: Numerical score (if available)
   - `experiment_name`: Associated experiment name
   - `run_id`: LangSmith run identifier
   - `start_time`: Evaluation start time
   - `evaluation_key`: Type of evaluation performed

2. **latest_experiments**
   - `id`: Primary key
   - `date`: Experiment date
   - `experiment_type`: Category of experiment
   - `experiment_name`: Full experiment name
   - `start_time`: Experiment start time
   - `run_count`: Number of runs in experiment
   - `updated_at`: Last update timestamp

## API Integration

The dashboard integrates with LangSmith API to:

- Fetch evaluation runs from the "evaluators" project
- Extract quality metrics and comments
- Track experiment metadata
- Handle rate limiting and timeouts gracefully

### Rate Limiting

The application includes built-in rate limiting:
- 0.1 second delay between API calls
- Automatic retry logic for failed requests
- Configurable timeout settings

## Customization

### Adding New Metrics

1. Add new methods to `EvaluationDatabase` class in `evaluation_database.py`
2. Update the `load_data()` function in `app.py`
3. Add new visualizations to the dashboard

### Styling

Custom CSS is included in the app for consistent styling. Modify the `<style>` section in `app.py` to customize colors, fonts, and layout.

### Database Schema

To modify the database schema:
1. Update the `init_database()` method in `EvaluationDatabase`
2. Add new indexes for performance
3. Update data extraction methods accordingly

## Troubleshooting

### Common Issues

1. **"No API Key Found"**
   - Ensure `LANGSMITH_API_KEY` environment variable is set
   - Check `.streamlit/secrets.toml` file exists and is properly formatted

2. **Database Connection Errors**
   - Verify `merged_evaluation.db` exists in the project directory
   - Check file permissions

3. **Missing Data**
   - Use "Fetch New Data" button to retrieve latest data from LangSmith
   - Check API key permissions and project access

4. **Performance Issues**
   - Data is cached by default; use "Refresh Data Cache" if needed
   - Large datasets may take time to load initially

### Debug Mode

Enable debug output by running:
```bash
streamlit run app.py --logger.level debug
```

## Development

### Project Structure

```
streamlit-app-new/
├── app.py                      # Main Streamlit application
├── evaluation_database.py      # Database and API integration
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── merged_evaluation.db        # SQLite database (auto-created)
└── .streamlit/                 # Streamlit configuration
    └── secrets.toml           # API keys (create manually)
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is provided as-is for internal use. Please ensure compliance with your organization's data handling policies.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review LangSmith API documentation
3. Check Streamlit documentation for UI-related issues

---

**Note**: This dashboard is designed to work with the existing `merged_evaluation.db` database. If you need to create a new database or modify the schema, update the `EvaluationDatabase` class accordingly.
