# Crow Platform source deployment

This deployment path is intended for a checked-out Crow Platform repository on a server.

## Install backbone and all first-party modules

Create and activate a virtual environment, then install the backbone:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[export]"
```

Install every first-party module declared by `modules/module_layout_manifest.json`:

```bash
crow-install-modules
```

The installer resolves `requires_modules` before dependants. Adding a future first-party module therefore requires the module package and its canonical layout-manifest entry, not another server-specific pip command.

Review the plan without changing the environment:

```bash
crow-install-modules --dry-run
```

## Workbench network binding

Workbench remains loopback-only by default:

```text
CROW_PLATFORM_BIND_ADDRESS=127.0.0.1
CROW_PLATFORM_PORT=8080
```

For an explicitly approved LAN deployment, export the desired values before starting Workbench, for example:

```bash
export CROW_PLATFORM_BIND_ADDRESS=192.168.5.168
export CROW_PLATFORM_PORT=8080
crow-workbench
```

The repository does not silently expose Workbench on all interfaces. TLS, reverse proxying, service supervision and external authentication remain separate deployment concerns.
