# Logging in to the container registry (OCIR)

To publish an agent's image, the push skill sends it to **OCI Container
Registry (OCIR)**. Your container engine (Docker, or Podman on Windows) must be
logged in to OCIR first. You need three values:

| Value | What it is | Example |
| --- | --- | --- |
| **Registry** | The OCIR address of your region. | `fra.ocir.io` |
| **Username** | Your tenancy namespace and your user name, joined with `/`. | `ansh81vru1zp/jdoe@acme.com` |
| **Password** | An **auth token** that you generate in the OCI Console. Not your Console password. | (a random string, shown once) |

This page explains how to find each one, step by step. All examples use
placeholder values; replace them with yours. Never paste an auth token into
the Codex chat or into any file.

## 1. Find the registry address

The registry address depends on the region in `OCI_REGION` of the tool's
`.env`. Its form is `<region-key>.ocir.io`:

| Region (`OCI_REGION`) | Registry |
| --- | --- |
| `eu-frankfurt-1` | `fra.ocir.io` |
| `us-chicago-1` | `ord.ocir.io` |
| `us-ashburn-1` | `iad.ocir.io` |
| `us-phoenix-1` | `phx.ocir.io` |

For any other region, see the region table in
[Preparing for Container Registry](https://docs.oracle.com/en-us/iaas/Content/Registry/Concepts/registryprerequisites.htm),
or let the tool compute it, from the tool home with the environment active:

```bash
scripts/resolve_ocir_registry.sh
```

On Windows, in PowerShell 7: `./scripts/resolve_ocir_registry.ps1`. It prints
the registry address, for example `fra.ocir.io`.

## 2. Build the username

The username has two or three parts:

```text
<tenancy-namespace>/<username>
<tenancy-namespace>/<identity-domain>/<username>
```

### 2a. Find the tenancy namespace

The namespace is a short, auto-generated string, for example `ansh81vru1zp`.
Find it in either way:

* **OCI CLI** (if step 4 of Getting started is done):

  ```bash
  oci os ns get
  ```

  It prints `{"data": "ansh81vru1zp"}`: the namespace is the value of `data`.
* **Console**: Profile menu (top right) → **Tenancy** → **Object storage
  namespace**.

In some older tenancies the namespace is the tenancy name in lower case, for
example `acme-dev`.

### 2b. Find your user name, and whether it needs the identity domain

Open the **Profile** menu (the person icon, top right of the OCI Console) and
look at the name shown at the top:

| The Profile menu shows | Your OCIR username |
| --- | --- |
| Only your user name, for example `jdoe@acme.com` | `<namespace>/jdoe@acme.com` |
| A domain and your user name, for example `oracleidentitycloudservice/jdoe@acme.com` | `<namespace>/oracleidentitycloudservice/jdoe@acme.com` |

In other words: write the namespace, a `/`, and then exactly what the Profile
menu shows. Users who sign in through their company's single sign-on
(federated users) usually see the domain, often `oracleidentitycloudservice`.

Examples, with the namespace `ansh81vru1zp`:

```text
ansh81vru1zp/jdoe@acme.com
ansh81vru1zp/oracleidentitycloudservice/jdoe@acme.com
```

The user name is case-sensitive as shown in the Console; it is usually your
e-mail address.

### 2c. Put it in the tool's `.env`

Write the complete username in `OCIR_USERNAME` (step 5 of Getting started):

```dotenv
OCIR_USERNAME=ansh81vru1zp/oracleidentitycloudservice/jdoe@acme.com
```

The username is not a secret; the auth token is, and it never goes in `.env`.

## 3. Generate an auth token (the password)

1. In the OCI Console, open the **Profile** menu (top right) and select
   **User settings** (in some tenancies **My profile**, or your account name).
2. Open the **Tokens and keys** tab, go to the **Auth tokens** section, and
   select **Generate token**.
3. Enter a description, for example `OCIR login from my laptop`. Do not put
   confidential information in it.
4. Select **Generate token**. The token is shown **only once**: copy it now
   into your password manager.
5. Close the dialog.

Each user can have **at most two** auth tokens. If you lose one, delete it in
the same section and generate a new one. A token works for your user only, so
it must belong to the same user as the username of step 2.

## 4. Log in

You do not need to do this by hand: during the push, Codex shows you the exact
command with your registry and username. Run it yourself in a terminal and
type the auth token only when the engine asks for the password, never in the
Codex chat.

With Docker (macOS, Linux, or Windows):

```bash
docker login --username 'ansh81vru1zp/oracleidentitycloudservice/jdoe@acme.com' fra.ocir.io
```

With Podman on Windows, in PowerShell 7:

```powershell
podman login --username 'ansh81vru1zp/oracleidentitycloudservice/jdoe@acme.com' fra.ocir.io
```

Expected: `Password:` appears; paste the auth token (nothing is shown while you
type) and press Enter. The engine prints `Login Succeeded`.

Use single quotes around the username, as above, so that the shell does not
interpret any character in it. Never pass the token with `--password` or
`-p`: it would stay in your shell history.

The engine keeps the login, so you normally log in once per workstation, and
again only after the token is deleted or the login is removed. Docker may warn
that it stores the credential unencrypted in its configuration file; Docker
Desktop normally uses the system keychain instead. To remove the stored login:

```bash
docker logout fra.ocir.io
```

## 5. If the login or the push fails

| Message | Likely cause | What to do |
| --- | --- | --- |
| `unauthorized`, `authentication required`, or `invalid username/password` at login | Wrong username format, or wrong token. | Rebuild the username from step 2 (check the identity domain part), and paste the token again. If you no longer have the token, generate a new one. |
| The same error with a username you are sure of | The token belongs to another user, or it was deleted. | Generate a new token while signed in as the same user. |
| `denied: requested access to the resource is denied` at push | Login is fine, but your user cannot push to that compartment. | Ask your tenancy administrator for the operator policies in [IAM policies](iam-policies.md#setup-for-the-administrator). |
| `no such host` or a connection error | Wrong registry address, or no network. | Check the registry with `scripts/resolve_ocir_registry.sh`. |
| Login worked for another region, not this one | Logins are per registry address. | Log in again to the registry of your current `OCI_REGION`. |

## Sources

Verified on 2026-10-12:

* [Pushing Images Using the Docker CLI](https://docs.oracle.com/en-us/iaas/Content/Registry/Tasks/registrypushingimagesusingthedockercli.htm):
  username formats, the Profile menu showing `<domain-name>/<username>`, and
  the auth token as password.
* [Getting an Auth Token](https://docs.oracle.com/en-us/iaas/Content/Registry/Tasks/registrygettingauthtoken.htm):
  Console steps, the token shown only once, and the limit of two tokens per
  user.
* [Preparing for Container Registry](https://docs.oracle.com/en-us/iaas/Content/Registry/Concepts/registryprerequisites.htm):
  registry addresses by region (for example `fra.ocir.io` for
  `eu-frankfurt-1`, `ord.ocir.io` for `us-chicago-1`).
* [Logging in to Oracle Cloud Infrastructure Registry](https://docs.oracle.com/en-us/iaas/Content/Functions/Tasks/functionslogintoocir.htm):
  `docker login <region-key>.ocir.io` and the note on unencrypted credential
  storage.
