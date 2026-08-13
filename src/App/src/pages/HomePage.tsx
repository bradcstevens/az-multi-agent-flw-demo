import React, { useEffect, useCallback } from 'react';
import { Spinner } from '@fluentui/react-components';
import '../styles/PlanPage.css';
import CoralShellColumn from '../commonComponents/components/Layout/CoralShellColumn';
import CoralShellRow from '../commonComponents/components/Layout/CoralShellRow';
import Content from '../commonComponents/components/Content/Content';
import HomeInput from '@/components/content/HomeInput';
import TransparencyRail from '@/components/transparency/TransparencyRail';
import { NewTaskService } from '../store/NewTaskService';
import PlanPanelLeft from '@/components/content/PlanPanelLeft';
import ContentToolbar from '@/commonComponents/components/Content/ContentToolbar';
import { TeamService } from '../store/TeamService';
import StoreIdentity from '../components/branding/StoreIdentity';
import { ASSISTANT_NAME, selectStoreAssistant } from '../models/storeSurface';
import InlineToaster, { useInlineToaster } from '../components/toast/InlineToaster';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import {
    selectSelectedTeam,
    selectIsLoadingTeam,
    setSelectedTeam,
    setIsLoadingTeam,
} from '../store/slices/teamSlice';
import { selectReloadLeftList } from '../store/slices/planSlice';

/**
 * HomePage component - displays task lists and provides navigation
 * Accessible via the route "/"
 */
const HomePage: React.FC = () => {
    const dispatch = useAppDispatch();
    const { showToast } = useInlineToaster();
    const selectedTeam = useAppSelector(selectSelectedTeam);
    const isLoadingTeam = useAppSelector(selectIsLoadingTeam);
    const reloadLeftList = useAppSelector(selectReloadLeftList);

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
            dispatch(setIsLoadingTeam(true));
            try {
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

                // The backend still has to build the workflow for it; the
                // response is only interesting when it fails.
                const initResponse = await TeamService.initializeTeam();
                if (!initResponse.success) {
                    console.error('Store assistant init failed:', initResponse.error);
                    showToast('The store assistant could not be started. Please try again.', 'warning');
                }
            } catch (error) {
                console.error('Store assistant initialization error:', error);
                dispatch(setSelectedTeam(null));
                showToast('The store assistant could not be reached.', 'warning');
            } finally {
                dispatch(setIsLoadingTeam(false));
            }
        };

        initTeam();
    }, [dispatch]); // eslint-disable-line react-hooks/exhaustive-deps

    const handleNewTaskButton = useCallback(() => {
        NewTaskService.handleNewTaskFromHome();
    }, []);

    return (
        <>
            <InlineToaster />
            <CoralShellColumn>
                <CoralShellRow>
                    <PlanPanelLeft
                        reloadTasks={reloadLeftList}
                        onNewTaskButton={handleNewTaskButton}
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
                      surface as well as the plan surface because the meter is
                      a running total across the whole walkthrough: the
                      identity boundary gate refuses a question *here*, and the
                      row proving that refusal cost nothing has to be beside
                      the rows that did cost something.
                    */}
                    <TransparencyRail team={selectedTeam} />
                </CoralShellRow>
            </CoralShellColumn>
        </>
    );
};

const MemoizedHomePage = React.memo(HomePage);
MemoizedHomePage.displayName = 'HomePage';
export default MemoizedHomePage;