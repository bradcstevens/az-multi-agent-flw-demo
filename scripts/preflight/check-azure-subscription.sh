#!/usr/bin/env bash
# Preflight: Azure subscription rights and policy for the vanilla (non-WAF) flavour.
#
# Re-runnable check behind the findings recorded in
# docs/preflight/azure-subscription-rights-and-policy.md.
#
# Exits non-zero if any check fails, so it can be wired into a feedback loop.
#
#   scripts/preflight/check-azure-subscription.sh            # check only
#   scripts/preflight/check-azure-subscription.sh --register # register missing providers
#   scripts/preflight/check-azure-subscription.sh --probe     # + live ARM policy probe

set -uo pipefail

SUBSCRIPTION_ID="${SUBSCRIPTION_ID:-3523b0e6-bb53-4e87-8340-25c416e26093}"
TENANT_ID="${TENANT_ID:-0f87abfb-0840-4199-96b7-1882c01a998b}"
LOCATION="${LOCATION:-eastus2}"

# Resource provider namespaces the vanilla flavour deploys, derived from
# infra/bicep/main.json in the MACAE accelerator at the pinned upstream commit.
VANILLA_PROVIDERS=(
  Microsoft.App
  Microsoft.Authorization
  Microsoft.CognitiveServices
  Microsoft.ContainerRegistry
  Microsoft.DocumentDB
  Microsoft.Insights
  Microsoft.ManagedIdentity
  Microsoft.OperationalInsights
  Microsoft.Resources
  Microsoft.Search
  Microsoft.Storage
  Microsoft.Web
)

# Roles at subscription scope that can both create the accelerator's resource
# types and make the role assignments it needs.
SUFFICIENT_ROLES=(Owner "User Access Administrator" "Role Based Access Control Administrator")

REGISTER=0
PROBE=0
for arg in "$@"; do
  case "$arg" in
    --register) REGISTER=1 ;;
    --probe) PROBE=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

failures=0
pass() { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; failures=$((failures + 1)); }
note() { printf '  ----  %s\n' "$1"; }
section() { printf '\n\033[1m%s\033[0m\n' "$1"; }

command -v az >/dev/null 2>&1 || { echo "az CLI not found on PATH" >&2; exit 2; }

section "Sign-in"
account_json=$(az account show -o json 2>/dev/null)
if [[ -z "$account_json" ]]; then
  fail "not signed in — run: az login --tenant $TENANT_ID"
  exit 1
fi
actual_sub=$(jq -r .id <<<"$account_json")
actual_tenant=$(jq -r .tenantId <<<"$account_json")
signed_in_user=$(jq -r .user.name <<<"$account_json")
[[ "$actual_sub" == "$SUBSCRIPTION_ID" ]] \
  && pass "active subscription is $SUBSCRIPTION_ID" \
  || fail "active subscription is $actual_sub, expected $SUBSCRIPTION_ID"
[[ "$actual_tenant" == "$TENANT_ID" ]] \
  && pass "tenant is $TENANT_ID" \
  || fail "tenant is $actual_tenant, expected $TENANT_ID"
note "signed in as $signed_in_user"

section "Build account rights"
principal_id=$(az ad signed-in-user show --query id -o tsv 2>/dev/null)
if [[ -z "$principal_id" ]]; then
  fail "could not resolve the signed-in principal"
else
  roles=$(az role assignment list \
    --assignee "$principal_id" --include-inherited --include-groups \
    --scope "/subscriptions/$SUBSCRIPTION_ID" \
    --query "[].roleDefinitionName" -o tsv 2>/dev/null)
  held=""
  while IFS= read -r role; do
    [[ -z "$role" ]] && continue
    for sufficient in "${SUFFICIENT_ROLES[@]}"; do
      [[ "$role" == "$sufficient" ]] && held+="$role "
    done
  done <<<"$roles"
  if [[ -n "$held" ]]; then
    pass "holds ${held% } at subscription scope — can create resources and assign roles"
  else
    fail "no role granting Microsoft.Authorization/roleAssignments/write found; holds: $(tr '\n' ',' <<<"$roles")"
  fi
fi

section "Policy: nothing denying public network access"
# --disable-scope-strict-match also surfaces assignments inherited from
# ancestor management groups, which the build account cannot read directly.
assignments=$(az policy assignment list --disable-scope-strict-match -o json 2>/dev/null)
assignment_count=$(jq 'length' <<<"$assignments")
note "$assignment_count policy assignment(s) in effect"

