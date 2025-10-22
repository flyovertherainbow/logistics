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
            
            # Submit login form
            page.click("#next")
            st.write("🟢 Login form submitted.")
            
            # Wait for possible redirect or additional prompts
            page.wait_for_timeout(8000)
            
            # Log current URL
            st.write("🔍 Current URL after login attempt:", page.url)
            
            # Log page title and some visible text for debugging
            st.write("📄 Page title:", page.title())
            visible_text = page.inner_text("body")
            st.text_area("🔍 Page content snapshot:", visible_text[:1000])  # Show first 1000 chars
            
            # Check for additional steps
            if page.locator("text=Keep me signed in").is_visible():
                st.info("🔄 'Keep me signed in' prompt detected. Clicking 'Yes'...")
                page.click("text=Yes")
                page.wait_for_timeout(5000)
            
            # Check for login success
            if page.url.startswith("https://www.portconnect.co.nz"):
                st.success("✅ Login successful. Redirected to PortConnect.")
            elif "portconnectauth.b2clogin.com" in page.url:
                st.warning("⚠️ Still on Azure login page. Login may not have completed.")
            else:
                st.warning("⚠️ Login status unclear. Unexpected redirect.")
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
