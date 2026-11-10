# Bootstrap design

**Status: design only; hardware not provisioned.**

Own first boot, guest configuration, K3s initialization/upgrades and cluster recovery. Run from outside the target cluster so reconstruction is possible when K3s is absent.

Future cloud-init/Ansible inputs include versions, inventory, trusted access, node roles, API endpoint, token handling, CNI and disabled competing components. No installer or playbook is present.

See the [authoritative design](../docs/design/v3/delivery-and-environments.md) and [construction-plan index](../docs/design/v3/README.md).
