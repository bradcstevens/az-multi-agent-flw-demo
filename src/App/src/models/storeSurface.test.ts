import { describe, it, expect } from 'vitest';

import {
    ASSISTANT_NAME,
    STORE_LABEL,
    STORE_ASSISTANT_TEAM_ID,
    TRANSPARENCY_RAIL_PINNED_CLOSED_DESCRIPTION,
    TRANSPARENCY_PANELS_LABEL,
    selectStoreAssistant,
} from './storeSurface';
import { TeamConfig } from './Team';

const team = (over: Partial<TeamConfig>): TeamConfig =>
    ({
        team_id: '00000000-0000-0000-0000-000000000001',
        name: 'HR Employee Onboarding',
        status: 'visible',
        agents: [],
        starting_tasks: [],
        ...over,
    } as TeamConfig);

const storeAssistant = team({
    team_id: STORE_ASSISTANT_TEAM_ID,
    name: 'Circle K Frontline Store Assistant',
});

describe('the store surface', () => {
    it('names the assistant and the store it is scoped to', () => {
        expect(ASSISTANT_NAME).toBe('Circle K Frontline Store Assistant');
        expect(STORE_LABEL).toBe('Store 223');
    });

    it("names the transparency drawer's control once, and never as an instruction", () => {
        // A disclosure button keeps **one** accessible name (ADR-035). A label
        // that flipped between *Show* and *Hide* would be a second control to
        // anybody reading the surface through a screen reader, and the name is
        // pinned here so the one place it is written is the one place it can
        // change.
        expect(TRANSPARENCY_PANELS_LABEL).toBe('Transparency panels');
    });

    it('describes only a rail the presenter pinned closed', () => {
        expect(TRANSPARENCY_RAIL_PINNED_CLOSED_DESCRIPTION).toBe(
            'Pinned closed for this conversation.',
        );
    });

    it('resolves the store assistant by its identifier', () => {
        expect(selectStoreAssistant([team({}), storeAssistant])).toBe(storeAssistant);
    });

    it('recognises the store assistant by name when the identifier has drifted', () => {
        // The pack is uploaded by a script (#19) and re-uploaded by hand more
        // than once. A renumbered identifier should cost the demo its brand
        // banner, not its assistant.
        const renamed = team({
            team_id: '00000000-0000-0000-0000-00000000abcd',
            name: 'Circle K Frontline Store Assistant',
        });

        expect(selectStoreAssistant([team({}), renamed])).toBe(renamed);
    });

    it('resolves to nothing rather than to a stock content pack', () => {
        // The suppression, made structural. Falling back to the first team the
        // backend happens to return would put the accelerator's HR roster
        // under the Circle K header — a surface saying something that is not
        // so, which is the one thing none of these surfaces may do.
        expect(selectStoreAssistant([team({}), team({ name: 'RFP Evaluation' })])).toBeNull();
    });

    it('resolves to nothing when the backend returned no teams at all', () => {
        expect(selectStoreAssistant([])).toBeNull();
        expect(selectStoreAssistant(null)).toBeNull();
    });
});
