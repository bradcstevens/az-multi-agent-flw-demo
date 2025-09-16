import React from 'react';
import { 
    Desktop20Regular, 
    Code20Regular, 
    Building20Regular,
    Organization20Regular,
    Search20Regular,
    Globe20Regular,
    Database20Regular,
    Wrench20Regular
} from '@fluentui/react-icons';
import { TeamService } from '@/services/TeamService';
import { TaskService } from '@/services';
import { iconMap } from '@/models/homeInput';

/**
 * Comprehensive utility function to get agent icon from multiple data sources
 * with consistent fallback patterns across all components
 */
export const getAgentIcon = (
    agentName: string, 
    planData?: any, 
    planApprovalRequest?: any,
    iconColor: string = 'var(--colorNeutralForeground2)'
): React.ReactNode => {
    const iconStyle = { fontSize: '16px', color: iconColor };

    // 1. First priority: Get from stored team configuration (TeamService)
    const storedTeam = TeamService.getStoredTeam();
    if (storedTeam?.agents) {
        const cleanAgentName = TaskService.cleanTextToSpaces(agentName);
        
        const agent = storedTeam.agents.find(a => 
            TaskService.cleanTextToSpaces(a.name).toLowerCase().includes(cleanAgentName.toLowerCase()) ||
            a.type.toLowerCase().includes(cleanAgentName.toLowerCase()) ||
            a.input_key.toLowerCase().includes(cleanAgentName.toLowerCase())
        );

        if (agent?.icon && iconMap[agent.icon]) {
            return React.cloneElement(iconMap[agent.icon] as React.ReactElement, {
                style: iconStyle
            });
        }
    }

    // 2. Second priority: Get from participant_descriptions in planApprovalRequest
    if (planApprovalRequest?.context?.participant_descriptions) {
        const participantDesc = planApprovalRequest.context.participant_descriptions[agentName];
        if (participantDesc?.icon && iconMap[participantDesc.icon]) {
            return React.cloneElement(iconMap[participantDesc.icon] as React.ReactElement, {
                style: iconStyle
            });
        }
    }

    // 3. Third priority: Get from planData team configuration
    if (planData?.team?.agents) {
        const cleanAgentName = TaskService.cleanTextToSpaces(agentName);

        const agent = planData.team.agents.find((a: any) =>
            TaskService.cleanTextToSpaces(a.name).toLowerCase().includes(cleanAgentName.toLowerCase()) ||
            a.type.toLowerCase().includes(cleanAgentName.toLowerCase()) ||
            a.input_key.toLowerCase().includes(cleanAgentName.toLowerCase())
        );

        if (agent?.icon && iconMap[agent.icon]) {
            return React.cloneElement(iconMap[agent.icon] as React.ReactElement, {
                style: iconStyle
            });
        }
    }

    // 4. Fallback: Pattern-based icon assignment based on agent name
    const cleanName = agentName.toLowerCase();
    
    if (cleanName.includes('coder') || cleanName.includes('coding') || cleanName.includes('executor')) {
        return <Code20Regular style={iconStyle} />;
    } else if (cleanName.includes('research') || cleanName.includes('data') || cleanName.includes('analyst')) {
        return <Database20Regular style={iconStyle} />;
    } else if (cleanName.includes('websurfer') || cleanName.includes('web') || cleanName.includes('browser')) {
        return <Globe20Regular style={iconStyle} />;
    } else if (cleanName.includes('search') || cleanName.includes('kb') || cleanName.includes('knowledge')) {
        return <Search20Regular style={iconStyle} />;
    } else if (cleanName.includes('hr') || cleanName.includes('human') || cleanName.includes('manager')) {
        return <Organization20Regular style={iconStyle} />;
    } else if (cleanName.includes('marketing') || cleanName.includes('business') || cleanName.includes('sales')) {
        return <Building20Regular style={iconStyle} />;
    } else if (cleanName.includes('custom') || cleanName.includes('tool') || cleanName.includes('utility')) {
        return <Wrench20Regular style={iconStyle} />;
    }

    // 5. Final fallback: Desktop icon for AI agents
    return <Desktop20Regular style={iconStyle} />;
};

/**
 * Get agent display name with proper formatting
 * Removes redundant "Agent" suffix and handles proper spacing
 */
export const getAgentDisplayName = (agentName: string): string => {
    if (!agentName) return 'Assistant';
    
    // Clean and format the name
    let cleanName = TaskService.cleanTextToSpaces(agentName);
    
    // Remove "Agent" suffix if it exists (case insensitive)
    cleanName = cleanName.replace(/\s*agent\s*$/gi, '').trim();
    
    // Convert to proper case
    cleanName = cleanName.replace(/\b\w/g, l => l.toUpperCase());
    
    // Handle special cases for better readability
    cleanName = cleanName
        .replace(/\bKb\b/g, 'KB')          // KB instead of Kb
        .replace(/\bApi\b/g, 'API')        // API instead of Api
        .replace(/\bHr\b/g, 'HR')          // HR instead of Hr
        .replace(/\bIt\b/g, 'IT')          // IT instead of It
        .replace(/\bAi\b/g, 'AI')          // AI instead of Ai
        .replace(/\bUi\b/g, 'UI')          // UI instead of Ui
        .replace(/\bDb\b/g, 'DB');         // DB instead of Db
    
    return cleanName || 'Assistant';
};

/**
 * Get agent display name with "Agent" suffix for display purposes
 */
export const getAgentDisplayNameWithSuffix = (agentName: string): string => {
    const baseName = getAgentDisplayName(agentName);
    return `${baseName} Agent`;
};

/**
 * Get agent icon with custom styling override
 */
export const getStyledAgentIcon = (
    agentName: string, 
    customStyle: React.CSSProperties,
    planData?: any, 
    planApprovalRequest?: any
): React.ReactNode => {
    const icon = getAgentIcon(agentName, planData, planApprovalRequest);
    
    if (React.isValidElement(icon)) {
        return React.cloneElement(icon, {
            style: { ...icon.props.style, ...customStyle }
        });
    }
    
    return icon;
};