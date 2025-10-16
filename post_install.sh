#!/bin/bash
echo "--- Running Playwright install script ---"
# Install only the Chromium browser, matching your packages.txt
python -m playwright install chromium
echo "--- Playwright install finished ---"
