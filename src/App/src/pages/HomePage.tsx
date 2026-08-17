import React, { useEffect, useCallback } from 'react';
import { Spinner } from '@fluentui/react-components';
import '../styles/ChatPage.css';
import CoralShellColumn from '../commonComponents/components/Layout/CoralShellColumn';
import CoralShellRow from '../commonComponents/components/Layout/CoralShellRow';
import Content from '../commonComponents/components/Content/Content';
import HomeInput from '@/components/content/HomeInput';
import TransparencyRail from '@/components/transparency/TransparencyRail';
import AgentTeamPanel from '@/components/transparency/AgentTeamPanel';
import { NewChatService } from '../store/NewChatService';
import ChatPanelLeft from '@/components/content/ChatPanelLeft';
import ContentToolbar from '@/commonComponents/components/Content/ContentToolbar';
import { TeamService } from '../store/TeamService';
import { waitForRuntimeBootstrap } from '../api/config';
import StoreIdentity from '../components/branding/StoreIdentity';
import { ASSISTANT_NAME, selectStoreAssistant } from '../models/storeSurface';
import InlineToaster, { useInlineToaster } from '../components/toast/InlineToaster';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import {
    selectSelectedTeam,
    selectIsLoadingTeam,
    selectTeamAgentCount,
    setSelectedTeam,
    setIsLoadingTeam,
} from '../store/slices/teamSlice';
import { selectReloadLeftList } from '../store/slices/planSlice';

/**
 * HomePage component - displays the chat history and provides navigation
 * Accessible via the route "/"
 */
const HomePage: React.FC = () => {
    const dispatch = useAppDispatch();
    const { showToast } = useInlineToaster();
    const selectedTeam = useAppSelector(selectSelectedTeam);
    const isLoadingTeam = useAppSelector(selectIsLoadingTeam);
    const reloadLeftList = useAppSelector(selectReloadLeftList);

    /*
     * How many specialists are **available**, for the rail (issue #79).
     *
     * `selectTeamAgentCount` rather than a `.length` beside it, for the reason
     * `PlanPanelRight` reads the same selector: the roster has one count, and a
     * second one derived at a call site is a second thing to disagree with it.
     */
    const availableCount = useAppSelector(selectTeamAgentCount);

    /*
     * The one assistant, resolved (issue #25).
     *
     * `selectStoreAssistant` recognises the store assistant rather than taking
     * whatever the backend listed first. That is where the accelerator's stock
     * content packs are suppressed: a deployment that still holds the HR
     * Onboarding or RFP Evaluation packs would otherwise put one of them under
     * the Circle K header, and a surface that is branded as one assistant while
     * running another is the one thing these surfaces may not do.
     *
     * No assistant is therefore a state the surface has to be able to be in,
     * and it says so plainly instead of quietly picking a stranger.
     */
    useEffect(() => {
        const initTeam = async () => {
            if (selectedTeam) {
                dispatch(setIsLoadingTeam(false));
                return;
            }

            dispatch(setIsLoadingTeam(true));
            try {
                await waitForRuntimeBootstrap();
                const teams = await TeamService.getUserTeams();
                const storeAssistant = selectStoreAssistant(teams);

                if (!storeAssistant) {
                    TeamService.clearStoredTeam();
                    dispatch(setSelectedTeam(null));
                    showToast(
                        `${ASSISTANT_NAME} is not loaded on this deployment.`,
                        'warning',
                    );
                    return;
                }

                dispatch(setSelectedTeam(storeAssistant));
                TeamService.storageTeam(storeAssistant);

                // Team attachment is enough to accept a question. The first
                // request declares the Lane that configures its Workflow.
                void TeamService.initializeTeam(storeAssistant.team_id)
                    .then((initResponse) => {
                        if (!initResponse.success) {
                            console.error('Store assistant init failed:', initResponse.error);
                            showToast('The store assistant could not be started. Please try again.', 'warning');
                        }
                    })
                    .catch((error) => {
                        console.error('Store assistant initialization error:', error);
                        showToast('The store assistant could not be reached.', 'warning');
                    });
            } catch (error) {
                console.error('Store assistant initialization error:', error);
                dispatch(setSelectedTeam(null));
                showToast('The store assistant could not be reached.', 'warning');
            } finally {
                dispatch(setIsLoadingTeam(false));
            }
        };

        initTeam();
    }, [dispatch, selectedTeam]); // eslint-disable-line react-hooks/exhaustive-deps

    const handleNewChatButton = useCallback(() => {
        NewChatService.handleNewChatFromHome();
    }, []);

    return (
        <>
            <InlineToaster />
            <CoralShellColumn>
                <CoralShellRow>
                    <ChatPanelLeft
                        reloadChats={reloadLeftList}
                        onNewChatButton={handleNewChatButton}
                        isLoadingTeam={isLoadingTeam}
                    />
                    <Content>
                        <ContentToolbar panelTitle={ASSISTANT_NAME}>
                            <StoreIdentity />
                        </ContentToolbar>
                        {!isLoadingTeam ? (
                            <HomeInput selectedTeam={selectedTeam} />
                        ) : (
                            <div
                                style={{
                                    display: 'flex',
                                    justifyContent: 'center',
                                    alignItems: 'center',
                                    height: '200px',
                                }}
                            >
                                <Spinner label="Starting the store assistant..." />
                            </div>
                        )}
                    </Content>
                    {/*
                      The transparency rail (issue #24). It is on the home
                      surface as well as the chat surface because the meter is
                      a running total across the whole walkthrough: the
                      identity boundary gate refuses a question *here*, and the
                      row proving that refusal cost nothing has to be beside
                      the rows that did cost something.

                      It heads that rail with who is **available** (issue #79).
                      The **store assistant roster** is the one this page has
                      already resolved, so the count needs no request of its own
                      and is the only claim this surface may make: the beat it
                      owns is the one where the number that participate is zero.
                      There is no conversation on the home surface, so the panel
                      is given no conversation roster to prefer.

                      Rendered only where there *is* a roster, on #78's rule.
                      `selectedTeam` is null for the whole of the team fetch and
                      again on a deployment with no store assistant, and the
                      panel's empty state — "No agent roster loaded for this
                      conversation." — is wrong twice over here: it would sit
                      beside a spinner reading "Starting the store assistant…",
                      which is #65's contradiction moved one surface across, and
                      it speaks of a conversation that does not exist. The
                      surface already says the honest version of the second case
                      once, in the middle of the screen, and once is enough.
                    */}
                    <TransparencyRail team={selectedTeam}>
                        {selectedTeam && (
                            <AgentTeamPanel
                                available={selectedTeam}
                                availableCount={availableCount}
                            />
                        )}
                    </TransparencyRail>
                </CoralShellRow>
            </CoralShellColumn>
        </>
    );
};

const MemoizedHomePage = React.memo(HomePage);
MemoizedHomePage.displayName = 'HomePage';
export default MemoizedHomePage;