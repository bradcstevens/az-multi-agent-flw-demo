import React from 'react';
import {
    Text,
} from "@fluentui/react-components";

/**
 * The words are the caller's, and the caller reads them from
 * `models/progressNarration.ts` (issue #64, ADR-023). This module used to
 * export four of its own — *"Initializing AI agents..."* and three more — that
 * `PlanPage` rotated on a 3000ms timer keyed to a GET being in flight. Nothing
 * scaffolded and nothing optimised.
 */
export interface LoadingMessageProps {
    loadingMessage: string;
    iconSrc?: string;
    iconWidth?: number;
    iconHeight?: number;
}

const LoadingMessage: React.FC<LoadingMessageProps> = ({
    loadingMessage,
    iconSrc,
    iconWidth = 64,
    iconHeight = 64
}) => {
    return (
        <div className="loadingWrapper">
            {iconSrc && (
                <img
                    src={iconSrc}
                    alt="Loading animation"
                    style={{ width: iconWidth, height: iconHeight }}
                />
            )}
            <Text>{loadingMessage}</Text>
        </div>
    );
};

export default LoadingMessage;