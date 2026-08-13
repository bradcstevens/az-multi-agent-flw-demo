import React from 'react';
import { Button, Caption1, Caption1Strong } from '@fluentui/react-components';
import {
    BuildingRetail20Regular,
    PersonProhibited20Regular,
    Person20Regular,
    SignOut20Regular,
} from '@fluentui/react-icons';

import { forgetSignedInDevice } from '../../models/signedInDevice';
import { useSignedInName } from '../../hooks/useSignedInDevice';
import { ANONYMOUS_IDENTITY_LABEL, STORE_LABEL } from '../../models/storeSurface';
import SimulatedBadge from './SimulatedBadge';
import '../../styles/storeSurface.css';

/**
 * The store identity (issue #25) — the store this shared device belongs to,
 * and who is signed in on it.
 *
 * Both halves are the demo's argument. The store is why the assistant may
 * decline a personal question; the *absence* of a user is what makes the
 * decline correct rather than rude, and it is the thing the **Mocked unlock**
 * changes (#27). So the anonymous state is stated out loud rather than left as
 * blank space — blank space reads as a component that failed to load, and the
 * audience has to be able to see the "before" of the before-and-after.
 *
 * **The name shown is the Session identity, never the EasyAuth principal.** The
 * Identity boundary gate reads server-side **Session state** and nothing else
 * (ADR-014); a header driven by the deployment's login would be a second
 * identity, free to disagree with the one that actually governs the answer. On
 * this deployment EasyAuth is off, so that second identity would have claimed a
 * signed-in user while every personal question went on being refused.
 *
 * Signing out is **forgetting** — the next request is created anonymous, which
 * is the refusing state. There is nothing to revoke, because there was never an
 * identity provider to revoke it with.
 */
const StoreIdentity: React.FC = () => {
    const signedInName = useSignedInName();

    return (
        <div className="store-identity" data-testid="store-identity">
            <span className="store-identity__store" data-testid="store-identity-store">
                <BuildingRetail20Regular aria-hidden="true" />
                <Caption1Strong>{STORE_LABEL}</Caption1Strong>
            </span>

            <SimulatedBadge what={STORE_LABEL} />

            {signedInName ? (
                <span className="store-identity__user" data-testid="store-identity-name">
                    <Person20Regular aria-hidden="true" />
                    <Caption1Strong>{signedInName}</Caption1Strong>
                    <SimulatedBadge what="This sign-in" />
                    <Button
                        appearance="subtle"
                        size="small"
                        data-testid="store-identity-sign-out"
                        icon={<SignOut20Regular />}
                        onClick={forgetSignedInDevice}
                    >
                        Sign out
                    </Button>
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
