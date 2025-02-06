import logging
import os
from pathlib import Path
import tempfile
import shutil
import json
from datetime import datetime
import time
import random
import asyncio
import sqlite3

from encryption.encryption_handler import EncryptionHandler
from data.database_handler import DatabaseHandler

logger = logging.getLogger(__name__)

class BackupManager:
    def __init__(self, encryption_handler: EncryptionHandler, config):
        """Initialize the backup manager."""
        #self.cloud_provider = cloud_provider
        self.encryption_handler = encryption_handler
        self.config = config

    async def set_cloud_provider(self, provider_name: str):
        """Set the cloud provider based on the selected option."""
        valid_providers = ["gdrive", "onedrive", "aws", "azure"]
        if provider_name not in valid_providers:
            ValueError(f"Provider {provider_name} not supported. Valid providers are: {', '.join(valid_providers)}")
        logging.info("Setting cloud provider...")
        try:
            if provider_name == "aws":
                from cloud.providers.aws_client import AWSClient
                aws_config = self.config.get('aws', {})
                self.cloud_provider = AWSClient(
                    aws_access_key=aws_config.get('aws_access_key'),
                    aws_secret_key=aws_config.get('aws_secret_key'),
                    bucket_name=aws_config.get('bucket_name'),
                    region=aws_config.get('region', 'us-east-1')
                )
                logging.info("AWS client initialized successfully")
            elif provider_name == "gdrive":
                from cloud.providers.gdrive_client import GoogleDriveClient
                gdrive_config = self.config.get('gdrive', {})
                self.cloud_provider = GoogleDriveClient(gdrive_config, True)
                logging.info("Google Drive client initialized successfully")
            elif provider_name == "onedrive":
                from cloud.providers.onedrive_client import OneDriveClient
                onedrive_config = self.config.get('onedrive', {})
                self.cloud_provider = OneDriveClient(
                    client_id=onedrive_config.get('client_id'),
                    client_secret=onedrive_config.get('client_secret'),
                    login=True
                )
                logging.info("OneDrive client initialized successfully")

            # Verify provider connection and handle token refresh
            try:
                await self.cloud_provider.verify_connection()
            except Exception as auth_error:
                try:
                    logging.info("Authentication failed. Attempting token refresh...")
                    await self.cloud_provider.refresh_token()
                except Exception as refresh_error:
                    logging.info(f"Token refresh failed: {refresh_error}")
                    logging.info("Attempting to re-authenticate...")
                    await self.cloud_provider.authenticate()

            logging.info(f"Using cloud provider: {provider_name}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to initialize {provider_name} provider: {e}")
            raise

    async def create_backup(self, source_path, encrypt=False):
        """Create a backup of the specified path."""
        try:
            logging.info(f"\n=== Starting backup process for: {source_path} ===")
            source_path = Path(source_path)
            if not source_path.exists():
                raise FileNotFoundError(f"Source path not found: {source_path}")

            # Create a temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / source_path.name
                logging.info(f"Created temporary directory: {temp_dir}")

                # If it's a directory, create a zip file
                if source_path.is_dir():
                    logging.info(f"Creating zip archive of {source_path}")
                    shutil.make_archive(str(temp_path), 'zip', source_path)
                    temp_path = Path(str(temp_path) + '.zip')
                else:
                    # If it's a file, just copy it
                    logging.info("Copying file to temporary location")
                    shutil.copy2(source_path, temp_path)

                # Encrypt if requested
                if encrypt:
                    logging.info("Encrypting backup...")
                    with open(temp_path, 'rb') as f:
                        data = f.read()
                    encrypted_data = self.encryption_handler.encrypt(data)
                    temp_path = temp_path.with_suffix(temp_path.suffix + '.encrypted')
                    with open(temp_path, 'wb') as f:
                        f.write(encrypted_data)
                    logging.info("Encryption completed")

                # Upload to cloud storage
                logging.info("Uploading to cloud storage...")
                backup_id = await self.cloud_provider.upload_file(
                    str(temp_path),
                    destination="backups"
                )

                logging.info(f"Backup completed successfully with ID: {backup_id}")
                return backup_id

        except Exception as e:
            logging.error(f"Error creating backup: {e}")
            raise

    async def restore_backup(self, backup_info):
        """Restore a backup to the specified destination."""
        try:
            logging.info(f"\n=== Starting restore process for backup ID: {backup_info['backup_id']} ===")
            
            destination = Path(backup_info['source_path'])

            # {'backup_id': 'BDBFF16B7EDF4034!s5efbdd4bfbad4c43966b45839321e34f', 'source_path': 'C:\\Users\\Antonio\\Pictures\\Roblox', 'timestamp': '2025-01-17 23:49:58', 'is_encrypted': 1, 'is_directory': 1, 'original_name': 'Roblox', 'provider': 'onedrive'}
            logging.info(f"backup_info: {backup_info}")

            logging.info(f"File is encrypted: {backup_info['is_encrypted']}")
            
            # Use the original name if available
            final_destination = destination / backup_info['original_name'] if backup_info['original_name'] else destination

            # Create destination directory if it doesn't exist
            logging.info(f"Creating destination directory: {destination}")
            destination.mkdir(parents=True, exist_ok=True)

            # Create a temporary directory for the download
            temp_dir = Path(tempfile.mkdtemp())
            logging.info(f"Using temporary directory for download: {temp_dir}")

            try:
                # Create a specific temporary file for the download
                temp_file = temp_dir / f"download_{backup_info['backup_id']}"
                logging.info(f"Downloading to temporary file: {temp_file}")
                
                logging.info(f"Set provider")
                await self.set_cloud_provider(backup_info['provider'])

                # Download the file using the cloud provider's download_file method
                logging.info(f"Starting file download from cloud")
                success = await self.cloud_provider.download_file(backup_info['backup_id'], str(temp_file))
                
                if not success:
                    raise Exception("Failed to download file")

                logging.info(f"File downloaded successfully to: {temp_file}")

                # Verify that the file exists
                if not temp_file.exists():
                    raise Exception(f"Downloaded file not found at {temp_file}")

                # Read the file content
                with open(temp_file, 'rb') as f:
                    file_content = f.read()

                # If the file is encrypted, decrypt it
                if backup_info['is_encrypted']:
                    logging.info("Decrypting file...")
                    try:
                        file_content = self.encryption_handler.decrypt(file_content)
                        logging.info("Decryption completed successfully")
                    except Exception as e:
                        logging.error(f"Error during decryption: {e}")
                        raise Exception(f"Failed to decrypt file: {e}")

                # If it was a directory (zip file)
                if backup_info['is_directory']:
                    logging.info(f"Processing zip archive")
                    try:
                        # Create a temporary zip file
                        temp_zip = temp_dir / f'temp_{backup_info['backup_id']}.zip'
                        with open(temp_zip, 'wb') as f:
                            f.write(file_content)
                        
                        # Extract the zip
                        logging.info(f"Extracting zip to: {destination}")
                        shutil.unpack_archive(str(temp_zip), str(destination))
                        
                    except Exception as e:
                        logging.error(f"Error processing zip archive: {e}")
                        raise
                else:
                    # Write the file to the final destination
                    logging.info(f"Writing file to: {final_destination}")
                    with open(final_destination, 'wb') as f:
                        f.write(file_content)

                logging.info(f"Restore completed successfully to: {destination}")
                return True

            finally:
                # Clean up the temporary directory
                try:
                    if temp_dir.exists():
                        shutil.rmtree(temp_dir)
                        logging.info(f"Temporary directory cleaned up: {temp_dir}")
                except Exception as e:
                    logging.warning(f"Warning: Could not delete temporary directory: {e}")

        except Exception as e:
            logging.error(f"Error restoring backup: {e}")
            raise

    async def delete_backup(self, backup_id: str, provider_name: str):
        """Delete a backup from the cloud provider and database."""
        try:
            logging.info(f"Deleting backup with ID: {backup_id} from provider: {provider_name}")
            
            logging.info(f"Set provider")
            await self.set_cloud_provider(provider_name)
            # Delete from cloud provider
            await self.cloud_provider.delete_file(backup_id)
            
            logging.info(f"Backup {backup_id} deleted successfully")
        except Exception as e:
            logging.error(f"Failed to delete backup {backup_id}: {e}")
            raise 