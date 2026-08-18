import React from 'react';
import { Badge, Body1Strong, Caption1, Caption1Strong } from '@fluentui/react-components';
import { ArrowRight16Regular, DocumentSearch20Regular } from '@fluentui/react-icons';

import { SourceUsed } from '../../models/transparency';
import { SECTION_HEADING } from '../../models/headingOutline';

/**
 * The Grounding panel (issue #24, R6).
 *
 * Its claim is not "a document was found". It is **this one answer left
 * Foundry** — so the panel leads with the platform and shows the route, and the
 * documents are the detail underneath rather than the headline. The route ends
 * at **Dataverse**, which is where the SOP corpus actually lives (ADR-012);
 * naming SharePoint would describe an architecture this demo deliberately does
 * not have.
 *
 * Two signals combined, as the requirement demands and as neither alone
 * satisfies: `platform` proves which platform answered, and the citations
 * parsed out of the SOP agent's own reply supply the document detail. Both
 * arrive together on the `source_used` payload because the backend put them
 * there, at the bridge where the hop actually happened.
 *
 * Three states, and the difference between them is the whole point:
 *
 * - **cited** — the route, and what came back.
 * - **uncited** — the route, and *nothing came back*. That is the rehearsed
 *   out-of-corpus probe: an honest miss, not a failure, and visibly not a
 *   **Policy block** (which never reaches this panel at all — it is a refused
 *   request, rendered where the question was asked).
 * - **no signal** — the panel describes itself and asserts nothing. It does
 *   *not* say the answer came from Foundry: nobody told it that, and a surface
 *   may say nothing but may not say something that is not so.
 */
export interface GroundingPanelProps {
    source: SourceUsed | null;
}

/** Where every cross-platform answer starts. */
export const ROUTE_ORIGIN = 'Foundry orchestrator';
export const COPILOT_STUDIO_PLATFORM = 'Copilot Studio';
export const SOP_TOOL_ROUTE_SEGMENT = 'search_store_procedures (MCP tool, plain HTTP)';
export const SOP_ASK_ROUTE_SEGMENT = 'POST /sop/ask';
export const DIRECT_LINE_ROUTE_SEGMENT = 'Direct Line';

const GroundingPanel: React.FC<GroundingPanelProps> = ({ source }) => (
    <section
        className="transparency-panel"
        data-testid="grounding-panel"
        data-tool-query={source?.toolQuery}
        data-retrieval-query={source?.retrievalQuery}
    >
        <Body1Strong as={SECTION_HEADING} className="transparency-panel__title">
            <DocumentSearch20Regular aria-hidden="true" /> Grounding
        </Body1Strong>

        {!source ? (
            <Caption1 data-testid="grounding-empty" className="transparency-panel__empty">
                Ask a store procedure question and this panel will show which platform answered
                and which documents it answered from.
            </Caption1>
        ) : (
            <>
                <div className="grounding-panel__platform">
                    <Badge
                        appearance="tint"
                        color="brand"
                        data-testid="grounding-platform"
                        data-platform={source.platform}
                        title="This answer was produced on a different platform from every other agent here"
                    >
                        {source.platform}
                    </Badge>
                    {source.agentName && <Caption1>{source.agentName}</Caption1>}
                </div>

                <div className="grounding-panel__route" data-testid="grounding-route">
                    <Caption1>{ROUTE_ORIGIN}</Caption1>
                    <ArrowRight16Regular aria-hidden="true" />
                    {source.platform === COPILOT_STUDIO_PLATFORM && (
                        <>
                            <Caption1>{SOP_TOOL_ROUTE_SEGMENT}</Caption1>
                            <ArrowRight16Regular aria-hidden="true" />
                            <Caption1>{SOP_ASK_ROUTE_SEGMENT}</Caption1>
                            <ArrowRight16Regular aria-hidden="true" />
                            <Caption1>{DIRECT_LINE_ROUTE_SEGMENT}</Caption1>
                            <ArrowRight16Regular aria-hidden="true" />
                        </>
                    )}
                    <Caption1>{source.platform}</Caption1>
                    {source.source && (
                        <>
                            <ArrowRight16Regular aria-hidden="true" />
                            <Caption1>{source.source}</Caption1>
                        </>
                    )}
                </div>

                {source.citations.length === 0 ? (
                    <Caption1
                        data-testid="grounding-miss"
                        className="grounding-panel__miss"
                        role="note"
                    >
                        Searched {source.source || 'the store procedures'} and found no matching
                        procedure. The assistant answers from these documents only, so it said so
                        rather than guessing.
                    </Caption1>
                ) : (
                    <ul className="grounding-panel__citations" data-testid="grounding-citations">
                        {source.citations.map((citation, index) => (
                            <li
                                key={`${citation.position}-${citation.name}-${index}`}
                                className="grounding-panel__citation"
                            >
                                <Caption1Strong>
                                    {/*
                                      A citation the backend could not name is
                                      still a document that came back. Labelling
                                      it for what it is keeps it out of the miss
                                      branch without inventing a title for it.
                                    */}
                                    {citation.name || 'Unnamed document'}
                                </Caption1Strong>
                                {citation.snippet && <Caption1>{citation.snippet}</Caption1>}
                            </li>
                        ))}
                    </ul>
                )}
            </>
        )}
    </section>
);

export default GroundingPanel;
