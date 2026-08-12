"""Tests for the Copilot Studio pay-as-you-go meter preflight check (issue #6).

The check exists because pay-as-you-go on a **Default environment** is
undocumented — Microsoft names only production and sandbox environments — so
the meter's presence cannot be assumed and must be re-checkable, not asserted
once in prose.

The seam under test is the pure evaluation: given the tenant's billing policies
and the Default environment's id, `evaluate` decides whether the Copilot Studio
meter is live on that environment. The live HTTP calls sit outside it.
"""

from preflight.copilot_studio_meter import (
    evaluate,
    format_report,
    main,
    metered_plan_id,
)

DEFAULT_ENVIRONMENT_ID = "Default-0f87abfb-0840-4199-96b7-1882c01a998b"


def billing_policy(**overrides):
    """A billing policy shaped like the licensing API's, meter included."""
    policy = {
        "id": "d94c286b-9621-47cb-956e-acc23c9607c6",
        "name": "PowerPlatformPayGo",
        "status": "Enabled",
        "environmentIds": [DEFAULT_ENVIRONMENT_ID],
        "payGoEntitlements": [
            {
                "entitlementId": "AppPass",
                "productCategory": "PowerApps",
                "payAsYouGoState": True,
            },
            {
                "entitlementId": "MCSMessages",
                "productCategory": "PowerVirtualAgent",
                "payAsYouGoState": True,
            },
        ],
        "billingInstrument": {
            "subscriptionId": "3523b0e6-bb53-4e87-8340-25c416e26093",
            "resourceGroup": "rg-copilot-paygo",
            "provisioningStatus": "Succeeded",
        },
    }
    policy.update(overrides)
    return policy


def test_given_enabled_plan_carrying_the_meter_when_evaluated_then_verdict_passes():
    verdict = evaluate([billing_policy()], DEFAULT_ENVIRONMENT_ID)

    assert verdict.ok


def test_given_meter_listed_but_switched_off_when_evaluated_then_verdict_fails():
    off = billing_policy(
        payGoEntitlements=[
            {
                "entitlementId": "MCSMessages",
                "productCategory": "PowerVirtualAgent",
                "payAsYouGoState": False,
            }
        ]
    )

    verdict = evaluate([off], DEFAULT_ENVIRONMENT_ID)

    assert not verdict.ok


def test_given_disabled_plan_when_evaluated_then_verdict_fails():
    verdict = evaluate([billing_policy(status="Disabled")], DEFAULT_ENVIRONMENT_ID)

    assert not verdict.ok
    assert not verdict.check("active-billing-plan").ok


def test_given_plan_linked_only_to_a_stale_environment_when_evaluated_then_verdict_fails():
    """The tenant's plan carried the meter but pointed at a deleted environment.

    A meter on a plan the Default environment is not linked to bills nothing —
    this is the failure the check was written to catch.
    """
    stale = billing_policy(environmentIds=["39bc9cf5-323a-e466-a0b6-8797aaeadf1e"])

    verdict = evaluate([stale], DEFAULT_ENVIRONMENT_ID)

    linked = verdict.check("default-environment-linked")
    assert not linked.ok
    assert "39bc9cf5-323a-e466-a0b6-8797aaeadf1e" in linked.detail


def test_given_billing_instrument_not_provisioned_when_evaluated_then_verdict_fails():
    unprovisioned = billing_policy(
        billingInstrument={
            "subscriptionId": "3523b0e6-bb53-4e87-8340-25c416e26093",
            "resourceGroup": "rg-copilot-paygo",
            "provisioningStatus": "Failed",
        }
    )

    verdict = evaluate([unprovisioned], DEFAULT_ENVIRONMENT_ID)

    assert not verdict.check("azure-subscription-attached").ok


def test_given_a_failing_verdict_when_formatted_then_the_report_names_the_failure():
    stale = billing_policy(environmentIds=["39bc9cf5-323a-e466-a0b6-8797aaeadf1e"])

    report = format_report(evaluate([stale], DEFAULT_ENVIRONMENT_ID))

    assert "FAIL  default-environment-linked" in report
    assert "PASS  copilot-studio-meter" in report


