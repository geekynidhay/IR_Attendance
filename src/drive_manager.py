"""
Google Drive Manager for IR Attendance Admin Panel
Handles OAuth2 authentication and file upload/download.

Drive Structure:
  Attendance Data/
  └── <username>/
      └── YYYY-MM-DD/
          └── <batch_id>.xlsx
"""
import os
import sys
import json
import threading
from pathlib import Path


def _get_token_path():
    """Return platform-appropriate token storage path."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "IR_Admin"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / "IR_Admin"
    else:
        base = Path.home() / ".ir_admin"
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "drive_token.json")


def _get_client_secrets_path():
    """Return platform-appropriate path for client_secrets.json."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "IR_Admin"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / "IR_Admin"
    else:
        base = Path.home() / ".ir_admin"
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "client_secrets.json")


def _get_cache_dir():
    """Return platform-appropriate local cache directory."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "IR_Admin" / "cache"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / "IR_Admin" / "cache"
    else:
        base = Path.home() / ".ir_admin" / "cache"
    base.mkdir(parents=True, exist_ok=True)
    return str(base)


# OAuth2 scopes needed
SCOPES = ["https://www.googleapis.com/auth/drive"]

def get_service_account_path():
    """Returns the expected path for the service account JSON key."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "IR_Admin"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / "IR_Admin"
    else:
        base = Path.home() / ".ir_admin"
    return str(base / "service_account.json")


