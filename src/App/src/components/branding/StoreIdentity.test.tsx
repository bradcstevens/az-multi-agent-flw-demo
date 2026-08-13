import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';

import StoreIdentity from './StoreIdentity';
import appReducer, { hydrateCurrentUser } from '../../store/slices/appSlice';

const renderWith = (user: Parameters<typeof hydrateCurrentUser>[0] | undefined) => {
    const store = configureStore({ reducer: { app: appReducer } });
    if (user !== undefined) {
        store.dispatch(hydrateCurrentUser(user));
    }
    return render(
        <Provider store={store}>
            <StoreIdentity />
        </Provider>,
    );
};

describe('the store identity', () => {
    it('shows the store the device is scoped to', () => {
        renderWith(undefined);

        expect(screen.getByTestId('store-identity-store')).toHaveTextContent('Store 223');
    });

    it('says plainly that nobody is signed in', () => {
        // The demo's opening state, and the half of the identity story the
        // boundary gate refuses on. An empty space here would read as a
        // rendering bug rather than as the anonymous shared device it is.
        renderWith(null);

        expect(screen.getByTestId('store-identity-user')).toHaveTextContent('No user signed in');
    });

    it('shows no personal name while anonymous', () => {
        renderWith(null);

        expect(screen.queryByTestId('store-identity-name')).not.toBeInTheDocument();
    });

    it('labels the store as simulated, because Store 223 is not a real store', () => {
        renderWith(null);

        expect(screen.getByTestId('store-identity')).toHaveTextContent(/simulated/i);
    });

    it('shows the named identity once somebody has signed in', () => {
        // #27 flips exactly this, by hydrating a user into the same slice.
        renderWith({ user_id: 'tanya-1', user_first_last_name: 'Tanya Miles' } as any);

        expect(screen.getByTestId('store-identity-name')).toHaveTextContent('Tanya Miles');
        expect(screen.queryByTestId('store-identity-user')).not.toBeInTheDocument();
    });

    it('treats the anonymous principal as nobody, not as a user named anonymous', () => {
        // EasyAuth is off on this deployment, so the backend hands back the
        // literal `anonymous` rather than nothing at all. Rendering that as a
        // signed-in identity would answer the personal question the gate is
        // there to refuse.
        renderWith({ user_id: 'anonymous', user_first_last_name: '' } as any);

        expect(screen.getByTestId('store-identity-user')).toHaveTextContent('No user signed in');
    });
});
