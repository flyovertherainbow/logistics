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
