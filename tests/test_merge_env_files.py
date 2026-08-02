from pathlib import Path

from governance.env_merge import merge_env_files


def test_merge_env_files_uses_secrets_to_override_shared(tmp_path: Path) -> None:
    shared = tmp_path / ".env.shared"
    secrets = tmp_path / ".env.secrets"
    shared.write_text("PRODUCT_ID=shared\nS3_ACCESS_KEY=shared-key\n", encoding="utf-8")
    secrets.write_text("S3_ACCESS_KEY=secret-key\n", encoding="utf-8")

    merged = merge_env_files(shared, secrets)

    assert "PRODUCT_ID=shared" in merged
    assert "S3_ACCESS_KEY=secret-key" in merged
    assert "S3_ACCESS_KEY=shared-key" not in merged
