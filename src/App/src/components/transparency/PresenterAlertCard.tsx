import React from 'react';
import { Badge, Body1, Body1Strong } from '@fluentui/react-components';
import { Alert24Regular } from '@fluentui/react-icons';

import { PresenterAlert } from '../../models/transparency';
import SimulatedBadge from '../branding/SimulatedBadge';

/**
 * The Presenter alert, rendered (issue #24, R8).
 *
 * An alert is **not a reply**. It answers no question, because nobody asked
 * one — that is the entire beat: the assistant reaches the associate rather
 * than waiting to be reached. Rendered in the reply stream it would read as an
 * answer to whatever was asked last, which is worse than not showing it, so it
 * is visibly a different object: `role="alert"`, its own icon and badge, a
 * title where a reply carries an agent name, and a label that says out loud
 * that it arrived unasked.
 */
export interface PresenterAlertCardProps {
    alert: PresenterAlert;
}

const PresenterAlertCard: React.FC<PresenterAlertCardProps> = ({ alert }) => (
    <div
        className="presenter-alert"
        role="alert"
        aria-live="polite"
        data-testid="presenter-alert"
        data-message-kind="alert"
    >
        <div className="presenter-alert__header">
            <Alert24Regular aria-hidden="true" />
            <Body1Strong>{alert.title}</Body1Strong>
            <Badge appearance="outline" color="warning" data-testid="presenter-alert-kind">
                Proactive alert
            </Badge>
            {/*
              The words are the server's, chosen from a rehearsed roster (#23)
              rather than produced by a shift-task system this demo talks to.
              An audience that finds that out afterwards discounts the panels
              that *are* connected, so it is said here rather than discovered.
            */}
            <SimulatedBadge what="This shift task" />
        </div>
        <Body1 className="presenter-alert__content">{alert.content}</Body1>
    </div>
);

export default PresenterAlertCard;
