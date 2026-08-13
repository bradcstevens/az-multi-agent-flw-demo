/**
 * The **Signed-in device** (issue #27).
 *
 * The demo's closing beat is a governance argument: the same question is
 * refused, the presenter taps *Sign in to continue*, and it answers. The
 * handoff is **mocked end to end** — no Entra, no Okta, no identity provider of
 * any kind — so what "signed in" means has to be written down precisely, and
 * this module is the browser's half of it.
 *
 * **This is not the identity.** The identity is the record in server-side
 * **Session state** that the Identity boundary gate reads (ADR-014), written by
 * `POST /session_state/{id}/sign_in`, and the gate reads nothing else. What
 * lives here is the *device's memory that the presenter tapped sign in*, held
 * for one browser session — which is what makes the next request's session get
 * an identity written into it, and what the header renders.
 *
 * Two consequences follow, and both are acceptance criteria:
 *
 * * **A fresh session is anonymous.** `sessionStorage`, deliberately, not
 *   `localStorage`: a new tab — and a laptop that has been closed and reopened
 *   — is a shared store device nobody has signed in on, which is where the
 *   demo has to start. Nothing to reset between rehearsals.
 * * **Signing out is forgetting.** There is nothing to revoke: a session whose
 *   identity was written is a conversation that is over, and the next one is
 *   created anonymous unless this says otherwise.
 *
 * **The name is never authored here.** It comes back from the sign-in route and
 * is stored verbatim. The name the header shows and the name the **Associate
 * record** is keyed by would otherwise be two strings in two languages, free to
 * drift, and the drift's symptom is a header confidently naming somebody the
 * gate will not answer for.
 */

/** Where the tab remembers the name. Namespaced, since the key is shared. */
export const SIGNED_IN_NAME_KEY = 'store-assistant.signed-in-associate';

type Listener = () => void;

const listeners = new Set<Listener>();

/**
 * The name in memory, so the module still works when storage does not.
 *
 * `undefined` means "not read from storage yet", which is what a reload leaves
 * behind; `null` means "read, and nobody is signed in".
 */
let remembered: string | null | undefined;

const usable = (name: unknown): string | null =>
    typeof name === 'string' && name.trim() ? name.trim() : null;

/**
 * Storage, if this browser has any that works.
 *
 * Private browsing throws on both read and write. A header that cannot
 * remember a sign-in across a reload is a small loss; a screen that throws is
 * the whole demo, so every access here is total.
 */
const readStored = (): string | null => {
    try {
        return usable(window.sessionStorage.getItem(SIGNED_IN_NAME_KEY));
    } catch {
        return null;
    }
};

const announce = (): void => {
    listeners.forEach((listener) => listener());
};

/** The associate signed in on this device, or nobody. */
export const signedInName = (): string | null => {
    if (remembered === undefined) {
        remembered = readStored();
    }
    return remembered;
};

/**
 * Remember the name the sign-in route returned.
 *
 * A blank name signed nobody in — recording it would put an empty identity on
 * the header while the gate goes on refusing, which is the surface claiming
 * something that is not so.
 */
export const rememberSignedInName = (name: unknown): void => {
    const usableName = usable(name);
    if (!usableName) return;

    remembered = usableName;
    try {
        window.sessionStorage.setItem(SIGNED_IN_NAME_KEY, usableName);
    } catch {
        /* Storage refused; the tab still knows until it is reloaded. */
    }
    announce();
};

/**
 * Sign out: forget, so the next request is created anonymous.
 *
 * Also what a **Policy block** means. The gate refusing *is* the statement that
 * nobody is signed in, and a header that goes on naming an associate the gate
 * has just declined to answer for is the one thing no surface here may do.
 */
export const forgetSignedInDevice = (): void => {
    remembered = null;
    try {
        window.sessionStorage.removeItem(SIGNED_IN_NAME_KEY);
    } catch {
        /* Nothing stored is nothing to remove. */
    }
    announce();
};

/** Subscribe to changes, for the header that renders this. */
export const subscribeToSignedInDevice = (listener: Listener): (() => void) => {
    listeners.add(listener);
    return () => {
        listeners.delete(listener);
    };
};
