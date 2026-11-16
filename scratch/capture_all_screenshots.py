"""
scratch/capture_all_screenshots.py
==================================
Captures high-resolution screenshots of the deployed Next.js web application
using headless Chrome with virtual time budget to allow React client rendering.
"""

import subprocess
import os
import time

chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
base_url = "https://sector-rotation-regime-discovery.vercel.app"
out_dir = os.path.abspath(r"scratch\screenshots")
os.makedirs(out_dir, exist_ok=True)

routes = [
    ("/", "01_dashboard_overview.png", "Main Dashboard & Market Overview"),
    ("/sector-rotation", "02_sector_rotation.png", "Active Sector Rotation & Weight Schedule"),
    ("/regime-intelligence", "03_regime_intelligence.png", "Market Regime Analysis & State Distributions"),
    ("/portfolio-analytics", "04_portfolio_analytics.png", "Portfolio Performance & Comparative Backtesting"),
    ("/event-intelligence", "05_event_intelligence.png", "Macroeconomic Event Analysis & Shocks"),
    ("/risk-drawdown", "06_risk_drawdown.png", "Risk Metrics & Drawdown Tracking"),
]

for route, filename, desc in routes:
    url = f"{base_url}{route}"
    out_path = os.path.join(out_dir, filename)
    print(f"Capturing {desc} from {url}...")
    cmd = [
        chrome_path,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--window-size=1440,960",
        "--virtual-time-budget=12000",
        f"--screenshot={out_path}",
        url
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(out_path):
        size_kb = os.path.getsize(out_path) / 1024
        print(f"  -> Successfully saved {filename} ({size_kb:.1f} KB)")
    else:
        print(f"  -> Failed to capture {filename}: {res.stderr}")

print("Screenshot capture completed.")
