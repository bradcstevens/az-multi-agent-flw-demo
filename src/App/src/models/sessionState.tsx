import { Lane } from './lane';

/**
 * Who, if anyone, is signed in on the shared store device (issue #20).
 *
 * Mocked end to end — no real identity provider writes this. Absent means
 * anonymous, and anonymous is the *refusing* state at the backend's Identity
 * boundary gate.
 */
export interface SessionIdentityState {
    display_name: string | null;
}

/**
 * The server-side state of one session.
 *
 * Held server-side rather than in browser storage precisely so a mid-demo
 * reload does not lose it. The two things it carries are the two the client
 * cannot re-derive: the identity the gate reads, and the Lane **taken** as the
 * backend's lane router decided it — re-deriving a lane in the browser would
 * be a second lane router with its own opinion.
 */
export interface SessionState {
    session_id: string;
    identity: SessionIdentityState;
    lane?: Lane | string | null;
}
