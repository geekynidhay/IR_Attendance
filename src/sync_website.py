#!/usr/bin/env python3
"""
Sync Website
Automatically scans Google Drive for all releases and generates the entire docs/ website.
"""

import os
import sys
import subprocess
from pathlib import Path
from collections import OrderedDict

# Need to make sure we can import drive_manager
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from drive_manager import drive_manager

FOLDERS = {
    "Batches": "1f0_1H7xeBr3cxIbp6-9osNijNMHmEM6C",
    "WindowsApp": "1gU115Gp5J3Pk8a7JGlzHOTJIk5lLZAwS",
    "AndroidApp": "1ZlNoX8R73riswZOoIHTL9LO1Ftt-0j0V",
    "RDServices": "1j-iCSlebGkJ9qeHB_o2afTfXZTJlk_TS",
    "OtherSoftware": "107sXfWBqBa4tG2KkQqyus8njbCr1xKZi"
}

DOCS_DIR = Path(__file__).parent.parent / "docs"

def get_subfolders(service, parent_id):
    query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)", orderBy="name").execute()
    return results.get("files", [])

def get_files(service, parent_id):
    query = f"'{parent_id}' in parents and mimeType!='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name, size)", orderBy="name").execute()
    return results.get("files", [])

def format_bytes(size_str):
    try:
        size = int(size_str)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    except:
        return "Unknown Size"

def fetch_folder_data(service, folder_id):
    """Returns an OrderedDict of {folder_name: [files]} sorted descending by name (latest first)."""
    subfolders = get_subfolders(service, folder_id)
    # Sort folders descending so "V1.2" comes before "V1.0"
    subfolders.sort(key=lambda x: x['name'], reverse=True)
    
    data = OrderedDict()
    for sub in subfolders:
        files = get_files(service, sub['id'])
        data[sub['name']] = files
    return data

def generate_accordion_page(title, subtitle, data, back_link="index.html"):
    """Generate a standard accordion HTML page for browsing versions/batches."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} - IR Attendance</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css?v=2">
  <link rel="icon" type="image/png" href="assets/Icon.png">
  <style>
    .accordion-container {{ max-width: 900px; margin: 40px auto; text-align: left; }}
    .accordion-btn {{ background-color: rgba(31, 40, 51, 0.8); color: var(--accent-cyan); cursor: pointer; padding: 18px 25px; width: 100%; text-align: left; border: 1px solid rgba(102, 252, 241, 0.2); outline: none; transition: 0.3s; font-size: 1.3rem; font-weight: 600; border-radius: 8px; margin-bottom: 5px; font-family: 'Inter', sans-serif; display: flex; justify-content: space-between; align-items: center; }}
    .accordion-btn.active, .accordion-btn:hover {{ background-color: rgba(102, 252, 241, 0.1); border-color: var(--accent-cyan); }}
    .accordion-btn:after {{ content: '\\02795'; font-size: 1rem; color: var(--accent-cyan); }}
    .accordion-btn.active:after {{ content: "\\2796"; }}
    .panel {{ padding: 0 15px; background-color: transparent; max-height: 0; overflow: hidden; transition: max-height 0.3s ease-out; margin-bottom: 15px; border-radius: 0 0 8px 8px; }}
    .batch-list {{ display: flex; flex-direction: column; gap: 15px; margin-top: 15px; margin-bottom: 15px; }}
    .batch-item {{ background: rgba(31, 40, 51, 0.5); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 20px; display: flex; justify-content: space-between; align-items: center; transition: all 0.3s; }}
    .batch-item:hover {{ background: rgba(31, 40, 51, 0.9); border-color: rgba(102, 252, 241, 0.3); transform: translateX(5px); }}
    .batch-info {{ text-align: left; }}
    .batch-name {{ font-size: 1.2rem; color: #fff; font-weight: 600; margin-bottom: 5px; word-break: break-all; }}
    .batch-meta {{ font-size: 0.9rem; color: #888; }}
    .btn-download {{ background: transparent; color: var(--accent-cyan); border: 1px solid var(--accent-cyan); padding: 8px 20px; border-radius: 20px; text-decoration: none; font-weight: 600; transition: all 0.2s; white-space: nowrap; margin-left: 10px; }}
    .btn-download:hover {{ background: var(--accent-cyan); color: #0b0c10; box-shadow: 0 0 15px rgba(102, 252, 241, 0.4); }}
  </style>
</head>
<body>
  <div class="topnav">
    <a href="index.html">Home</a>
    <a href="windows_versions.html">Windows App</a>
    <a href="android_versions.html">Android App</a>
    <a href="rd_services.html">RD Services</a>
    <a href="batches.html">Batches</a>
    <a href="other_software.html">Other Software</a>
  </div>
  <div class="container">
    <header>
      <a href="index.html"><img src="assets/Icon.png" alt="IR Attendance Logo" style="width: 80px;"></a>
      <h1 style="font-size: 2.5rem;">{title}</h1>
      <p class="subtitle">{subtitle}</p>
      <br>
      <a href="{back_link}" class="btn-secondary" style="font-size: 0.9rem;">&larr; Back</a>
    </header>
"""

    if not data:
        html += """
    <div style="text-align: center; margin-top: 50px;">
        <p>No files found. Check your Google Drive folders!</p>
    </div>
"""
    else:
        html += '    <div class="accordion-container">\n'
        for folder_name, files in data.items():
            html += f'      <button class="accordion-btn">{folder_name}</button>\n'
            html += '      <div class="panel">\n'
            html += '        <div class="batch-list">\n'
            if not files:
                html += f'          <div class="batch-item"><div class="batch-info"><div class="batch-name">No files available</div></div></div>\n'
            else:
                for f in files:
                    download_link = f"https://drive.google.com/uc?export=download&id={f['id']}"
                    html += f"""
          <div class="batch-item">
            <div class="batch-info">
              <div class="batch-name">{f['name']}</div>
              <div class="batch-meta">File Size: {format_bytes(f.get('size', 0))}</div>
            </div>
            <a href="{download_link}" class="btn-download" target="_blank" rel="noopener">Download</a>
          </div>
"""
            html += '        </div>\n'
            html += '      </div>\n'
        html += '    </div>\n'

    html += """
    <footer style="margin-top: 60px;">
      <p>&copy; 2026 IR Attendance Project. All Rights Reserved.</p>
    </footer>
  </div>

  <script>
    var acc = document.getElementsByClassName("accordion-btn");
    for (var i = 0; i < acc.length; i++) {
      acc[i].addEventListener("click", function() {
        this.classList.toggle("active");
        var panel = this.nextElementSibling;
        if (panel.style.maxHeight) {
          panel.style.maxHeight = null;
        } else {
          panel.style.maxHeight = panel.scrollHeight + "px";
        }
      });
    }
  </script>
</body>
</html>
"""
    return html

