import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import subprocess
import sys
import io
import time
import re

# --- Configuration ---
PORTCONNECT_URL = "https://www.portconnect.co.nz/#/home"
USERNAME = "Calony.lam@ecly.co.nz"
PASSWORD = "Eclyltd88$"
# This is the single source of truth for the container input selector
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

#login
def execute_login_sequence(page, USERNAME, PASSWORD, PORTCONNECT_URL, status_placeholder):
    """
    Performs the login and navigates to the Track & Trace Search page.
    Uses element waiting instead of strict networkidle for better resilience.
    """
    # --- 1. Define Selectors ---
    DROPDOWN_SELECTOR = "#navbar > ul.nav.navbar-top-links.navbar-right > li > a"
    SIGN_IN_LINK_SELECTOR = "#navbar > ul.nav.navbar-top-links.navbar-right > li > ul > li:nth-child(1) > a"
    EMAIL_SELECTOR = "#signInName"
    PASSWORD_SELECTOR = "#password"
    SUBMIT_BUTTON_SELECTOR = "#next"
    
    # --- Critical Post-Login/Dashboard Selector ---
    # NEW STRATEGY: Using a highly specific XPath selector based on your suggestion, 
    # extended to target the actual anchor tag (a) for clicking.
    TRACK_AND_TRACE_MENU_LINK_LOCATOR = 'xpath=//*[@id="pc-menu"]/li[2]/a'
    
    # Track and Trace Dropdown Link (Main Menu Link) - This is now the robust locator string
    TRACK_AND_TRACE_MENU_LINK = TRACK_AND_TRACE_MENU_LINK_LOCATOR 
    
    # Search Link (Nested inside the Track and Trace Dropdown)
    # This selector remains reliable as it uses the unique destination URL.
    TRACK_AND_TRACE_SEARCH_LINK = "a[href='/#/track-trace/search']"

    try:
        # --- 2. Click Dropdown & Sign-in Link ---
        status_placeholder.info("1. Initiating Sign-in process...")
        page.wait_for_selector(DROPDOWN_SELECTOR, state="visible", timeout=10000).click()
        page.wait_for_selector(SIGN_IN_LINK_SELECTOR, state="visible", timeout=10000).click()

        # --- 3. Fill and Submit Login Form (B2C Redirect) ---
        status_placeholder.info("2. Filling and submitting B2C login form...")
        page.wait_for_selector(EMAIL_SELECTOR, state="visible", timeout=15000)
        page.fill(EMAIL_SELECTOR, USERNAME)
        page.fill(PASSWORD_SELECTOR, PASSWORD)
        
        # Click the submit button
        page.click(SUBMIT_BUTTON_SELECTOR)
        
        # --- 4. Post-Login Wait (Simplified) ---
        # We will now ONLY wait for the dashboard to load.
        # Per your request, logic for "Stay signed in" has been removed.
        status_placeholder.info("3. Waiting for authenticated dashboard to load...")
        
        # We look for any link with "Track and Trace" text
        dashboard_selector = 'a:has-text("Track and Trace")' 
        dashboard_locator = page.locator(dashboard_selector)

        try:
            dashboard_locator.wait_for(state="visible", timeout=45000)
        except PlaywrightTimeoutError:
            status_placeholder.error("Timeout after login: Dashboard link ('Track and Trace') did not appear.")
            status_placeholder.error("This may be due to a 'Stay Signed In' prompt (which this script now ignores) or incorrect credentials.")
            return False
            
        status_placeholder.success("Signed in successfully!")

        # --- 5. Navigate to Search ---
        status_placeholder.info("4. Navigating to Track and Trace Search page...")
        
        # 5a. Click the 'Track and Trace' link to open the dropdown
        # We now use the robust dashboard_locator we found earlier
        dashboard_locator.click(timeout=15000)

        # 5b. Wait for the 'Search' link to appear and click it
        status_placeholder.info("Clicking Search link...")
        page.wait_for_selector(TRACK_AND_TRACE_SEARCH_LINK, state="visible", timeout=10000)

        # Click the search link and wait for navigation to complete
        with page.expect_navigation(timeout=30000):
            page.click(TRACK_AND_TRACE_SEARCH_LINK)
        
        # Wait for the specific container input field to confirm the page has loaded
        page.wait_for_selector(CONTAINER_INPUT_SELECTOR, state="visible", timeout=30000)

        status_placeholder.success("Navigation to Track & Trace Search confirmed!")
        return True

    except PlaywrightTimeoutError as e:
        status_placeholder.error(f"Login or Navigation Timeout Error: {e}. Check credentials or increase the timeout limit.")
        return False
    except Exception as e:
        status_placeholder.error(f"An unexpected error occurred during login sequence: {e}")
        return False


