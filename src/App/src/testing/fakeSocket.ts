/**
 * A stand-in for the browser's `WebSocket`, so tests can drive `WebSocketService`
 * from the wire rather than from inside it.
 *
 * It lives in one place because two suites need it and they must not drift: the
 * #47 finding is that four tests agreeing with each other about a shape the
 * service does not produce is not four tests. A fake at the *browser boundary*
 * is the opposite of that — nothing between it and the panels is mocked.
 */
export class FakeSocket {
    static instances: FakeSocket[] = [];
    static readonly OPEN = 1;

    readyState = 0;
    onopen: (() => void) | null = null;
    onmessage: ((event: { data: string }) => void) | null = null;
    onclose: ((event: unknown) => void) | null = null;
    onerror: ((event: unknown) => void) | null = null;
    closedWith: number | null = null;

    constructor(readonly url: string) {
        FakeSocket.instances.push(this);
    }

    send(): void {}

    close(code?: number): void {
        this.readyState = 3;
        this.closedWith = code ?? null;
    }

    addEventListener(): void {}

    open(): void {
        this.readyState = FakeSocket.OPEN;
        this.onopen?.();
    }

    deliver(text: string): void {
        this.onmessage?.({ data: text });
    }

    /** The socket the service opened most recently, or `undefined` if it opened none. */
    static latest(): FakeSocket | undefined {
        return FakeSocket.instances[FakeSocket.instances.length - 1];
    }

    /** Every socket opened for one plan — a double connect shows up as a second entry. */
    static forPlan(planId: string): FakeSocket[] {
        return FakeSocket.instances.filter((socket) => socket.url.includes(`/${planId}?`));
    }
}

/** One frame, exactly as the backend put it on the wire. */
export const frame = (type: string, data: unknown): string => JSON.stringify({ type, data });
