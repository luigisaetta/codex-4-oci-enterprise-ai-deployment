# Spec 026: managed ADB storage at creation

Status: draft.
Date: 2026-10-14.
Amends [Spec 003](003-skill-oci-agent-deploy.md) (deploy) and
[Spec 006](006-agent-manifest-configuration.md) (manifest). Input:
[managed ADB storage spike](../docs/managed-storage-adb-spike.md).
[Spec 027](027-agents-with-a-database.md) defines the agent side.

## Problem

Agents can keep data only in memory or in read-only files packaged in the
image. A demo that records what it does (for example the orders of an
express-order agent) loses it on every restart, and each replica has its own
copy. Hosted Applications offer managed storage: an Oracle Autonomous
Database that the service creates and connects to the application, with no
database, wallet, network, or credentials to manage. The deploy script omits
`--storage-configs` on purpose, so the tool cannot use it.

## Scope

* An optional `deploy.storage` section in `agent.yaml` for one managed ADB
  storage.
* On a first release, the deploy finds or creates the storage and links it
  when it **creates** the Hosted Application. The plan shows it.
* On an existing application, a difference between the manifest and the
  application stops the deploy.
* Documented cleanup: the storage is deleted separately, after the
  application.
* Bash and PowerShell twins; offline tests; documentation.

## Non-goals

* Storage types `POSTGRESQL` and `CACHE`; more than one storage per
  application.
* Adding, changing, or removing the storage of an existing application (the
  service does not support it, F3).
* A teardown command (TODO item 13). Cleanup stays a documented manual step.
* Moving data between applications, backups, exports, or access to the
  database from outside the application (the service does not allow it, F7).
* Databases that the user manages (own ADB, customer networking).

## Platform facts

Observed in the spike of 2026-10-14 (eu-frankfurt-1, OCI CLI 3.95.0), unless
another source is given.

