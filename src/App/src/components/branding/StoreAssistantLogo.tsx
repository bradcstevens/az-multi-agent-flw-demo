import React from 'react';

/**
 * The store assistant's mark (issue #25).
 *
 * Deliberately an abstract storefront rather than a reproduction of Circle K's
 * trademark: this is a demonstration built for a customer conversation, not a
 * licensed use of their brand assets, and a wrong-looking copy of a real logo
 * on a stakeholder's screen is worse than an honest placeholder. The wordmark
 * beside it carries the name.
 */
const StoreAssistantLogo: React.FC = () => (
    <svg
        width="32"
        height="32"
        viewBox="0 0 32 32"
        fill="none"
        role="img"
        aria-label="Store assistant"
        data-testid="store-assistant-logo"
        xmlns="http://www.w3.org/2000/svg"
    >
        <path
            d="M5 12.5 8 6h16l3 6.5v2a3 3 0 0 1-5.5 1.7 3 3 0 0 1-5 0 3 3 0 0 1-5 0A3 3 0 0 1 5 14.5v-2Z"
            fill="var(--colorBrandForeground1)"
        />
        <path
            d="M7 18.2V25a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1v-6.8"
            stroke="var(--colorBrandForeground1)"
            strokeWidth="2"
            strokeLinecap="round"
        />
        <path
            d="M13 26v-5h6v5"
            stroke="var(--colorBrandForeground1)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        />
    </svg>
);

export default StoreAssistantLogo;
