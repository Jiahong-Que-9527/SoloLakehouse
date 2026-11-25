"""Publish one approved Gold release to Landing with a create-only identity."""

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path

import google.auth
from google.api_core.exceptions import PreconditionFailed
from google.auth import impersonated_credentials
from google.cloud import storage

from ingest_release import digest, verify_release


CLOUD_PLATFORM = "https://www.googleapis.com/auth/cloud-platform"
PAYLOAD_FILES = ("contract.yaml", "data/part-0001.parquet")
CONTROL_FILES = ("manifest.json", "validation.json", "approval.json", "_SUCCESS")


def approved_release_id(local_dir: Path) -> str:
    manifest = json.loads((local_dir / "manifest.json").read_text(encoding="utf-8"))
    release_id = manifest["release_id"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", release_id):
        raise ValueError(f"invalid release ID: {release_id!r}")
    if set(manifest["files"]) != set(PAYLOAD_FILES):
        raise ValueError("expected a contract and one Parquet file in the manifest")
    verdict = verify_release(local_dir)
    if not verdict.ok:
        raise ValueError(verdict.reason)
    for name in CONTROL_FILES[1:]:
        record = json.loads((local_dir / name).read_text(encoding="utf-8"))
        if record.get("release_id") != release_id:
            raise ValueError(f"{name} does not match release {release_id}")
    return release_id


def upload_release(local_dir: Path, writer, reader) -> dict:
    release_id = approved_release_id(local_dir)
    result = {
        "release_id": release_id,
        "landing": f"gs://{writer.name}/releases/{release_id}",
        "created": [],
        "reused": [],
    }
    # Publish the completion marker after every other object is in place.
    for name in (*PAYLOAD_FILES, *CONTROL_FILES):
        source = local_dir / name
        object_name = f"releases/{release_id}/{name}"
        try:
            writer.blob(object_name).upload_from_filename(source, if_generation_match=0)
        except PreconditionFailed:
            # A retry may find an object created by an earlier attempt. The
            # reader confirms the bytes while the writer keeps create-only IAM.
            with tempfile.TemporaryFile() as remote:
                reader.blob(object_name).download_to_file(remote)
                remote.seek(0)
                remote_sha = hashlib.file_digest(remote, "sha256").hexdigest()
            if remote_sha != digest(source):
                raise ValueError(f"Landing checksum mismatch: {object_name}") from None
            result["reused"].append(name)
        else:
            result["created"].append(name)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release", type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument("--landing-bucket", required=True)
    parser.add_argument("--uploader", required=True, help="create-only service account email")
    parser.add_argument("--reader", help="reader service account email (defaults to ADC)")
    args = parser.parse_args()

    source, _ = google.auth.default(scopes=[CLOUD_PLATFORM])
    writer = impersonated_credentials.Credentials(
        source, args.uploader, target_scopes=[CLOUD_PLATFORM])
    reader = source
    if args.reader:
        reader = impersonated_credentials.Credentials(
            source, args.reader, target_scopes=[CLOUD_PLATFORM])
    write_bucket = storage.Client(project=args.project, credentials=writer).bucket(args.landing_bucket)
    read_bucket = storage.Client(project=args.project, credentials=reader).bucket(args.landing_bucket)
    try:
        result = upload_release(args.release, write_bucket, read_bucket)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"release upload failed: {exc}\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
