from typing import Literal

import googlemaps
from pydantic import BaseModel, SecretStr

from backend.data.block import Block, BlockCategory, BlockOutput, BlockSchema
from backend.data.model import (
    APIKeyCredentials,
    CredentialsField,
    CredentialsMetaInput,
    SchemaField,
)
from backend.integrations.providers import ProviderName

TEST_CREDENTIALS = APIKeyCredentials(
    id="01234567-89ab-cdef-0123-456789abcdef", # Change this
    provider="google_maps",
    api_key=SecretStr("mock-google-maps-api-key"),
    title="Mock Google Maps API key",
    expires_at=None,
)
TEST_CREDENTIALS_INPUT = {
    "provider": TEST_CREDENTIALS.provider,
    "id": TEST_CREDENTIALS.id,
    "type": TEST_CREDENTIALS.type,
    "title": TEST_CREDENTIALS.type,
}

class GoogleDriveImageUploaderBlock(Block):
    class Input(BlockSchema):
        folder_id: str = SchemaField(description="ID of the Google Drive folder containing images.")
        auth_token: str = SchemaField(description="OAuth2 token or API key for Google Drive authentication.")

    class Output(BlockSchema):
        uploaded_files: list[str] = SchemaField(description="List of paths or URLs of uploaded images.")
        error: str = SchemaField(description="Error message, if any.", default="")

    def __init__(self):
        super().__init__(
            id="unique-block-id",
            description="Uploads images from a Google Drive folder.",
            categories={BlockCategory.MULTIMEDIA},
            input_schema=GoogleDriveImageUploaderBlock.Input,
            output_schema=GoogleDriveImageUploaderBlock.Output,
        )

    def run(
        self,
        input_data: Input,
        *,
        graph_exec_id: str,
        **kwargs,
    ) -> BlockOutput:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
        import io

        try:
            # Authenticate with Google Drive
            drive_service = build('drive', 'v3', credentials=input_data.auth_token)

            # List files in the folder
            query = f"'{input_data.folder_id}' in parents and mimeType contains 'image/'"
            results = drive_service.files().list(q=query).execute()
            files = results.get('files', [])

            if not files:
                yield "error", "No image files found in the specified folder."
                return

            # Download files
            downloaded_files = []
            for file in files:
                request = drive_service.files().get_media(fileId=file['id'])
                file_path = f"{graph_exec_id}_{file['name']}"
                with io.FileIO(file_path, 'wb') as fh:
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    while not done:
                        _, done = downloader.next_chunk()

                downloaded_files.append(file_path)

            yield "uploaded_files", downloaded_files

        except Exception as e:
            yield "error", str(e)
