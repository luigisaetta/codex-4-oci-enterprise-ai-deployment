<!-- BEGIN oci-agent-skills: customer name (Spec 020) -->
## Customer name in demos

These rules apply to every task in this repository, with or without a skill.

* Name the customer only with the name approved for demos: `Supremo`, unless
  the OCI agent skills' `.env` sets `DEMO_CUSTOMER_NAME`. To read it, run
  `python <tool-home>/scripts/tool_config.py demo-customer`, where
  `<tool-home>` is the folder two levels above the real path of
  `~/.agents/skills/oci-agent-new`.
* The real customer's name may be used only in the conversation and in online
  searches about the customer's business. Never write it to any file of this
  repository, in any form (full name, abbreviation, domain, or e-mail
  address), nor in a commit message.
* When the user names the real customer, reply once, without repeating the
  name: "In every file and in the demo the customer is called <demo name>."
* Never copy from online results product names, brands, people, addresses, or
  figures that identify the real customer.
* Before finishing a task that changed files, search the changed files for the
  real name, case-insensitively, and replace every match with the demo name.

## IAM changes

* Never create, change, or delete dynamic groups, policies, groups, users, or
  identity domains, even when asked to fix a problem or to do "whatever is
  needed". IAM belongs to the tenancy administrator.
* When a release fails on permissions (for example "the container image could
  not be accessed or validated"), stop: report what is missing, citing
  `docs/iam-policies.md` in the tool home, and ask the user to send it to the
  tenancy administrator.
* The read-only lookups that the OCI agent skills' scripts make (compartment
  and region) are part of normal operation. Any other IAM inspection, such as
  reading dynamic groups or policies, only when the user asks for it.
* Never write wrapper scripts or alternative commands that bypass the OCI
  agent skills.

## Changing the agent code

* When you change the code of this agent, with or without a skill, follow the
  code rules (Q rules) in
  `<tool-home>/skills/oci-agent-new/references/agent-guidelines.md`; for an
  agent with a database (`deploy.storage` in `agent.yaml`), Q8 and Q9 in
  particular.
<!-- END oci-agent-skills: customer name -->
