# Unplanned features

Features that the project deliberately does **not** plan to support today.
Each entry records the decision, what the tool does instead, and what would
make us reconsider it. Planned work is in [TODO.md](TODO.md); an entry moves
back there only with a new decision.

| Feature | Decided | Instead |
| --- | --- | --- |
| [Private endpoints and custom networking](#private-endpoints-and-custom-networking) | 2026-10-14 | Public endpoints with Oracle-managed networking |

## Private endpoints and custom networking

Moved from TODO item 15 on 2026-10-14.

* **What it would be:** Hosted Applications with a private endpoint, or with
  customer networking (a VCN and a subnet of the user's tenancy), for example
  through a `private` manifest profile.
* **What the tool does:** every application has a public endpoint and
  Oracle-managed networking (`endpointMode: PUBLIC`, `networkMode: MANAGED`).
  Access is restricted with the `public-idcs` profile (identity-domain
  tokens) when needed. The deploy skill states that it omits custom
  networking.
* **Workaround:** an agent that needs a private endpoint or customer
  networking is created and configured outside the skills, with the OCI
  Console or the OCI CLI; the skills do not manage it.
* **Reconsider if:** a real use case needs it and the service capabilities
  (VCN, subnet, private endpoint) are verified against the documentation.
