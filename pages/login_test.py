import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import subprocess
import sys
import io
import time

# --- Configuration ---
PORTCONNECT_URL = "https://www.portconnect.co.nz/#/home"
USERNAME = "Calony.lam@gmail.com"
PASSWORD = "Eclyltd88$"
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


from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Set headless=True to run without UI
        page = browser.new_page()

        # Step 1: Go to PortConnect homepage
        page.goto("https://www.portconnect.co.nz/#/home")

        # Step 2: Click on Sign-in/Sign-up dropdown
        page.click("#navbar > ul.nav.navbar-top-links.navbar-right > li > a")

        # Step 3: Click on the Sign-in link
        page.click("#navbar > ul.nav.navbar-top-links.navbar-right > li > ul > li:nth-child(1) > a")

        # Step 4: Wait for login page to load
        page.wait_for_selector("#signInName")

        # Step 5: Fill in email and password
        page.fill("#signInName", "test@gmail.com")
        page.fill("#password", "pass1243")

        # Step 6: Click the Sign-in button
        page.click("#next")

        # Step 7: Wait for redirect and check if member page is loaded
        page.wait_for_url("https://www.portconnect.co.nz/#/home", timeout=10000)

        # Step 8: Check for member-specific menu item (example: Dashboard)
        if page.locator("text=Dashboard").is_visible():
            print("✅ Login successful and member page loaded.")
        else:
            print("❌ Login may have failed or member page not loaded.")

        browser.close()

run()
