import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import subprocess
import sys
import time

# --- Configuration ---
PORTCONNECT_URL = "https://www.portconnect.co.nz/#/home"
USERNAME = "Calony.lam@ecly.co.nz"
PASSWORD = "Eclyltd88$"
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

def test_login_sequence(page, status_placeholder):
    """Test login sequence with detailed diagnostics"""
    try:
        status_placeholder.info("🔍 Starting login diagnostic...")
        
        # Step 1: Navigate to home page
        status_placeholder.info("1. Navigating to PortConnect home page...")
        page.goto(PORTCONNECT_URL, wait_until="load", timeout=30000)
        
        # Take screenshot of initial page
        page.screenshot(path="debug_home_page.png")
        status_placeholder.success("✅ Home page loaded")
        
        # Step 2: Check for login dropdown
        DROPDOWN_SELECTOR = "#navbar > ul.nav.navbar-top-links.navbar-right > li > a"
        status_placeholder.info("2. Looking for login dropdown...")
        
        try:
            dropdown = page.wait_for_selector(DROPDOWN_SELECTOR, state="visible", timeout=10000)
            status_placeholder.success("✅ Login dropdown found")
            dropdown.click()
            page.screenshot(path="debug_dropdown_opened.png")
        except PlaywrightTimeoutError:
            status_placeholder.error("❌ Login dropdown not found - page structure may have changed")
            # Check what's actually on the page
            page_content = page.content()
            if "login" in page_content.lower():
                status_placeholder.info("Found 'login' text in page content")
            if "sign in" in page_content.lower():
                status_placeholder.info("Found 'sign in' text in page content")
            return False
        
        # Step 3: Click sign in link
        SIGN_IN_LINK_SELECTOR = "#navbar > ul.nav.navbar-top-links.navbar-right > li > ul > li:nth-child(1) > a"
        status_placeholder.info("3. Clicking sign in link...")
        
        try:
            sign_in_link = page.wait_for_selector(SIGN_IN_LINK_SELECTOR, state="visible", timeout=10000)
            status_placeholder.success("✅ Sign in link found")
            sign_in_link.click()
            page.screenshot(path="debug_sign_in_clicked.png")
        except PlaywrightTimeoutError:
            status_placeholder.error("❌ Sign in link not found")
            return False
        
        # Step 4: Fill login form
        EMAIL_SELECTOR = "#signInName"
        PASSWORD_SELECTOR = "#password"
        SUBMIT_BUTTON_SELECTOR = "#next"
        
        status_placeholder.info("4. Filling login form...")
        
        try:
            email_field = page.wait_for_selector(EMAIL_SELECTOR, state="visible", timeout=15000)
            password_field = page.wait_for_selector(PASSWORD_SELECTOR, state="visible", timeout=10000)
            submit_button = page.wait_for_selector(SUBMIT_BUTTON_SELECTOR, state="visible", timeout=10000)
            
            status_placeholder.success("✅ All login form elements found")
            
            # Fill credentials
            email_field.fill(USERNAME)
            password_field.fill(PASSWORD)
            
            page.screenshot(path="debug_form_filled.png")
            status_placeholder.success("✅ Form filled with credentials")
            
        except PlaywrightTimeoutError as e:
            status_placeholder.error(f"❌ Login form elements not found: {e}")
            # Check if we're on the right page
            current_url = page.url
            status_placeholder.info(f"Current URL: {current_url}")
            return False
        
        # Step 5: Submit form
        status_placeholder.info("5. Submitting login form...")
        page.click(SUBMIT_BUTTON_SELECTOR)
        
        # Wait for redirect and check result
        status_placeholder.info("6. Waiting for login response...")
        
        try:
            # Wait for any of these possible outcomes
            page.wait_for_timeout(5000)  # Give it time to process
            
            current_url = page.url
            page_content = page.content()
            
            page.screenshot(path="debug_after_submit.png")
            
            if "dashboard" in current_url.lower() or "home" in current_url.lower():
                status_placeholder.success("✅ Login appears successful - redirected to dashboard/home")
                return True
            elif "error" in page_content.lower() or "invalid" in page_content.lower():
                status_placeholder.error("❌ Login failed - invalid credentials detected")
                if "username" in page_content.lower():
                    status_placeholder.info("Username field still present - login failed")
                return False
            elif "track and trace" in page_content.lower():
                status_placeholder.success("✅ Login successful - found Track and Trace menu")
                return True
            else:
                status_placeholder.warning("⚠️  Login result unclear - checking page content...")
                status_placeholder.info(f"Current URL: {current_url}")
                if "login" in current_url.lower():
                    status_placeholder.error("Still on login page - credentials may be invalid")
                    return False
                return True  # Assume success if we're not on login page
                
        except Exception as e:
            status_placeholder.error(f"❌ Error during login verification: {e}")
            return False
            
    except Exception as e:
        status_placeholder.error(f"❌ Unexpected error in login test: {e}")
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
                
                # Try to navigate to search page
                status_placeholder.info("7. Navigating to Track & Trace Search...")
                
                # Look for Track and Trace menu
                try:
                    track_trace_menu = page.locator('a:has-text("Track and Trace")')
                    track_trace_menu.wait_for(state="visible", timeout=10000)
                    track_trace_menu.click()
                    
                    # Look for search link
                    search_link = page.locator('a[href="/#/track-trace/search"]')
                    search_link.wait_for(state="visible", timeout=10000)
                    search_link.click()
                    
                    # Wait for search page
                    page.wait_for_selector(CONTAINER_INPUT_SELECTOR, state="visible", timeout=15000)
                    page.screenshot(path="debug_search_page.png")
                    
                    status_placeholder.success("✅ Successfully reached search page!")
                    return pd.DataFrame(), True
                    
                except PlaywrightTimeoutError as e:
                    status_placeholder.error(f"❌ Failed to reach search page: {e}")
                    return pd.DataFrame(), False
            else:
                status_placeholder.error("❌ Login test failed - please check credentials and page structure")
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


