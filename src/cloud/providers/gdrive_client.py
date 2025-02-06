from utils.file_handler import FileHandler
from ..interfaces.cloud_provider import CloudProvider
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import pickle
import os
import io
import logging
from pathlib import Path
from utils.logger import setup_logging

logger = logging.getLogger(__name__)

class GoogleDriveClient(CloudProvider):
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    DEFAULT_PORT = 52479
    
    def __init__(self, gdrive_config: dict, login:bool=False):
        """
        Initialize with gdrive section from config.json
        Args:
            gdrive_config (dict): The 'gdrive' section from config.json
        """
        self.config = gdrive_config
        self.token_dir =  FileHandler.get_paht('.cache') #'.cache'
        self.token_path = os.path.join(self.token_dir, 'gdrive_token.pickle')
        self.service = self._initialize_service(login)
        setup_logging()

    def _initialize_service(self, login=False): 
        creds = None
        
        # Create cache directory if it doesn't exist
        os.makedirs(self.token_dir, exist_ok=True)

        # Load cached token if available
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, 'rb') as token:
                    creds = pickle.load(token)
                logging.debug("Loaded credentials from cache")
            except Exception as e:
                logging.warning(f"Failed to load cached credentials: {e}")

        # If no valid credentials available, refresh or get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logging.debug("Refreshing expired credentials")
                creds.refresh(Request())
            elif login:
                logging.debug("Getting new credentials")
                flow = InstalledAppFlow.from_client_config(
                    {"installed": self.config["installed"]},  # Format required by from_client_config
                    self.SCOPES
                )
                creds = flow.run_local_server(port=self.DEFAULT_PORT)
            
            # Save the credentials for future use
            try:
                with open(self.token_path, 'wb') as token:
                    pickle.dump(creds, token)
                logging.debug("Saved credentials to cache")
            except Exception as e:
                logging.warning(f"Failed to cache credentials: {e}")

        try:
            service = build('drive', 'v3', credentials=creds)
            return service
        except Exception as e:
            logging.error(f"Failed to initialize Google Drive service: {e}")
            raise

    async def get_or_create_backup_folder(self) -> str:
            """Get or create 'backups' folder in Google Drive and return its ID"""
            folder_name = 'backups'
            
            # Buscar si la carpeta ya existe
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(q=query, spaces='drive', fields='files(id)').execute()
            files = results.get('files', [])
            
            if files:
                # Si la carpeta existe, retornar su ID
                return files[0]['id']
            
            # Si no existe, crear la carpeta
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            return folder.get('id')

    async def upload_file(self, file_path: str, destination: str) -> str:
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            # Obtener o crear la carpeta de backups
            backup_folder_id = await self.get_or_create_backup_folder()

            # Preparar los metadatos del archivo incluyendo la carpeta padre
            file_metadata = {
                'name': destination,
                'parents': [backup_folder_id]  # Especificar la carpeta donde se subirá
            }

            media = MediaFileUpload(
                str(file_path),
                resumable=True
            )

            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()

            file_id = file.get('id')
            if not file_id:
                raise Exception("No file ID returned from Google Drive")

            logging.info(f"Successfully uploaded {file_path} to Google Drive 'backups' folder with ID: {file_id}")
            return file_id
            
        except Exception as e:
            logging.error(f"Failed to upload file to Google Drive: {e}")
            raise

    async def download_file(self, file_id: str, destination: str):
        try:
            logging.info(f"Downloading Google Drive file ID: {file_id}")
            
            request = self.service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                if status:
                    logging.info(f"Download Progress: {int(status.progress() * 100)}%")

            fh.seek(0)
            with open(destination, 'wb') as f:
                f.write(fh.read())
                f.flush()

            logging.info(f"Successfully downloaded file to {destination}")
            return True
        except Exception as e:
            logging.error(f"Failed to download file from Google Drive: {e}")
            raise 

    async def verify_connection(self):
        """Verify the current connection is valid."""
        try:
            logging.info("Verifying Google Drive connection...")
            # Try to list files (with minimal fields) to verify connection
            self.service.files().list(pageSize=1, fields="files(id)").execute()
            logging.info("Connection verified successfully")
            return True
        except Exception as e:
            logging.error(f"Connection Google Drive verification failed: {e}")
            raise

    async def refresh_token(self):
        """Refresh the access token."""
        try:
            creds = None
            if os.path.exists(self.token_path):
                with open(self.token_path, 'rb') as token:
                    creds = pickle.load(token)
            
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Save refreshed credentials
                with open(self.token_path, 'wb') as token:
                    pickle.dump(creds, token)
                # Rebuild service with new credentials
                self.service = build('drive', 'v3', credentials=creds)
                logging.info("Token refreshed successfully")
                return True
            else:
                raise Exception("No valid credentials available for refresh")
        except Exception as e:
            logging.error(f"Token refresh failed: {e}")
            raise

    async def authenticate(self):
        """Perform interactive authentication."""
        try:
            flow = InstalledAppFlow.from_client_config(
                {"installed": self.config["installed"]},
                self.SCOPES
            )
            creds = flow.run_local_server(port=self.DEFAULT_PORT)
            
            # Save new credentials
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)
            
            # Rebuild service with new credentials
            self.service = build('drive', 'v3', credentials=creds)
            logging.info("Authentication completed successfully")
            return True
        except Exception as e:
            logging.error(f"Authentication failed: {e}")
            raise 

    async def delete_file(self, file_id: str):
        try:
            self.service.files().delete(fileId=file_id).execute()
            logging.info(f"Successfully deleted file with ID: {file_id} from Google Drive")
        except Exception as e:
            logging.error(f"Failed to delete file from Google Drive: {e}")
            raise 