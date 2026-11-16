"""
scratch/generate_simplified_flowchart.py
========================================
Generates a simplified, visually elegant, and professional Figure 5.1
project workflow diagram for the B.Tech CSE Machine Learning Final Project Report.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Set high DPI and styling
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'

fig, ax = plt.subplots(figsize=(12, 7.5), dpi=300)
ax.set_xlim(0, 12)
ax.set_ylim(0, 8.5)
ax.axis('off')

# Color palette: Clean academic corporate blue / slate
box_bg = "#F8FAFC"
box_border = "#0284C7"
header_bg = "#0EA5E9"
arrow_color = "#475569"
text_dark = "#0F172A"
text_muted = "#334155"

stages = [
    {
        "num": "Stage 1",
        "title": "Data Acquisition & Alignment",
        "x": 0.5, "y": 5.2, "w": 3.2, "h": 2.6,
        "items": [
            "• 8 Market Series (NSE Indices + VIX)",
            "• Yahoo Finance & NSE Verification",
            "• Asynchronous Holiday Alignment",
            "• 1,886 Synchronized Daily Sessions"
        ]
    },
    {
        "num": "Stage 2",
        "title": "Feature Engineering & Scaling",
        "x": 4.4, "y": 5.2, "w": 3.2, "h": 2.6,
        "items": [
            "• 42 Canonical Stationary Features",
            "• Multi-Horizon Sector Momentum",
            "• Sector Relative Strength vs. NIFTY 50",
            "• Leakage-Safe RobustScaler on Train"
        ]
    },
    {
        "num": "Stage 3",
        "title": "Unsupervised Regime Discovery",
        "x": 8.3, "y": 5.2, "w": 3.2, "h": 2.6,
        "items": [
            "• 3-Fold Expanding Walk-Forward CV",
            "• Tournament: K-Means, GMM, HMM",
            "• Gaussian HMM (K=6, Diagonal Cov)",
            "• Causal Real-Time Forward Filtering"
        ]
    },
    {
        "num": "Stage 6",
        "title": "Backtesting & Deployment",
        "x": 0.5, "y": 1.0, "w": 3.2, "h": 2.6,
        "items": [
            "• Vectorized Daily Portfolio Backtest",
            "• 15 bps Flat Transaction Cost Model",
            "• Out-of-Sample Holdout Evaluation",
            "• Cloud Database & Live Next.js Web UI"
        ]
    },
    {
        "num": "Stage 5",
        "title": "Portfolio Construction",
        "x": 4.4, "y": 1.0, "w": 3.2, "h": 2.6,
        "items": [
            "• 4 Standardized Strategy Variants",
            "• Equal-Weight & Inverse-Volatility",
            "• Defensive Cash Reserves in Crises",
            "• Realistic Execution at t+1 Close"
        ]
    },
    {
        "num": "Stage 4",
        "title": "Regime Rules & Sector Ranking",
        "x": 8.3, "y": 1.0, "w": 3.2, "h": 2.6,
        "items": [
            "• Empirical Regime Profiling (R0–R5)",
            "• Top-2 Sector Selection per State",
            "• 50% Probability Acceptance Gate",
            "• 5-Day Minimum Holding Lockup"
        ]
    },
]

# Draw boxes and content
for stage in stages:
    x, y, w, h = stage["x"], stage["y"], stage["w"], stage["h"]
    
    # Outer box with shadow effect
    shadow = patches.FancyBboxPatch(
        (x + 0.04, y - 0.04), w, h,
        boxstyle="round,pad=0.08,rounding_size=0.15",
        edgecolor="none", facecolor="#E2E8F0", zorder=1
    )
    ax.add_patch(shadow)
    
    box = patches.FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.08,rounding_size=0.15",
        edgecolor="#94A3B8", facecolor="#FFFFFF", linewidth=1.5, zorder=2
    )
    ax.add_patch(box)
    
    # Header bar
    header = patches.FancyBboxPatch(
        (x, y + h - 0.65), w, 0.65,
        boxstyle="round,pad=0.08,rounding_size=0.12",
        edgecolor="none", facecolor="#1E293B", zorder=3
    )
    ax.add_patch(header)
    
    # Header text
    ax.text(
        x + w / 2, y + h - 0.22,
        f"{stage['num']}: {stage['title']}",
        ha="center", va="center", color="#FFFFFF",
        fontsize=10.5, fontweight="bold", zorder=4
    )
    
    # Body bullet points
    text_y = y + h - 0.95
    for item in stage["items"]:
        ax.text(
            x + 0.2, text_y, item,
            ha="left", va="top", color=text_muted,
            fontsize=9.0, zorder=4
        )
        text_y -= 0.40

# Draw Connecting Arrows
arrow_style = "Simple,tail_width=2.0,head_width=7,head_length=8"
arrow_kw = dict(arrowstyle=arrow_style, color="#0284C7", zorder=5)

# Stage 1 -> Stage 2
ax.annotate("", xy=(4.35, 6.5), xytext=(3.75, 6.5), arrowprops=arrow_kw)

# Stage 2 -> Stage 3
ax.annotate("", xy=(8.25, 6.5), xytext=(7.65, 6.5), arrowprops=arrow_kw)

# Stage 3 -> Stage 4 (Downwards on right)
ax.annotate("", xy=(9.9, 3.65), xytext=(9.9, 5.15), arrowprops=arrow_kw)

# Stage 4 -> Stage 5 (Leftwards on bottom)
ax.annotate("", xy=(7.65, 2.3), xytext=(8.25, 2.3), arrowprops=arrow_kw)

# Stage 5 -> Stage 6 (Leftwards on bottom)
ax.annotate("", xy=(3.75, 2.3), xytext=(4.35, 2.3), arrowprops=arrow_kw)

plt.tight_layout()
out_path = r"scratch\simplified_workflow_diagram.png"
plt.savefig(out_path, dpi=300, bbox_inches='tight', facecolor="#FFFFFF")
plt.close()

print(f"Successfully generated simplified workflow diagram at {out_path}")
