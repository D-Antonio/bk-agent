from cloud.providers.gdrive_client import GoogleDriveClient
from cloud.providers.onedrive_client import OneDriveClient
from cloud.providers.aws_client import AWSClient

class CloudFactory:
    @staticmethod
    def get_provider(provider_name, credentials):
        if provider_name == "gdrive":
            return GoogleDriveClient(credentials)
        elif provider_name == "onedrive":
            return OneDriveClient(credentials.get('client_id'), credentials.get('client_secret'))
        elif provider_name == "aws":
            return AWSClient(
                credentials.get('aws_access_key'),
                credentials.get('aws_secret_key'),
                credentials.get('bucket_name'),
                credentials.get('region', 'us-east-1')
            )

        else:
            ValueError(f"Unsupported cloud provider: {provider_name}") 

    @staticmethod
    async def check_provider_status(provider_name, credentials):
        try:
            provider = CloudFactory.get_provider(provider_name, credentials)
            await provider.verify_connection()
            return True
        except Exception:
            return False

    @staticmethod
    def get_available_providers():
        return {
            "gdrive": "Google Drive",
            "onedrive": "OneDrive",
            "aws": "AWS S3",
        } 