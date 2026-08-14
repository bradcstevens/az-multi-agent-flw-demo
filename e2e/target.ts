/**
 * Which surface the walkthrough is being asserted against.
 *
 * The **Demo validator** and the **Stage driver** (#51) run the *same specs*
 * both ways, so a target is a base URL and nothing more. Two suites would be
 * two descriptions of the walkthrough, and they would disagree (ADR-016).
 *
 * `deployed` is the default, deliberately. The reason this suite exists is that
 * every declared feedback loop in this repository runs against fakes, and none
 * of them observes a deployment at all — which is how the Container Apps came
 * to be running the stock accelerator while everything was green. A validator
 * that defaults to localhost would have the same blind spot.
 */
export type TargetName = 'deployed' | 'local';

export interface Target {
    name: TargetName;
    baseURL: string;
}

/** Where a local `npm run dev` serves the store surface (`vite.config.ts`). */
export const LOCAL_BASE_URL = 'http://localhost:3001';

export function resolveTarget(env: NodeJS.ProcessEnv = process.env): Target {
    const name = (env.E2E_TARGET || 'deployed') as TargetName;
    if (name !== 'deployed' && name !== 'local') {
        throw new Error(
            `E2E_TARGET must be 'deployed' or 'local', not ${JSON.stringify(name)}`,
        );
    }

    const configured = (env.E2E_BASE_URL || '').trim();
    if (configured) {
        return { name, baseURL: configured.replace(/\/$/, '') };
    }

    if (name === 'local') {
        return { name, baseURL: LOCAL_BASE_URL };
    }

    // Resolving the deployed FQDN needs `az`, and the resource group and app
    // names are already written down once, in `scripts/preflight/
    // deployed_surface.py`. `scripts/e2e-tests.sh` reads them from there and
    // passes the answer in, so this suite never keeps a second copy of where
    // the deployment is.
    throw new Error(
        'E2E_BASE_URL is not set. Run the Demo validator through ' +
            '`bash scripts/e2e-tests.sh`, which resolves the deployed ' +
            "frontend's ingress with `az`, or pass --target local.",
    );
}
