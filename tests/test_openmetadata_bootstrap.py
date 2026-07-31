from __future__ import annotations

from pathlib import Path

import yaml


def test_openmetadata_compose_bootstraps_settings_before_server() -> None:
    compose = yaml.safe_load(Path("docker/docker-compose.openmetadata.yml").read_text())
    services = compose["services"]

    bootstrap = services["om-bootstrap"]
    assert bootstrap["depends_on"]["om-migrate"]["condition"] == "service_completed_successfully"
    assert "emailConfiguration" in bootstrap["command"][2]

    server = services["openmetadata-server"]
    assert server["depends_on"]["om-bootstrap"]["condition"] == "service_completed_successfully"
    assert (
        server["environment"]["AUTHORIZER_ADMIN_PRINCIPALS"]
        == "[${OPENMETADATA_ADMIN_PRINCIPAL:-admin}]"
    )
    assert all(port.startswith("127.0.0.1:") for port in server["ports"])
