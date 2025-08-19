export interface QuickTask {
    id: string;
    title: string;
    description: string;
    icon: React.ReactNode | string;
}

export interface HomeInputProps {
    selectedTeam?: TeamConfig | null;
}

import { TeamConfig } from './Team';
