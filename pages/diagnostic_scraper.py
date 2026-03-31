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
    """Diagnostic login tester — NO Search button clicks in this function"""

    try:
        status.info("1. Navigating to PortConnect...")
        page.goto(PORTCONNECT_URL, wait_until="load")

        status.info("2. Clicking Sign-in/Sign-up dropdown...")
        page.click("#navbar > ul.nav.navbar-top-links.navbar-right > li > a")

        status.info("3. Clicking Sign-in link...")
        page.click("#navbar > ul.nav.navbar-top-links.navbar-right > li > ul > li:nth-child(1) > a")

        # Azure B2C login
        page.wait_for_selector("#signInName", timeout=15000)
        status.info("4. Entering credentials...")
        page.fill("#signInName", USERNAME)
        page.fill("#password", PASSWORD)

        status.info("5. Submitting login form...")
        page.click("#next")
        page.wait_for_timeout(6000)

        current_url = page.url
        status.write(f"🔍 URL after login: {current_url}")
        status.write(f"📄 Page title: {page.title()}")
        status.text_area("Page snippet:", page.inner_text("body")[:1000])

        # Optional: Keep me signed in
        if page.locator("text=Keep me signed in").is_visible():
            status.info("Selecting 'Yes' on Keep Me Signed In")
            page.click("text=Yes")
            page.wait_for_timeout(3000)

        if "Incorrect username" in page.inner_text("body"):
            status.error("❌ Wrong username or password")
            return False

        if "portconnect.co.nz" in current_url.lower():
            status.success("✅ Login successful")
            return True

        status.warning("⚠️ Login unclear — still on unknown page")
        return False

    except Exception as e:
        status.error(f"🚨 Login sequence error: {e}")
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
