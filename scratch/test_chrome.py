import subprocess
import os

chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
out_img = os.path.abspath(r"scratch\screenshots\sector_rotation_home.png")
cmd = [
    chrome_path,
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--window-size=1440,900",
    "--virtual-time-budget=10000",
    f"--screenshot={out_img}",
    "https://sector-rotation-regime-discovery.vercel.app/sector-rotation"
]
print("Running chrome screenshot on vercel app...")
res = subprocess.run(cmd, capture_output=True, text=True)
print("Exit code:", res.returncode)
print("Stderr:", res.stderr)
print("File exists?", os.path.exists(out_img))
if os.path.exists(out_img):
    print("Size:", os.path.getsize(out_img))
