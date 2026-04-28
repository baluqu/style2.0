from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


class UploadStorageError(RuntimeError):
    pass


def _supabase_storage_enabled() -> bool:
    return bool(
        current_app.config.get("SUPABASE_USE_STORAGE")
        and current_app.config.get("SUPABASE_URL")
        and current_app.config.get("SUPABASE_SERVICE_ROLE_KEY")
        and current_app.config.get("SUPABASE_STORAGE_BUCKET")
    )


def _get_supabase_client():
    client = current_app.extensions.get("stylebridge_supabase")
    if client is not None:
        return client

    try:
        from supabase import create_client
    except ImportError as exc:  # pragma: no cover - depends on optional prod dependency
        raise UploadStorageError(
            "Supabase storage is enabled, but the 'supabase' package is not installed."
        ) from exc

    client = create_client(
        current_app.config["SUPABASE_URL"],
        current_app.config["SUPABASE_SERVICE_ROLE_KEY"],
    )
    current_app.extensions["stylebridge_supabase"] = client
    return client


def _public_url_from_response(response) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        for key in ("publicUrl", "publicURL", "public_url"):
            value = response.get(key)
            if value:
                return value
        data = response.get("data")
        if isinstance(data, dict):
            for key in ("publicUrl", "publicURL", "public_url"):
                value = data.get(key)
                if value:
                    return value
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        for key in ("publicUrl", "publicURL", "public_url"):
            value = data.get(key)
            if value:
                return value
    return ""


def _content_type_for(file_storage: FileStorage, filename: str) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return (file_storage.mimetype or guessed or "application/octet-stream").strip()


def _save_local_upload(file_storage: FileStorage, save_name: str, subdirectory: str) -> str:
    upload_root = Path(current_app.config["UPLOAD_FOLDER"])
    target_dir = upload_root / subdirectory if subdirectory else upload_root
    target_dir.mkdir(parents=True, exist_ok=True)
    save_path = target_dir / save_name
    file_storage.save(str(save_path))
    if subdirectory:
        return f"/static/uploads/{subdirectory}/{save_name}"
    return f"/static/uploads/{save_name}"


def _save_supabase_upload(file_storage: FileStorage, save_name: str, subdirectory: str) -> str:
    client = _get_supabase_client()
    bucket = current_app.config["SUPABASE_STORAGE_BUCKET"]
    object_path = f"{subdirectory}/{save_name}" if subdirectory else save_name
    payload = file_storage.read()
    file_storage.stream.seek(0)

    if not payload:
        raise UploadStorageError("The uploaded file was empty.")

    options = {"content-type": _content_type_for(file_storage, save_name), "upsert": "false"}

    try:
        client.storage.from_(bucket).upload(object_path, payload, file_options=options)
        public_url = _public_url_from_response(client.storage.from_(bucket).get_public_url(object_path))
    except Exception as exc:  # pragma: no cover - depends on external service
        raise UploadStorageError(f"Upload to Supabase Storage failed: {exc}") from exc

    if not public_url:
        raise UploadStorageError("Supabase Storage upload succeeded, but no public URL was returned.")

    return public_url


def save_uploaded_file(file_storage: FileStorage, prefix: str, *, subdirectory: str = "") -> str:
    if not file_storage or not file_storage.filename:
        return ""

    filename = secure_filename(file_storage.filename)
    if not filename:
        return ""

    save_name = f"{prefix}_{uuid.uuid4().hex[:8]}_{filename}"
    if _supabase_storage_enabled():
        return _save_supabase_upload(file_storage, save_name, subdirectory)
    return _save_local_upload(file_storage, save_name, subdirectory)
