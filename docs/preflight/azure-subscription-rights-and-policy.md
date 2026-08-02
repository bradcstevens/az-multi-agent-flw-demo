# Preflight: Azure subscription rights and policy

**Verified:** 2026-08-01 · **Issue:** [#7](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/7) · **Spec:** [#1](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/1)

**Verdict: the vanilla (non-WAF) deployment flavour is permitted.** Nothing in the target
subscription denies public network access, so the WAF flavour is **not** forced and the
infrastructure ticket can proceed against `main.parameters.json` with `DEPLOYMENT_FLAVOR=bicep`.

Re-run every check with `scripts/preflight/check-azure-subscription.sh` (add `--probe` for the
live ARM validation, `--register` to register any missing provider).

## Target

| | |
| --- | --- |
| Subscription | `3523b0e6-bb53-4e87-8340-25c416e26093` (`Managed-Environment`, Enabled) |
| Tenant | `0f87abfb-0840-4199-96b7-1882c01a998b` |
| Region | `eastus2` |
| Build account | `brad.stevens@MngEnvMCAP786696.onmicrosoft.com` (object id `1d9e94c7-25c1-4fc5-9cd2-334052b43f47`) |

The subscription is Lighthouse-managed by tenant `72f988bf` (MCAPS), which is why policy was
checked rather than assumed.

## Finding 1 — no policy denies public network access

Four policy assignments are in effect, all at subscription scope. `--disable-scope-strict-match`
also surfaces assignments inherited from ancestor management groups, and none appeared — relevant
because the build account cannot read `Microsoft.Management/managementGroups` directly.

| Assignment | Definition | Effect |
| --- | --- | --- |
| `SecurityCenterBuiltIn` | ASC Default initiative (226 member definitions) | Audit / AuditIfNotExists / Disabled |
| `OpenSourceRelationalDatabasesProtectionSecurityCenter` | ASC OSS database protection initiative (5 members) | DeployIfNotExists |
| `AddSecurityControlIgnoreTag` | Add a tag to resources | Modify |
| `AddSecurityControlIgnoreTagRG` | Add a tag to resource groups | Modify |

All 233 effective policy definitions were expanded and their `effect` parameters resolved against
the assignment parameters (empty) and then the initiative defaults. **Sixteen** definitions test a
`publicNetworkAccess`, `networkAcls` or private-endpoint condition — including
*Azure AI Services resources should restrict network access*, *Azure Cosmos DB should disable public
network access*, *Container registries should not allow unrestricted network access* and
*Storage accounts should restrict network access*. **All sixteen resolve to `Audit` (14) or
`Disabled` (2). None resolves to `Deny`.**

There are **no policy exemptions**, and the only deny assignments are the system-owned
*Container Apps Managed Resource Group* ones, which protect a managed resource group's own
lifecycle and do not constrain what this build deploys.

Confirmed empirically rather than only by reading the rules: an `az deployment group validate` in
`eastus2` — which runs full policy evaluation — accepted a storage account, an AI Services account,
an AI Search service and a Cosmos DB account, each with `publicNetworkAccess` enabled and local auth
disabled. The probe template is `scripts/preflight/public-network-probe.bicep`; it is validated
only, never deployed, and its temporary resource group is deleted afterwards.

### Consequence for the MCAPS `SecurityControl=Ignore` decision

`AddSecurityControlIgnoreTag` is a `Modify` policy that tags resources on create; it does not
require the build to set anything. This is consistent with the spec's decision **not** to apply the
tag manually and **not** to re-enable local auth — the accelerator is keyless by design and the
MCAPS local-auth policies are a no-op against it.

## Finding 2 — the build account's rights are sufficient

The build account holds **Owner** at subscription scope, whose permission set is `actions: ["*"]`
with no `notActions`. That covers both halves of the requirement: creating every resource type the
accelerator deploys, and `Microsoft.Authorization/roleAssignments/write` for the role assignments it
makes to the managed identity.

It additionally holds *Cognitive Services OpenAI Contributor* and *Foundry User* at subscription
scope; neither is load-bearing given Owner.

The spec's warning about the *"reuse an existing Foundry project"* deployment path is a defect in
the upstream template (the deployer role grants are commented out), not a rights problem here.

## Finding 3 — the WAF flavour is not forced, and what it would cost if it were

Recorded so a later policy change does not require rediscovering this.

If a policy denying public network access is ever introduced, the build switches to
`DEPLOYMENT_FLAVOR=avm-waf` and copies `main.waf.parameters.json` over `main.parameters.json`. The
additional registration that flavour requires — and the vanilla flavour does not — is the
**`Microsoft.Compute/EncryptionAtHost` feature**, needed because the WAF flavour deploys VMs and a
Bastion host with `encryptionAtHost: true`:

```bash
az feature register --name EncryptionAtHost --namespace Microsoft.Compute
az feature show --name EncryptionAtHost --namespace Microsoft.Compute --query properties.state -o tsv
az provider register --namespace Microsoft.Compute   # propagates the feature; takes several minutes
```

**Current state: `NotRegistered`.** Deliberately left unregistered — registering it is only useful
under the WAF flavour, and doing it speculatively would imply a flavour choice the spec has already
settled against.

The compiled AVM template the WAF flavour deploys additionally references `Microsoft.Network`,
`Microsoft.KeyVault`, `Microsoft.Compute`, `Microsoft.Maintenance`, `Microsoft.GuestConfiguration`,
`Microsoft.OperationsManagement`, `Microsoft.RecoveryServices` and `Microsoft.Automanage` on top of
the vanilla set below, plus private endpoints, a virtual network and a jumpbox — materially more
infrastructure work than the vanilla flavour, which is why this ticket gates the infrastructure
ticket.

## Finding 4 — vanilla-flavour resource providers are registered

Derived from `infra/bicep/main.json` in the MACAE accelerator at the pinned upstream commit
`c5a7a4d1f0bfb6930b4c7b7f6356f28e7e03c309`, which is the compiled template the `bicep` flavour
actually deploys. All twelve are **Registered**:

| Namespace | Deployed for |
| --- | --- |
| `Microsoft.App` | Container Apps environment and the single-replica app |
| `Microsoft.Authorization` | role assignments to the managed identity |
| `Microsoft.CognitiveServices` | AI Services account, Foundry project, model deployments |
| `Microsoft.ContainerRegistry` | container registry the app images are pushed to |
| `Microsoft.DocumentDB` | Cosmos DB account, database, container, SQL role assignments |
| `Microsoft.Insights` | Application Insights |
| `Microsoft.ManagedIdentity` | user-assigned identity carrying the keyless authentication |
| `Microsoft.OperationalInsights` | Log Analytics workspace |
| `Microsoft.Resources` | nested deployments and tags |
| `Microsoft.Search` | AI Search service |
| `Microsoft.Storage` | storage account and blob container |
| `Microsoft.Web` | app service plan and web app |

`Microsoft.Compute` is also already registered on this subscription, but that is incidental — the
vanilla flavour does not use it, and provider registration alone is not sufficient for the WAF
flavour, which needs the `EncryptionAtHost` **feature** registered as well.

## Not covered here

- **Model quota tier** — issue [#4](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/4). Quota is subscription-scoped and tiered, and a sufficient role does not imply available capacity.
- **Power Platform and Dataverse rights** — issues [#2](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/2), [#3](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/3), [#5](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/5), [#6](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/6). Azure RBAC does not govern the Copilot Studio side of this build.
