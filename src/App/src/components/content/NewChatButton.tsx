import React from 'react';
import { Button } from '@fluentui/react-components';
import { ChatAdd20Regular } from '@fluentui/react-icons';

import { NEW_CHAT_LABEL } from '@/models/storeSurface';

interface NewChatButtonProps {
    onClick: () => void;
}

/** Starts a Chat from the content toolbar, whether history is open or closed. */
const NewChatButton: React.FC<NewChatButtonProps> = ({ onClick }) => (
    <Button appearance="subtle" icon={<ChatAdd20Regular />} onClick={onClick}>
        {NEW_CHAT_LABEL}
    </Button>
);

export default NewChatButton;
