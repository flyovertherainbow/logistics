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
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            st.info("Navigating to PortConnect...")
            page.goto(PORTCONNECT_URL)

            st.info("Clicking Sign-in/Sign-up dropdown...")
            page.click("#navbar > ul.nav.navbar-top-links.navbar-right > li > a")

            st.info("Clicking Sign-in link...")
            page.click("#navbar > ul.nav.navbar-top-links.navbar-right > li > ul > li:nth-child(1) > a")

            page.wait_for_selector("#signInName", timeout=10000)

            st.info("Entering credentials...")
            page.fill("#signInName", USERNAME)
            page.fill("#password", PASSWORD)

            page.click("#next")

            st.info("Waiting for redirect...")
            page.wait_for_url(PORTCONNECT_URL, timeout=15000)

            # Check for member-only element (adjust selector as needed)
            if page.locator("text=Container Search").is_visible():
                st.success("✅ Login successful and member page loaded.")
            else:
                st.warning("❌ Login may have failed or member page not loaded.")

            browser.close()

    except PlaywrightTimeoutError:
        st.error("⏱️ Timeout occurred during login process.")
    except Exception as e:
        st.error(f"🚨 Unexpected error: {e}")

# --- Streamlit UI ---
st.title("PortConnect Login Automation")

if install_playwright():
    if st.button("Run Login Automation"):
        automate_login()
