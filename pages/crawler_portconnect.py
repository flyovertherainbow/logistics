import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import subprocess
import sys
import time

# --- Configuration ---
PORTCONNECT_URL = "https://www.portconnect.co.nz/#/home"
USERNAME = "importdoc@ecly.co.nz"
PASSWORD = "Import261!!"
CONTAINER_INPUT_SELECTOR = "#txContainerInput"

# --- Diagnostic Mode ---
IS_STREAMLIT_CLOUD = st.runtime.exists() if hasattr(st, 'runtime') else False

@st.cache_resource(show_spinner="Setting up browser environment...")
def install_playwright():
    """Ensures Playwright browser binaries are installed and cached."""
    try:
        if IS_STREAMLIT_CLOUD:
            st.info("Detected Streamlit Cloud environment - using lightweight setup...")
            try:
                result = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], 
                             capture_output=True, text=True, check=True, timeout=120)
                st.success("Playwright installed successfully for cloud environment")
                st.text(f"Install output: {result.stdout}")
                return True
            except subprocess.CalledProcessError as e:
                st.warning(f"Standard install failed: {e.stderr}")
                st.warning("Trying minimal install...")
                result = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], 
                             capture_output=True, text=True, check=True, timeout=120)
                st.success("Minimal install successful")
                st.text(f"Minimal install output: {result.stdout}")
                return True
        else:
            st.info("Attempting to run 'playwright install chromium'...")
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                text=True,
                check=True
            )
            st.success(f"Playwright install successful: {result.stdout.strip()}")
            return True
    except Exception as e:
        st.error(f"Playwright installation failed: {e}")
        return False

def test_login_sequence(page, status):
    """Diagnostic login tester based on your working automate_login() function"""

    try:
        status.info("1. Navigating to PortConnect...")
        page.goto(PORTCONNECT_URL, wait_until="load")

        status.info("2. Clicking Sign-in/Sign-up dropdown...")
        page.click("#navbar > ul.nav.navbar-top-links.navbar-right > li > a")

        status.info("3. Clicking Sign-in link...")
        page.click("#navbar > ul.nav.navbar-top-links.navbar-right > li > ul > li:nth-child(1) > a")

        status.info("4. Waiting for Azure B2C login page...")
        page.wait_for_selector("#signInName", timeout=15000)

        status.info("5. Entering username & password...")
        page.fill("#signInName", USERNAME)
        page.fill("#password", PASSWORD)

        status.info("6. Submitting login form...")
        page.click("#next")
        page.wait_for_timeout(6000)

        # Log current state
        current_url = page.url
        page_title = page.title()
        page_body = page.inner_text("body")[:1000]

        status.write(f"🔍 URL after login: {current_url}")
        status.write(f"📄 Page title: {page_title}")
        status.text_area("🔍 Page content snapshot:", page_body)

        # Handle "Keep me signed in"
        if page.locator("text=Keep me signed in").is_visible():
            status.info("🔄 'Keep me signed in' detected — clicking Yes...")
            page.click("text=Yes")
            page.wait_for_timeout(3000)

        # Detect login success/failure
        if page.locator("text=Incorrect username or password").is_visible():
            status.error("❌ Login failed: Incorrect username or password.")
            return False

        # Successful redirect
        if "portconnect.co.nz" in current_url:
            status.success("✅ Login successful — redirected to PortConnect portal.")
            return True

        # Still stuck in Azure B2C
        if "b2clogin.com" in current_url:
            status.warning("⚠️ Still on Azure B2C login page — login may not have completed.")
            return False

        status.warning("⚠️ Login result unclear — unexpected page state.")
        return False

    except PlaywrightTimeoutError:
        status.error("⏱️ Timeout occurred during login test.")
        return False

    except Exception as e:
        status.error(f"🚨 Unexpected error: {e}")
        return False

def run_diagnostic_scraper(container_list, status_placeholder):
    """Run diagnostic version of scraper"""
    if not install_playwright():
        return pd.DataFrame(), False

    try:
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(
                headless=True,  # Always headless for diagnostic
                args=['--no-sandbox', '--disable-dev-shm-usage'] if IS_STREAMLIT_CLOUD else []
            )
            page = browser.new_page()
            
            # Test login
            login_success = test_login_sequence(page, status_placeholder)
            
            if login_success:
                status_placeholder.success("🎉 Login test passed!")
                
                # -------------------------------
                # NEW SEARCH PAGE LOGIC STARTS HERE
                # -------------------------------
                status_placeholder.info("7. Navigating to Track & Trace Search...")

                # Navigate to Track & Trace main menu
                page.locator('a[href="/#/track-trace"]').click()                 ### <-- UPDATED
                page.wait_for_timeout(1000)                                     ### <-- UPDATED

                # Navigate to Search page
                page.locator('a[href="/#/track-trace/search"]').click()         ### <-- UPDATED

                # Wait for container input box to appear
                container_box = page.locator("#txContainerInput")               ### <-- UPDATED
                container_box.wait_for(state="visible", timeout=15000)          ### <-- UPDATED

                page.screenshot(path="debug_search_page.png")                   ### <-- UPDATED
                status_placeholder.success("✅ Search page loaded")             ### <-- UPDATED

                # Diagnostic: test entering only the first container
                if container_list:
                    container_number = container_list[0]
                    status_placeholder.info(f"🔍 Entering container: {container_number}")  ### <-- UPDATED

                    container_box.fill(container_number)                       ### <-- UPDATED

                    # Click Search button (new stable selector)
                    page.get_by_role("button", name="Search").click()          ### <-- UPDATED

                    page.wait_for_timeout(4000)                                ### <-- UPDATED
                    page.screenshot(path="debug_after_search.png")             ### <-- UPDATED

                return pd.DataFrame(), True                                     ### <-- UPDATED

                # -------------------------------
                # END OF UPDATED SECTION
                # -------------------------------

            else:
                status_placeholder.error(
                    "❌ Login test failed - please check credentials and page structure"
                )
                return pd.DataFrame(), False
                
    except Exception as e:
        status_placeholder.error(f"❌ Browser error: {e}")
        return pd.DataFrame(), False


# --- Streamlit UI ---
st.title("🔍 PortConnect Scraper Diagnostic")
st.markdown("This diagnostic tool will help identify login and scraping issues.")

# Input containers
container_input = st.text_area("Container Numbers (one per line):", height=100)
container_list = [c.strip() for c in container_input.split('\n') if c.strip()]

# Status placeholder
status_placeholder = st.empty()

# Run diagnostic button
if st.button("Run Diagnostic Test"):
    if container_list:
        df, success = run_diagnostic_scraper(container_list, status_placeholder)
        if success:
            st.success("🎉 Diagnostic completed successfully!")
            st.balloons()
        else:
            st.error("❌ Diagnostic failed - check the status messages above")
    else:
        st.warning("Please enter at least one container number")

# Display screenshots if available
st.markdown("---")
st.markdown("### 📸 Debug Screenshots")
if st.button("Refresh Screenshots"):
    try:
        col1, col2 = st.columns(2)
        with col1:
            st.image("debug_home_page.png", caption="Home Page")
            st.image("debug_form_filled.png", caption="Login Form Filled")
        with col2:
            st.image("debug_dropdown_opened.png", caption="Dropdown Opened")
            st.image("debug_after_submit.png", caption="After Login Submit")
    except:
        st.info("Screenshots not available yet - run the diagnostic first")


