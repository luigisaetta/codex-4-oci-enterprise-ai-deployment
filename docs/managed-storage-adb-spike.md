# Managed ADB storage for Hosted Applications: spike results

This note records a live investigation of the managed storage of OCI
Generative AI Hosted Applications, with the Autonomous Database (ADB) storage
type. The goal was to learn whether an agent can save data (for example
catalogs and results) in an Oracle database without managing one.

The deploy supports managed ADB storage through `deploy.storage`
([Spec 026](../specs/026-managed-adb-storage-at-creation.md)), and
`oci-agent-new` generates agents that use it
([Spec 027](../specs/027-agents-with-a-database.md)).

## Scope

* Date: 2026-10-14. Region `eu-frankfurt-1`, one compartment.
* Tools: OCI CLI 3.95.0, OCI Python SDK 2.188.0, `python-oracledb` thin mode.
* A throwaway FastAPI agent, outside this repository, with `GET /db-info`.
  The endpoint reported only metadata (variable names, a sanitized connect
  string, file paths and sizes), never credential values. On each call it
  created the table `spike_items` if missing, inserted one row, and returned
  the row count and the database version. The table name and structure were
  chosen in the agent code (see Database schema).
* Public endpoint without authentication, Oracle-managed networking, one
  deployment. All resources were deleted at the end (see Cleanup).

Everything below was observed in one session; it was not repeated in other
regions or tenancies.

## How it works

1. Create the storage. It was `ACTIVE` immediately:

   ```bash
   oci --region <region> generative-ai hosted-application-storage create \
     --compartment-id <compartment-ocid> --storage-type ADB \
     --display-name <storage-name>
   ```

2. Link it when the application is **created**, naming the environment
   variable that receives the connect string:

   ```bash
   oci --region <region> generative-ai hosted-application create ... \
     --storage-configs '[{"environmentVariableKey":"DB_CONNECT_STRING","storageId":"<storage-ocid>"}]'
   ```

   `hosted-application update` has no `--storage-configs` option, so storage
   cannot be added to an existing application.

3. At run time the container receives:

   * the connect string in the named variable. It points to a local TLS
     endpoint, so no wallet is needed:

     ```text
     (DESCRIPTION=(RETRY_COUNT=20)(RETRY_DELAY=3)
       (ADDRESS=(PROTOCOL=TCPS)(HOST=127.0.0.1)(PORT=1521))
       (CONNECT_DATA=(SERVICE_NAME=<database>_high.adb.oraclecloud.com))
       (SECURITY=(SSL_SERVER_DN_MATCH=NO)))
     ```

   * the database user and password as files, mounted as a Kubernetes-style
     secret volume: `/mnt/secrets/adb/username` and
     `/mnt/secrets/adb/password`.

4. `python-oracledb` in thin mode (no Oracle Client) connects with
   `oracledb.connect(user=..., password=..., dsn=os.environ["DB_CONNECT_STRING"])`.

The database runs in the service tenancy: it is not reachable from outside
the application, and there is no administrator access to it.

## Database schema

The service provides an empty schema: it creates no tables and offers no
schema definition or migration mechanism. The agent creates its own tables.

In the spike the agent created this table on each request, ignoring the
"name is already used" error (ORA-00955) so that later requests did not
fail:

```sql
begin
  execute immediate 'create table spike_items (
    id number generated always as identity,
    note varchar2(100))';
exception
  when others then
    if sqlcode != -955 then raise; end if;
end;
```

The `create table` succeeded, so the database user provided by the service
can create tables in its schema. Other privileges (views, sequences,
procedures, indexes) were not tested.

## Results

| Test | Observed |
| --- | --- |
| Application creation with storage | `CREATING` for about 4 minutes the first time; about 1.5 minutes when the storage already existed. |
| Connection | Works. Oracle Database **19c** (19.33.0.1.0), not 23ai. |
| Initial schema | Empty; the table was created by the agent code. |
| Table create, insert, count | Works; rows accumulate across requests (1, 2, 3). |
| New version of the same application | Released with `scripts/deploy_hosted_application.sh --apply` (case "New version"). The data **survived** (4 rows). |
| Storage link after creation | The storage reports the application in `application-ids`. |
| Delete the active deployment alone | Refused: `409 Conflict`, "Hosted deployment cannot be deleted … because it is not active", although it was `ACTIVE`. |
| Delete the application | Succeeded in about 1 minute and deleted the deployment too. |
| Storage after application deletion | **Still `ACTIVE`**, `application-ids` empty. The Oracle documentation states that the storage is deleted with the application; this was not the case. |
| New application linked to the same storage | Works; same database (same service name). The data was **gone**: the row count restarted at 1. |
| Delete the storage | `hosted-application-storage delete` succeeded in about 2.5 minutes; state `DELETED`. |

## Conclusions

* Managed ADB storage is the simplest way to give an agent an Oracle
  database: no database to provision, no wallet, no network rules, no
  credentials to handle in the manifest.
* Data survives new versions of the same application, but not the deletion
  of the application, even when a new application reuses the same storage.
  Treat deleting an application as losing its data.
* The agent owns its schema: it must create its tables idempotently (at
  startup or on first use) and handle schema changes between versions,
  because the data of earlier versions stays in place.
* The storage has its own life cycle: delete it explicitly after the
  application, otherwise it stays active.
* Storage must be declared at application creation; adding it later means
  creating a new application, which loses the data.
* 19c features only: for example, no `VECTOR` data type.

## Open questions

* Cost of the managed storage, and whether an orphaned storage is billed.
* Why the data disappears: the schema may be emptied when the application is
  deleted, or each application may receive a new user in the same database.
* Privileges of the database user beyond creating tables.
* Behavior with several replicas, and connection limits.
* Whether the `POSTGRESQL` and `CACHE` storage types behave the same way.

## Impact on the tool

Spec 026 implements the deploy side: the storage section in the manifest,
creation of the storage and `--storage-configs` at application creation, the
refusal to change storage on an existing application, and the documented
cleanup. Spec 027 covers the agent code: credentials read from the
files, idempotent schema creation by the agent, schema changes between
versions, lazy connection, and verification without a local database.

## Cleanup

Deleted at the end of the session: both applications and their deployments,
the storage, the OCIR repository of the spike image, and the local Docker
images.

## Sources

* [Managed storage for Hosted Applications](https://docs.oracle.com/en-us/iaas/Content/generative-ai/managed-storage.htm),
  consulted 2026-10-14.
* [Creating a Hosted Application](https://docs.oracle.com/en-us/iaas/Content/generative-ai/create-application.htm),
  consulted 2026-10-14.
* OCI CLI 3.95.0 help of `generative-ai hosted-application create`,
  `hosted-application update`, and `hosted-application-storage`.
