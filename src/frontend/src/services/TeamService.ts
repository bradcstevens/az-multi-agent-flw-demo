import { TeamConfig } from '../models/Team';
import { apiClient } from '../api/apiClient';

// Hardcoded default teams (will be replaced with API call)
const HARDCODED_TEAMS: TeamConfig[] = [
    {
        team_id: "retail-concierge-001",
        name: "Retail Concierge",
        description: "Resolve complex customer service issues for luxury retail",
        status: "active",
        created: new Date().toISOString(),
        created_by: "system",
        logo: "🛍️",
        plan: "Provide exceptional customer service experience",
        agents: [
            {
                id: "agent-customer-service-001",
                name: "Customer Service Agent",
                description: "Handles general customer inquiries and complaints",
                role: "primary",
                capabilities: ["customer_support", "complaint_resolution", "order_management"]
            },
            {
                id: "agent-loyalty-program-001",
                name: "Loyalty Program Agent", 
                description: "Manages customer loyalty programs and rewards",
                role: "specialist",
                capabilities: ["loyalty_management", "rewards_processing", "tier_upgrades"]
            },
            {
                id: "agent-product-specialist-001",
                name: "Product Agent",
                description: "Provides detailed product information and recommendations",
                role: "specialist", 
                capabilities: ["product_knowledge", "recommendations", "inventory_check"]
            },
            {
                id: "agent-reasoning-coordinator-001",
                name: "Reasoning Agent",
                description: "Analyzes complex scenarios and provides strategic solutions",
                role: "coordinator",
                capabilities: ["strategic_analysis", "decision_making", "escalation_handling"]
            }
        ],
        starting_tasks: [
            "Handle customer complaint about delayed order",
            "Process loyalty points redemption",
            "Recommend products based on customer preferences",
            "Resolve billing dispute"
        ]
    },
    {
        team_id: "healthcare-support-001",
        name: "Healthcare Support",
        description: "Provide comprehensive healthcare assistance and patient support",
        status: "active",
        created: new Date().toISOString(),
        created_by: "system",
        logo: "🏥",
        plan: "Deliver quality healthcare support services",
        agents: [
            {
                id: "agent-patient-care-001",
                name: "Patient Care Agent",
                description: "Manages patient interactions and care coordination",
                role: "primary",
                capabilities: ["patient_communication", "care_coordination", "appointment_scheduling"]
            },
            {
                id: "agent-medical-records-001",
                name: "Medical Records Agent",
                description: "Handles medical records and documentation",
                role: "specialist",
                capabilities: ["records_management", "documentation", "compliance_check"]
            },
            {
                id: "agent-insurance-specialist-001",
                name: "Insurance Agent",
                description: "Processes insurance claims and coverage verification",
                role: "specialist",
                capabilities: ["insurance_verification", "claims_processing", "coverage_analysis"]
            },
            {
                id: "agent-clinical-reasoning-001",
                name: "Clinical Reasoning Agent",
                description: "Provides clinical decision support and analysis",
                role: "coordinator",
                capabilities: ["clinical_analysis", "decision_support", "risk_assessment"]
            }
        ],
        starting_tasks: [
            "Schedule patient appointment",
            "Verify insurance coverage",
            "Process medical records request",
            "Coordinate care plan"
        ]
    },
    {
        team_id: "financial-advisory-001",
        name: "Financial Advisory",
        description: "Provide comprehensive financial planning and investment guidance",
        status: "active",
        created: new Date().toISOString(),
        created_by: "system",
        logo: "💰",
        plan: "Deliver expert financial advisory services",
        agents: [
            {
                id: "agent-financial-planner-001",
                name: "Financial Planner Agent",
                description: "Creates comprehensive financial plans and strategies",
                role: "primary",
                capabilities: ["financial_planning", "retirement_planning", "investment_strategy"]
            },
            {
                id: "agent-investment-advisor-001",
                name: "Investment Advisor Agent",
                description: "Provides investment recommendations and portfolio management",
                role: "specialist",
                capabilities: ["portfolio_management", "risk_assessment", "market_analysis"]
            },
            {
                id: "agent-tax-specialist-001",
                name: "Tax Specialist Agent",
                description: "Handles tax planning and compliance matters",
                role: "specialist",
                capabilities: ["tax_planning", "compliance", "deduction_optimization"]
            },
            {
                id: "agent-financial-reasoning-001",
                name: "Financial Reasoning Agent",
                description: "Analyzes complex financial scenarios and provides strategic recommendations",
                role: "coordinator",
                capabilities: ["financial_analysis", "strategic_planning", "decision_support"]
            }
        ],
        starting_tasks: [
            "Create retirement savings plan",
            "Analyze investment portfolio",
            "Optimize tax strategy",
            "Develop financial goals roadmap"
        ]
    }
];

export class TeamService {
    /**
     * Get all default teams (currently hardcoded, will be API call)
     */
    static async getDefaultTeams(): Promise<TeamConfig[]> {
        // TODO: Replace with actual API call
        // return await apiClient.get('/api/teams/default');
        
        // Simulate API delay
        await new Promise(resolve => setTimeout(resolve, 500));
        
        return HARDCODED_TEAMS;
    }

    /**
     * Upload a custom team configuration
     */
    static async uploadCustomTeam(teamFile: File): Promise<{ success: boolean; team?: TeamConfig; error?: string }> {
        try {
            const formData = new FormData();
            formData.append('file', teamFile);

            const response = await apiClient.upload('/api/upload_team_config', formData);

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
            const response = await apiClient.get('/api/team_configs');
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
            await apiClient.delete(`/api/team_configs/${teamId}`);
            return true;
        } catch (error) {
            console.error('Failed to delete team:', error);
            return false;
        }
    }
}

export default TeamService;