def generate_flat_page(title, subtitle, files, back_link="index.html"):
    """Generate a simple flat-list HTML page for folders whose files sit directly inside (no subfolders)."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} - IR Attendance</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css?v=2">
  <link rel="icon" type="image/png" href="assets/Icon.png">
  <style>
    .software-list {{ max-width: 900px; margin: 40px auto; text-align: left; display: flex; flex-direction: column; gap: 15px; }}
    .software-item {{ background: rgba(31, 40, 51, 0.5); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 20px 25px; display: flex; justify-content: space-between; align-items: center; transition: all 0.3s; }}
    .software-item:hover {{ background: rgba(31, 40, 51, 0.9); border-color: rgba(102, 252, 241, 0.3); transform: translateX(5px); }}
    .software-info {{ text-align: left; }}
    .software-name {{ font-size: 1.2rem; color: #fff; font-weight: 600; margin-bottom: 5px; word-break: break-all; }}
    .software-meta {{ font-size: 0.9rem; color: #888; }}
    .btn-download {{ background: transparent; color: var(--accent-cyan); border: 1px solid var(--accent-cyan); padding: 10px 24px; border-radius: 20px; text-decoration: none; font-weight: 600; transition: all 0.2s; white-space: nowrap; margin-left: 15px; }}
    .btn-download:hover {{ background: var(--accent-cyan); color: #0b0c10; box-shadow: 0 0 15px rgba(102, 252, 241, 0.4); }}
  </style>
</head>
<body>
  <div class="topnav">
    <a href="index.html">Home</a>
    <a href="windows_versions.html">Windows App</a>
    <a href="android_versions.html">Android App</a>
    <a href="rd_services.html">RD Services</a>
    <a href="batches.html">Batches</a>
    <a href="other_software.html" class="active">Other Software</a>
  </div>
  <div class="container">
    <header>
      <a href="index.html"><img src="assets/Icon.png" alt="IR Attendance Logo" style="width: 80px;"></a>
      <h1 style="font-size: 2.5rem;">{title}</h1>
      <p class="subtitle">{subtitle}</p>
      <br>
      <a href="{back_link}" class="btn-secondary" style="font-size: 0.9rem;">&larr; Back</a>
    </header>
"""

    if not files:
        html += """
    <div style="text-align: center; margin-top: 50px;">
        <p>No files found. Check your Google Drive folders!</p>
    </div>
"""
    else:
        html += '    <div class="software-list">\n'
        for f in files:
            download_link = f"https://drive.google.com/uc?export=download&id={f['id']}"
            html += f"""
      <div class="software-item">
        <div class="software-info">
          <div class="software-name">{f['name']}</div>
          <div class="software-meta">File Size: {format_bytes(f.get('size', 0))}</div>
        </div>
        <a href="{download_link}" class="btn-download" target="_blank" rel="noopener">Download</a>
      </div>
"""
        html += '    </div>\n'

    html += """
    <footer style="margin-top: 60px;">
      <p>&copy; 2026 IR Attendance Project. All Rights Reserved.</p>
    </footer>
  </div>
</body>
</html>
"""
    return html

