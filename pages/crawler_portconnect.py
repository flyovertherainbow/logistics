import streamlit as st
from playwright.sync_api import sync_playwright
import subprocess
import sys

# --- CACHE THE PLAYWRIGHT INSTALLATION ---
# This function attempts to run the installation command ONCE 
# when the Streamlit app first loads.
@st.cache_resource(show_spinner="Setting up browser environment...")
def install_playwright():
    try:
        # Check if the browser is installed by attempting to run the install command
        # This is safe because playwright install is idempotent (it only downloads if needed)
        st.info("Attempting to run 'playwright install chromium'...")
        
        # Use subprocess to run the command in the shell
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            check=True # Raise error if command fails
        )
        st.success(f"Playwright install successful: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        st.error(f"Playwright installation failed. Stderr: {e.stderr.strip()}")
        st.error("Please ensure packages.txt contains 'chromium' and check file permissions.")
        return False
    except Exception as e:
         st.error(f"Unexpected error during Playwright setup: {e}")
         return False

def run_playwright_task(url):
    # Ensure installation runs and is cached
    if not install_playwright():
        return None

    st.info(f"Starting Playwright task for: {url}")
    
    try:
        # Use sync_playwright() to run the headless browser
        with sync_playwright() as p:
            # Launch the browser (Chromium is usually the safest bet)
            # Add timeout to handle potential slow launches
            browser = p.chromium.launch(headless=True, timeout=30000) 
            page = browser.new_page()
            
            page.goto(url)
            
            # ... Perform your scraping or automation actions here ...
            title = page.title() 
            
            browser.close()
            st.success(f"Playwright task succeeded. Page Title: {title}")
            return title
            
    except Exception as e:
        st.error(f"Playwright error: {e}")
        return None

# Example usage in Streamlit
if st.button("Run Playwright"):
    run_playwright_task("https://www.google.com")
