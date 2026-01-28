import streamlit as st
import pandas as pd
import os
import sys
import subprocess
from scraper import process_csv

# --- Setup & Installation Check ---
# This ensures Playwright browsers are installed when deployed to Streamlit Cloud
def install_playwright():
    try:
        # Check if the browser is installed by trying to launch it?
        # A simpler way is to just run the install command with a flag or check a marker.
        # But running 'playwright install chromium' is idempotent and fast if already installed.
        with st.spinner("Ensuring browser engine is installed... (this may take a minute on first run)"):
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    except Exception as e:
        st.error(f"Failed to install browser engine: {e}")

# Run install check on module load (or we could do it on button press)
if "OPENED_ONCE" not in st.session_state:
    install_playwright()
    st.session_state["OPENED_ONCE"] = True

# --- App UI ---

st.set_page_config(page_title="Ads Transparency Scraper", page_icon="🔍")

st.title("🔍 Google Ads Transparency Scraper")
st.markdown("""
Upload a CSV file containing Google Ads Transparency URLs to scrape the "Approximately ... ads" count.
""")

st.info("Input CSV must have a column named **'url'** containing the links.")

uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    try:
        input_df = pd.read_csv(uploaded_file)
        st.write("Preview of input data:")
        st.dataframe(input_df.head())
        
        # Initialize session state for results if not present
        if "result_df" not in st.session_state:
            st.session_state.result_df = None
            
        start_button = st.button("Start Scraping")
        
        if start_button:
            # Create a placeholder for progress
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Temporary file paths
            input_path = "temp_input.csv"
            output_path = "temp_output.csv"
            
            # Save uploaded file temporarily
            input_df.to_csv(input_path, index=False)
            
            def progress_callback(current, total, message):
                progress = current / total if total > 0 else 0
                progress_bar.progress(progress)
                status_text.text(f"{message} ({current}/{total})")
            
            try:
                # Run the scraper
                with st.spinner("Scraping in progress..."):
                    process_csv(input_path, output_path, progress_callback=progress_callback)
                
                st.success("Scraping Completed!")
                
                # Load result and store in session state
                st.session_state.result_df = pd.read_csv(output_path)
                
            except Exception as e:
                st.error(f"An error occurred: {e}")
                
            finally:
                # Cleanup
                if os.path.exists(input_path):
                    os.remove(input_path)
                if os.path.exists(output_path):
                    os.remove(output_path)
        
        # Display results if they exist in session state
        if st.session_state.result_df is not None:
            st.write("### Results")
            st.dataframe(st.session_state.result_df)
            
            # CSV conversion
            csv = st.session_state.result_df.to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label="Download Results as CSV",
                data=csv,
                file_name='ads_count_results.csv',
                mime='text/csv',
            )

    except Exception as e:
        st.error(f"Error reading file: {e}")
