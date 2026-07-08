@echo off
echo Building Admin Panel...
call .venv\Scripts\activate
pyinstaller --noconsole --onefile --name Admin_Panel --icon=admin.ico --add-data "Admin Icon.png;." src/admin_panel.py
echo Admin Panel Build Complete.
pause