def generate_index_html(latest_win, latest_and):

    """Generate the main index.html file with a top nav and dynamic latest links."""
    win_link = f"https://drive.google.com/uc?export=download&id={latest_win}" if latest_win else "windows_versions.html"
    and_link = f"https://drive.google.com/uc?export=download&id={latest_and}" if latest_and else "android_versions.html"
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>IR Attendance - Official Downloads</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css?v=2">
  <link rel="icon" type="image/png" href="assets/Icon.png">
  <style>
    .card-actions {{ display: flex; flex-direction: column; gap: 15px; margin-top: 25px; }}
  </style>
</head>
<body>
  <div class="topnav">
    <a href="index.html" class="active">Home</a>
    <a href="windows_versions.html">Windows App</a>
    <a href="android_versions.html">Android App</a>
    <a href="rd_services.html">RD Services</a>
    <a href="batches.html">Batches</a>
    <a href="other_software.html">Other Software</a>
  </div>

  <div class="container" style="margin-top: 40px;">
    <header>
      <img src="assets/Icon.png" alt="IR Attendance Logo">
      <h1>IR <span>Attendance</span></h1>
      <p class="subtitle">The definitive automated attendance tracking and image batch processing suite.</p>
    </header>

    <h2 class="section-title">Download Application</h2>
    <div class="cards">
      <!-- Windows App -->
      <div class="card">
        <h3>Windows Desktop</h3>
        <p>Full suite including AI Attendance, Manual Processing, and JPG Batch Splitting.</p>
        <div class="card-actions">
          <a href="{win_link}" class="btn" target="_blank" rel="noopener">Download Latest (.exe)</a>
          <a href="windows_versions.html" class="btn-secondary">Previous Versions</a>
        </div>
      </div>

      <!-- Android App -->
      <div class="card">
        <h3>Android Mobile</h3>
        <p>Companion app for mobile attendance taking and wireless computer mirroring.</p>
        <div class="card-actions">
          <a href="{and_link}" class="btn" target="_blank" rel="noopener">Download Latest (.apk)</a>
          <a href="android_versions.html" class="btn-secondary">Previous Versions</a>
        </div>
      </div>
    </div>
    
    <h2 class="section-title" style="margin-top: 60px;">Resources</h2>
    <div class="cards" style="margin-bottom: 40px;">
      <!-- RD Services -->
      <div class="card">
        <h3>RD Services</h3>
        <p>Browse and download biometric drivers directly from our cloud storage.</p>
        <div class="card-actions">
          <a href="rd_services.html" class="btn" rel="noopener">Browse Drivers</a>
        </div>
      </div>
      
      <!-- Batches -->
      <div class="card">
        <h3>Batches</h3>
        <p>Ready-to-use zip archives of image batches. Import them instantly into your database.</p>
        <div class="card-actions">
          <a href="batches.html" class="btn" rel="noopener">Browse Batches</a>
        </div>
      </div>

      <!-- Other Software -->
      <div class="card">
        <h3>Other Software</h3>
        <p>Additional utilities and companion tools like the IRIS PDF Generator.</p>
        <div class="card-actions">
          <a href="other_software.html" class="btn" rel="noopener">Browse Software</a>
        </div>
      </div>
    </div>

    <footer>
      <p>&copy; 2026 IR Attendance Project. All Rights Reserved.</p>
    </footer>
  </div>
