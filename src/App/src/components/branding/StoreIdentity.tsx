import React from 'react';
import { Caption1, Caption1Strong } from '@fluentui/react-components';
import {
    BuildingRetail20Regular,
    PersonProhibited20Regular,
    Person20Regular,
} from '@fluentui/react-icons';

import { useAppSelector } from '../../store/hooks';
import { ANONYMOUS_IDENTITY_LABEL, STORE_LABEL } from '../../models/storeSurface';
import SimulatedBadge from './SimulatedBadge';
import '../../styles/storeSurface.css';

/**
 * The store identity (issue #25) — the store this shared device belongs to,
 * and who is signed in on it.
 *
 * Both halves are the demo's argument. The store is why the assistant may
 * decline a personal question; the *absence* of a user is what makes the
 * decline correct rather than rude, and it is the thing #27's sign-in changes.
 * So the anonymous state is stated out loud rather than left as blank space —
 * blank space reads as a component that failed to load, and the audience has to
 * be able to see the "before" of the before-and-after.
 *
 * `anonymous` is the literal principal the backend hands back when EasyAuth is
 * off, so it is nobody, not somebody called anonymous.
 */
const StoreIdentity: React.FC = () => {
    const userId = useAppSelector((state) => state.app.userId);
    const userName = useAppSelector((state) => state.app.userName);
    const isSignedIn = Boolean(userId) && userId !== 'anonymous';
    const displayName = userName?.trim() || userId;

    return (
        <div className="store-identity" data-testid="store-identity">
            <span className="store-identity__store" data-testid="store-identity-store">
                <BuildingRetail20Regular aria-hidden="true" />
                <Caption1Strong>{STORE_LABEL}</Caption1Strong>
            </span>

            <SimulatedBadge what={STORE_LABEL} />

            {isSignedIn ? (
                <span className="store-identity__user" data-testid="store-identity-name">
                    <Person20Regular aria-hidden="true" />
                    <Caption1Strong>{displayName}</Caption1Strong>
                </span>
            ) : (
                <span className="store-identity__user" data-testid="store-identity-user">
                    <PersonProhibited20Regular aria-hidden="true" />
                    <Caption1>{ANONYMOUS_IDENTITY_LABEL}</Caption1>
                </span>
            )}
        </div>
    );
};

export default StoreIdentity;
