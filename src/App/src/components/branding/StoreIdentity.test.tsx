import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { readFileSync } from 'node:fs';

import StoreIdentity from './StoreIdentity';
import appReducer, { hydrateCurrentUser } from '../../store/slices/appSlice';
import {
    forgetSignedInDevice,
    rememberSignedInName,
} from '../../models/signedInDevice';
import { sourceFiles } from '@/testing/stylesheets';

const renderIdentity = () => {
    const store = configureStore({ reducer: { app: appReducer } });
    return render(
        <Provider store={store}>
            <StoreIdentity />
        </Provider>,
    );
};

beforeEach(() => {
    window.sessionStorage.clear();
    forgetSignedInDevice();
});

describe('the store identity', () => {
    it('shows the store the device is scoped to', () => {
        renderIdentity();

        expect(screen.getByTestId('store-identity-store')).toHaveTextContent('Store 223');
    });

    it('says plainly that nobody is signed in', () => {
        // The demo's opening state, and the half of the identity story the
        // boundary gate refuses on. An empty space here would read as a
        // rendering bug rather than as the anonymous shared device it is.
        renderIdentity();

        expect(screen.getByTestId('store-identity-user')).toHaveTextContent('No user signed in');
    });

    it('shows no personal name while anonymous', () => {
        renderIdentity();

        expect(screen.queryByTestId('store-identity-name')).not.toBeInTheDocument();
    });

    it('renders no simulation badge anywhere on the store surface', () => {
        // The old five renders were an enumeration, not an exhaustive test
        // fixture. Source-wide inspection makes a newly added card fail too.
        const badgedSources = sourceFiles().filter((path) =>
            /<SimulatedBadge\b|<Badge\b[^>]*>[\s\S]*?(?:simulated-badge|SIMULATED_LABEL|Simulated)/.test(
                readFileSync(path, 'utf8'),
            ),
        );

        expect(badgedSources, 'simulation badges must not return to any surface state').toEqual([]);
    });

    it('renders no chip beside the store while anonymous', () => {
        renderIdentity();

        expect(screen.queryByTestId('simulated-badge')).not.toBeInTheDocument();
    });

    it('shows the named identity once the mocked sign-in has run', () => {
        // The closing beat's visible half (#27): the header gains a name, and
        // the delta between this render and the one above it is the whole
        // licensing and governance conversation the customer has been avoiding.
        rememberSignedInName('Clara Workman');

        renderIdentity();

        expect(screen.getByTestId('store-identity-name')).toHaveTextContent('Clara Workman');
        expect(screen.queryByTestId('store-identity-user')).not.toBeInTheDocument();
    });

    it('renders no chip beside the named identity', () => {
        rememberSignedInName('Clara Workman');

        renderIdentity();

        expect(screen.queryByTestId('simulated-badge')).not.toBeInTheDocument();
    });

    it('offers a way back to the anonymous, refusing state', async () => {
        rememberSignedInName('Clara Workman');
        renderIdentity();

        await userEvent.click(screen.getByTestId('store-identity-sign-out'));

        expect(screen.getByTestId('store-identity-user')).toHaveTextContent(
            'No user signed in',
        );
    });

    it('offers no sign-out while nobody is signed in', () => {
        renderIdentity();

        expect(screen.queryByTestId('store-identity-sign-out')).not.toBeInTheDocument();
    });

    it('ignores the EasyAuth principal entirely', () => {
        // Two identities that can disagree are one identity too many. The
        // Identity boundary gate reads **Session state** and nothing else
        // (ADR-014), so a header driven by the deployment's login would claim
        // an identity the gate never sees — and on this deployment EasyAuth is
        // off, so it would claim it while every personal question is refused.
        const store = configureStore({ reducer: { app: appReducer } });
        store.dispatch(
            hydrateCurrentUser({
                user_id: 'someone',
                user_first_last_name: 'Someone Else',
            } as any),
        );

        render(
            <Provider store={store}>
                <StoreIdentity />
            </Provider>,
        );

        expect(screen.getByTestId('store-identity-user')).toHaveTextContent('No user signed in');
        expect(screen.queryByText('Someone Else')).not.toBeInTheDocument();
    });

    it('names nobody the backend did not name', () => {
        // The browser never authors the associate's name: it stores what the
        // sign-in route returned, and a blank one signed nobody in.
        rememberSignedInName('   ');
        renderIdentity();

        expect(screen.getByTestId('store-identity-user')).toHaveTextContent('No user signed in');
    });
});
