import React from 'react';
import { Button } from '@fluentui/react-components';
import { PanelRightContract20Regular } from '@fluentui/react-icons';

import useDesktopDrawer from '@/hooks/useDesktopDrawer';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
    selectTransparencyRailExpanded,
    transparencyRailToggled,
} from '@/store/slices/transparencySlice';

const TransparencyRailToggle: React.FC = () => {
    const dispatch = useAppDispatch();
    const isDesktopDrawer = useDesktopDrawer();
    const expanded = useAppSelector(selectTransparencyRailExpanded);

    if (!isDesktopDrawer) return null;

    return (
        <Button
            appearance="subtle"
            className="transparency-rail-toggle"
            icon={<PanelRightContract20Regular />}
            aria-controls="transparency-rail"
            aria-expanded={expanded}
            onClick={() => dispatch(transparencyRailToggled())}
        >
            Transparency panels
        </Button>
    );
};

export default TransparencyRailToggle;