| # | Fact | Evidence |
| --- | --- | --- |
| F1 | `hosted-application-storage create --compartment-id --storage-type ADB --display-name` creates a storage; it was `ACTIVE` immediately. `hosted-application-storage-collection list-hosted-application-storages --compartment-id` lists storages with `display-name` and `lifecycle-state`. | Spike. |
| F2 | `hosted-application create --storage-configs '[{"environmentVariableKey":"<NAME>","storageId":"<ocid>"}]'` links the storage. Afterwards the storage reports the application in `application-ids`. | Spike. |
| F3 | `hosted-application update` has no `--storage-configs` option. | OCI CLI 3.95.0 help. |
| F4 | At run time the variable `<NAME>` holds a TCPS connect string to a local endpoint (no wallet); user and password are files in `/mnt/secrets/adb/`. | Spike. |
| F5 | The data survives a new version of the same application. One database serves all replicas of the application. | Spike; the shared database follows from F2 (one storage per application). |
| F6 | Deleting the application deletes its deployments but **not** the storage, which stays `ACTIVE` with empty `application-ids`. This contradicts the [managed storage page](https://docs.oracle.com/en-us/iaas/Content/generative-ai/managed-storage.htm) (consulted 2026-10-14), which states that the storage is deleted with the agent. | Spike. |
| F7 | A new application linked to an orphaned storage reaches the same database, but the data of the deleted application is gone. | Spike. |
| F8 | `hosted-application-storage delete` takes about 2.5 minutes and ends `DELETED`. | Spike. |
| F9 | Creating an application with a new storage took about 4 minutes, against about 1.5 minutes with an existing storage. | Spike. |
| F10 | The [IAM policies page](https://docs.oracle.com/en-us/iaas/Content/generative-ai/iam-policies.htm) (consulted 2026-10-14) lists no storage resource type of its own; it links "API-Level Permissions for Application Storage". The spike ran as a tenancy administrator. | Documentation; not verified for an operator. |

## Intended behavior

1. **Manifest.**

   ```yaml
   deploy:
     storage:
       type: ADB
       connect_env: DB_CONNECT_STRING
   ```

   * `type` is required and must be `ADB`.
   * `connect_env` is optional, default `DB_CONNECT_STRING`; it must be a
     valid variable name, must not be one of the names in `runtime.env`, and
     must not be a tool tenancy key (`OCI_*`, `OCIR_*`).
   * Unknown fields are rejected.
2. **Storage name.** `<application_name>-storage`, in the deployment
   compartment.
3. **Plan.** A line `Storage: ADB, connect string in <connect_env>` followed
   by `create <name>` or `reuse <name> (not linked to any application)`, or
   `Storage: none`. The plan states that application creation with storage
   takes several minutes (F9).
4. **First release.** Before creating the application, the deploy lists the
   non-deleted storages named `<name>`:
   * none: it creates one and waits until it is `ACTIVE`, with the bounded
     wait of [Spec 012](012-reliable-deploy-wait.md);
   * one, `ACTIVE`, with empty `application-ids`: it reuses it. This makes a
     rerun after a failed application creation safe (no duplicate). The
     storage is empty for the new application (F7);
   * one linked to an application, more than one, or one in another state:
     exit 20 with the state found, and no mutation.

   Then it adds `--storage-configs` to `hosted-application create`. Without
   the section, nothing changes: no storage is listed or created.
5. **Existing application.** The deploy compares the manifest with the
   application's `storage-configs`: section present and application without
   storage, section absent and application with storage, or another
   `connect_env`, stop with exit 20 and the message "Existing Hosted
   Application storage differs from the manifest; storage can be set only
   when the application is created. Creating a new application starts with
   an empty database." Otherwise the release continues as today; a new
   version keeps the data (F5).
6. **Manifest helper.** `agent_manifest.py storage-config` prints the
   storage section as JSON, or nothing when absent;
   `storage-matches` reads the application JSON on stdin and exits 0 when
   manifest and application agree, 1 otherwise. Same pattern as Spec 023.
7. **Release record.** The deploy prints the storage OCID with the other
   resource references.
8. **Permissions.** A `NotAuthorizedOrNotFound` error on the storage
   operations stops the deploy with the OCI message and the IAM rule of
   Spec 019: report and stop, never change IAM.

## Cleanup (documented, manual)

Data is lost when the application is deleted (F7). To remove an agent with
storage: delete the Hosted Application (this also deletes its deployments;
the active deployment cannot be deleted alone), then delete the storage,
which otherwise stays active (F6, F8):

```bash
oci --region <region> generative-ai hosted-application delete --hosted-application-id <application-ocid>
```

```bash
oci --region <region> generative-ai hosted-application-storage delete --hosted-application-storage-id <storage-ocid>
```

## Documentation

* `docs/agent-manifest-reference.md`: the `deploy.storage` section, the
  rule "storage only at creation", and data loss on application deletion.
* `skills/oci-agent-deploy/SKILL.md`: plan line, storage cases, the stop on
  a difference; the Limitations section no longer says that
  `--storage-configs` is omitted.
* `docs/iam-policies.md`: the operator permission for storage once verified
  (acceptance criterion 3).
* `docs/managed-storage-adb-spike.md`: link to this specification.
* `CHANGELOG.md`.

## Tests (offline)

* `tests/test_agent_manifest.py` or a new module: valid section; default
  `connect_env`; rejected values (other types, invalid names, collision with
  `runtime.env`, tool keys, unknown fields); `storage-config` and
  `storage-matches`.
* Deploy release cases, both script families, with the fake OCI CLI:
  first release creates the storage and sends `--storage-configs`; reuse of
  an orphaned storage; a linked storage or two storages stop with exit 20
  and no mutation; without the section no storage call is made; an existing
  application with a storage difference stops with exit 20; the plan lines.

## Acceptance criteria

1. The offline tests, Black, Pylint, and pytest pass; links resolve.
2. Live, with the acceptance agent of Spec 027: a first release creates the
   storage and the application; a read-only `hosted-application get` shows
   the storage link; a new version keeps the data; a rerun of the deploy
   plan shows "Already released" and creates no second storage.
3. Live, as an operator who is not a tenancy administrator: the release
   succeeds with the policies of `docs/iam-policies.md`, or the missing
   permission is identified and documented by the administrator.

## Verification record

None yet.
