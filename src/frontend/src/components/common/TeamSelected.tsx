import { TeamConfig } from "@/models";
import { Body1, Caption1 } from "@fluentui/react-components";

export interface TeamSelectedProps {
    selectedTeam?: TeamConfig | null;
    styles: { [key: string]: string };
}

const TeamSelected: React.FC<TeamSelectedProps> = ({ selectedTeam, styles }) => {
    return (
        <div className={styles.teamSelectorContent}>
            <Caption1 className={styles.currentTeamLabel}>
                Current Team
            </Caption1>
            <Body1 className={styles.currentTeamName}>
                {selectedTeam ? selectedTeam.name : 'No team selected'}
            </Body1>
        </div>
    );
}
export default TeamSelected;