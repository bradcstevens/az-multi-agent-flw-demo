import React, { useState } from 'react';
import {
  Button,
  Dialog,
  DialogTrigger,
  DialogSurface,
  DialogTitle,
  DialogContent,
  DialogBody,
  DialogActions,
  Text,
  Spinner,
  Card,
  Body1,
  Body2,
  Caption1,
  Tooltip,
  Badge,
  Input,
} from '@fluentui/react-components';
import {
  Settings20Regular,
  CloudAdd20Regular,
  Delete20Regular,
  Checkmark20Filled,
  Search20Regular,
  Desktop20Regular,
  BookmarkMultiple20Regular,
  Wrench20Regular,
  Person20Regular,
  Building20Regular,
  Document20Regular,
  Database20Regular,
  Code20Regular,
  Play20Regular,
  Shield20Regular,
  Globe20Regular,
  Clipboard20Regular,
  WindowConsole20Regular,
} from '@fluentui/react-icons';
import { TeamConfig } from '../../models/Team';
import { TeamService } from '../../services/TeamService';

// Icon mapping function to convert string icons to FluentUI icons
const getIconFromString = (iconString: string): React.ReactNode => {
  const iconMap: Record<string, React.ReactNode> = {
    // Agent icons
    'Terminal': <WindowConsole20Regular />,
    'MonitorCog': <Desktop20Regular />,
    'BookMarked': <BookmarkMultiple20Regular />,
    'Search': <Search20Regular />,
    'Robot': <Person20Regular />, // Fallback since Robot20Regular doesn't exist
    'Code': <Code20Regular />,
    'Play': <Play20Regular />,
    'Shield': <Shield20Regular />,
    'Globe': <Globe20Regular />,
    'Person': <Person20Regular />,
    'Database': <Database20Regular />,
    'Document': <Document20Regular />,
    
    // Team logos
    'Wrench': <Wrench20Regular />,
    'TestTube': <Clipboard20Regular />, // Fallback since TestTube20Regular doesn't exist
    'Building': <Building20Regular />,
    'Desktop': <Desktop20Regular />,
    
    // Common fallbacks
    'default': <Person20Regular />,
  };
  
  return iconMap[iconString] || iconMap['default'] || <Person20Regular />;
};

interface SettingsButtonProps {
  onTeamSelect?: (team: TeamConfig) => void;
  onTeamUpload?: () => Promise<void>;
  selectedTeam?: TeamConfig | null;
}

