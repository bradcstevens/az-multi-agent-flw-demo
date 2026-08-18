import { describe, expect, it } from 'vitest';

import { PERSONAL_ANSWER_KIND, parsePersonalAnswer } from './personalAnswer';

const provenance = 'A Provenance line received from the backend.';

const payload = {
    kind: PERSONAL_ANSWER_KIND,
    display_name: 'Tanya Alvarez',
    role: 'Store associate, Store 223',
    facts: [
        { label: 'PTO balance', value: '34.5 hours' },
        { label: 'Next scheduled shift', value: 'Thursday, 06:00 - 14:00' },
    ],
    provenance_line: provenance,
};

describe('the personal answer', () => {
    it('reads the associate the record answers for', () => {
        expect(parsePersonalAnswer({ personal_answer: payload })?.displayName).toBe(
            'Tanya Alvarez',
        );
    });

    it('reads the facts in the order the record states them', () => {
        const answer = parsePersonalAnswer({ personal_answer: payload });

        expect(answer?.facts.map((fact) => fact.label)).toEqual([
            'PTO balance',
            'Next scheduled shift',
        ]);
    });

    it('carries the provenance line the associate record authored', () => {
        expect(parsePersonalAnswer({ personal_answer: payload })?.provenanceLine).toBe(provenance);
    });

    it('reads nothing out of a response that carries no answer', () => {
        // The ordinary case: every store question in the walkthrough returns a
        // plan and no personal answer.
        expect(parsePersonalAnswer({ plan_id: 'plan-1', status: 'ok' })).toBeNull();
    });

    it('refuses a payload that does not name itself a personal answer', () => {
        // The discriminator is the point. A **Policy block** and a personal
        // answer are the same beat's two outcomes and travel the same surface;
        // reading one as the other would render a refusal as somebody's pay.
        expect(
            parsePersonalAnswer({ personal_answer: { ...payload, kind: 'policy_block' } }),
        ).toBeNull();
    });

    it('refuses an answer with no associate named', () => {
        // An answer nobody is named on is a pay record on a shared device with
        // no claim about whose it is.
        expect(
            parsePersonalAnswer({ personal_answer: { ...payload, display_name: '  ' } }),
        ).toBeNull();
    });

    it('drops a half-written fact rather than blanking it', () => {
        // A label with no value renders as *nothing owed*, which is a claim
        // about an associate's entitlement that nobody authored. The answer may
        // say less than the record holds; it may not say something else.
        const answer = parsePersonalAnswer({
            personal_answer: {
                ...payload,
                facts: [{ label: 'PTO balance', value: '' }, { label: '', value: '9' }],
            },
        });

        expect(answer?.facts).toEqual([]);
    });

    it('survives an answer with nothing in it but a name', () => {
        // A thin record still answers: it says who is signed in and lists
        // nothing, which is true. Failing here would look on stage exactly like
        // the refusal the sign-in was supposed to lift.
        const answer = parsePersonalAnswer({
            personal_answer: { kind: PERSONAL_ANSWER_KIND, display_name: 'Tanya Alvarez' },
        });

        expect(answer).toEqual({
            displayName: 'Tanya Alvarez',
            role: '',
            facts: [],
            provenanceLine: '',
        });
    });

    it('reads nothing out of rubbish', () => {
        [null, undefined, 'personal_answer', 42, []].forEach((rubbish) => {
            expect(parsePersonalAnswer(rubbish)).toBeNull();
        });
    });
});
