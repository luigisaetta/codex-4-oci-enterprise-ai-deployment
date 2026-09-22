# OCI hosted deployment container requirements

Source: [Oracle: Preparing Container Images](https://docs.oracle.com/en-us/iaas/Content/generative-ai/prepare-artifacts.htm).
Verified against the source on 2026-09-22. This is a summary of the requirements
relevant to this build workflow; it is not a remote deployment certification.

* Build for `linux/amd64`.
* Listen on `0.0.0.0`, port `8080`.
* Expose `GET /ready` and return HTTP 200 when ready; return non-200 otherwise.
* Expose `GET /health` and return HTTP 200 when healthy; return non-200 for an
  unrecoverable or deadlocked application. Probe content type is `application/json`.
* Write local files only under `/tmp`; the rest of the filesystem is read-only.
* Define the startup command in the Dockerfile with `CMD` or `ENTRYPOINT`;
  custom entry point commands are unsupported.
* Volume mapping is unsupported. Containers must be stateless because local file
  data is not preserved across redeployment or node replacement.

## Local tooling references

Reviewed 2026-09-22:

* [buildx inspect](https://docs.docker.com/reference/cli/docker/buildx/inspect/):
  builder selection and advertised platforms. A `*` marks manually set platforms.
* [buildx build](https://docs.docker.com/reference/cli/docker/buildx/build/):
  `--platform`, `--load`, `--file`, builder selection, and cache controls.
* [docker run](https://docs.docker.com/reference/cli/docker/container/run/):
  read-only root filesystem, tmpfs, port publishing, and container lifecycle.
* [Rancher Desktop emulation](https://docs.rancherdesktop.io/ui/preferences/virtual-machine/emulation/):
  VZ/Rosetta and QEMU options on macOS.

The binary-wheel constraint, semantic image tags, and script exit codes are
repository policies defined in [Spec 001](../../../specs/001-skill-oci-agent-build.md).
