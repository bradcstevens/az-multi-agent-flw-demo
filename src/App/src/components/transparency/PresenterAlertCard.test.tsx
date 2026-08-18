import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import PresenterAlertCard from './PresenterAlertCard';
import { parsePresenterAlert } from '../../models/transparency';

const provenance = 'A Provenance line received from the backend.';

const alert = parsePresenterAlert({
    title: 'Shift task due',
    content: 'The coffee station deep clean is due before the 15:00 handover at Store 223.',
    timestamp: '2026-08-13T09:00:00+00:00',
    provenance_line: provenance,
})!;

describe('the Presenter alert', () => {
    it('shows the title and the words the server chose', () => {
        render(<PresenterAlertCard alert={alert} />);

        expect(screen.getByText('Shift task due')).toBeInTheDocument();
        expect(screen.getByText(/coffee station deep clean/)).toBeInTheDocument();
    });

    it('renders as an alert and not as a reply, so it is never mistaken for an answer', () => {
        render(<PresenterAlertCard alert={alert} />);

        const card = screen.getByTestId('presenter-alert');
        expect(card).toHaveAttribute('role', 'alert');
        expect(card).toHaveAttribute('data-message-kind', 'alert');
        // An agent reply carries an agent name; an alert carries a title and
        // deliberately no agent, because nothing was asked.
        expect(screen.queryByTestId('agent-message')).not.toBeInTheDocument();
    });

    it('says out loud that nobody asked for it', () => {
        render(<PresenterAlertCard alert={alert} />);

        expect(screen.getByTestId('presenter-alert-kind')).toHaveTextContent(/proactive/i);
    });

    it('is labelled as simulated, because the shift task is rehearsed', () => {
        // The alert's words come from a rehearsed roster in the backend, not
        // from a shift-task system this demo is connected to (#23). A
        // stakeholder who discovers that afterwards discounts everything else
        // on the surface — including the parts that are real.
        render(<PresenterAlertCard alert={alert} />);

        expect(screen.getByTestId('presenter-alert')).toHaveTextContent(/simulated/i);
    });

    it('renders the provenance line the server delivered', () => {
        render(<PresenterAlertCard alert={alert} />);

        expect(screen.getByTestId('presenter-alert-provenance')).toHaveTextContent(provenance);
    });

    it('renders no provenance line when the payload carries none', () => {
        const alertWithoutProvenance = parsePresenterAlert({
            title: 'Shift task due',
            content: 'The coffee station deep clean is due before the 15:00 handover at Store 223.',
            timestamp: '2026-08-13T09:00:00+00:00',
        })!;

        render(<PresenterAlertCard alert={alertWithoutProvenance} />);

        expect(screen.queryByTestId('presenter-alert-provenance')).not.toBeInTheDocument();
    });
});
