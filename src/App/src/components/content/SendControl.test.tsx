import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FluentProvider, teamsDarkTheme, teamsLightTheme } from '@fluentui/react-components';

import SendControl, { SEND_QUESTION } from './SendControl';

const inTheme = (theme: typeof teamsLightTheme) =>
    render(
        <FluentProvider theme={theme}>
            <SendControl label={SEND_QUESTION} onSend={vi.fn()} />
        </FluentProvider>,
    );

describe('the send control and the two themes', () => {
    it.each([
        ['light', teamsLightTheme],
        ['dark', teamsDarkTheme],
    ])('declares no colour of its own in the %s theme', (_name, theme) => {
        // The half the stylesheet guard cannot see. A rule in `styles/` about
        // this control is a rule Fluent overrides; an *inline* one is the
        // opposite failure and the one the plan surface actually had — a brand
        // foreground on a transparent background, hardcoded past the theme, so
        // the contrast it happened to meet in one theme was nobody's guarantee
        // in the other (#56). Colour is the theme's to state, in both.
        const { unmount } = inTheme(theme);
        const declared =
            screen.getByRole('button', { name: SEND_QUESTION }).getAttribute('style') ?? '';
        unmount();

        expect(declared).not.toMatch(/(^|[;\s])(color|background|border)/);
    });
});
