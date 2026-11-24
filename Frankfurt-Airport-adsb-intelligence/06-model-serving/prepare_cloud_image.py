"""Stage the serving image with one verified release, without cloud access."""

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMAGE_FILES = ("app.py", "pyproject.toml", "uv.lock")


def prepare_context(release_dir: Path, trusted_manifest: Path, output: Path) -> dict:
    manifest_bytes = trusted_manifest.read_bytes()
    if (release_dir / "manifest.json").read_bytes() != manifest_bytes:
        raise ValueError("local release manifest differs from the trusted manifest")
    manifest = json.loads(manifest_bytes)
    if manifest["schema_version"] != "frankfurt-airport-model-release-v1" or manifest["artifact"]["path"] != "model.pkl":
        raise ValueError("unsupported serving release format")
    model = (release_dir / "model.pkl").read_bytes()
    model_sha256 = hashlib.sha256(model).hexdigest()
    if model_sha256 != manifest["artifact"]["sha256"]:
        raise ValueError("model bytes differ from the trusted SHA-256")
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(output)
    with tempfile.TemporaryDirectory(dir=output.parent) as stage_dir:
        stage = Path(stage_dir) / "context"
        release = stage / "release"
        release.mkdir(parents=True)
        for name in IMAGE_FILES:
            shutil.copyfile(HERE / name, stage / name)
        (release / "manifest.json").write_bytes(manifest_bytes)
        (release / "model.pkl").write_bytes(model)
        dockerfile = (HERE / "Dockerfile").read_text(encoding="utf-8").rstrip()
        (stage / "Dockerfile").write_text(
            f"{dockerfile}\n\nCOPY --chmod=0444 release/manifest.json release/model.pkl /release/\n"
            f"ENV MODEL_MANIFEST_SHA256={manifest_sha256}\n", encoding="utf-8",
        )
        stage.rename(output)
    return {"model_release_id": manifest["model_release_id"], "model_manifest_sha256": manifest_sha256,
            "model_artifact_sha256": model_sha256}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--trusted-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare_context(args.release_dir, args.trusted_manifest, args.output), sort_keys=True))
    except (KeyError, OSError, ValueError) as exc:
        parser.exit(1, f"prepare cloud image: {exc}\n")


if __name__ == "__main__":
    main()
