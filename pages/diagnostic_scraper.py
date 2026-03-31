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

def test_login_sequence(page, status_placeholder):
    """Stable login sequence using correct menu structure and credentials"""

    try:
        status_placeholder.info("🔍 Starting login diagnostic...")

        # -----------------------------
        # 1. Load Home Page
        # -----------------------------
        page.goto(PORTCONNECT_URL, wait_until="load", timeout=30000)
        page.screenshot(path="debug_home_page.png")
        status_placeholder.success("✅ Home page loaded")

        # -----------------------------
        # 2. Click 'Sign-in/Sign-up' dropdown
        # -----------------------------
        status_placeholder.info("2. Opening Sign-in/Sign-up menu...")

        # This is the top-right menu (NOT the login button yet)
        dropdown_link = page.get_by_role("link", name="Sign-in/Sign-up")   ### <-- UPDATED
        dropdown_link.click()                                              ### <-- UPDATED

        page.wait_for_timeout(500)
        page.screenshot(path="debug_dropdown_opened.png")

        # -----------------------------
        # 3. Click actual "Sign-in" item inside dropdown
        # -----------------------------
        status_placeholder.info("3. Clicking Sign-in inside dropdown...")

        login_item = page.get_by_role("link", name="Sign-in")              ### <-- UPDATED
        login_item.click()                                                 ### <-- UPDATED

        page.wait_for_load_state("networkidle")
        page.screenshot(path="debug_signin_clicked.png")

        status_placeholder.success("✅ Sign-in redirect triggered")

        # -----------------------------
        # 4. Wait for Microsoft Login Form
        # -----------------------------
        status_placeholder.info("4. Waiting for Microsoft B2C login page...")

        email_input = page.get_by_label("Email Address")                   ### <-- UPDATED
        password_input = page.get_by_label("Password")                     ### <-- UPDATED

        email_input.wait_for(state="visible", timeout=20000)
        password_input.wait_for(state="visible", timeout=20000)

        status_placeholder.success("✅ Login form detected")

        # -----------------------------
        # 5. Fill user credentials
        # -----------------------------
        status_placeholder.info("5. Filling credentials...")

        email_input.fill(USERNAME)                                         ### <-- UPDATED
        password_input.fill(PASSWORD)                                      ### <-- UPDATED

        page.screenshot(path="debug_form_filled.png")
        status_placeholder.success("✅ Credentials entered")

        # -----------------------------
        # 6. Submit the form
        # -----------------------------
        status_placeholder.info("6. Submitting login form...")

        page.get_by_role("button", name="Sign in").click()                 ### <-- UPDATED
        page.wait_for_load_state("networkidle")

        page.screenshot(path="debug_after_submit.png")

        # -----------------------------
        # 7. Validate login success
        # -----------------------------
        status_placeholder.info("7. Validating login result...")

        page.wait_for_timeout(3000)
        current_url = page.url.lower()

        if (
            "/#/home" in current_url
            or "track-trace" in current_url
            or "portconnect" in current_url
        ):                                                                  ### <-- UPDATED
            status_placeholder.success("🎉 Login successful!")
            return True

        status_placeholder.warning(f"⚠ Unexpected post-login URL: {current_url}")
        return False

    except Exception as e:
        status_placeholder.error(f"❌ Login error: {e}")
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
        import os
        def mtime_caption(path, base_caption):
            try:
                ts = os.path.getmtime(path)
                ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
                return f"{base_caption} • {ts_str}"
            except Exception:
                return base_caption
        col1, col2 = st.columns(2)
        with col1:
            with open("debug_home_page.png", "rb") as f:
                st.image(f.read(), caption=mtime_caption("debug_home_page.png", "Home Page"))
            with open("debug_form_filled.png", "rb") as f:
                st.image(f.read(), caption=mtime_caption("debug_form_filled.png", "Login Form Filled"))
        with col2:
            with open("debug_dropdown_opened.png", "rb") as f:
                st.image(f.read(), caption=mtime_caption("debug_dropdown_opened.png", "Dropdown Opened"))
            with open("debug_after_submit.png", "rb") as f:
                st.image(f.read(), caption=mtime_caption("debug_after_submit.png", "After Login Submit"))
    except FileNotFoundError:
        st.info("Screenshots not available yet - run the diagnostic first")
