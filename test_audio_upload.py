"""Test script to debug audio upload issue."""

import io
from google import genai
from google.genai import types
from config import AppConfig

def test_webm_upload():
    """Test uploading a webm file to Gemini."""
    config = AppConfig()
    client = genai.Client(api_key=config.gemini_api_key)

    # Create a minimal valid WebM file (Opus audio in WebM container)
    # This is a minimal WebM header + silence
    minimal_webm = bytes.fromhex(
        '1a45dfa3' + '01000000' + '00000014' + '42868100' +
        '00000000'  # Minimal EBML header (will fail but shows the error)
    )

    # Write to temp file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f:
        f.write(minimal_webm)
        temp_path = f.name

    try:
        print(f"Attempting to upload webm file: {temp_path}")

        # Try upload with explicit MIME type
        uploaded = client.files.upload(
            file=temp_path,
            config=types.UploadFileConfig(
                mime_type='audio/webm',
                display_name='test_audio'
            )
        )
        print(f"SUCCESS: Uploaded file: {uploaded.name}")
        print(f"URI: {uploaded.uri}")
        print(f"MIME type: {uploaded.mime_type}")

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        import os
        os.unlink(temp_path)

if __name__ == '__main__':
    test_webm_upload()
