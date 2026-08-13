/**
 * The workflow's agent roster, read for what the transparency panels need
 * (issue #24).
 *
 * The roster — not the plan. With **Plan review** off there is no plan object
 * at all (ADR-013), so a panel that read agent names out of the plan would be
 * empty on the Fast lane, which is most of the walkthrough. The roster is on
 * the plan-fetch response as `team.agents` and is present either way.
 *
 * It is also the only place the **per-agent model assignment** lives, as
 * `deployment_name`. That assignment is the architecture's "cheap models on
 * cheap work" claim, and R7 wants it visible rather than asserted.
 */

import { Agent, TeamConfig } from './Team';

/** Every spelling of an executor id that might come back on the wire. */
const aliases = (name: string): string[] => {
    const snake = name
        .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
        .replace(/\s+/g, '_')
        .toLowerCase();
    return Array.from(new Set([name, snake, name.toLowerCase()]));
};

/**
 * Executor id → deployment name, for the Token meter's model column.
 *
 * The meter's rows are keyed by **executor identifier**, which is what the
 * event stream attributes a cost to, while the roster is keyed by agent name.
 * They are usually the same string and occasionally differ in case or in
 * underscores, so every spelling gets an entry rather than the column silently
 * emptying.
 *
 * An agent the roster assigns no model gets **no entry** — the panel renders
 * `—` for a missing one, and inventing a default here would put a model name
 * on screen that nobody configured.
 */
export function modelsByExecutor(team: TeamConfig | null | undefined): Record<string, string> {
    const models: Record<string, string> = {};
    for (const agent of team?.agents ?? []) {
        if (!agent?.name || !agent.deployment_name) continue;
        for (const alias of aliases(agent.name)) {
            models[alias] = agent.deployment_name;
        }
    }
    return models;
}

/**
 * The agents to show in the Agent Team panel, roster first.
 *
 * Falls back to the plan's flat list of names when there is no roster — a
 * historical plan fetched without its team still has something to show — and
 * to nothing at all when there is neither, which the panel says out loud.
 */
export function rosterAgents(
    team: TeamConfig | null | undefined,
    planTeam: string[] | null | undefined,
): Agent[] {
    const agents = team?.agents ?? [];
    if (agents.length > 0) return agents;
    return (planTeam ?? []).map(
        (name): Agent => ({ input_key: '', type: '', name }),
    );
}
