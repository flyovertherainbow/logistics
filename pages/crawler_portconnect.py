import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import subprocess
import sys
import io
import time

# --- Configuration ---
PORTCONNECT_URL = "https://www.portconnect.co.nz/#/home"
USERNAME = "Calony.lam@ecly.co.nz"
PASSWORD = "Eclyltd88$"
CONTAINER_INPUT_SELECTOR = "#txContainerInput"

# --- Playwright Installation and Caching ---

@st.cache_resource(show_spinner="Setting up browser environment...")
def install_playwright():
    """Ensures Playwright browser binaries are installed and cached."""
    try:
        st.info("Attempting to run 'playwright install chromium'...")
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            check=True
        )
        st.success(f"Playwright install successful: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        st.error(f"Playwright installation failed. Stderr: {e.stderr.strip()}")
        st.error("Please ensure the environment supports running external commands.")
        return False
    except Exception as e:
        st.error(f"Unexpected error during Playwright setup: {e}")
        return False

# --- Core Scraping Logic ---

def run_crawler(container_list, status_placeholder):
    """
    Executes the Playwright script to log in, search, and scrape results.
    """
    if not install_playwright():
        return pd.DataFrame(), False

    status_placeholder.info(f"Starting crawler for {len(container_list)} containers...")
    
    # Format containers for input (newline separated)
    container_input_text = "\n".join(container_list)
    
    try:
        with sync_playwright() as p:
            # Launch the browser in headless mode
            browser = p.chromium.launch(headless=True, timeout=30000)
            page = browser.new_page()
            
            # --- 1. Navigation ---
            status_placeholder.info("1. Navigating to PortConnect...")
            page.goto(PORTCONNECT_URL, wait_until="load", timeout=20000)
            
            # --- 2. Login Sequence ---
            DROPDOWN_SELECTOR = "#navbar > ul.nav.navbar-top-links.navbar-right > li > a"
            SIGN_IN_LINK_SELECTOR = "#navbar > ul.nav.navbar-top-links.navbar-right > li > ul > li:nth-child(1) > a"
            EMAIL_SELECTOR = "#signInName"
            PASSWORD_SELECTOR = "#password"
            SUBMIT_BUTTON_SELECTOR = "#next"
            
            status_placeholder.info("2. Clicking Sign-in/Sign-up dropdown...")
            page.wait_for_selector(DROPDOWN_SELECTOR, state="visible", timeout=10000).click()

            status_placeholder.info("3. Clicking Sign-in link...")
            page.wait_for_selector(SIGN_IN_LINK_SELECTOR, state="visible", timeout=10000).click()
            
            status_placeholder.info("4. Filling login form...")
            # Wait for the login form to load (it might be a redirect or a modal)
            page.wait_for_selector(EMAIL_SELECTOR, state="visible", timeout=15000)
            
            page.fill(EMAIL_SELECTOR, USERNAME)
            page.fill(PASSWORD_SELECTOR, PASSWORD)
            
            status_placeholder.info("5. Submitting login...")
            page.click(SUBMIT_BUTTON_SELECTOR)
            
            # Wait for successful navigation to the post-login state (URL pattern)
            page.wait_for_url(PORTCONNECT_URL + "*", timeout=15000)
            
            # --- 3. Navigate to Search ---
            TRACK_TRACE_MENU = 'a:text("Track and Trace")' # Using text content for reliability
            SEARCH_LINK = 'a[href="/#/track-trace/search"]'
            
            status_placeholder.info("6. Navigating to Track and Trace -> Search...")
            # Click the dropdown menu
            page.click(TRACK_TRACE_MENU)
            # Click the search link inside the dropdown
            page.wait_for_selector(SEARCH_LINK, state="visible", timeout=10000).click()
            
            # Wait for the search page URL to load
            page.wait_for_url("*/track-trace/search", timeout=15000)
            
            # --- 4. Perform Search ---
            SEARCH_BUTTON_SELECTOR = 'div.search-item-button > button.btn.btn-primary:text("Search")'
            
            status_placeholder.info("7. Inputting container numbers and searching...")
            # Input container numbers
            page.wait_for_selector(CONTAINER_INPUT_SELECTOR, state="visible", timeout=10000).fill(container_input_text)
            
            # Click the search button
            page.click(SEARCH_BUTTON_SELECTOR)
            
            # --- 5. Scrape Results ---
            RESULTS_TABLE_BODY_SELECTOR = "#tblImport > tbody.ng-star-inserted"
            
            status_placeholder.info("8. Waiting for search results...")
            
            # Wait for the table body to contain results (or for a common load indicator to disappear)
            # We wait for the results table to appear. If it doesn't appear in time, we assume no results/error.
            try:
                page.wait_for_selector(RESULTS_TABLE_BODY_SELECTOR, state="attached", timeout=30000)
            except PlaywrightTimeoutError:
                status_placeholder.warning("Search results table not found or timed out. This may indicate an empty result set or a login/navigation error.")
                browser.close()
                return pd.DataFrame(), True # Return empty dataframe but successful navigation

            status_placeholder.info("9. Extracting data from results table...")
            
            # Scrape all rows
            rows = page.locator(f'{RESULTS_TABLE_BODY_SELECTOR} tr').all()
            scraped_data = []

            # Define headers (inferred from the table structure)
            headers = [
                'Details_Icon', 'Port', 'Container_Number', 'Flow', 
                'Vessel_Voyage', 'Date_Time_Hidden', 'Status_Location', 
                'Field_7_Hidden', 'Field_8_Hidden', 'Field_9_Hidden', 
                'Field_10_Hidden', 'Field_11_Hidden', 'Customs_Status_Icon', 
                'Field_13_Empty', 'Field_14_Hidden', 'Field_15_Hidden', 
                'Field_16_Hidden', 'Field_17_Hidden', 'Date_Time_Empty', 'Clock_Icon'
            ]
            
            for row in rows:
                cols = row.locator('td').all_text_contents()
                # Clean up extracted texts
                cleaned_cols = [c.strip().replace('\n', ' ') for c in cols]
                # Filter out the empty column at index 13 if it's always empty
                if len(cleaned_cols) == 20: # Match the inferred 20 columns
                    # The first column is usually an icon, skip it in clean data if it's not useful
                    scraped_data.append(cleaned_cols[1:]) # Start from Port
            
            browser.close()

            # Create DataFrame
            df = pd.DataFrame(scraped_data, columns=headers[1:])
            
            status_placeholder.success(f"Scraping complete! Found {len(df)} results.")
            return df, True
            
    except PlaywrightTimeoutError as e:
        status_placeholder.error(f"Playwright timed out during execution: {e}. Check selectors or network connection.")
        try:
            browser.close()
        except:
            pass
        return pd.DataFrame(), False
    except Exception as e:
        status_placeholder.error(f"An unexpected error occurred during crawling: {e}")
        st.exception(e)
        try:
            browser.close()
        except:
            pass
        return pd.DataFrame(), False

# --- Streamlit App UI ---

def main():
    st.set_page_config(page_title="PortConnect Container Crawler", layout="centered")
    st.title("🚢 PortConnect Container Tracker")
    st.markdown("Upload a text file containing container numbers (one per line) to automatically log in and retrieve tracking information.")

    # --- File Uploader ---
    uploaded_file = st.file_uploader(
        "Upload Container List (Text File)", 
        type=['txt'], 
        help="Drag and drop a .txt file. Each container number should be on a new line."
    )

    container_numbers = []
    if uploaded_file is not None:
        # To read file as string and split by lines
        try:
            string_data = uploaded_file.getvalue().decode("utf-8")
            # Remove empty lines and duplicates
            container_numbers = [
                c.strip() 
                for c in string_data.splitlines() 
                if c.strip()
            ]
            if container_numbers:
                st.success(f"Read {len(container_numbers)} unique container numbers.")
                st.expander("Preview Container Numbers").code("\n".join(container_numbers[:10]) + ("\n..." if len(container_numbers) > 10 else ""))
            else:
                st.warning("The file is empty or contains no valid container numbers.")
        except Exception as e:
            st.error(f"Error reading file: {e}")
            container_numbers = []

    # --- Execution Button ---
    status_placeholder = st.empty()
    
    if st.button("Start Search & Scrape", disabled=not container_numbers):
        if not container_numbers:
            status_placeholder.warning("Please upload a file with container numbers first.")
            return

        # Run the crawler logic
        df_results, success_status = run_crawler(container_numbers, status_placeholder)
        
        if success_status:
            if not df_results.empty:
                # --- Display Results ---
                st.subheader("✅ Scraped Results Preview")
                st.dataframe(df_results)
                
                # --- CSV Download Button ---
                csv_buffer = io.StringIO()
                df_results.to_csv(csv_buffer, index=False)
                st.download_button(
                    label="⬇️ Download Results as CSV",
                    data=csv_buffer.getvalue(),
                    file_name='portconnect_tracking_results.csv',
                    mime='text/csv',
                    key='download-csv'
                )
            else:
                st.info("The search completed but returned no results. Please check your container numbers and the website status.")

if __name__ == "__main__":
    main()
