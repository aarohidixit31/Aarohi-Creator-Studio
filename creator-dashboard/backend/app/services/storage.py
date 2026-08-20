import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


@dataclass
class StorageResult:
    url: str
    backend: str
    public_id: str | None = None


def cloudinary_is_configured() -> bool:
    return all(
        os.getenv(name)
        for name in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")
    )


def storage_status() -> dict:
    environment = os.getenv("ENVIRONMENT", "development").casefold()
    return {
        "backend": "cloudinary" if cloudinary_is_configured() else "local",
        "cloudinary_configured": cloudinary_is_configured(),
        "production_safe": cloudinary_is_configured(),
        "environment": environment,
    }


def store_image(
    contents: bytes,
    *,
    original_filename: str,
    content_type: str,
    local_directory: Path,
    local_url_prefix: str,
    local_extension: str,
) -> StorageResult:
    if cloudinary_is_configured():
        return _upload_cloudinary(
            contents, original_filename, content_type,
            resource_type="image", folder="aarohi-inframe/media-kit",
        )

    if os.getenv("ENVIRONMENT", "development").casefold() == "production":
        raise RuntimeError(
            "Cloudinary is required in production. Configure CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET."
        )

    filename = f"{uuid4().hex}{local_extension}"
    local_directory.mkdir(parents=True, exist_ok=True)
    (local_directory / filename).write_bytes(contents)
    return StorageResult(
        url=f"{local_url_prefix.rstrip('/')}/{filename}",
        backend="local",
    )


def store_document(
    contents: bytes,
    *,
    original_filename: str,
    content_type: str,
    local_directory: Path,
    local_url_prefix: str,
    local_extension: str,
) -> StorageResult:
    if cloudinary_is_configured():
        return _upload_cloudinary(
            contents, original_filename, content_type,
            resource_type="raw", folder="aarohi-inframe/agreements",
        )
    if os.getenv("ENVIRONMENT", "development").casefold() == "production":
        raise RuntimeError("Cloudinary is required in production for permanent document uploads")
    filename = f"{uuid4().hex}{local_extension}"
    local_directory.mkdir(parents=True, exist_ok=True)
    (local_directory / filename).write_bytes(contents)
    return StorageResult(url=f"{local_url_prefix.rstrip('/')}/{filename}", backend="local")


def _upload_cloudinary(
    contents: bytes,
    original_filename: str,
    content_type: str,
    *,
    resource_type: str,
    folder: str,
) -> StorageResult:
    cloud_name = os.environ["CLOUDINARY_CLOUD_NAME"]
    api_key = os.environ["CLOUDINARY_API_KEY"]
    api_secret = os.environ["CLOUDINARY_API_SECRET"]
    endpoint = f"https://api.cloudinary.com/v1_1/{cloud_name}/{resource_type}/upload"
    boundary = f"----aarohi-dashboard-{uuid4().hex}"
    body = _multipart_body(
        boundary,
        fields={"folder": folder},
        file_field=("file", original_filename or "media-kit.webp", content_type, contents),
    )
    credentials = base64.b64encode(f"{api_key}:{api_secret}".encode("utf-8")).decode("ascii")
    request = Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
            "User-Agent": "aarohi-creator-dashboard/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Cloudinary rejected the upload ({exc.code}): {detail}") from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise RuntimeError(f"Cloudinary upload failed: {exc}") from exc

    secure_url = result.get("secure_url")
    if not secure_url:
        raise RuntimeError("Cloudinary upload succeeded without returning a secure URL")
    return StorageResult(
        url=secure_url,
        backend="cloudinary",
        public_id=result.get("public_id"),
    )


def _multipart_body(
    boundary: str,
    *,
    fields: dict[str, str],
    file_field: tuple[str, str, str, bytes],
) -> bytes:
    chunks = []
    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            str(value).encode(),
            b"\r\n",
        ])
    field_name, filename, content_type, contents = file_field
    safe_filename = Path(filename).name.replace('"', "")
    chunks.extend([
        f"--{boundary}\r\n".encode(),
        (
            f'Content-Disposition: form-data; name="{field_name}"; '
            f'filename="{safe_filename}"\r\n'
        ).encode(),
        f"Content-Type: {content_type}\r\n\r\n".encode(),
        contents,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    return b"".join(chunks)
