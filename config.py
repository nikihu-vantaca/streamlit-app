import os

def get_api_key():
    """Get API key from Streamlit secrets or environment variable"""
    try:
        import streamlit as st
        # Try to get from Streamlit secrets first (matches your .streamlit/secrets.toml structure)
        return st.secrets["langsmith"]["api_key"]
    except ImportError:
        # Streamlit not available, fall back to environment variable
        return os.getenv("LANGSMITH_API_KEY", "")
    except:
        # Fallback to environment variable
        return os.getenv("LANGSMITH_API_KEY", "")

def get_api_key_standalone():
    """Get API key for standalone scripts (outside of Streamlit)"""
    # Try environment variable first
    api_key = os.getenv("LANGSMITH_API_KEY", "")
    if not api_key:
        # You can also read from a local file if needed
        try:
            with open(".env", "r") as f:
                for line in f:
                    if line.startswith("LANGSMITH_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
        except:
            pass
    return api_key
