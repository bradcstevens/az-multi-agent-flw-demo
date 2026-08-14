import { Page } from '@playwright/test';

/**
 * The frames the surface actually received, as the browser received them.
 *
 * Issue #50. Two of the walkthrough's claims are about things that **did not
 * happen**, and neither is visible in the DOM:
 *
 * - *the associate is never asked for their troubleshooting history a second
 *   time* — a question that was asked and left unanswered renders as an agent
 *   turn among other agent turns, in prose a model wrote, and the beat then
 *   fails as a timeout somewhere else entirely;
 * - *approving the plan **is** the ticket being raised — one confirmation, not
 *   two* — where the second confirmation, if it ever appears, is a second
 *   approval prompt or a clarification between the approval and the card.
 *
 * A `user_clarification_request` frame is neither prose nor a rendering
 * decision: it is the backend asking, on the wire, in the vocabulary
 * `models/messages.py` and `models/enums.tsx` already share. Counting them is
 * the only way to assert an absence without asserting a sentence.
 *
 * It is also how the *positive* half of the troubleshooting beat is graded. The
 * clarification arrives as an ordinary agent turn wearing the Group Chat
 * Manager's name (`usePlanWebSocket`), so "the fault provoked a question" read
 * off the page is a claim about wording. Read off the wire it is a fact.
 */

/** One frame the surface received, in the backend's own vocabulary. */
export interface WireFrame {
    type: string;
    data: unknown;
    /** Milliseconds since the recorder was installed. */
    at: number;
}

/**
 * A recording of one page's socket traffic.
 *
 * Holds no assertions — a spec asks it questions and grades the answers, the
 * same division the page objects keep. `mark()` and the `from` argument exist
 * because most of what this issue asserts is *scoped*: not "no clarification
 * was ever asked", which is false of the troubleshooting beat by design, but
 * "none was asked after the plan was approved".
 */
export class WireLog {
    private readonly received: WireFrame[] = [];
    private readonly startedAt = Date.now();

    /** Every frame recorded so far, oldest first. */
    all(from = 0): WireFrame[] {
        return this.received.slice(from);
    }

    /** The frames of one type, in arrival order. */
    of(type: string, from = 0): WireFrame[] {
        return this.all(from).filter((frame) => frame.type === type);
    }

    count(type: string, from = 0): number {
        return this.of(type, from).length;
    }

    /**
     * A cursor into the recording, for scoping a later question to what
     * happened *after* some step of the walkthrough.
     */
    mark(): number {
        return this.received.length;
    }

    /**
     * Wait for a frame of one type to arrive.
     *
     * Fails with **what did arrive** rather than a bare timeout. A beat that
     * waits five minutes for `plan_approval_request` and reports only that it
     * did not come sends the reader looking for a broken selector; one that
     * says the socket carried `agent_message`, `final_result_message` and no
     * approval says the request took the Fast lane, which is a different
     * morning's work.
     */
    async waitFor(
        type: string,
        { timeout = 240_000, from = 0 }: { timeout?: number; from?: number } = {},
    ): Promise<WireFrame> {
        const deadline = Date.now() + timeout;
        for (;;) {
            const found = this.of(type, from);
            if (found.length > 0) {
                return found[0];
            }
            if (Date.now() >= deadline) {
                throw new Error(
                    `no '${type}' frame reached the browser within ${Math.round(
                        timeout / 1000,
                    )}s. The socket carried: ${this.summary(from)}`,
                );
            }
            await new Promise((resolve) => setTimeout(resolve, 250));
        }
    }

    /**
     * Wait until the recording answers a question, and return that answer.
     *
     * The escalation beat needs it because "what happens next" has more than
     * one legitimate answer: the approved plan may stop to ask the associate
     * something, or go straight to the ticket, and the walkthrough has to do a
     * different thing in each case. Waiting for one frame type alone would sit
     * through the framework's 300-second clarification wait and then report the
     * wrong finding — a missing ticket, on a turn that was waiting for an
     * answer nobody gave.
     */
    async waitUntil<T>(
        question: (log: WireLog) => T | null,
        {
            timeout = 240_000,
            from = 0,
            expecting,
        }: { timeout?: number; from?: number; expecting: string },
    ): Promise<T> {
        const deadline = Date.now() + timeout;
        for (;;) {
            const answer = question(this);
            if (answer !== null) {
                return answer;
            }
            if (Date.now() >= deadline) {
                throw new Error(
                    `${expecting} did not happen within ${Math.round(
                        timeout / 1000,
                    )}s. The socket carried: ${this.summary(from)}`,
                );
            }
            await new Promise((resolve) => setTimeout(resolve, 250));
        }
    }

    /** What the socket carried, as counts by type — the failure diagnostic. */
    summary(from = 0): string {
        const counts = new Map<string, number>();
        for (const frame of this.all(from)) {
            counts.set(frame.type, (counts.get(frame.type) || 0) + 1);
        }
        if (counts.size === 0) {
            return 'nothing at all';
        }
        return [...counts.entries()]
            .map(([type, count]) => `${type}\u00d7${count}`)
            .join(', ');
    }

    /** Record a frame the page received. Called by the recorder. */
    push(payload: string): void {
        let parsed: unknown;
        try {
            parsed = JSON.parse(payload);
        } catch {
            // The socket also carries keepalives and, on some paths, plain
            // text. A frame that is not JSON is not a claim about anything
            // this suite grades, so it is dropped rather than recorded as an
            // unnamed type that a count could later trip over.
            return;
        }
        if (!parsed || typeof parsed !== 'object') {
            return;
        }
        const frame = parsed as { type?: unknown; data?: unknown };
        if (typeof frame.type !== 'string') {
            return;
        }
        this.received.push({
            type: frame.type,
            data: frame.data,
            at: Date.now() - this.startedAt,
        });
    }
}

/**
 * Start recording every socket frame this page receives.
 *
 * Install it **before** `page.goto`: the surface opens its socket as the plan
 * page mounts, and a recorder attached afterwards misses the frames of the beat
 * it was installed to watch.
 */
export function recordWire(page: Page): WireLog {
    const log = new WireLog();
    page.on('websocket', (socket) => {
        socket.on('framereceived', (frame) => {
            if (typeof frame.payload === 'string') {
                log.push(frame.payload);
            }
        });
    });
    return log;
}
