import { TeamConfig } from '../models/Team';
import { apiClient } from '../api/apiClient';

export class TeamService {
    /**
     * Upload a custom team configuration
     */
    static async uploadCustomTeam(teamFile: File): Promise<{ success: boolean; team?: TeamConfig; error?: string; raiError?: any }> {
        try {
            console.log('TeamService: Starting team upload for file:', teamFile.name);
            const formData = new FormData();
            formData.append('file', teamFile);

            console.log('TeamService: Calling /upload_team_config endpoint...');
            const response = await apiClient.upload('/upload_team_config', formData);
            console.log('TeamService: Upload response:', response);
            console.log('TeamService: Upload response data:', response.data);

            return {
                success: true,
                team: response.data
            };
        } catch (error: any) {
            console.error('TeamService: Upload failed:', error);
            console.error('TeamService: Upload error details:', error.response?.data);
            
            // Check if this is an RAI validation error
            const errorDetail = error.response?.data?.detail || error.response?.data;
            
            // If the error message contains "inappropriate content", treat it as RAI error
            if (typeof errorDetail === 'string' && errorDetail.includes('inappropriate content')) {
                return {
                    success: false,
                    raiError: {
                        error_type: 'RAI_VALIDATION_FAILED',
                        message: errorDetail,
                        description: errorDetail
                    }
                };
            }
            
            // Get error message from the response
            let errorMessage = error.message || 'Failed to upload team configuration';
            if (error.response?.data?.detail) {
                errorMessage = error.response.data.detail;
            }
            
            return {
                success: false,
                error: errorMessage
            };
        }
    }

    /**
     * Get user's custom teams
     */
    static async getUserTeams(): Promise<TeamConfig[]> {
        try {
            console.log('TeamService: Calling /team_configs endpoint...');
            const response = await apiClient.get('/team_configs');
            console.log('TeamService: API response:', response);
            
            // The apiClient returns the response data directly, not wrapped in a data property
            const teams = Array.isArray(response) ? response : [];
            
            console.log('TeamService: Parsed teams:', teams);
            console.log('TeamService: Number of teams returned:', teams.length);
            return teams;
        } catch (error: any) {
            console.error('TeamService: Failed to fetch user teams:', error);
            console.error('TeamService: Error details:', error.response?.data);
            return [];
        }
    }

    /**
     * Get a specific team by ID
     */
    static async getTeamById(teamId: string): Promise<TeamConfig | null> {
        try {
            console.log('TeamService: Getting team by ID:', teamId);
            const teams = await this.getUserTeams();
            const team = teams.find(t => t.team_id === teamId);
            console.log('TeamService: Found team:', team?.name || 'Not found');
            return team || null;
        } catch (error: any) {
            console.error('TeamService: Failed to get team by ID:', error);
            return null;
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
