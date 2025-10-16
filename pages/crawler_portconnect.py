import streamlit as st
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import subprocess
import sys

# Define the login credentials and URL
PORTCONNECT_URL = "https://www.portconnect.co.nz/#/home"
USERNAME = "test@gmail.com"
PASSWORD = "pass1243"

# --- CACHE THE PLAYWRIGHT INSTALLATION ---
@st.cache_resource(show_spinner="Setting up browser environment...")
def install_playwright():
    """Ensures Playwright browser binaries are installed and cached."""
    try:
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
        st.error("Please ensure packages.txt contains 'chromium'.")
        return False
    except Exception as e:
        st.error(f"Unexpected error during Playwright setup: {e}")
        return False

def run_portconnect_login():
    """
    Executes the Playwright script to navigate, log in, and check the post-login state.
    """
    # Ensure installation runs and is cached
    if not install_playwright():
        return

    st.info(f"Starting PortConnect login sequence for: {PORTCONNECT_URL}")
    
    try:
        with sync_playwright() as p:
            # Launch the browser
            # Setting 'slow_mo' for debugging might be helpful, but generally keep it 0
            # NOTE: Keep headless=True for cloud deployment. Change to False ONLY for local debugging.
            browser = p.chromium.launch(headless=True, timeout=30000) 
            page = browser.new_page()
            
            st.markdown("1. Navigating to PortConnect...")
            page.goto(PORTCONNECT_URL, wait_until="load", timeout=20000)
            
            # --- LOGIN STEPS ---
            
            # 2. Click the Sign-in/Sign-up dropdown menu (Wait for the dropdown link to be visible)
            DROPDOWN_SELECTOR = "#navbar > ul.nav.navbar-top-links.navbar-right > li > a"
            st.markdown(f"2. Clicking dropdown: `{DROPDOWN_SELECTOR}`")
            page.wait_for_selector(DROPDOWN_SELECTOR, state="visible", timeout=10000).click()

            # 3. Click the Sign-in link inside the dropdown (Wait for the sign-in link to be visible after dropdown opens)
            SIGN_IN_LINK_SELECTOR = "#navbar > ul.nav.navbar-top-links.navbar-right > li > ul > li:nth-child(1) > a"
            st.markdown(f"3. Clicking Sign-in link: `{SIGN_IN_LINK_SELECTOR}`")
            page.wait_for_selector(SIGN_IN_LINK_SELECTOR, state="visible", timeout=10000).click()
            
            # The click usually triggers a redirect or modal, wait for the login page URL or elements
            st.markdown("4. Waiting for the login form to load...")
            # Wait for the email input field to appear, confirming the login form is ready
            EMAIL_SELECTOR = "#signInName"
            page.wait_for_selector(EMAIL_SELECTOR, state="visible", timeout=15000)
            
            # 5. Input username and password
            PASSWORD_SELECTOR = "#password"
            SUBMIT_BUTTON_SELECTOR = "#next"
            
            st.markdown(f"5. Filling email: `{USERNAME}`")
            page.fill(EMAIL_SELECTOR, USERNAME)
            
            st.markdown(f"6. Filling password: `********`")
            page.fill(PASSWORD_SELECTOR, PASSWORD)
            
            # 7. Click the submit button
            st.markdown(f"7. Clicking Sign-in button: `{SUBMIT_BUTTON_SELECTOR}`")
            # Click and wait for navigation to the next page
            page.click(SUBMIT_BUTTON_SELECTOR)

            # 8. Check post-login status (Wait for successful navigation or a visible error message)
            st.markdown("8. Waiting for post-login page load...")
            page.wait_for_url(PORTCONNECT_URL + "*", timeout=15000)
            
            current_url = page.url
            title = page.title()
            
            browser.close()
            
            # Final Status Output
            if current_url.startswith(PORTCONNECT_URL):
                 st.success(f"Login sequence completed. Browser is now on: {title} ({current_url})")
                 st.info("Since test credentials were used, the app is likely stuck at a login error page or redirected back to the main site. If the URL changed, the submission was successful.")
            else:
                 st.warning(f"Login sequence resulted in unexpected URL: {current_url}")
            
    except PlaywrightTimeoutError:
        st.error(f"Playwright timed out while waiting for an element or navigation. Current URL: {page.url if 'page' in locals() else 'N/A'}")
    except Exception as e:
        st.error(f"An unexpected Playwright error occurred: {e}")

# --- STREAMLIT APP LAYOUT ---

st.title("🚢 PortConnect Crawler (Playwright)")
st.write("This page executes the PortConnect login routine using Playwright's headless browser.")

if st.button("Run PortConnect Login Test"):
    run_portconnect_login()

st.info("Note: This script relies on the `install_playwright` function to ensure the necessary browser binaries (Chromium) are available in the Streamlit Cloud environment.")

