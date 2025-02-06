from cloud.interfaces.cloud_provider import CloudProvider
from azure.storage.blob import BlobServiceClient
from azure.identity import ClientSecretCredential
from azure.core.exceptions import AzureError
import logging
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)

class AzureClient(CloudProvider):
    def __init__(self, connection_string: str, container_name: str, tenant_id: str = None, client_id: str = None, client_secret: str = None):
        self.container_name = container_name
        self.connection_string = connection_string
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        # Azure SDK handles credential caching automatically
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_client = self.blob_service_client.get_container_client(container_name)

    async def upload_file(self, file_path: str, destination: str):
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            # Generar un ID único para el archivo
            file_id = str(uuid.uuid4())
            
            # Usar el ID como parte del path en Azure
            blob_path = f"{destination}/{file_id}/{file_path.name}"

            blob_client = self.container_client.get_blob_client(blob_path)
            with open(file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)
            
            logging.info(f"Successfully uploaded {file_path} to Azure Blob Storage")
            return file_id  # Devolver el ID único
        except Exception as e:
            logging.error(f"Failed to upload file to Azure: {e}")
            raise

    async def download_file(self, file_id: str, destination: str):
        try:
            # Buscar el blob usando el file_id en la estructura de carpetas
            prefix = f"backups/{file_id}/"
            blobs = self.container_client.list_blobs(name_starts_with=prefix)
            
            # Obtener el primer blob que coincida con el prefix
            blob = next(blobs, None)
            if not blob:
                raise FileNotFoundError(f"No file found with ID: {file_id}")

            # Obtener el blob client para el archivo específico
            blob_client = self.container_client.get_blob_client(blob.name)
            
            logging.info(f"Downloading Azure blob: {blob.name}")
            
            # Descargar el archivo
            with open(destination, "wb") as file:
                data = blob_client.download_blob()
                file.write(data.readall())
            
            logging.info(f"Successfully downloaded file to {destination}")
            return True
        except Exception as e:
            logging.error(f"Failed to download file from Azure: {e}")
            raise 

    async def authenticate(self):
        """Autenticación básica (si es necesario)."""
        try:
            # Verifica si la cadena de conexión es válida (esto es opcional si ya está gestionado por Azure SDK).
            if not self.connection_string:
                raise ValueError("Connection string is missing.")
            logging.info("Authentication successful with connection string.")
            # Si se requiere autenticar con Azure AD:
            if self.tenant_id and self.client_id and self.client_secret:
                credential = ClientSecretCredential(
                    tenant_id=self.tenant_id,
                    client_id=self.client_id,
                    client_secret=self.client_secret
                )
                self.blob_service_client = BlobServiceClient(account_url=self.connection_string, credential=credential)
                logging.info("Authentication with Azure AD completed successfully.")
            else:
                logging.info("Authentication completed using connection string.")
        except Exception as e:
            logging.error(f"Authentication failed: {e}")
            raise

    async def refresh_token(self):
        """Refresca el token si se usa autenticación basada en Azure AD."""
        try:
            if self.tenant_id and self.client_id and self.client_secret:
                credential = ClientSecretCredential(
                    tenant_id=self.tenant_id,
                    client_id=self.client_id,
                    client_secret=self.client_secret
                )
                logging.info("Refreshing token...")
                # Esto en realidad refresca automáticamente el token de forma interna cuando se hace una solicitud.
                return credential
            else:
                logging.warning("No Azure AD credentials found. Refresh token is not required.")
        except Exception as e:
            logging.error(f"Failed to refresh token: {e}")
            raise

    async def verify_connection(self):
        """Verifica que la conexión a Azure Blob Storage sea válida."""
        try:
            # Realizamos una operación simple, como listar los blobs del contenedor, para verificar la conexión.
            blobs = list(self.container_client.list_blobs())
            if not blobs:
                raise AzureError(f"No blobs found in the container {self.container_name}.")
            logging.info(f"Successfully connected to Azure Blob Storage container {self.container_name}.")
            return True
        except AzureError as e:
            logging.error(f"Failed to verify connection to Azure Blob Storage: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error during connection verification: {e}")
            raise

    async def delete_file(self, file_id: str):
        try:
            # Construct the blob path from the file ID
            prefix = f"backups/{file_id}/"
            blobs = self.container_client.list_blobs(name_starts_with=prefix)
            
            for blob in blobs:
                blob_client = self.container_client.get_blob_client(blob.name)
                blob_client.delete_blob()
            
            logging.info(f"Successfully deleted file with ID: {file_id} from Azure Blob Storage")
        except Exception as e:
            logging.error(f"Failed to delete file from Azure: {e}")
            raise