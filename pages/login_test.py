import streamlit as st
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import subprocess
import sys

# --- Configuration ---
PORTCONNECT_URL = "https://www.portconnect.co.nz/#/home"
USERNAME = "Calony.lam@gmail.com"
PASSWORD = "Eclyltd88$"

# --- Playwright Installation ---
@st.cache_resource(show_spinner="Setting up browser environment...")
def install_playwright():
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except Exception as e:
        st.error(f"Playwright setup failed: {e}")
        return False

# --- Login Automation ---
def automate_login():
    try:
        with sync_playwright() as p:
            #browser = p.chromium.launch(headless=False)  # Set to True for silent mode
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            st.info("Navigating to PortConnect...")
            page.goto(PORTCONNECT_URL)

            st.info("Clicking Sign-in/Sign-up dropdown...")
            page.click("#navbar > ul.nav.navbar-top-links.navbar-right > li > a")

            st.info("Clicking Sign-in link...")
            page.click("#navbar > ul.nav.navbar-top-links.navbar-right > li > ul > li:nth-child(1) > a")

            # Wait for Azure B2C login page
            page.wait_for_selector("#signInName", timeout=15000)

            st.info("Entering credentials...")
            page.fill("#signInName", USERNAME)
            page.fill("#password", PASSWORD)

            st.info("Submitting login form...")
            page.click("#next")

            # Wait for redirect or page change
            page.wait_for_timeout(5000)  # Give time for redirect
            # Log current URL
            current_url = page.url
            st.write("🔍 Current URL after login attempt:", current_url)

            # Check for login success or failure
            if page.locator("text=Incorrect username or password").is_visible():
                st.error("❌ Login failed: Incorrect username or password.")
            elif page.locator("text=Container Search").is_visible():
                st.success("✅ Login successful and member page loaded.")
            elif "portconnectauth.b2clogin.com" in current_url:
                st.warning("⚠️ Still on Azure login page. Login may not have completed.")
            else:
                st.warning("⚠️ Login status unclear. No redirect or error message detected.")

            browser.close()

    except PlaywrightTimeoutError:
        st.error("⏱️ Timeout occurred during login process.")
    except Exception as e:
        st.error(f"🚨 Unexpected error: {e}")

# --- Streamlit UI ---
st.title("🔐 PortConnect Login Automation")

if install_playwright():
    if st.button("Run Login Automation"):
        automate_login()