</body>
</html>
"""
    return html

def get_latest_file_id(data):
    """Returns the file ID of the first file in the most recent folder."""
    if not data:
        return None
    # data is an OrderedDict, the first key is the latest version
    latest_folder = list(data.values())[0]
    if latest_folder:
        return latest_folder[0]['id']
    return None

def run_sync(log_cb=print):
    log_cb("=" * 50)
    log_cb(" IR Attendance - Full Web Sync ")
    log_cb("=" * 50)
    
    # 1. Authenticate
    log_cb("\nAuthenticating with Google Drive...")
    success, msg = drive_manager.authenticate()
    if not success:
        log_cb(f"Error: {msg}")
        return False

    log_cb(f"Authenticated as: {drive_manager.connected_email}")
    
    svc = drive_manager._service
    os.makedirs(DOCS_DIR, exist_ok=True)
    
    # 2. Fetch Data — track which fetches SUCCEEDED so we only overwrite on success
    fetch_errors = []

    log_cb("\nFetching Batches...")
    batches_data = None
    try:
        batches_data = fetch_folder_data(svc, FOLDERS["Batches"])
    except Exception as e:
        log_cb(f"Failed to fetch Batches: {e}")
        fetch_errors.append("Batches")
        
    log_cb("Fetching Windows App versions...")
    win_data = None
    try:
        win_data = fetch_folder_data(svc, FOLDERS["WindowsApp"])
    except Exception as e:
        log_cb(f"Failed to fetch Windows App: {e}")
        fetch_errors.append("WindowsApp")
        
    log_cb("Fetching Android App versions...")
    and_data = None
    try:
        and_data = fetch_folder_data(svc, FOLDERS["AndroidApp"])
    except Exception as e:
        log_cb(f"Failed to fetch Android App: {e}")
        fetch_errors.append("AndroidApp")
        
    log_cb("Fetching RD Services...")
    rd_data = None
    try:
        rd_data = fetch_folder_data(svc, FOLDERS["RDServices"])
    except Exception as e:
        log_cb(f"Failed to fetch RD Services: {e}")
        fetch_errors.append("RDServices")

    log_cb("Fetching Other Software...")
    other_sw_files = None
    try:
        other_sw_files = get_files(svc, FOLDERS["OtherSoftware"])
    except Exception as e:
        log_cb(f"Failed to fetch Other Software: {e}")
        fetch_errors.append("OtherSoftware")

    if fetch_errors:
        log_cb(f"\n⚠ WARNING: {len(fetch_errors)} folder(s) failed to fetch: {', '.join(fetch_errors)}")
        log_cb("Skipping overwrite of pages that could not be fetched to preserve existing content.")

    # 3. Generate Accordion Pages — only write if fetch succeeded (data is not None)
    log_cb("\nGenerating pages...")
    pages = {
        "batches.html": (batches_data, generate_accordion_page("Batches", "Download complete image archives to import directly into your local database.", batches_data or {})),
        "windows_versions.html": (win_data, generate_accordion_page("Windows App Versions", "Browse and download previous versions of the IR Attendance Windows Desktop application.", win_data or {})),
        "android_versions.html": (and_data, generate_accordion_page("Android App Versions", "Browse and download previous versions of the IR Attendance Android Mobile application.", and_data or {})),
        "rd_services.html": (rd_data, generate_accordion_page("RD Services & Drivers", "Browse and download biometric drivers (Mantra, Morpho, etc.).", rd_data or {})),
        "other_software.html": (other_sw_files, generate_flat_page("Other Software", "Additional utility tools and companion software for the IR Attendance ecosystem.", other_sw_files or []))
    }
    
    for filename, (data, html) in pages.items():
        if data is None:
            log_cb(f" - SKIPPED {filename} (fetch failed — preserving existing content)")
            continue
        with open(DOCS_DIR / filename, "w", encoding="utf-8") as f:
            f.write(html)
        log_cb(f" - Generated {filename}")

    # 4. Generate Index HTML with latest links (only if at least win/android data was fetched)
    if win_data is not None or and_data is not None:
        latest_win_id = get_latest_file_id(win_data or {})
        latest_and_id = get_latest_file_id(and_data or {})
        
        index_html = generate_index_html(latest_win_id, latest_and_id)
        with open(DOCS_DIR / "index.html", "w", encoding="utf-8") as f:
            f.write(index_html)
        log_cb(" - Generated index.html")
    else:
        log_cb(" - SKIPPED index.html (all fetches failed — preserving existing content)")

    # 5. Git commit & push
    log_cb("\nPushing changes to GitHub...")
    try:
        subprocess.run(["git", "add", "docs/"], check=True)
        
        # Check if there's anything to commit
        status = subprocess.run(["git", "status", "--porcelain", "docs/"], capture_output=True, text=True)
        if not status.stdout.strip():
            log_cb("No changes detected. Website is already up to date!")
            return True
            
        subprocess.run(["git", "commit", "-m", "chore: Auto-sync website releases"], check=True)
        log_cb("Pulling latest changes from GitHub...")
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True)
        log_cb("Pushing to GitHub...")
        subprocess.run(["git", "push", "origin", "main"], check=True)
        log_cb("Website successfully updated and pushed!")
    except Exception as e:
        log_cb(f"Git push failed: {e}. You may need to commit and push manually.")
    
    return True

def main():
    run_sync(print)
        
if __name__ == "__main__":
    main()
