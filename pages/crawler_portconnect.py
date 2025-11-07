import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import subprocess
import sys
import io
import time
import re

# Try to import Streamlit, but make it optional
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False
    # Create a mock Streamlit module for compatibility
    class MockStreamlit:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    st = MockStreamlit()

# --- Configuration ---
PORTCONNECT_URL = "https://www.portconnect.co.nz/#/home"
USERNAME = "Calony.lam@ecly.co.nz"
PASSWORD = "Eclyltd88$"
CONTAINER_INPUT_SELECTOR = "#txContainerInput"

# Search timeout configuration (in seconds)
SEARCH_TIMEOUT = 10  # Reduced for faster response while maintaining reliability

# Detect if running on Streamlit Cloud (only if Streamlit is available)
IS_STREAMLIT_CLOUD = st.runtime.exists() if HAS_STREAMLIT and hasattr(st, 'runtime') else False

# --- Playwright Installation and Caching ---

def install_playwright():
    """Ensures Playwright browser binaries are installed and cached."""
    try:
        # For Streamlit Cloud, we need special handling
        if IS_STREAMLIT_CLOUD:
            if HAS_STREAMLIT:
                st.info("Detected Streamlit Cloud environment - using lightweight setup...")
            # Try to install with reduced dependencies
            try:
                subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], 
                             capture_output=True, text=True, check=True, timeout=120)
                if HAS_STREAMLIT:
                    st.success("Playwright installed successfully for cloud environment")
                return True
            except subprocess.CalledProcessError as e:
                if HAS_STREAMLIT:
                    st.warning(f"Standard install failed: {e.stderr}")
                    st.warning("Trying minimal install...")
                try:
                    result = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], 
                                 capture_output=True, text=True, check=True, timeout=120)
                    if HAS_STREAMLIT:
                        st.success("Minimal install successful")
                        st.text(f"Minimal install output: {result.stdout}")
                    return True
                except subprocess.CalledProcessError as e2:
                    if HAS_STREAMLIT:
                        st.error(f"Minimal install also failed: {e2.stderr}")
                        st.error("Playwright installation failed completely")
                    return False
        
        if HAS_STREAMLIT:
            st.info("Attempting to run 'playwright install chromium'...")
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            check=True
        )
        if HAS_STREAMLIT:
            st.success(f"Playwright install successful: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        if HAS_STREAMLIT:
            st.error(f"Playwright installation failed. Stderr: {e.stderr.strip()}")
            st.error("Please ensure the environment supports running external commands.")
        else:
            print(f"Playwright installation failed. Stderr: {e.stderr.strip()}")
            print("Please ensure the environment supports running external commands.")
        return False
    except Exception as e:
        if HAS_STREAMLIT:
            st.error(f"Unexpected error during Playwright setup: {e}")
        else:
            print(f"Unexpected error during Playwright setup: {e}")
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
            status_placeholder.error("This may be due to:")
            status_placeholder.error("1. Invalid credentials (check username/password)")
            status_placeholder.error("2. Account locked or suspended")
            status_placeholder.error("3. 'Stay Signed In' prompt (which this script now ignores)")
            status_placeholder.error("4. Website structure changes")
            
            # Try to capture more diagnostic info
            try:
                current_url = page.url
                page_content = page.content()
                status_placeholder.info(f"Current URL: {current_url}")
                
                if "login" in current_url.lower():
                    status_placeholder.error("Still on login page - credentials likely invalid")
                if "error" in page_content.lower():
                    status_placeholder.error("Error message detected on page")
                    
                # Save diagnostic screenshot
                page.screenshot(path="login_failure_diagnostic.png")
                
            except Exception as diag_e:
                status_placeholder.warning(f"Could not capture diagnostic info: {diag_e}")
                
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

def run_crawler(container_list, status_placeholder, debug_mode=False):
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
    
    # --- Container Summary for Error Reporting (Not displayed on Playwright Timeout) ---
    if len(container_list) > 5:
        container_summary = ", ".join(container_list[:5]) + f", and {len(container_list) - 5} more."
    elif container_list:
        container_summary = ", ".join(container_list)
    else:
        container_summary = "None."
    # ------------------------------------------------------------------------------------
    
    try:
        with sync_playwright() as p:
            # Launch browser with cloud-optimized settings
            if IS_STREAMLIT_CLOUD:
                # Streamlit Cloud requires specific browser arguments
                browser = p.chromium.launch(
                    headless=True,  # Must be headless on cloud
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor'
                    ],
                    timeout=60000  # Longer timeout for cloud
                )
            else:
                # Local development settings
                browser = p.chromium.launch(headless=not debug_mode, timeout=30000)
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
                    display_preview = ", ".join(display_input_list[:5]) + "..."
                    status_placeholder.info(f"Input verification: Successfully entered {len(display_input_list)} containers (first 5: {display_preview}).")
                else:
                    display_preview = ", ".join(display_input_list)
                    status_placeholder.info(f"Input verification: Successfully entered all {len(display_input_list)} containers: {display_preview}.")

            except Exception as debug_e:
                status_placeholder.warning(f"Could not verify input value: {debug_e}")
            # --- END DEBUGGING STEP ---
            
            # Click the search button
            page.click(SEARCH_BUTTON_SELECTOR)
            
            # --- 4. Scrape Results (Simplified and Improved) ---
            # Updated selectors based on actual HTML structure
            RESULTS_TABLE_BODY_SELECTOR = "tbody.ng-star-inserted"
            RESULTS_FIRST_ROW_SELECTOR = f"{RESULTS_TABLE_BODY_SELECTOR} tr"
            
            status_placeholder.info(f"9. Waiting for search results (timeout: {SEARCH_TIMEOUT}s)...")
            
            try:
                # Simplified approach: Wait for either results OR no results message
                # Give the search time to process (configurable timeout)
                status_placeholder.info(f"   -> Waiting {SEARCH_TIMEOUT} seconds for search to complete...")
                page.wait_for_timeout(SEARCH_TIMEOUT * 1000)  # Convert to milliseconds
                
                # Check multiple possible outcomes
                results_found = False
                no_results_found = False
                
                # Strategy 1: Check if results table appears
                try:
                    if page.locator(RESULTS_FIRST_ROW_SELECTOR).first.is_visible(timeout=5000):
                        results_found = True
                        status_placeholder.info("   -> Results table detected!")
                        
                        # Additional check: Look for our specific container
                        for container in container_list:
                            if page.locator(f"td:has-text('{container}')").count() > 0:
                                status_placeholder.info(f"   -> Found container: {container}")
                                break
                except:
                    pass
                
                # Strategy 2: If no results, check for "no results" messages
                if not results_found:
                    no_results_texts = ["No results found", "Not Found", "No data", "No containers found"]
                    for text in no_results_texts:
                        try:
                            if page.locator(f"text='{text}'").is_visible(timeout=2000):
                                no_results_found = True
                                status_placeholder.info(f"   -> '{text}' message detected")
                                break
                        except:
                            continue
                
                # Strategy 3: Check if table exists (even if empty)
                if not results_found and not no_results_found:
                    try:
                        table_exists = page.locator(RESULTS_TABLE_BODY_SELECTOR).count() > 0
                        if table_exists:
                            row_count = page.locator(f'{RESULTS_TABLE_BODY_SELECTOR} tr').count()
                            status_placeholder.info(f"   -> Table found with {row_count} rows")
                            if row_count > 0:
                                results_found = True
                            else:
                                no_results_found = True
                        else:
                            status_placeholder.warning("   -> No results table found")
                    except:
                        pass
                
                # Strategy 4: Check page content for clues
                if not results_found and not no_results_found:
                    try:
                        page_content = page.text_content()
                        if "no results" in page_content.lower() or "not found" in page_content.lower():
                            no_results_found = True
                            status_placeholder.info("   -> 'No results' detected in page content")
                        elif "container" in page_content.lower():
                            # Page mentions containers but we can't find results - take screenshot
                            page.screenshot(path='debug_search_results.png', full_page=True)
                            status_placeholder.warning("   -> Page mentions containers but results unclear - screenshot saved")
                    except:
                        pass
                
                # Final determination
                if results_found:
                    status_placeholder.success("   -> Search completed successfully!")
                elif no_results_found:
                    status_placeholder.info("   -> Search completed: No results found for these containers")
                else:
                    # Take screenshot for debugging
                    page.screenshot(path='debug_search_timeout.png', full_page=True)
                    status_placeholder.warning("   -> Search results unclear - screenshot saved for debugging")
                    # Don't treat this as fatal - continue with empty results
                    
                # Small delay for any final rendering
                page.wait_for_timeout(1000)
                
            except Exception as search_e:
                status_placeholder.error(f"Error during search: {search_e}")
                # Take screenshot and continue with empty results
                try:
                    page.screenshot(path='debug_search_error.png', full_page=True)
                except:
                    pass 

            status_placeholder.info("10. Extracting data from results table...")
            
            # Debug: Check what we actually find on the page
            try:
                # Check if our table selector finds anything
                table_count = page.locator(RESULTS_TABLE_BODY_SELECTOR).count()
                status_placeholder.info(f"   -> Found {table_count} results tables")
                
                # Check for any table with our container
                container_found = False
                for container in container_list:
                    if page.locator(f"td:has-text('{container}')").count() > 0:
                        container_found = True
                        status_placeholder.info(f"   -> Container '{container}' found in page")
                        break
                
                if not container_found:
                    status_placeholder.warning(f"   -> No containers found in page content")
                    
            except Exception as debug_e:
                status_placeholder.warning(f"   -> Debug check failed: {debug_e}")
            
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
                cols = row.locator('td').all()
                if len(cols) == 20:  # Only process complete rows
                    row_data = []
                    for i, col in enumerate(cols):
                        # Handle special cases for columns with complex content
                        if i == 13:  # Impediments column with divs
                            impediments = col.locator('div').all_text_contents()
                            row_data.append(' '.join(impediments).strip() if impediments else '')
                        elif i == 12:  # Cleared column with icons
                            cleared_text = col.text_content().strip()
                            # Check for cross icon (not cleared)
                            if col.locator('.fa-times').count() > 0:
                                row_data.append('No')
                            else:
                                row_data.append(cleared_text or 'Yes')
                        else:
                            row_data.append(col.text_content().strip())
                    
                    # Skip the first column (Detail Icon) for the final DataFrame
                    scraped_data.append(row_data[1:])
            
            browser.close()

            # Create DataFrame
            df = pd.DataFrame(scraped_data, columns=headers[1:])
            
            status_placeholder.success(f"Scraping complete! Found {len(df)} results.")
            return df, True
            
    except PlaywrightTimeoutError as e:
        # This is the catch-all for any other Playwright timeout (e.g., during login/navigation)
        status_placeholder.error(f"CRITICAL TIMEOUT DURING CRAWLER EXECUTION: {e}")
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

    # --- Debug Mode Option ---
    debug_mode = st.checkbox("Enable Debug Mode (shows browser window)", value=False,
                            help="Enable this to see the browser window for troubleshooting")
    
    # --- Execution Button ---
    status_placeholder = st.empty()
    
    if st.button("Start Search & Scrape", disabled=not container_numbers):
        if not container_numbers:
            status_placeholder.warning("Please upload a file with container numbers first.")
            return

        # Run the crawler logic
        df_results, success_status = run_crawler(container_numbers, status_placeholder, debug_mode)
        
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


