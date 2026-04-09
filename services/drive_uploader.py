"""
services/drive_uploader.py — Google Drive upload via official google-api-python-client.
Supports both Service Account (recommended) and OAuth2 credentials.
Creates dated folders automatically.
"""
from __future__ import annotations
import asyncio
from datetime import datetime
from functools import partial
from pathlib import Path

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
MIME_MP4 = "video/mp4"
MIME_TXT = "text/plain"
MIME_FOLDER = "application/vnd.google-apps.folder"


class DriveUploaderService:
    def __init__(self) -> None:
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service

        creds_path = Path(settings.gdrive_credentials_json)
        if not creds_path.exists():
            raise FileNotFoundError(
                f"Google credentials not found at: {creds_path}. "
                "See README for setup instructions."
            )

        # Try Service Account first (preferred for automation)
        try:
            creds = service_account.Credentials.from_service_account_file(
                str(creds_path), scopes=SCOPES
            )
            self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
            logger.info("drive_auth", method="service_account")
            return self._service
        except Exception:
            pass

        # Fallback: OAuth2 (user consent flow — run once, token cached)
        token_path = Path("token.json")
        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                creds = flow.run_local_server(port=0)
            token_path.write_text(creds.to_json())

        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        logger.info("drive_auth", method="oauth2")
        return self._service

    def _create_folder_sync(self, name: str, parent_id: str) -> str:
        svc = self._get_service()
        metadata = {
            "name": name,
            "mimeType": MIME_FOLDER,
            "parents": [parent_id],
        }
        folder = svc.files().create(body=metadata, fields="id, webViewLink").execute()
        return folder["id"], folder.get("webViewLink", "")

    def _upload_file_sync(self, path: Path, folder_id: str, mime: str) -> str:
        svc = self._get_service()
        metadata = {"name": path.name, "parents": [folder_id]}
        media = MediaFileUpload(str(path), mimetype=mime, resumable=True)
        file = (
            svc.files()
            .create(body=metadata, media_body=media, fields="id, webViewLink")
            .execute()
        )
        return file.get("webViewLink", "")

    async def upload_job_assets(
        self,
        job_id: str,
        video_path: Path,
        text_path: Path,
    ) -> str:
        """
        Creates a dated subfolder in root Drive folder,
        uploads video + text, returns folder URL.
        """
        loop = asyncio.get_running_loop()
        date_str = datetime.now().strftime("%Y-%m-%d")
        folder_name = f"{date_str}_{job_id[:8]}"

        # Create dated folder
        folder_id, folder_url = await loop.run_in_executor(
            None,
            partial(
                self._create_folder_sync,
                folder_name,
                settings.gdrive_root_folder_id,
            ),
        )
        logger.info("drive_folder_created", folder=folder_name, id=folder_id)

        # Upload video
        await loop.run_in_executor(
            None,
            partial(self._upload_file_sync, video_path, folder_id, MIME_MP4),
        )
        logger.info("drive_uploaded", file=video_path.name)

        # Upload text
        await loop.run_in_executor(
            None,
            partial(self._upload_file_sync, text_path, folder_id, MIME_TXT),
        )
        logger.info("drive_uploaded", file=text_path.name)

        return folder_url
