@echo off
cd /d "%~dp0"
echo Running Batches Web Sync GUI...
start .venv\Scripts\pythonw src\sync_website_gui.py
