import streamlit as st
from playwright.sync_api import sync_playwright

def run_playwright_task(url):
    st.info(f"Starting Playwright task for: {url}")
    
    try:
        # Use sync_playwright() to run the headless browser
        with sync_playwright() as p:
            # Launch the browser (Chromium is usually the safest bet)
            browser = p.chromium.launch(headless=True)
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
