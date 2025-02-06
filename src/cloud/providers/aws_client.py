from cloud.interfaces.cloud_provider import CloudProvider
import boto3
import logging
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)

class AWSClient(CloudProvider):
    def __init__(self, aws_access_key: str, aws_secret_key: str, bucket_name: str, region: str = 'us-east-1'):
        self.bucket_name = bucket_name
        # AWS SDK (boto3) handles credential caching automatically
        # in ~/.aws/credentials and ~/.aws/config
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=region
        )

    async def upload_file(self, file_path: str, destination: str):
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            # Generar un ID único para el archivo
            file_id = str(uuid.uuid4())
            
            # Usar el ID como parte del path en S3
            s3_path = f"{destination}/{file_id}/{file_path.name}"

            self.s3_client.upload_file(
                str(file_path),
                self.bucket_name,
                s3_path
            )
            logging.info(f"Successfully uploaded {file_path} to S3")
            return file_id  # Devolver el ID único
        except Exception as e:
            logging.error(f"Failed to upload file to S3: {e}")
            raise

    async def download_file(self, file_id: str, destination: str):
        try:
            # Buscar el objeto en el bucket usando el file_id en la estructura de carpetas
            prefix = f"backups/{file_id}/"
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )

            # Obtener el primer objeto que coincida con el prefix
            if 'Contents' not in response or not response['Contents']:
                raise FileNotFoundError(f"No file found with ID: {file_id}")

            # Obtener la key completa del primer objeto
            s3_key = response['Contents'][0]['Key']
            
            logging.info(f"Downloading S3 object: {s3_key}")
            
            # Descargar el archivo
            self.s3_client.download_file(
                self.bucket_name,
                s3_key,
                destination
            )
            
            logging.info(f"Successfully downloaded file to {destination}")
            return True
        except Exception as e:
            logging.error(f"Failed to download file from S3: {e}")
            raise 

    async def verify_connection(self):
        try:
            # Attempt to list buckets to verify connection
            self.s3_client.list_buckets()
            logging.info("AWS S3 connection verified successfully")
            return True
        except Exception as e:
            logging.error(f"Failed to verify AWS S3 connection: {e}")
            raise

    async def refresh_token(self):
        # AWS SDK (boto3) handles token refresh automatically
        logging.info("AWS S3 token refresh is handled automatically by boto3")
        return True

    async def authenticate(self):
        # AWS SDK (boto3) handles authentication automatically
        logging.info("AWS S3 authentication is handled automatically by boto3")
        return True 

    async def delete_file(self, file_id: str):
        try:
            # Construct the S3 key from the file ID
            prefix = f"backups/{file_id}/"
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    self.s3_client.delete_object(Bucket=self.bucket_name, Key=obj['Key'])
            
            logging.info(f"Successfully deleted file with ID: {file_id} from S3")
        except Exception as e:
            logging.error(f"Failed to delete file from S3: {e}")
            raise 