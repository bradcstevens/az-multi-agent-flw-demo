import { TeamConfig } from '../models/Team';
import { apiClient } from '../api/apiClient';

export class TeamService {
    /**
     * Upload a custom team configuration
     */
    static async uploadCustomTeam(teamFile: File): Promise<{ success: boolean; team?: TeamConfig; error?: string }> {
        try {
            const formData = new FormData();
            formData.append('file', teamFile);

            const response = await apiClient.upload('/upload_team_config', formData);

            return {
                success: true,
                team: response.data
            };
        } catch (error: any) {
            return {
                success: false,
                error: error.message || 'Failed to upload team configuration'
            };
        }
    }

    /**
     * Get user's custom teams
     */
    static async getUserTeams(): Promise<TeamConfig[]> {
        try {
            const response = await apiClient.get('/team_configs');
            return response.data || [];
        } catch (error) {
            console.error('Failed to fetch user teams:', error);
            return [];
        }
    }

    /**
     * Delete a custom team
     */
    static async deleteTeam(teamId: string): Promise<boolean> {
        try {
            await apiClient.delete(`/team_configs/${teamId}`);
            return true;
        } catch (error) {
            console.error('Failed to delete team:', error);
            return false;
        }
    }
}

export default TeamService;
