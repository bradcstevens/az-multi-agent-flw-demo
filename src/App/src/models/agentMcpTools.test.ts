import { describe, it, expect } from 'vitest';

import { AGENT_DOSSIER_COPY } from './agentDossier';
import { MCP_TOOLS_BY_DOMAIN, mcpToolsForDomain } from './agentMcpTools';

describe('the MCP tools the Agent dossier says an agent holds', () => {
    it('names a plain-English gloss beside every tool it mirrors', () => {
        // The gloss map is the third copy of one fact, after the backend
        // allowlist and this mirror, and the one no CI contract reads. A tool
        // whose gloss went missing renders its identifier with nothing beside
        // it — half the disclosure the ticket asked for, and `tsc` does not run
        // in the frontend loop to catch it.
        const glossed = Object.entries(MCP_TOOLS_BY_DOMAIN).flatMap(([domain, tools]) =>
            tools.map((tool) => [
                `${domain}/${tool}`,
                AGENT_DOSSIER_COPY.mcpToolGlosses[tool] ?? '',
            ]),
        );

        expect(glossed.filter(([, gloss]) => gloss.trim() === '')).toEqual([]);
    });

    it('names no tool at all where the roster gave it no domain to read', () => {
        // Absence, not invention. A roster entry with no `toolbox_filter` is
        // the same standing fact as one naming a domain nobody here mirrors:
        // the browser has nothing true to say, so it says nothing.
        expect(mcpToolsForDomain(undefined)).toEqual([]);
        expect(mcpToolsForDomain('')).toEqual([]);
        expect(mcpToolsForDomain('a-domain-this-repository-does-not-serve')).toEqual([]);
    });

    it('does not mistake a name JavaScript inherits for a domain it serves', () => {
        // The mirror is a plain object, so `MCP_TOOLS_BY_DOMAIN.constructor`
        // answers `Object` — truthy, with a `length` of 1 and no `map` — and a
        // pack naming any of these would take the dossier from "renders
        // nothing" to a thrown TypeError with the dialog half-drawn.
        for (const inherited of ['constructor', 'toString', 'valueOf', 'hasOwnProperty']) {
            expect(mcpToolsForDomain(inherited), `${inherited} is not a domain`).toEqual([]);
        }
    });
});
