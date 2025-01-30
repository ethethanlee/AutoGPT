import io
from typing import List
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from pydantic import SecretStr
from backend.data.block import Block, BlockCategory, BlockOutput, BlockSchema
from backend.data.model import SchemaField
from backend.util.file import MediaFile, get_exec_file_path, store_media_file


class GoogleDriveImageUploaderBlock(Block):
    class Input(BlockSchema):
        folder_id: str = SchemaField(
            description="ID of the Google Drive folder containing images."
        )
        auth_token: SecretStr = SchemaField(
            description="OAuth2 token or API key for Google Drive authentication."
        )

    class Output(BlockSchema):
        uploaded_files: List[str] = SchemaField(
            description="List of paths to the stored image files."
        )
        error: str = SchemaField(description="Error message, if any.", default="")

    def __init__(self):
        super().__init__(
            id="7f6e326d-9c5d-422d-bb2d-3e4b3af9a932",  # Unique UUID
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
        try:
            # Initialize the Google Drive API client
            credentials = input_data.auth_token.get_secret_value()
            drive_service = build("drive", "v3", developerKey=credentials)

            # Fetch image files from the specified folder
            query = f"'{input_data.folder_id}' in parents and mimeType contains 'image/'"
            response = drive_service.files().list(q=query).execute()
            files = response.get("files", [])

            query2 = f"'{input_data.folder_id}' in parents"
            response2 = drive_service.files().list(q=query2).execute()
            all_files = response2.get("files", [])

            non_image_files = [file.get("name") for file in all_files if not file.get("mimeType", "").startswith("image/")]

            if not files:
                yield "error", f"No image files found in the specified folder. wahh. alle files: {all_files}"
                return

            # if not files:
            #     yield "error", "No image files found in the specified folder." 
            #     return

            # Download and store each image
            stored_files = []
            for file in files:
                file_id = file.get("id")
                file_name = file.get("name")
                if not file_id or not file_name:
                    continue

                # Download the file content
                request = drive_service.files().get_media(fileId=file_id)
                local_temp_path = f"{graph_exec_id}_{file_name}"
                with io.FileIO(local_temp_path, "wb") as fh:
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    while not done:
                        _, done = downloader.next_chunk()

                # Use `store_media_file` to save the downloaded file securely
                stored_file_path = store_media_file(
                    graph_exec_id=graph_exec_id, file=local_temp_path, return_content=False
                )
                stored_files.append(stored_file_path)

            yield "uploaded_files", stored_files

        except Exception as e:
            yield "error", f"An error occurred: {str(e)}"
