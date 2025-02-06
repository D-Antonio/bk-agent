from cloud.interfaces.cloud_provider import CloudProvider
import logging
from msal import PublicClientApplication
import logging
from pathlib import Path
import asyncio
import aiohttp
import urllib.parse
import os
import pickle
from utils.file_handler import FileHandler

logger = logging.getLogger(__name__)

class OneDriveClient(CloudProvider):
    # Define required Microsoft Graph API scopes
    SCOPES = [
        'User.Read',
        'Files.ReadWrite',
        'Files.ReadWrite.All',
        'Sites.ReadWrite.All'
    ]
    
    def __init__(self, client_id: str, client_secret: str, login:bool=False):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_dir = FileHandler.get_paht('.cache') #'.cache'
        self.token_path = os.path.join(self.token_dir, 'onedrive_token.pickle')
        self.app = PublicClientApplication(
            client_id=self.client_id,
            authority="https://login.microsoftonline.com/common",
            token_cache=self._load_token_cache()
        )
        self._credentials = None
        self._token = None
        self.login = login

    def _load_token_cache(self):
        from msal import SerializableTokenCache
        cache = SerializableTokenCache()
        
        os.makedirs(self.token_dir, exist_ok=True)
        
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as file:
                cache.deserialize(pickle.load(file))
        return cache

    def _save_token_cache(self):
        if self.app.token_cache.has_state_changed:
            os.makedirs(self.token_dir, exist_ok=True)
            
            with open(self.token_path, 'wb') as file:
                pickle.dump(self.app.token_cache.serialize(), file)

    def _initialize_client(self):
        try:
            logging.info("Starting client initialization...")
            # Try to get token silently first
            accounts = self.app.get_accounts()
            if accounts:
                result = self.app.acquire_token_silent(self.SCOPES, account=accounts[0])
                if result:
                    self._token = result["access_token"]
                    logging.info("Token retrieved from cache")
                    self._save_token_cache()  # Save any cache changes
                    return

            # If silent token acquisition fails, get interactive
            logging.info("No cached token found, starting interactive authentication...")
            if self.login:
                result = self.app.acquire_token_interactive(
                    scopes=self.SCOPES,
                    prompt="select_account"
                )
            
            if "access_token" in result:
                logging.info("Access token obtained successfully")
                self._token = result["access_token"]
                self._save_token_cache()  # Save the token cache
            else:
                logging.info("Failed to obtain access token")
                raise Exception("Could not obtain access token")
            
        except Exception as e:
            logging.error(f"Failed to initialize OneDrive client: {e}")
            raise

    def _clean_path(self, path: str) -> str:
        return path.strip()

    async def _get_folder_items(self, folder_path: str):
        """Get items in a OneDrive folder."""
        try:
            encoded_path = urllib.parse.quote(folder_path)
            url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{encoded_path}:/children"
            headers = {"Authorization": f"Bearer {self._token}"}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('value', [])
                    else:
                        error_text = await response.text()
                        raise Exception(f"Failed to get folder items: {error_text}")
        except Exception as e:
            logging.info(f"Error getting folder items: {e}")
            raise

    async def _download_file_async(self, file_id: str, destination_path: str):
        """Download a file from OneDrive."""
        try:
            logging.info(f"\n>>> Starting download process for file ID: {file_id}")
            logging.info(f">>> Destination path: {destination_path}")
            
            # Ensure the destination directory exists
            directory = os.path.dirname(destination_path)
            logging.info(f">>> Creating directory if not exists: {directory}")
            os.makedirs(directory, exist_ok=True)
            logging.info(">>> Directory ready")

            # Get download URL
            url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content"
            logging.info(f">>> Requesting file from URL: {url}")
            headers = {"Authorization": f"Bearer {self._token}"}

            async with aiohttp.ClientSession() as session:
                logging.info(">>> Making download request...")
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        logging.info(">>> File content received successfully")
                        content = await response.read()
                        logging.info(f">>> Read {len(content)} bytes")
                        
                        logging.info(f">>> Writing file to: {destination_path}")
                        with open(destination_path, 'wb') as f:
                            f.write(content)
                        logging.info(f">>> File downloaded successfully to {destination_path}")
                        return destination_path
                    else:
                        error_text = await response.text()
                        logging.info(f">>> ERROR: Download failed with status {response.status}")
                        logging.info(f">>> Error details: {error_text}")
                        raise Exception(f"Download failed: {error_text}")

        except Exception as e:
            logging.info(f">>> ERROR: Error downloading file: {e}")
            raise

    async def restore_folder_async(self, backup_info: dict, destination_path: str):
        """Restore an entire folder from OneDrive."""
        try:
            logging.info(f"\n=== Starting folder restoration process ===")
            logging.info(f"Destination path: {destination_path}")
            
            # Ensure the destination folder exists
            logging.info(f"Creating destination folder if not exists: {destination_path}")
            os.makedirs(destination_path, exist_ok=True)
            logging.info("Destination folder ready")

            # Get the list of files from the backup info
            files = backup_info.get('files', [])
            logging.info(f"\nFound {len(files)} files to restore")
            
            for index, file_info in enumerate(files, 1):
                file_id = file_info.get('id')
                relative_path = file_info.get('path')
                
                if file_id and relative_path:
                    logging.info(f"\n--- Processing file {index}/{len(files)} ---")
                    logging.info(f"File ID: {file_id}")
                    logging.info(f"Original path: {relative_path}")
                    
                    # Construct the full destination path
                    full_path = os.path.join(destination_path, os.path.basename(relative_path))
                    logging.info(f"Will restore to: {full_path}")
                    
                    try:
                        # Download the file
                        await self._download_file_async(file_id, full_path)
                        logging.info(f"File {index} restored successfully")
                    except Exception as e:
                        logging.info(f"ERROR: Failed to restore file {index}: {e}")
                        raise
                else:
                    logging.info(f"\nWARNING: Skipping file {index} due to missing information")
                    logging.info(f"File info: {file_info}")

            return True

        except Exception as e:
            logging.error(f"OneDrive - ERROR: Error restoring folder: {e}")
            raise

    def restore_backup(self, backup_info: dict, destination_path: str):
        """Synchronous wrapper for folder restoration."""
        try:
            logging.info("Starting backup restoration process")
            
            destination_path = self._clean_path(destination_path)
            logging.info(f"Cleaned destination path: {destination_path}")
            
            logging.info("\nValidating backup info...")
            if not isinstance(backup_info, dict):
                raise ValueError(f"Invalid backup info type: {type(backup_info)}")
            
            if 'files' not in backup_info:
                raise ValueError("Backup info does not contain 'files' key")
            
            logging.info("Backup info validated successfully")
            logging.info(f"Found {len(backup_info.get('files', []))} files to restore")
            
            # Run the async restoration
            logging.info("\nStarting async restoration process...")
            success = asyncio.run(self.restore_folder_async(backup_info, destination_path))
            
            if success:
                logging.info(f"Backup restored successfully to {destination_path}")
                return True
            
            logging.warning("\nWARNING: Restoration completed but returned False")
            return False

        except Exception as e:
            logging.error(f"Failed to restore backup: {e}")
            raise

    async def _upload_file_async(self, file_path: Path, destination: str):
        """Async method to upload file to OneDrive."""
        try:
            # Limpiar la ruta de destino
            destination = self._clean_path(destination)
            
            logging.info(f"Starting async upload for file: {file_path}")
            logging.info(f"Reading file content...")
            with open(file_path, 'rb') as upload_file:
                file_content = upload_file.read()
            logging.info(f"File content read successfully ({len(file_content)} bytes)")

            try:
                # Construir y codificar la ruta completa para el archivo
                full_path = f"{destination}/{file_path.name}"
                encoded_path = urllib.parse.quote(full_path)
                logging.info(f"Uploading to path: {full_path}")
                logging.info(f"Encoded path: {encoded_path}")

                # Preparar la URL y headers para la petición
                url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{encoded_path}:/content"
                headers = {
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/octet-stream"
                }

                logging.info(f"Making request to URL: {url}")
                # Realizar la petición HTTP
                async with aiohttp.ClientSession() as session:
                    async with session.put(url, headers=headers, data=file_content) as response:
                        if response.status == 200 or response.status == 201:
                            result = await response.json()
                            logging.info("File content uploaded successfully")
                            return result.get('id')
                        else:
                            error_text = await response.text()
                            raise Exception(f"Upload failed with status {response.status}: {error_text}")

            except Exception as e:
                logging.info(f"Error during file operations: {e}")
                logging.error(f"Error during file operations: {e}")
                raise

        except Exception as e:
            logging.info(f"Error during async file upload: {e}")
            logging.error(f"Error during async file upload: {e}")
            raise

    async def upload_file(self, file_path: str, destination: str) -> str:
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            # Obtener el ID del archivo subido
            result = await self._upload_file_async(file_path, destination)
            
            if not result or not isinstance(result, str):
                raise Exception("No file ID returned from OneDrive")

            logging.info(f"Successfully uploaded {file_path} to OneDrive with ID: {result}")
            return result  # Devolver el ID del archivo de OneDrive
        except Exception as e:
            logging.error(f"Failed to upload file to OneDrive: {e}")
            raise

    async def download_file(self, file_id: str, destination: str):
        try:
            logging.info(f"Downloading OneDrive file ID: {file_id}")
            
            url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content"
            headers = {
                "Authorization": f"Bearer {self._token}",
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(destination, 'wb') as f:
                            f.write(content)
                        logging.info(f"Successfully downloaded file to {destination}")
                        return True
                    else:
                        error_text = await response.text()
                        raise Exception(f"Download failed with status {response.status}: {error_text}")
        except Exception as e:
            logging.error(f"Failed to download file from OneDrive: {e}")
            raise

    def restore_file(self, file_id: str, destination_path: str):
        """Synchronous wrapper for file download."""
        try:
            logging.info(f"\nStarting file restore process...")
            logging.info(f"File ID: {file_id}")
            logging.info(f"Destination: {destination_path}")

            # Run async download in event loop
            result_path = asyncio.run(self.download_file(file_id, destination_path))
            
            logging.info(f"Restore completed successfully to: {result_path}")
            logging.info(f"Successfully restored file to {result_path}")
            return result_path

        except Exception as e:
            logging.error(f"Failed to restore file: {e}")
            raise 

    async def refresh_token(self):
        """Refresh the access token using the refresh token."""
        try:
            logging.info("Attempting to refresh token...")
            accounts = self.app.get_accounts()
            if accounts:
                result = self.app.acquire_token_silent(self.SCOPES, account=accounts[0])
                if result:
                    self._token = result["access_token"]
                    self._save_token_cache()
                    logging.info("Token refreshed successfully")
                    return True
            raise Exception("No valid accounts found for token refresh")
        except Exception as e:
            logging.error(f"OneDrive - Token refresh failed: {e}")
            raise

    async def authenticate(self):
        """Perform interactive authentication."""
        try:
            logging.info("Starting interactive authentication...")
            result = self.app.acquire_token_interactive(
                scopes=self.SCOPES,
                prompt="select_account"
            )
            
            if "access_token" in result:
                logging.info("Access token obtained successfully")
                self._token = result["access_token"]
                self._save_token_cache()
                return True
            else:
                raise Exception("Failed to obtain access token")
        except Exception as e:
            logging.error(f"Authentication OneDrive failed: {e}")
            raise

    async def verify_connection(self):
        """Verify the current connection is valid."""
        try:
            logging.info("Verifying OneDrive connection...")
            
            # First ensure we have a valid token
            if not self._token:
                logging.info("No token found, initializing client...")
                self._initialize_client()
                
            if not self._token:
                raise Exception("Failed to obtain valid token")

            url = "https://graph.microsoft.com/v1.0/me/drive"
            headers = {"Authorization": f"Bearer {self._token}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        logging.info("Connection verified successfully")
                        return True
                    elif response.status == 401:  # Unauthorized - try to refresh token
                        logging.info("Token expired, attempting refresh...")
                        await self.refresh_token()
                        # Retry verification with new token
                        return await self.verify_connection()
                    else:
                        error_text = await response.text()
                        raise Exception(f"Connection verification failed: {error_text}")
        except Exception as e:
            logging.error(f"Connection verification OneDrive failed: {e}")
            
            raise 

    async def delete_file(self, file_id: str):
        try:
            url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}"
            headers = {"Authorization": f"Bearer {self._token}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.delete(url, headers=headers) as response:
                    if response.status in [200, 204]:
                        logging.info(f"Successfully deleted file with ID: {file_id} from OneDrive")
                    else:
                        error_text = await response.text()
                        raise Exception(f"Failed to delete file: {error_text}")
        except Exception as e:
            logging.error(f"Failed to delete file from OneDrive: {e}")
            raise 