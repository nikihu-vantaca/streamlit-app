@echo off
echo Starting LangSmith Evaluation Dashboard...
echo.
echo Make sure you have:
echo 1. Python installed and in PATH
echo 2. Dependencies installed (pip install -r requirements.txt)
echo 3. LANGSMITH_API_KEY set or .streamlit/secrets.toml configured
echo.
echo Starting Streamlit...
streamlit run app.py
pause