# --- Core Scraping Logic ---

def run_crawler(container_list, status_placeholder):
    """
    Executes the Playwright script to log in, search, and scrape results.
    
    The navigation to the 'Track and Trace Search' page is handled internally 
    by the execute_login_sequence function, removing duplication.
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
            page.goto(PORTCONNECT_URL, wait_until="load", timeout=30000)
            
            # ---- 2. Login and Navigation to Search ----
            # This function logs in AND navigates to the search page.
            if not execute_login_sequence(page, USERNAME, PASSWORD, PORTCONNECT_URL, status_placeholder):
                browser.close()
                return pd.DataFrame(), False

            # --- 3. Perform Search ---
            SEARCH_BUTTON_SELECTOR = 'div.search-item-button > button.btn.btn-primary:text("Search")'
            
            status_placeholder.info("8. Inputting container numbers and searching...")
            
            # Input container numbers.
            page.wait_for_selector(CONTAINER_INPUT_SELECTOR, state="visible", timeout=10000).fill(container_input_text)
            
            # --- NEW DEBUGGING STEP: Verify input field content ---
            try:
                current_input = page.locator(CONTAINER_INPUT_SELECTOR).input_value()
                display_input_list = current_input.split('\n')
                
                if len(display_input_list) > 5:
                    display_summary = ", ".join(display_input_list[:5]) + "..."
                    status_placeholder.info(f"Input verification: Successfully entered {len(display_input_list)} containers (first 5: {display_summary}).")
                else:
                    display_summary = ", ".join(display_input_list)
                    status_placeholder.info(f"Input verification: Successfully entered all {len(display_input_list)} containers: {display_summary}.")

            except Exception as debug_e:
                status_placeholder.warning(f"Could not verify input value: {debug_e}")
            # --- END DEBUGGING STEP ---
            
            # Click the search button
            page.click(SEARCH_BUTTON_SELECTOR)
            
            # --- 4. Scrape Results ---
            RESULTS_TABLE_BODY_SELECTOR = "#tblImport > tbody.ng-star-inserted"
            
            # We will wait for the FIRST ROW (tr) inside the body.
            RESULTS_FIRST_ROW_SELECTOR = f"{RESULTS_TABLE_BODY_SELECTOR} tr"
            
            status_placeholder.info("9. Waiting for search results (waiting for first row)...")
            
            # Wait for the table body to appear after the search submission
            try:
                # Wait until the first table row is visible (data has rendered)
                page.wait_for_selector(RESULTS_FIRST_ROW_SELECTOR, state="visible", timeout=45000)
                
                # Wait an extra second to ensure all data rendering is complete and stable before scraping.
                page.wait_for_timeout(1000) 
                
            except PlaywrightTimeoutError:
                status_placeholder.error("Timeout while waiting for search results. The page structure may have changed, or the search failed to execute.")
                browser.close()
                return pd.DataFrame(), False 

            status_placeholder.info("10. Extracting data from results table...")
            
            # Scrape all rows
            rows = page.locator(f'{RESULTS_TABLE_BODY_SELECTOR} tr').all()
            scraped_data = []

            # Define headers based on the HTML provided by the user (matching both "Not Found" and "Found" structure)
            headers = [
                'Detail_Icon', 'Port', 'Container', 'Category', 
                'Vessel_Visit', 'VesselETA/ATA_Hidden', 'Location', 
                'Status_Hidden', 'MTReturn_Hidden', 'ISO_Hidden', 
                'Weight(Kg)_Hidden', 'SecurityCheck_Hidden', 'Cleared', 
                'Impediments', 'ImpedimentGroups_Hidden', 'Temp_Hidden', 
                'Hazard_Hidden', 'OverSize_Hidden', 'Last_FreeTime', 'History_Icon'
            ]
            
            for row in rows:
                cols = row.locator('td').all_text_contents()
                # Clean up extracted texts
                # The Impediments column (index 13) contains divs, all_text_contents should flatten it.
                cleaned_cols = [c.strip().replace('\n', ' ') for c in cols]
                
                # We expect 20 columns (0-19). Skip the first column (Detail Icon) for the final DataFrame.
                if len(cleaned_cols) == 20: 
                    scraped_data.append(cleaned_cols[1:]) # Start from Port
            
            browser.close()

            # Create DataFrame
            df = pd.DataFrame(scraped_data, columns=headers[1:])
            
            status_placeholder.success(f"Scraping complete! Found {len(df)} results.")
            return df, True
            
    except PlaywrightTimeoutError as e:
        status_placeholder.error(f"Playwright timed out during execution: {e}. A critical step exceeded the maximum wait time.")
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
                st.info("The search completed but returned no results. This is expected if all containers were marked as 'Not Found'.")

if __name__ == "__main__":
    main()