class DriveManager:
    """Manages Google Drive operations for the IR Attendance admin panel."""

    def __init__(self):
        self._service = None
        self._creds = None
        self._lock = threading.Lock()
        self.sa_path = get_service_account_path()
        self.token_path = _get_token_path()
        self.client_secrets_path = _get_client_secrets_path()
        self.cache_dir = _get_cache_dir()
        self.root_folder_name = "Attendance Data"
        self._root_folder_id = None
        self._folder_id_cache = {}   # path string → drive folder id
        self.connected_email = None
        self.is_service_account = False

    # ──────────────────────────────────────────────────────────────────────
    #  Authentication
    # ──────────────────────────────────────────────────────────────────────

    def authenticate(self, sa_json_path=None):
        """
        Authenticate using either a Service Account or OAuth 2.0 Client Secrets JSON.
        Automatically detects key type and configures flow.
        Returns (success: bool, message: str).
        """
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
        except ImportError as e:
            return False, f"Missing library: {e}. Please install requirements."

        if sa_json_path and os.path.exists(sa_json_path):
            try:
                with open(sa_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Check JSON credentials type
                if "installed" in data or "web" in data:
                    # It's an OAuth 2.0 Desktop/Web Client Secrets file!
                    import shutil
                    os.makedirs(os.path.dirname(self.client_secrets_path), exist_ok=True)
                    shutil.copy(sa_json_path, self.client_secrets_path)
                    
                    # Clean up other credential files to avoid conflict
                    if os.path.exists(self.sa_path):
                        try: os.remove(self.sa_path)
                        except: pass
                    if os.path.exists(self.token_path):
                        try: os.remove(self.token_path)
                        except: pass
                elif data.get("type") == "service_account":
                    # It's a Service Account key file!
                    import shutil
                    os.makedirs(os.path.dirname(self.sa_path), exist_ok=True)
                    shutil.copy(sa_json_path, self.sa_path)
                    
                    # Clean up other credential files to avoid conflict
                    if os.path.exists(self.client_secrets_path):
                        try: os.remove(self.client_secrets_path)
                        except: pass
                    if os.path.exists(self.token_path):
                        try: os.remove(self.token_path)
                        except: pass
                else:
                    return False, "Unknown Google credentials file format."
            except Exception as e:
                return False, f"Invalid JSON key file: {e}"

        # Try to load bundled key if no key is currently present
        if not os.path.exists(self.sa_path) and not os.path.exists(self.client_secrets_path) and not os.path.exists(self.token_path):
            try:
                import sys
                base_path = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.abspath(os.path.dirname(__file__))
                bundled_json = os.path.join(base_path, "ir-attendance-497712-b3ae57837200.json")
                if os.path.exists(bundled_json):
                    import shutil
                    os.makedirs(os.path.dirname(self.sa_path), exist_ok=True)
                    shutil.copy(bundled_json, self.sa_path)
            except Exception:
                pass

        # Perform authentication flow based on what files exist
        if os.path.exists(self.token_path) or os.path.exists(self.client_secrets_path):
            return self.authenticate_oauth2()
        elif os.path.exists(self.sa_path):
            return self.authenticate_service_account()
        
        return False, "No credentials found. Please connect Google Drive first."

    def authenticate_service_account(self):
        """Connect to Google Drive using a Service Account."""
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            
            creds = service_account.Credentials.from_service_account_file(
                self.sa_path, scopes=SCOPES
            )
            self._creds = creds
            self._service = build("drive", "v3", credentials=creds)
            self.connected_email = creds.service_account_email
            self.is_service_account = True
            return True, f"Connected as {self.connected_email}"
        except Exception as e:
            return False, f"Failed to authenticate Service Account: {e}"

    def authenticate_oauth2(self):
        """Connect to Google Drive using OAuth 2.0 User (Desktop) flow."""
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            
            creds = None
            if os.path.exists(self.token_path):
                try:
                    creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
                except Exception:
                    pass

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                    except Exception:
                        creds = None
                
                if not creds:
                    if not os.path.exists(self.client_secrets_path):
                        return False, "OAuth client secrets JSON file not found."
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.client_secrets_path, SCOPES
                    )
                    creds = flow.run_local_server(port=0, prompt='consent')
                
                # Save the new token
                with open(self.token_path, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())

            self._creds = creds
            self._service = build("drive", "v3", credentials=creds)
            self.is_service_account = False
            
            # Fetch user email to show connection state
            try:
                about = self._service.about().get(fields="user(emailAddress)", supportsAllDrives=True).execute()
                self.connected_email = about.get("user", {}).get("emailAddress", "User Account")
            except Exception:
                self.connected_email = "Authenticated User"
                
            return True, f"Connected as {self.connected_email}"
        except Exception as e:
            return False, f"Failed to authenticate OAuth 2.0: {e}"

    def revoke_and_disconnect(self):
        """Delete saved credential files — forces re-login on next authenticate()."""
        for p in [self.sa_path, self.client_secrets_path, self.token_path]:
            if os.path.exists(p):
                try: os.remove(p)
                except: pass
        self._service = None
        self._creds = None
        self._root_folder_id = None
        self._folder_id_cache.clear()
        self.connected_email = None
        self.is_service_account = False

    def is_authenticated(self):
        if self._service is None:
            # Check if any saved credentials exist
            bundled_exists = False
            try:
                import sys
                base_path = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.abspath(os.path.dirname(__file__))
                bundled_json = os.path.join(base_path, "ir-attendance-497712-b3ae57837200.json")
                if os.path.exists(bundled_json):
                    bundled_exists = True
            except Exception:
                pass
                
            if os.path.exists(self.sa_path) or os.path.exists(self.client_secrets_path) or os.path.exists(self.token_path) or bundled_exists:
                try:
                    success, msg = self.authenticate()
                    print(f"Auto-authenticating with credentials: {success} ({msg})")
                except Exception as e:
                    print(f"Auto-authenticating failed: {e}")
        return self._service is not None

    # ──────────────────────────────────────────────────────────────────────
    #  Folder helpers
    # ──────────────────────────────────────────────────────────────────────

    def _find_or_create_folder(self, name, parent_id=None):
        """Find a folder by name (under parent), or create it. Returns folder_id."""
        svc = self._service
        query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        results = svc.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        files = results.get("files", [])
        if files:
            return files[0]["id"]

        # Create it
        meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent_id:
            meta["parents"] = [parent_id]
        folder = svc.files().create(
            body=meta,
            fields="id",
            supportsAllDrives=True
        ).execute()
        return folder["id"]

    def _get_root_folder_id(self):
        if not self._root_folder_id:
            self._root_folder_id = self._find_or_create_folder(self.root_folder_name)
        return self._root_folder_id

    def _get_folder_id(self, path_parts):
        """
        Recursively find/create nested folders.
        path_parts = ["username", "2026-05-28"]
        Returns the deepest folder's id.
        """
        cache_key = "/".join(path_parts)
        if cache_key in self._folder_id_cache:
            return self._folder_id_cache[cache_key]

        parent_id = self._get_root_folder_id()
        for part in path_parts:
            parent_id = self._find_or_create_folder(part, parent_id)

        self._folder_id_cache[cache_key] = parent_id
        return parent_id

    # ──────────────────────────────────────────────────────────────────────
    #  Upload
    # ──────────────────────────────────────────────────────────────────────

    def upload_xlsx(self, local_path, username, date_str, batch_id, progress_cb=None):
        """
        Upload a local XLSX file to Drive.
        Path on Drive: Attendance Data/<username>/<date_str>/<batch_id>.xlsx
        progress_cb(message) called with status updates.
        Returns (success: bool, message: str).
        """
        if not self.is_authenticated():
            return False, "Not authenticated"

        try:
            from googleapiclient.http import MediaFileUpload

            if progress_cb:
                progress_cb(f"Uploading {batch_id}.xlsx for {username}...")

            folder_id = self._get_folder_id([username, date_str])
            file_name = f"{batch_id}.xlsx"

            # Check if file already exists (update vs create)
            query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
            results = self._service.files().list(
                q=query,
                fields="files(id)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            existing = results.get("files", [])

            media = MediaFileUpload(
                local_path,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                resumable=False
            )

            if existing:
                # Update existing file
                self._service.files().update(
                    fileId=existing[0]["id"],
                    media_body=media,
                    supportsAllDrives=True
                ).execute()
            else:
                # Create new file
                meta = {"name": file_name, "parents": [folder_id]}
                self._service.files().create(
                    body=meta,
                    media_body=media,
                    fields="id",
                    supportsAllDrives=True
                ).execute()

            return True, f"Uploaded {batch_id}.xlsx"

        except Exception as e:
            return False, f"Upload failed: {e}"

    def upload_json(self, local_path, username, date_str, batch_id, progress_cb=None):
        """
        Upload a local JSON file to Drive.
        Path on Drive: Attendance Data/<username>/<date_str>/<batch_id>.json
        progress_cb(message) called with status updates.
        Returns (success: bool, message: str).
        """
        if not self.is_authenticated():
            return False, "Not authenticated"

        try:
            from googleapiclient.http import MediaFileUpload

            if progress_cb:
                progress_cb(f"Uploading {batch_id}.json for {username}...")

            folder_id = self._get_folder_id([username, date_str])
            file_name = f"{batch_id}.json"

            # Check if file already exists (update vs create)
            query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
            results = self._service.files().list(
                q=query,
                fields="files(id)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            existing = results.get("files", [])

            media = MediaFileUpload(
                local_path,
                mimetype="application/json",
                resumable=False
            )

            if existing:
                # Update existing file
                self._service.files().update(
                    fileId=existing[0]["id"],
                    media_body=media,
                    supportsAllDrives=True
                ).execute()
            else:
                # Create new file
                meta = {"name": file_name, "parents": [folder_id]}
                self._service.files().create(
                    body=meta,
                    media_body=media,
                    fields="id",
                    supportsAllDrives=True
                ).execute()

            return True, f"Uploaded {batch_id}.json"

        except Exception as e:
            return False, f"Upload failed: {e}"

    # ──────────────────────────────────────────────────────────────────────
    #  Download / List
    # ──────────────────────────────────────────────────────────────────────

    def list_users(self):
        """List all usernames (subfolder names) under Attendance Data. Returns list of str."""
        if not self.is_authenticated():
            return []
        try:
            root_id = self._get_root_folder_id()
            query = f"'{root_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self._service.files().list(
                q=query,
                fields="files(id, name)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            return [(f["name"], f["id"]) for f in results.get("files", [])]
        except Exception as e:
            print(f"Drive list_users error: {e}")
            return []

    def list_dates_for_user(self, username):
        """List all date folders for a given username. Returns list of (date_str, folder_id)."""
        if not self.is_authenticated():
            return []
        try:
            parent_id = self._get_folder_id([username])
            query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self._service.files().list(
                q=query,
                fields="files(id, name)",
                orderBy="name",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            return [(f["name"], f["id"]) for f in results.get("files", [])]
        except Exception as e:
            print(f"Drive list_dates error: {e}")
            return []

    def list_batches_for_date(self, username, date_str):
        """List all batch JSON files for a given username and date. Returns list of (batch_id, file_id)."""
        if not self.is_authenticated():
            return []
        try:
            parent_id = self._get_folder_id([username, date_str])
            query = f"'{parent_id}' in parents and trashed=false"
            results = self._service.files().list(
                q=query,
                fields="files(id, name)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            batches = []
            for f in results.get("files", []):
                name = f["name"]
                if name.endswith(".json"):
                    batch_id = name[:-5]  # strip .json
                    batches.append((batch_id, f["id"]))
            return batches
        except Exception as e:
            print(f"Drive list_batches error: {e}")
            return []

    def download_xlsx(self, file_id, local_path):
        """Download a Drive file by ID to local_path. Returns (success, message)."""
        if not self.is_authenticated():
            return False, "Not authenticated"
        try:
            from googleapiclient.http import MediaIoBaseDownload
            import io

            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            request = self._service.files().get_media(
                fileId=file_id,
                supportsAllDrives=True
            )
            buf = io.BytesIO()
            downloader = MediaIoBaseDownload(buf, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            with open(local_path, "wb") as f:
                f.write(buf.getvalue())
            return True, "Downloaded"
        except Exception as e:
            return False, f"Download failed: {e}"

    def download_batch_xlsx(self, username, date_str, batch_id):
        """
        Download a specific batch's XLSX from Drive to local cache.
        Returns (success, local_path_or_error_msg).
        """
        cache_path = os.path.join(self.cache_dir, username, date_str, f"{batch_id}.xlsx")
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)

        batches = self.list_batches_for_date(username, date_str)
        file_id = None
        for bid, fid in batches:
            if bid == batch_id:
                file_id = fid
                break

        if not file_id:
            return False, f"File {batch_id}.xlsx not found on Drive for {username}/{date_str}"

        ok, msg = self.download_xlsx(file_id, cache_path)
        if ok:
            return True, cache_path
        return False, msg

    def download_json(self, file_id, local_path):
        """Download a Drive JSON file by ID to local_path. Returns (success, message)."""
        if not self.is_authenticated():
            return False, "Not authenticated"
        try:
            from googleapiclient.http import MediaIoBaseDownload
            import io

            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            request = self._service.files().get_media(
                fileId=file_id,
                supportsAllDrives=True
            )
            buf = io.BytesIO()
            downloader = MediaIoBaseDownload(buf, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            with open(local_path, "wb") as f:
                f.write(buf.getvalue())
            return True, "Downloaded"
        except Exception as e:
            return False, f"Download failed: {e}"

    def download_batch_json(self, username, date_str, batch_id):
        """
        Download a specific batch's JSON from Drive to local cache.
        Returns (success, local_path_or_error_msg).
        """
        cache_path = os.path.join(self.cache_dir, username, date_str, f"{batch_id}.json")
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)

        batches = self.list_batches_for_date(username, date_str)
        file_id = None
        for bid, fid in batches:
            if bid == batch_id:
                file_id = fid
                break

        if not file_id:
            return False, f"File {batch_id}.json not found on Drive for {username}/{date_str}"

        ok, msg = self.download_json(file_id, cache_path)
        if ok:
            return True, cache_path
        return False, msg

    def sync_all_to_cache(self, progress_cb=None):
        """
        Download all user/date/batch JSON files from Drive to local cache.
        progress_cb(current, total, message) called for UI progress.
        Returns list of downloaded file paths.
        """
        downloaded = []
        try:
            users = self.list_users()
            total_ops = len(users)
            for i, (username, _) in enumerate(users):
                if progress_cb:
                    progress_cb(i, total_ops, f"Syncing {username}...")
                dates = self.list_dates_for_user(username)
                for date_str, _ in dates:
                    batches = self.list_batches_for_date(username, date_str)
                    for batch_id, file_id in batches:
                        cache_path = os.path.join(self.cache_dir, username, date_str, f"{batch_id}.json")
                        # Only download if not cached
                        if not os.path.exists(cache_path):
                            ok, result = self.download_json(file_id, cache_path)
                            if ok:
                                downloaded.append(cache_path)
            if progress_cb:
                progress_cb(total_ops, total_ops, "Sync complete")
        except Exception as e:
            print(f"Sync error: {e}")
        return downloaded

    def get_cached_dates_for_user(self, username):
        """Return list of date strings available in local cache for a user."""
        user_cache = os.path.join(self.cache_dir, username)
        if not os.path.exists(user_cache):
            return []
        return sorted([d for d in os.listdir(user_cache) if os.path.isdir(os.path.join(user_cache, d))])

    def get_cached_batches_for_date(self, username, date_str):
        """Return list of batch_ids available in local cache for a user/date."""
        date_cache = os.path.join(self.cache_dir, username, date_str)
        if not os.path.exists(date_cache):
            return []
        return [f[:-5] for f in os.listdir(date_cache) if f.endswith(".json")]

    def get_cached_xlsx_path(self, username, date_str, batch_id):
        """Return local cache path for a specific file (may not exist)."""
        return os.path.join(self.cache_dir, username, date_str, f"{batch_id}.xlsx")

    def get_cached_json_path(self, username, date_str, batch_id):
        """Return local cache path for a specific JSON file."""
        return os.path.join(self.cache_dir, username, date_str, f"{batch_id}.json")


# Global singleton
drive_manager = DriveManager()
