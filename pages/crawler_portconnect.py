import streamlit as st
import pandas as pd
import json
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

        # Check if already logged in — portal is loaded and no B2C redirect occurred
        current_url = page.url
        if "portconnect.co.nz" in current_url and "b2clogin.com" not in current_url:
            if not page.locator("#signInName").is_visible():
                status.success("✅ Already logged in — skipping login steps.")
                return True

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

def scrape_results_table(page, status):
    """Scrape both results tables from the Track & Trace search page.

    Primary strategy: read column headers from <thead th>, map to <tbody td> text.
    Fallback: read all span.sm-label / span.sm-value pairs within each row
    (used when the responsive layout collapses columns into a single cell).
    """
    records = []

    sections = page.locator("div.panel.panel-default").all()
    for section in sections:
        try:
            section_title = section.locator("h3, h4, .panel-title").first.inner_text().strip()
        except Exception:
            section_title = "Unknown"

        # Build header list from thead, stripping sort-icon whitespace
        header_els = section.locator("thead th").all()
        headers = []
        for th in header_els:
            text = th.inner_text().strip().replace("\n", " ").strip()
            headers.append(text)

        rows = section.locator("tbody tr").all()
        for row in rows:
            # Skip rows hidden by responsive CSS (duplicate mobile layout)
            if not row.is_visible():
                continue
            cells = row.locator("td").all()
            if not cells:
                continue

            record = {"section": section_title}
            has_data = False

            if headers:
                # Desktop layout: one value per <td>, mapped by header position
                for i, cell in enumerate(cells):
                    if i >= len(headers):
                        break
                    header = headers[i]
                    if not header or header.lower() == "detail":
                        continue
                    # Prefer sm-value span if present, otherwise full cell text
                    value_el = cell.locator("span.sm-value")
                    value = value_el.first.inner_text().strip() if value_el.count() > 0 else cell.inner_text().strip()
                    if value:
                        record[header] = value
                        has_data = True
            else:
                # Responsive fallback: all sm-label/sm-value pairs anywhere in the row
                label_els = row.locator("span.sm-label").all()
                value_els = row.locator("span.sm-value").all()
                for lbl, val in zip(label_els, value_els):
                    label = lbl.inner_text().strip()
                    value = val.inner_text().strip()
                    if label:
                        record[label] = value
                        has_data = True

            if has_data:
                records.append(record)

    status.info(f"📊 Scraped {len(records)} row(s) across all sections")
    return records


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
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            
            # Test login
            login_success = test_login_sequence(page, status_placeholder)
            
            if login_success:
                status_placeholder.success("🎉 Login test passed!")
                
                # -------------------------------
                # NAVIGATION: Track & Trace → Search
                # -------------------------------
                status_placeholder.info("7. Opening Track & Trace dropdown...")

                # Step 1: Click the Track and Trace dropdown toggle to open the menu
                page.locator('a[data-toggle="dropdown"][href="/#/track-trace"]').click()

                # Step 2: Wait for the Search link to become visible in the dropdown
                search_nav_link = page.locator('a[href="/#/track-trace/search"]')
                search_nav_link.wait_for(state="visible", timeout=5000)
                status_placeholder.info("8. Clicking Search in dropdown menu...")
                search_nav_link.click()

                # Step 3: Wait for the search page URL and container input to load
                page.wait_for_url("**/track-trace/search**", timeout=10000)
                container_box = page.locator("#txContainerInput")
                container_box.wait_for(state="visible", timeout=15000)

                page.screenshot(path="debug_search_page.png")
                status_placeholder.success("✅ Search page loaded")

                # Step 4: Enter all container numbers and search
                if container_list:
                    containers_text = ",".join(container_list)
                    status_placeholder.info(f"🔍 Entering {len(container_list)} container(s)...")
                    container_box.fill(containers_text)

                    # Click Search button — scoped to form button group to avoid nav ambiguity
                    page.locator("div.search-item-button").get_by_role("button", name="Search", exact=True).click()

                    # Wait for results table to populate
                    page.wait_for_selector("table tbody tr", timeout=15000)
                    page.screenshot(path="debug_after_search.png")
                    status_placeholder.success("✅ Results loaded")

                    # Scrape both results tables and drop exact duplicate rows
                    records = scrape_results_table(page, status_placeholder)
                    df = pd.DataFrame(records).drop_duplicates().reset_index(drop=True)
                    return df, True

                return pd.DataFrame(), True

                # -------------------------------
                # END OF NAVIGATION SECTION
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
container_input = st.text_area("Container Numbers (comma-separated, e.g. MSKU1234567, SUDU7654722):", height=80)
container_list = [c.strip() for c in container_input.split(',') if c.strip()]

# Status placeholder
status_placeholder = st.empty()

# Run diagnostic button
if st.button("Run Diagnostic Test"):
    if container_list:
        df, success = run_diagnostic_scraper(container_list, status_placeholder)
        if success:
            st.success("🎉 Diagnostic completed successfully!")
            if not df.empty:
                # Group results by container number
                container_col = "Container" if "Container" in df.columns else None

                if container_col:
                    grouped = df.groupby(container_col, sort=False)
                    container_groups = {name: group.drop(columns=[container_col]) for name, group in grouped}
                else:
                    # Fallback: treat all results as one group
                    container_groups = {"All Results": df}

                st.markdown(f"### 📋 Results — {len(container_groups)} container(s) found")

                all_data = {}

                # --- Tables section ---
                for container_num, group_df in container_groups.items():
                    st.markdown(f"---\n#### 📦 {container_num}")
                    st.dataframe(group_df, use_container_width=True)
                    all_data[container_num] = group_df.to_dict(orient="records")

                # --- JSON section at the bottom ---
                st.markdown("---")
                st.markdown("### 🗂️ JSON Results")
                for container_num, records in all_data.items():
                    st.markdown(f"**{container_num}**")
                    st.json(records)
                    st.download_button(
                        label=f"⬇️ Download {container_num}.json",
                        data=json.dumps(records, indent=2),
                        file_name=f"{container_num}.json",
                        mime="application/json",
                        key=f"dl_{container_num}",
                    )

                # Combined download for all containers
                if len(all_data) > 1:
                    st.markdown("---")
                    st.download_button(
                        label="⬇️ Download All Containers (combined JSON)",
                        data=json.dumps(all_data, indent=2),
                        file_name="portconnect_results_all.json",
                        mime="application/json",
                        key="dl_all",
                    )
            else:
                st.info("No results returned for the given container(s).")
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
















