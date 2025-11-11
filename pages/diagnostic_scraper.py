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
        page.goto(PORTCONNECT_URL, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass
        
        # Take screenshot of initial page
        page.screenshot(path="debug_home_page.png")
        status_placeholder.success("✅ Home page loaded")
        
        # --- NEW: Handle cookie consent banner if present ---
        try:
            cookie_button = page.locator(
                'button#onetrust-accept-btn-handler, button:has-text("Accept"), button:has-text("I agree"), button:has-text("OK"), button:has-text("Got it")'
            ).first
            if cookie_button and cookie_button.is_visible(timeout=3000):
                cookie_button.click()
                status_placeholder.info("🍪 Cookie banner accepted")
                page.screenshot(path="debug_cookies_accepted.png")
        except:
            pass
        
        # Step 2: Find and click sign in / login link using robust selectors
        status_placeholder.info("2. Looking for sign in / login link...")
        try:
            sign_in_candidate = page.locator(
                'a:has-text("Sign in"), a:has-text("Sign In"), a:has-text("Login"), button:has-text("Sign in"), button:has-text("Login")'
            ).first
            sign_in_candidate.wait_for(state="visible", timeout=10000)
            status_placeholder.success("✅ Sign in / Login link found")
            sign_in_candidate.click()
            page.screenshot(path="debug_sign_in_clicked.png")
        except PlaywrightTimeoutError:
            status_placeholder.error("❌ Sign in / Login link not found - trying navbar fallback")
            # Fallback to previous navbar selectors
            DROPDOWN_SELECTOR = "#navbar > ul.nav.navbar-top-links.navbar-right > li > a"
            SIGN_IN_LINK_SELECTOR = "#navbar > ul.nav.navbar-top-links.navbar-right > li > ul > li:nth-child(1) > a"
            try:
                dropdown = page.wait_for_selector(DROPDOWN_SELECTOR, state="visible", timeout=8000)
                dropdown.click()
                page.screenshot(path="debug_dropdown_opened.png")
                sign_in_link = page.wait_for_selector(SIGN_IN_LINK_SELECTOR, state="visible", timeout=8000)
                sign_in_link.click()
                page.screenshot(path="debug_sign_in_clicked_navbar.png")
            except PlaywrightTimeoutError:
                status_placeholder.error("❌ Navbar fallback failed - page structure likely changed")
                status_placeholder.info(f"Current URL: {page.url}")
                page.screenshot(path="debug_signin_not_found.png")
                return False
        
        # Step 4: Fill login form
        EMAIL_SELECTOR = "#signInName"
        PASSWORD_SELECTOR = "#password"
        SUBMIT_BUTTON_SELECTOR = "#next"
        
        status_placeholder.info("4. Filling login form...")
        
        try:
            email_field = page.wait_for_selector(EMAIL_SELECTOR, state="visible", timeout=20000)
            password_field = page.wait_for_selector(PASSWORD_SELECTOR, state="visible", timeout=15000)
            submit_button = page.wait_for_selector(SUBMIT_BUTTON_SELECTOR, state="visible", timeout=15000)
            
            status_placeholder.success("✅ All login form elements found")
            
            # Fill credentials
            email_field.fill(USERNAME)
            password_field.fill(PASSWORD)
            
            page.screenshot(path="debug_form_filled.png")
            status_placeholder.success("✅ Form filled with credentials")
            
        except PlaywrightTimeoutError as e:
            status_placeholder.error(f"❌ Login form elements not found: {e}")
            # Check if alternative field IDs exist
            try:
                alt_email = page.locator('input[name="email"], input[name="username"], input[type="email"]').first
                alt_password = page.locator('input[type="password"]').first
                if alt_email and alt_password and alt_email.is_visible(timeout=3000) and alt_password.is_visible(timeout=3000):
                    alt_email.fill(USERNAME)
                    alt_password.fill(PASSWORD)
                    page.screenshot(path="debug_form_filled_alt.png")
                    status_placeholder.success("✅ Filled alternative login fields")
                else:
                    current_url = page.url
                    status_placeholder.info(f"Current URL: {current_url}")
                    return False
            except:
                current_url = page.url
                status_placeholder.info(f"Current URL: {current_url}")
                return False
        
        # Step 5: Submit form
        status_placeholder.info("5. Submitting login form...")
        page.click(SUBMIT_BUTTON_SELECTOR)
        
        # Wait for redirect and check result
        status_placeholder.info("6. Waiting for login response...")
        
        try:
            page.wait_for_timeout(5000)  # Give it time to process
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except:
                pass
            
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
            # --- NEW: Create context with a standard User-Agent ---
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
            )
            page = context.new_page()
            
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
                    context.close()
                    browser.close()
                    return pd.DataFrame(), True
                    
                except PlaywrightTimeoutError as e:
                    status_placeholder.error(f"❌ Failed to reach search page: {e}")
                    context.close()
                    browser.close()
                    return pd.DataFrame(), False
            else:
                status_placeholder.error("❌ Login test failed - please check credentials and page structure")
                context.close()
                browser.close()
                return pd.DataFrame(), False
                
    except Exception as e:
        status_placeholder.error(f"❌ Browser error: {e}")
        try:
            context.close()
            browser.close()
        except:
            pass
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