def test_given_a_passing_verdict_when_formatted_then_the_payg_rate_limit_is_recorded():
    """The 100 RPM figure #6 asks to record is a property of the *verdict*.

    A pay-as-you-go environment gets 100 RPM / 2,000 RPH for generative AI
    messages; without the meter the Default environment falls back to the 10 RPM
    trial/developer quota. Reporting the wrong one would be worse than silence.
    """
    report = format_report(evaluate([billing_policy()], DEFAULT_ENVIRONMENT_ID))

    assert "100 RPM" in report
    assert "2,000 RPH" in report


def stub_tenant(policies, default_environment_id=DEFAULT_ENVIRONMENT_ID):
    """Stand in for the live licensing/BAP reads, so main() stays testable."""
    return lambda: (policies, default_environment_id)


def test_given_the_meter_is_live_when_main_runs_then_it_exits_zero(capsys):
    assert main([], read_tenant=stub_tenant([billing_policy()])) == 0
    assert "100 RPM" in capsys.readouterr().out


def test_given_the_meter_is_absent_when_main_runs_then_it_exits_non_zero(capsys):
    unmetered = billing_policy(payGoEntitlements=[])

    assert main([], read_tenant=stub_tenant([unmetered])) == 1
    assert "FAIL  copilot-studio-meter" in capsys.readouterr().out


def test_given_several_plans_when_choosing_one_to_link_then_the_metered_active_plan_wins():
    """--link must attach the Default environment to the plan carrying the meter."""
    plans = [
        billing_policy(id="inactive", status="Disabled"),
        billing_policy(id="no-meter", payGoEntitlements=[]),
        billing_policy(id="metered", environmentIds=[]),
    ]

    assert metered_plan_id(plans) == "metered"


def test_given_no_metered_plan_when_choosing_one_to_link_then_there_is_nothing_to_link():
    assert metered_plan_id([billing_policy(payGoEntitlements=[])]) is None


def test_given_meter_switched_off_when_evaluated_then_the_environment_counts_as_unmetered():
    """A switched-off meter meters nothing, however the environment is linked."""
    off = billing_policy(
        payGoEntitlements=[
            {
                "entitlementId": "MCSMessages",
                "productCategory": "PowerVirtualAgent",
                "payAsYouGoState": False,
            }
        ]
    )

    verdict = evaluate([off], DEFAULT_ENVIRONMENT_ID)

    assert not verdict.check("default-environment-linked").ok


def test_given_two_plans_each_half_qualifying_when_evaluated_then_verdict_fails():
    """Every check must hold of *one* plan; two half-good plans do not add up.

    A plan that covers the Default environment but cannot bill, plus a plan that
    can bill but covers nothing, leaves the environment unmetered.
    """
    covers_but_cannot_bill = billing_policy(
        id="covers",
        billingInstrument={
            "subscriptionId": "3523b0e6-bb53-4e87-8340-25c416e26093",
            "resourceGroup": "rg-copilot-paygo",
            "provisioningStatus": "Failed",
        },
    )
    bills_but_covers_nothing = billing_policy(id="bills", environmentIds=[])

    verdict = evaluate(
        [covers_but_cannot_bill, bills_but_covers_nothing], DEFAULT_ENVIRONMENT_ID
    )

    assert not verdict.ok
    assert not verdict.check("azure-subscription-attached").ok


def test_given_an_unmetered_plan_listed_first_when_evaluated_then_a_later_metered_plan_still_counts():
    unmetered = billing_policy(id="unmetered", payGoEntitlements=[])

    verdict = evaluate([unmetered, billing_policy()], DEFAULT_ENVIRONMENT_ID)

    assert verdict.ok


def test_given_a_failing_verdict_when_formatted_then_no_quota_is_claimed():
    """Failing only shows pay-as-you-go is not in effect, not which quota is.

    Prepaid message packs and Microsoft 365 Copilot entitlement both set their
    own quota, and this check gathers no evidence about either.
    """
    report = format_report(evaluate([billing_policy(payGoEntitlements=[])], DEFAULT_ENVIRONMENT_ID))

    assert "100 RPM" not in report
    assert "not established" in report