deny_effects=$(python3 - "$assignments" <<'PY'
import json, subprocess, sys

def az(cmd):
    out = subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout
    return json.loads(out) if out.strip() else None

assignments = json.loads(sys.argv[1])
denies = []
for assignment in assignments:
    definition_id = assignment["policyDefinitionId"]
    assigned = assignment.get("parameters") or {}
    if "/policySetDefinitions/" in definition_id:
        initiative = az(f"az policy set-definition show --name {definition_id.split('/')[-1]} -o json") or {}
        set_params = initiative.get("parameters", {})
        members = initiative.get("policyDefinitions", [])
    else:
        set_params, members = {}, [{"policyDefinitionId": definition_id, "parameters": {}}]

    for member in members:
        effect = (member.get("parameters") or {}).get("effect", {}).get("value")
        if isinstance(effect, str) and effect.startswith("[parameters("):
            key = effect.split("'")[1]
            effect = (assigned.get(key) or {}).get("value") or (set_params.get(key) or {}).get("defaultValue")
        definition = az(f"az policy definition show --name {member['policyDefinitionId'].split('/')[-1]} -o json")
        if not definition:
            continue
        rule = json.dumps(definition.get("policyRule", {}))
        touches_network = "publicNetworkAccess" in rule or "networkAcls" in rule or "privateEndpoint" in rule.lower()
        if effect is None:
            effect = definition["policyRule"]["then"].get("effect")
            if isinstance(effect, str) and effect.startswith("[parameters("):
                key = effect.split("'")[1]
                effect = (definition.get("parameters", {}).get(key) or {}).get("defaultValue")
        if touches_network and str(effect).lower() in ("deny", "denyaction"):
            denies.append(f"{assignment['name']}: {definition.get('displayName')} -> {effect}")

print("\n".join(denies))
PY
)

if [[ -z "$deny_effects" ]]; then
  pass "no policy resolves to Deny on a public-network-access condition — vanilla flavour permitted"
else
  fail "policies deny public network access — the WAF flavour is forced:"
  while IFS= read -r line; do note "$line"; done <<<"$deny_effects"
fi

blocking_deny_assignments=$(az rest --method get \
  --url "https://management.azure.com/subscriptions/$SUBSCRIPTION_ID/providers/Microsoft.Authorization/denyAssignments?api-version=2022-04-01" \
  --query "value[?!contains(properties.denyAssignmentName, 'Managed Resource Group')].properties.denyAssignmentName" \
  -o tsv 2>/dev/null)
if [[ -z "$blocking_deny_assignments" ]]; then
  pass "no deny assignments beyond system-owned managed resource groups"
else
  fail "unexpected deny assignments: $blocking_deny_assignments"
fi

section "Resource providers (vanilla flavour)"
for namespace in "${VANILLA_PROVIDERS[@]}"; do
  state=$(az provider show -n "$namespace" --query registrationState -o tsv 2>/dev/null)
  if [[ "$state" == "Registered" ]]; then
    pass "$namespace registered"
  elif [[ "$REGISTER" == "1" ]]; then
    note "$namespace is $state — registering"
    az provider register --namespace "$namespace" --wait -o none 2>/dev/null
    state=$(az provider show -n "$namespace" --query registrationState -o tsv 2>/dev/null)
    [[ "$state" == "Registered" ]] && pass "$namespace registered" || fail "$namespace is $state"
  else
    fail "$namespace is ${state:-unknown} — re-run with --register"
  fi
done

section "WAF-flavour contingency"
encryption_at_host=$(az feature show --name EncryptionAtHost --namespace Microsoft.Compute \
  --query properties.state -o tsv 2>/dev/null)
note "Microsoft.Compute/EncryptionAtHost is ${encryption_at_host:-unknown}"
note "Only required if the WAF flavour is forced. Register with:"
note "  az feature register --name EncryptionAtHost --namespace Microsoft.Compute"
note "  az provider register --namespace Microsoft.Compute"

if [[ "$PROBE" == "1" ]]; then
  section "Live ARM policy probe"
  probe_rg="rg-preflight-policy-probe"
  probe_suffix="pfp$RANDOM"
  template="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/public-network-probe.bicep"
  az group create -n "$probe_rg" -l "$LOCATION" --tags purpose=preflight-policy-probe -o none 2>/dev/null
  if az deployment group validate -g "$probe_rg" -f "$template" -p suffix="$probe_suffix" -o none 2>/dev/null; then
    pass "ARM accepted storage, AI Services, AI Search and Cosmos DB with publicNetworkAccess enabled"
  else
    fail "ARM rejected a public-network-access resource — inspect with: az deployment group validate -g $probe_rg -f $template -p suffix=$probe_suffix"
  fi
  az group delete -n "$probe_rg" --yes --no-wait -o none 2>/dev/null
fi

section "Result"
if [[ "$failures" -eq 0 ]]; then
  printf '  \033[32mall checks passed\033[0m — vanilla (non-WAF) deployment is permitted\n\n'
  exit 0
fi
printf '  \033[31m%d check(s) failed\033[0m\n\n' "$failures"
exit 1
