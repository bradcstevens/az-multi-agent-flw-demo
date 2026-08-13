import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import LaneBadge from './LaneBadge';

describe('the Lane, made visible', () => {
    it('names the lane it was given', () => {
        render(<LaneBadge lane="fast" />);

        expect(screen.getByTestId('lane-badge')).toHaveTextContent('Fast lane');
    });

    it('says what the Deliberate lane costs the associate', () => {
        render(<LaneBadge lane="deliberate" variant="taken" />);

        const badge = screen.getByTestId('lane-badge');
        expect(badge).toHaveAttribute('data-lane', 'deliberate');
        expect(badge).toHaveAttribute('data-lane-variant', 'taken');
        expect(badge.getAttribute('title')).toMatch(/approve/i);
    });

    it('claims nothing about the Fast lane beyond the approval step', () => {
        // A Lane decides exactly one thing — whether the plan-review gate is
        // built — so that is the only thing the badge may claim. Two claims it
        // must not make, and one Quick Task falsifies each (#26):
        //
        // * a **latency** claim. Fast-lane latency is still unmeasured, and
        //   ADR-013 makes that measurement the sole trigger for reopening the
        //   orchestrator-bypass question. A tooltip is not the place the number
        //   gets asserted for the first time.
        // * an **answer**. The one-tap boundary probe declares the Fast lane
        //   and is never answered at all — the Identity boundary gate refuses
        //   it above the lane router — so a badge promising a reply is the
        //   surface saying something that is not so on the beat the whole
        //   governance argument turns on.
        render(<LaneBadge lane="fast" />);

        const title = screen.getByTestId('lane-badge').getAttribute('title') ?? '';
        expect(title).toMatch(/approval/i);
        expect(title).not.toMatch(/answer|straight away|second|fast|quick/i);
    });
});