const SettingsButton: React.FC<SettingsButtonProps> = ({
  onTeamSelect,
  onTeamUpload,
  selectedTeam,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [teams, setTeams] = useState<TeamConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [tempSelectedTeam, setTempSelectedTeam] = useState<TeamConfig | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');

  const loadTeams = async () => {
    setLoading(true);
    setError(null);
    try {
      console.log('SettingsButton: Loading teams...');
      // Get all teams from the API (no separation between default and user teams)
      const teamsData = await TeamService.getUserTeams();
      console.log('SettingsButton: Teams loaded:', teamsData);
      console.log('SettingsButton: Number of teams:', teamsData.length);
      setTeams(teamsData);
    } catch (err: any) {
      console.error('SettingsButton: Error loading teams:', err);
      setError(err.message || 'Failed to load teams');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenChange = async (open: boolean) => {
    setIsOpen(open);
    if (open) {
      await loadTeams();
      setTempSelectedTeam(selectedTeam || null);
      setError(null);
      setUploadMessage(null);
      setSearchQuery(''); // Clear search when opening
    } else {
      setTempSelectedTeam(null);
      setError(null);
      setUploadMessage(null);
      setSearchQuery(''); // Clear search when closing
    }
  };

  const handleTeamCardClick = (team: TeamConfig) => {
    setTempSelectedTeam(team);
  };

  const handleContinue = () => {
    if (tempSelectedTeam) {
      onTeamSelect?.(tempSelectedTeam);
    }
    setIsOpen(false);
  };

  const handleCancel = () => {
    setTempSelectedTeam(null);
    setIsOpen(false);
  };

  // Filter teams based on search query
  const filteredTeams = teams.filter(team => 
    team.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    team.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Validation function for team configuration JSON
  const validateTeamConfig = (data: any): { isValid: boolean; errors: string[] } => {
    const errors: string[] = [];

    // Check if data is empty or null
    if (!data || typeof data !== 'object') {
      errors.push('JSON file cannot be empty and must contain a valid object');
      return { isValid: false, errors };
    }

    // Required root level fields
    if (!data.name || typeof data.name !== 'string' || data.name.trim() === '') {
      errors.push('Team name is required and cannot be empty');
    }

    if (!data.description || typeof data.description !== 'string' || data.description.trim() === '') {
      errors.push('Team description is required and cannot be empty');
    }

    // Required ID fields
    if (!data.id || typeof data.id !== 'string' || data.id.trim() === '') {
      errors.push('Team id is required and cannot be empty');
    }

    if (!data.team_id || typeof data.team_id !== 'string' || data.team_id.trim() === '') {
      errors.push('Team team_id is required and cannot be empty');
    }

    // Additional required fields with defaults
    if (!data.status || typeof data.status !== 'string' || data.status.trim() === '') {
      errors.push('Team status is required and cannot be empty');
    }

    if (!data.created || typeof data.created !== 'string' || data.created.trim() === '') {
      errors.push('Team created date is required and cannot be empty');
    }

    if (!data.created_by || typeof data.created_by !== 'string' || data.created_by.trim() === '') {
      errors.push('Team created_by is required and cannot be empty');
    }

    // Agents validation
    if (!data.agents || !Array.isArray(data.agents)) {
      errors.push('Agents array is required');
    } else if (data.agents.length === 0) {
      errors.push('Team must have at least one agent');
    } else {
      // Validate each agent
      data.agents.forEach((agent: any, index: number) => {
        if (!agent || typeof agent !== 'object') {
          errors.push(`Agent ${index + 1}: Invalid agent object`);
          return;
        }

        if (!agent.name || typeof agent.name !== 'string' || agent.name.trim() === '') {
          errors.push(`Agent ${index + 1}: Agent name is required and cannot be empty`);
        }

        if (!agent.type || typeof agent.type !== 'string' || agent.type.trim() === '') {
          errors.push(`Agent ${index + 1}: Agent type is required and cannot be empty`);
        }

        if (!agent.input_key || typeof agent.input_key !== 'string' || agent.input_key.trim() === '') {
          errors.push(`Agent ${index + 1}: Agent input_key is required and cannot be empty`);
        }

        // Optional fields validation (can be empty but must be strings if present)
        if (agent.description !== undefined && typeof agent.description !== 'string') {
          errors.push(`Agent ${index + 1}: Agent description must be a string`);
        }

        if (agent.system_message !== undefined && typeof agent.system_message !== 'string') {
          errors.push(`Agent ${index + 1}: Agent system_message must be a string`);
        }

        if (agent.icon !== undefined && typeof agent.icon !== 'string') {
          errors.push(`Agent ${index + 1}: Agent icon must be a string`);
        }

        if (agent.index_name !== undefined && typeof agent.index_name !== 'string') {
          errors.push(`Agent ${index + 1}: Agent index_name must be a string`);
        }
      });
    }

    // Starting tasks validation (optional but must be valid if present)
    if (data.starting_tasks !== undefined) {
      if (!Array.isArray(data.starting_tasks)) {
        errors.push('Starting tasks must be an array if provided');
      } else {
        data.starting_tasks.forEach((task: any, index: number) => {
          if (!task || typeof task !== 'object') {
            errors.push(`Starting task ${index + 1}: Invalid task object`);
            return;
          }

          if (!task.name || typeof task.name !== 'string' || task.name.trim() === '') {
            errors.push(`Starting task ${index + 1}: Task name is required and cannot be empty`);
          }

          if (!task.prompt || typeof task.prompt !== 'string' || task.prompt.trim() === '') {
            errors.push(`Starting task ${index + 1}: Task prompt is required and cannot be empty`);
          }

          if (!task.id || typeof task.id !== 'string' || task.id.trim() === '') {
            errors.push(`Starting task ${index + 1}: Task id is required and cannot be empty`);
          }

          if (!task.created || typeof task.created !== 'string' || task.created.trim() === '') {
            errors.push(`Starting task ${index + 1}: Task created date is required and cannot be empty`);
          }

          if (!task.creator || typeof task.creator !== 'string' || task.creator.trim() === '') {
            errors.push(`Starting task ${index + 1}: Task creator is required and cannot be empty`);
          }

          if (task.logo !== undefined && typeof task.logo !== 'string') {
            errors.push(`Starting task ${index + 1}: Task logo must be a string if provided`);
          }
        });
      }
    }

    // Optional root level fields validation
    const stringFields = ['team_id', 'status', 'logo', 'plan'];
    stringFields.forEach(field => {
      if (data[field] !== undefined && typeof data[field] !== 'string') {
        errors.push(`${field} must be a string if provided`);
      }
    });

    if (data.protected !== undefined && typeof data.protected !== 'boolean') {
      errors.push('Protected field must be a boolean if provided');
    }

    return { isValid: errors.length === 0, errors };
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    console.log('SettingsButton: Starting file upload for:', file.name);
    setUploadLoading(true);
    setError(null);
    setUploadMessage('Reading and validating team configuration...');

    try {
      // First, validate the file type
      if (!file.name.toLowerCase().endsWith('.json')) {
        throw new Error('Please upload a valid JSON file');
      }

      // Read and parse the JSON file
      const fileContent = await file.text();
      let teamData;
      
      try {
        teamData = JSON.parse(fileContent);
      } catch (parseError) {
        throw new Error('Invalid JSON format. Please check your file syntax');
      }

      // Validate the team configuration
      setUploadMessage('Validating team configuration structure...');
      const validation = validateTeamConfig(teamData);
      
      if (!validation.isValid) {
        const errorMessage = `Team configuration validation failed:\n\n${validation.errors.map(error => `• ${error}`).join('\n')}`;
        throw new Error(errorMessage);
      }

      setUploadMessage('Uploading team configuration...');
      const result = await TeamService.uploadCustomTeam(file);
      console.log('SettingsButton: Upload result:', result);
      
      if (result.success) {
        console.log('SettingsButton: Upload successful, reloading teams...');
        setUploadMessage('Team uploaded successfully! Refreshing teams...');
        // Reload teams to include the new custom team
        await loadTeams();
        console.log('SettingsButton: Teams reloaded after upload');
        setUploadMessage(null);
        // Notify parent component about the upload
        if (onTeamUpload) {
          console.log('SettingsButton: Notifying parent about upload...');
          await onTeamUpload();
        }
      } else if (result.raiError) {
        console.error('SettingsButton: Upload failed due to RAI validation:', result.raiError);
        setError('Upload failed: Team configuration contains inappropriate content.');
        setUploadMessage(null);
      } else {
        console.error('SettingsButton: Upload failed:', result.error);
        setError(result.error || 'Failed to upload team configuration');
        setUploadMessage(null);
      }
    } catch (err: any) {
      console.error('SettingsButton: Upload exception:', err);
      setError(err.message || 'Failed to upload team configuration');
      setUploadMessage(null);
    } finally {
      setUploadLoading(false);
      // Reset the input
      event.target.value = '';
    }
  };

  const handleDeleteTeam = async (teamId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    try {
      const success = await TeamService.deleteTeam(teamId);
      if (success) {
        await loadTeams();
      } else {
        setError('Failed to delete team');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to delete team');
    }
  };

  const renderTeamCard = (team: TeamConfig, isCustom = false) => {
    const isSelected = tempSelectedTeam?.team_id === team.team_id;
    
    return (
      <Card
        style={{
          cursor: 'pointer',
          border: isSelected ? '2px solid #6264a7' : '1px solid #e1e1e1',
          borderRadius: '8px',
          position: 'relative',
          transition: 'all 0.2s ease',
          backgroundColor: isSelected ? '#f0f0ff' : 'white',
          padding: '12px',
          width: '100%',
          boxSizing: 'border-box',
          display: 'block',
        }}
        onClick={() => handleTeamCardClick(team)}
      >
        {/* Team Icon and Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <div style={{
            backgroundColor: '#f8f9fa',
            borderRadius: '4px',
            padding: '4px',
            width: '35px',
            height: '35px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}>
            <div style={{ fontSize: '20px', color: '#333' }}>
              {getIconFromString(team.logo)}
            </div>
          </div>
          
          <div style={{ flex: 1, minWidth: 0 }}>
            <Body1 style={{ 
              fontWeight: '600', 
              fontSize: '16px',
              margin: 0,
              color: '#333'
            }}>
              {team.name}
            </Body1>
          </div>

          {/* Selection Checkmark */}
          {isSelected && (
            <div style={{
              backgroundColor: '#6264a7',
              borderRadius: '50%',
              width: '24px',
              height: '24px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}>
              <Checkmark20Filled style={{ color: 'white', fontSize: '14px' }} />
            </div>
          )}

          {/* Delete Button for Custom Teams */}
          {isCustom && !isSelected && (
            <Tooltip content="Delete custom team" relationship="label">
              <Button
                icon={<Delete20Regular />}
                appearance="subtle"
                size="small"
                onClick={(e) => handleDeleteTeam(team.team_id, e)}
                style={{ backgroundColor: 'rgba(255, 255, 255, 0.9)' }}
              />
            </Tooltip>
          )}
        </div>

        {/* Description */}
        <div style={{ marginBottom: '12px' }}>
          <Caption1 style={{ color: '#666', fontSize: '14px', lineHeight: '1.4' }}>
            {team.description}
          </Caption1>
        </div>

        {/* Agents Section */}
        <div>
          <Body2 style={{ 
            fontWeight: '600', 
            marginBottom: '12px', 
            fontSize: '14px',
            color: '#333',
            display: 'block'
          }}>
            Agents
          </Body2>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
            {team.agents.map((agent) => (
              <Badge
                key={agent.input_key}
                appearance="outline"
                style={{
                  backgroundColor: '#f8f9fa',
                  border: '1px solid #e1e1e1',
                  color: '#333',
                  fontSize: '12px',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <span style={{ fontSize: '14px', display: 'flex', alignItems: 'center' }}>
                  {getIconFromString(agent.icon || 'default')}
                </span>
                {agent.name}
              </Badge>
            ))}
          </div>
        </div>
      </Card>
    );
  };

  return (
    <Dialog open={isOpen} onOpenChange={(event, data) => handleOpenChange(data.open)}>
      <DialogTrigger disableButtonEnhancement>
        <Tooltip content="Team Settings" relationship="label">
          <Button
            icon={<Settings20Regular />}
            appearance="subtle"
            size="medium"
            aria-label="Team Settings"
            style={{
              display: 'flex',
              gap: '12px',
              alignItems: 'center',
              justifyContent: 'flex-start',
              padding: '0',
              margin: '0',
              height: 'auto',
              minHeight: '40px',
              width: '100%',
              borderRadius: '4px',
              border: 'none',
              background: 'transparent',
            }}
          >
            Settings
          </Button>
        </Tooltip>
      </DialogTrigger>
      <DialogSurface style={{ maxWidth: '600px', width: '90vw', minWidth: '500px' }}>
        <DialogTitle style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Select a Team</span>
          <div>
            <input
              type="file"
              accept=".json"
              onChange={handleFileUpload}
              style={{ display: 'none' }}
              id="team-upload-input"
              disabled={uploadLoading}
            />
            <Button
              icon={<CloudAdd20Regular />}
              appearance="outline"
              size="small"
              disabled={uploadLoading}
              onClick={() => document.getElementById('team-upload-input')?.click()}
            >
              {uploadLoading ? <Spinner size="extra-small" /> : 'Upload custom team'}
            </Button>
          </div>
        </DialogTitle>
        <DialogContent style={{ width: '100%', padding: '0' }}>
          <DialogBody style={{ width: '100%', padding: '16px 24px', display: 'block' }}>
            {error && (
              <div style={{ 
                color: '#d13438', 
                marginBottom: '16px',
                padding: '12px',
                backgroundColor: '#fdf2f2',
                border: '1px solid #f5c6cb',
                borderRadius: '4px'
              }}>
                <Text style={{ whiteSpace: 'pre-line' }}>{error}</Text>
              </div>
            )}

            {uploadMessage && (
              <div style={{ 
                color: '#107c10', 
                marginBottom: '16px',
                padding: '12px',
                backgroundColor: '#f3f9f3',
                border: '1px solid #c6e7c6',
                borderRadius: '4px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <Spinner size="extra-small" />
                <Text>{uploadMessage}</Text>
              </div>
            )}

            {/* Upload requirements info */}
            <div style={{ 
              marginBottom: '16px',
              padding: '12px',
              backgroundColor: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '4px'
            }}>
              <Text size={300} weight="semibold" style={{ display: 'block', marginBottom: '8px', color: 'inherit' }}>
                Upload Requirements:
              </Text>
              <Text size={200} style={{ display: 'block', lineHeight: '1.4', color: 'inherit' }}>
                • JSON file must contain: <strong>id</strong>, <strong>team_id</strong>, <strong>name</strong>, and <strong>description</strong><br/>
                • At least one agent with <strong>name</strong>, <strong>type</strong>, and <strong>input_key</strong><br/>
                • Starting tasks are optional but must have <strong>name</strong> and <strong>prompt</strong> if included<br/>
                • All text fields cannot be empty
              </Text>
            </div>

            {/* Search input */}
            <div style={{ marginBottom: '16px' }}>
              <Input
                placeholder="Search teams..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                contentBefore={<Search20Regular />}
                style={{ width: '100%' }}
              />
            </div>

            {loading ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '32px' }}>
                <Spinner label="Loading teams..." />
              </div>
            ) : filteredTeams.length > 0 ? (
              <div style={{ 
                marginBottom: '24px',
                display: 'block',
                width: '100%'
              }}>
                {filteredTeams.map((team) => (
                  <div key={team.team_id} style={{ marginBottom: '8px', width: '100%' }}>
                    {renderTeamCard(team, team.created_by !== 'system')}
                  </div>
                ))}
              </div>
            ) : searchQuery ? (
              <div style={{ 
                marginBottom: '24px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                padding: '32px 16px',
                textAlign: 'center'
              }}>
                <Text size={400} style={{ color: '#666', marginBottom: '8px' }}>
                  No teams found matching "{searchQuery}"
                </Text>
                <Text size={300} style={{ color: '#888' }}>
                  Try a different search term
                </Text>
              </div>
            ) : teams.length === 0 ? (
              <div style={{ 
                marginBottom: '24px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                padding: '32px 16px',
                textAlign: 'center'
              }}>
                <Text size={400} style={{ color: '#666', marginBottom: '8px' }}>
                  No teams available
                </Text>
                <Text size={300} style={{ color: '#888' }}>
                  Upload a JSON team configuration to get started
                </Text>
              </div>
            ) : null}
          </DialogBody>
        </DialogContent>
        <DialogActions>
          <Button appearance="secondary" onClick={handleCancel}>
            Cancel
          </Button>
          <Button 
            appearance="primary" 
            onClick={handleContinue}
            disabled={!tempSelectedTeam}
          >
            Continue
          </Button>
        </DialogActions>
      </DialogSurface>
    </Dialog>
  );
};

export default SettingsButton;
