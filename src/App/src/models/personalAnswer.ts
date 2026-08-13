/**
 * The **Personal answer** — the previously refused question, answered (#27).
 *
 * The mirror image of `api/policyBlock.ts`, deliberately and structurally. The
 * same keyword match in the Identity boundary gate decides both, one surface
 * renders both, and the only thing that differs between them is whether
 * anybody is signed in. So each names its own `kind` and the browser switches
 * on that name rather than on the shape of what it received: a refusal read as
 * an answer, or an answer read as a refusal, would be the demo's closing beat
 * making the opposite of its point.
 *
 * The refusal arrives as a failed request (HTTP 403) because nothing happened.
 * The answer arrives on a **successful** one, beside a `plan_id` of `null` —
 * no plan was created, because the answer cost no agent and no tokens, exactly
 * as the refusal did. That null is not a failure to create a plan and must not
 * be rendered as one.
 *
 * Every fact here is authored demo content. There is no `simulated` flag to
 * omit, for the reason the **Simulated ticket** has none: nothing else can be
 * produced, so the framing is a property of the answer and the surface says it
 * unconditionally.
 */

/** The discriminator, beside `POLICY_BLOCK_KIND`. */
export const PERSONAL_ANSWER_KIND = 'personal_answer';

/** One labelled row of the record. */
export interface PersonalFact {
    label: string;
    value: string;
}

/** A signed-in associate's record, as the surface renders it. */
export interface PersonalAnswer {
    displayName: string;
    role: string;
    facts: PersonalFact[];
    note: string;
}

const text = (value: unknown): string =>
    typeof value === 'string' ? value.trim() : '';

/**
 * Read a personal answer out of a create-plan response, or return null.
 *
 * Total, and it degrades towards *no answer*: a response with no personal
 * answer, one that does not name itself as one, or one that names no associate
 * reads as nothing, and the surface says nothing rather than rendering an
 * unattributed pay record on a shared device.
 *
 * A **half-written fact is dropped, not blanked**. A label with no value
 * renders as *nothing owed*, and that is a claim about somebody's entitlement
 * that nobody authored — the answer may say less than the record holds, but it
 * may not say something the record does not.
 */
export function parsePersonalAnswer(response: unknown): PersonalAnswer | null {
    if (!response || typeof response !== 'object' || Array.isArray(response)) {
        return null;
    }

    const payload = (response as { personal_answer?: unknown }).personal_answer;
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
        return null;
    }

    const { kind, display_name, role, facts, note } = payload as Record<string, unknown>;
    if (kind !== PERSONAL_ANSWER_KIND) return null;

    const displayName = text(display_name);
    if (!displayName) return null;

    const rows = Array.isArray(facts) ? facts : [];

    return {
        displayName,
        role: text(role),
        note: text(note),
        facts: rows
            .map((fact) => ({
                label: text((fact as { label?: unknown })?.label),
                value: text((fact as { value?: unknown })?.value),
            }))
            .filter((fact) => fact.label !== '' && fact.value !== ''),
    };
}
