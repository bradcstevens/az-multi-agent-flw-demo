import React, { useState, useCallback } from 'react';
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
  Badge,
  Input,
  Radio,
  RadioGroup,
  Tab,
  TabList
} from '@fluentui/react-components';
import {
  ChevronUp16Regular,
  ChevronDown16Regular,
  CloudAdd20Regular,
  Delete20Regular,
  Search20Regular,
  Desktop20Regular,
  BookmarkMultiple20Regular,
  Person20Regular,
  Building20Regular,
  Document20Regular,
  Database20Regular,
  Play20Regular,
  Shield20Regular,
  Globe20Regular,
  Clipboard20Regular,
  WindowConsole20Regular,
  Code20Regular,
  Wrench20Regular,
} from '@fluentui/react-icons';
import { TeamConfig } from '../../models/Team';
import { TeamService } from '../../services/TeamService';

// Icon mapping function to convert string icons to FluentUI icons
const getIconFromString = (iconString: string): React.ReactNode => {
  const iconMap: Record<string, React.ReactNode> = {
    'Terminal': <WindowConsole20Regular />,
    'MonitorCog': <Desktop20Regular />,
    'BookMarked': <BookmarkMultiple20Regular />,
    'Search': <Search20Regular />,
    'Robot': <Person20Regular />,
    'Code': <Code20Regular />,
    'Play': <Play20Regular />,
    'Shield': <Shield20Regular />,
    'Globe': <Globe20Regular />,
    'Person': <Person20Regular />,
    'Database': <Database20Regular />,
    'Document': <Document20Regular />,
    'Wrench': <Wrench20Regular />,
    'TestTube': <Clipboard20Regular />,
    'Building': <Building20Regular />,
    'Desktop': <Desktop20Regular />,
    'default': <Person20Regular />,
  };
  
  return iconMap[iconString] || iconMap['default'] || <Person20Regular />;
};

interface TeamSelectorProps {
  onTeamSelect?: (team: TeamConfig | null) => void;
  onTeamUpload?: () => Promise<void>;
  selectedTeam?: TeamConfig | null;
}

const TeamSelector: React.FC<TeamSelectorProps> = ({
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
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [teamToDelete, setTeamToDelete] = useState<TeamConfig | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<string>('teams');

  const loadTeams = async () => {
    setLoading(true);
    setError(null);
    try {
      const teamsData = await TeamService.getUserTeams();
      setTeams(teamsData);
    } catch (err: any) {
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
      setSearchQuery('');
      setActiveTab('teams');
    } else {
      setTempSelectedTeam(null);
      setError(null);
      setUploadMessage(null);
      setSearchQuery('');
    }
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

  const handleDeleteTeam = (team: TeamConfig, event: React.MouseEvent) => {
    event.stopPropagation();
    setTeamToDelete(team);
    setDeleteConfirmOpen(true);
  };

  const confirmDeleteTeam = async () => {
    if (!teamToDelete || deleteLoading) return;
    
    if (teamToDelete.protected) {
      setError('This team is protected and cannot be deleted.');
      setDeleteConfirmOpen(false);
      setTeamToDelete(null);
      return;
    }
    
    setDeleteLoading(true);
    
    try {
      const success = await TeamService.deleteTeam(teamToDelete.id);
      
      if (success) {
        setDeleteConfirmOpen(false);
        setTeamToDelete(null);
        setDeleteLoading(false);
        
        if (tempSelectedTeam?.team_id === teamToDelete.team_id) {
          setTempSelectedTeam(null);
          if (selectedTeam?.team_id === teamToDelete.team_id) {
            onTeamSelect?.(null);
          }
        }
        
        setTeams(currentTeams => currentTeams.filter(team => team.id !== teamToDelete.id));
        await loadTeams();
      } else {
        setError('Failed to delete team configuration.');
        setDeleteConfirmOpen(false);
        setTeamToDelete(null);
      }
    } catch (err: any) {
      let errorMessage = 'Failed to delete team configuration. Please try again.';
      
      if (err.response?.status === 404) {
        errorMessage = 'Team not found. It may have already been deleted.';
      } else if (err.response?.status === 403) {
        errorMessage = 'You do not have permission to delete this team.';
      } else if (err.response?.status === 409) {
        errorMessage = 'Cannot delete team because it is currently in use.';
      } else if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      } else if (err.message) {
        errorMessage = `Delete failed: ${err.message}`;
      }
      
      setError(errorMessage);
      setDeleteConfirmOpen(false);
      setTeamToDelete(null);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploadLoading(true);
    setError(null);
    setUploadMessage('Reading and validating team configuration...');

    try {
      if (!file.name.toLowerCase().endsWith('.json')) {
        throw new Error('Please upload a valid JSON file');
      }

      // Read and parse the JSON file to check agent count
      const fileText = await file.text();
      let teamData;
      try {
        teamData = JSON.parse(fileText);
      } catch (parseError) {
        throw new Error('Invalid JSON file format');
      }

      // Check if the team has more than 6 agents
      if (teamData.agents && Array.isArray(teamData.agents) && teamData.agents.length > 6) {
        throw new Error(`Team configuration cannot have more than 6 agents. Your team has ${teamData.agents.length} agents.`);
      }

      setUploadMessage('Uploading team configuration...');
      const result = await TeamService.uploadCustomTeam(file);
      
      if (result.success) {
        setUploadMessage('Team uploaded successfully!');
        
        if (result.team) {
          setTeams(currentTeams => [...currentTeams, result.team!]);
        }
        
        setUploadMessage(null);
        if (onTeamUpload) {
          await onTeamUpload();
        }
      } else if (result.raiError) {
        setError('❌ Content Safety Check Failed\n\nYour team configuration contains content that doesn\'t meet our safety guidelines.');
        setUploadMessage(null);
      } else if (result.modelError) {
        setError('🤖 Model Deployment Validation Failed\n\nYour team configuration references models that are not properly deployed.');
        setUploadMessage(null);
      } else if (result.searchError) {
        setError('🔍 RAG Search Configuration Error\n\nYour team configuration includes RAG/search agents but has search index issues.');
        setUploadMessage(null);
      } else {
        setError(result.error || 'Failed to upload team configuration');
        setUploadMessage(null);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to upload team configuration');
      setUploadMessage(null);
    } finally {
      setUploadLoading(false);
      event.target.value = '';
    }
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.style.borderColor = '#6264a7';
    event.currentTarget.style.backgroundColor = '#f0f0ff';
  };

  const handleDragLeave = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.style.borderColor = '#d1d5db';
    event.currentTarget.style.backgroundColor = '#f9fafb';
  };

  const handleDrop = async (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    
    // Reset visual state
    event.currentTarget.style.borderColor = '#d1d5db';
    event.currentTarget.style.backgroundColor = '#f9fafb';

    const files = event.dataTransfer.files;
    if (files.length === 0) return;

    const file = files[0];
    if (!file.name.toLowerCase().endsWith('.json')) {
      setError('Please upload a valid JSON file');
      return;
    }

    setUploadLoading(true);
    setError(null);
    setUploadMessage('Reading and validating team configuration...');

    try {
      // Read and parse the JSON file to check agent count
      const fileText = await file.text();
      let teamData;
      try {
        teamData = JSON.parse(fileText);
      } catch (parseError) {
        throw new Error('Invalid JSON file format');
      }

      // Check if the team has more than 6 agents
      if (teamData.agents && Array.isArray(teamData.agents) && teamData.agents.length > 6) {
        throw new Error(`Team configuration cannot have more than 6 agents. Your team has ${teamData.agents.length} agents.`);
      }

      setUploadMessage('Uploading team configuration...');
      const result = await TeamService.uploadCustomTeam(file);
      
      if (result.success) {
        setUploadMessage('Team uploaded successfully!');
        
        if (result.team) {
          setTeams(currentTeams => [...currentTeams, result.team!]);
        }
        
        setUploadMessage(null);
        if (onTeamUpload) {
          await onTeamUpload();
        }
      } else if (result.raiError) {
        setError('❌ Content Safety Check Failed\n\nYour team configuration contains content that doesn\'t meet our safety guidelines.');
        setUploadMessage(null);
      } else if (result.modelError) {
        setError('🤖 Model Deployment Validation Failed\n\nYour team configuration references models that are not properly deployed.');
        setUploadMessage(null);
      } else if (result.searchError) {
        setError('🔍 RAG Search Configuration Error\n\nYour team configuration includes RAG/search agents but has search index issues.');
        setUploadMessage(null);
      } else {
        setError(result.error || 'Failed to upload team configuration');
        setUploadMessage(null);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to upload team configuration');
      setUploadMessage(null);
    } finally {
      setUploadLoading(false);
    }
  };

  const renderTeamCard = (team: TeamConfig) => {
    const isSelected = tempSelectedTeam?.team_id === team.team_id;
    
    return (
      <div 
        key={team.team_id} 
        style={{ 
          display: 'flex',
          alignItems: 'center',
          padding: '16px',
          border: '1px solid #ddd',
          borderRadius: '8px',
          marginBottom: '12px',
          justifyContent: 'space-between',
          backgroundColor: isSelected ? '#f5f5ff' : '#fff',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
          boxSizing: 'border-box',
          width: '100%'
        }}
        onClick={() => setTempSelectedTeam(team)}
      >
        {/* Radio Button */}
        <Radio
          checked={isSelected}
          value={team.team_id}
        />

        {/* Team Info */}
        <div style={{ flex: 2, marginLeft: '16px' }}>
          <div style={{ fontWeight: 600, color: '#323130' }}>
            {team.name}
          </div>
          <div style={{ fontSize: '13px', color: '#666', marginTop: '4px' }}>
            {team.description}
          </div>
        </div>

        {/* Tags */}
        <div style={{ 
          flex: 1, 
          display: 'flex', 
          gap: '6px', 
          flexWrap: 'wrap', 
          justifyContent: 'center',
          minWidth: '200px'
        }}>
          {team.agents.slice(0, 3).map((agent) => (
            <Badge
              key={agent.input_key}
              appearance="tint"
              size="small"
              style={{
                backgroundColor: '#e6f3ff',
                color: '#0066cc',
                border: '1px solid #b3d9ff'
              }}
            >
              {agent.type}
            </Badge>
          ))}
          {team.agents.length > 3 && (
            <Badge
              appearance="tint"
              size="small"
              style={{
                backgroundColor: '#e6f3ff',
                color: '#0066cc',
                border: '1px solid #b3d9ff'
              }}
            >
              +{team.agents.length - 3}
            </Badge>
          )}
        </div>

        {/* Delete Button */}
        <Button
          icon={<Delete20Regular />}
          appearance="subtle"
          size="small"
          onClick={(e) => handleDeleteTeam(team, e)}
          style={{ 
            color: '#d13438',
            marginLeft: '12px',
            minWidth: '32px'
          }}
        />
      </div>
    );
  };

  return (
    <>
      <Dialog open={isOpen} onOpenChange={(event, data) => handleOpenChange(data.open)}>
        <DialogTrigger disableButtonEnhancement>
          <Button
            appearance="subtle"
            size="medium"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              width: '100%',
              height: 'auto',
              minHeight: '44px',
              padding: '12px 16px',
              borderRadius: '6px',
              border: 'none',
              background: 'transparent',
              color: '#323130',
              textAlign: 'left',
              fontSize: '14px'
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', flex: 1 }}>
              <Caption1 style={{ color: '#605e5c', fontSize: '11px', marginBottom: '2px' }}>
                Current Team
              </Caption1>
              <Body1 style={{ color: '#323130', fontWeight: 500, fontSize: '14px' }}>
                {selectedTeam ? selectedTeam.name : 'No team selected'}
              </Body1>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
              <ChevronUp16Regular style={{ color: '#605e5c' }} />
              <ChevronDown16Regular style={{ color: '#605e5c' }} />
            </div>
          </Button>
        </DialogTrigger>
        <DialogSurface style={{ 
          maxWidth: '800px', 
          width: '90vw', 
          minWidth: '600px',
          borderRadius: '12px',
          padding: '0',
          backgroundColor: '#ffffff',
          color: '#323130',
          border: '1px solid #e1e1e1',
          boxSizing: 'border-box'
        }}>
          <DialogTitle style={{ 
            padding: '24px 24px 16px 24px',
            fontSize: '20px',
            fontWeight: 600,
            margin: '0',
            color: '#323130',
            width: '100%',
            boxSizing: 'border-box'
          }}>
            Select a Team
          </DialogTitle>
          <DialogContent style={{ padding: '0', width: '100%', margin: '0' }}>
            <DialogBody style={{ 
              padding: '24px', 
              backgroundColor: '#ffffff', 
              width: '100%', 
              margin: '0',
              display: 'block',
              overflow: 'visible',
              gap: 'unset',
              maxHeight: 'unset',
              gridTemplateRows: 'unset',
              gridTemplateColumns: 'unset'
            }}>
              {/* Tab Navigation - Integrated with content */}
              <div style={{ 
                marginBottom: '20px',
                width: '100%'
              }}>
                <TabList
                  selectedValue={activeTab}
                  onTabSelect={(event, data) => setActiveTab(data.value as string)}
                  style={{ 
                    width: '100%',
                    backgroundColor: '#ffffff'
                  }}
                >
                  <Tab 
                    value="teams"
                    style={{ 
                      color: activeTab === 'teams' ? '#6264a7' : '#323130',
                      fontWeight: activeTab === 'teams' ? 600 : 400,
                      padding: '12px 16px',
                      marginRight: '24px'
                    }}
                  >
                    Teams
                  </Tab>
                  <Tab 
                    value="upload"
                    style={{ 
                      color: activeTab === 'upload' ? '#6264a7' : '#323130',
                      fontWeight: activeTab === 'upload' ? 600 : 400,
                      padding: '12px 16px'
                    }}
                  >
                    Upload Team
                  </Tab>
                </TabList>
              </div>

              {/* Tab Content - Directly below tabs without separation */}
              {activeTab === 'teams' && (
                <div style={{ 
                  width: '100%'
                }}>
                  {error && (
                    <div style={{ 
                      color: '#d13438', 
                      marginBottom: '16px',
                      padding: '12px',
                      backgroundColor: '#fdf2f2',
                      border: '1px solid #f5c6cb',
                      borderRadius: '4px'
                    }}>
                      <Text style={{ whiteSpace: 'pre-line', color: '#d13438' }}>{error}</Text>
                    </div>
                  )}

                  {/* Search Input */}
                  <div style={{ marginBottom: '16px', width: '100%' }}>
                    <Input
                      placeholder="Search teams..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      contentBefore={<Search20Regular />}
                      style={{ 
                        width: '100%',
                        backgroundColor: '#ffffff',
                        border: '1px solid #e1e1e1',
                        color: '#323130'
                      }}
                    />
                  </div>

                  {/* Teams List */}
                  {loading ? (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: '32px', width: '100%' }}>
                      <Spinner label="Loading teams..." style={{ color: '#ffffff' }} />
                    </div>
                  ) : filteredTeams.length > 0 ? (
                    <div style={{ width: '100%' }}>
                      <RadioGroup 
                        value={tempSelectedTeam?.team_id || ''}
                        style={{ width: '100%' }}
                      >
                        <div style={{ 
                          maxHeight: '400px', 
                          overflowY: 'auto',
                          paddingRight: '4px',
                          marginRight: '-4px',
                          width: '100%',
                          boxSizing: 'border-box'
                        }}>
                          {filteredTeams.map((team) => renderTeamCard(team))}
                        </div>
                      </RadioGroup>
                    </div>
                  ) : searchQuery ? (
                    <div style={{ 
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      padding: '32px 16px',
                      textAlign: 'center'
                    }}>
                      <Text size={400} style={{ color: '#cccccc', marginBottom: '8px' }}>
                        No teams found matching "{searchQuery}"
                      </Text>
                    </div>
                  ) : (
                    <div style={{ 
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      padding: '32px 16px',
                      textAlign: 'center'
                    }}>
                      <Text size={400} style={{ color: '#cccccc', marginBottom: '8px' }}>
                        No teams available
                      </Text>
                      <Text size={300} style={{ color: '#aaaaaa' }}>
                        Upload a JSON team configuration to get started
                      </Text>
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'upload' && (
                <div style={{ 
                  width: '100%'
                }}>
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

                  {error && (
                    <div style={{ 
                      color: '#d13438', 
                      marginBottom: '16px',
                      padding: '12px',
                      backgroundColor: '#fdf2f2',
                      border: '1px solid #f5c6cb',
                      borderRadius: '4px'
                    }}>
                      <Text style={{ whiteSpace: 'pre-line', color: '#d13438' }}>{error}</Text>
                    </div>
                  )}

                  {/* Drag and Drop Zone */}
                  <div 
                    style={{
                      border: '2px dashed #d1d5db',
                      borderRadius: '8px',
                      padding: '40px 20px',
                      textAlign: 'center',
                      backgroundColor: '#f9fafb',
                      marginBottom: '20px',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease'
                    }}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => document.getElementById('team-upload-input')?.click()}
                  >
                    <div style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '8px'
                    }}>
                      <div style={{
                        width: '24px',
                        height: '24px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#9ca3af'
                      }}>
                        ↑
                      </div>
                      <Text style={{ 
                        fontSize: '16px', 
                        fontWeight: '500',
                        color: '#374151',
                        marginBottom: '4px'
                      }}>
                        Drag & drop your team JSON here
                      </Text>
                      <Text style={{ 
                        fontSize: '14px',
                        color: '#6b7280'
                      }}>
                        or <span style={{ color: '#6264a7', textDecoration: 'underline', cursor: 'pointer' }}>click to browse</span>
                      </Text>
                    </div>
                    
                    <input
                      type="file"
                      accept=".json"
                      onChange={handleFileUpload}
                      style={{ display: 'none' }}
                      id="team-upload-input"
                      disabled={uploadLoading}
                    />
                  </div>

                  {/* Upload Requirements */}
                  <div style={{
                    padding: '16px',
                    borderRadius: '8px'
                  }}>
                    <Text style={{ 
                      fontSize: '14px', 
                      fontWeight: '600', 
                      color: '#323130',
                      display: 'block',
                      marginBottom: '12px'
                    }}>
                      Upload Requirements
                    </Text>
                    <ul style={{
                      margin: '0',
                      paddingLeft: '20px',
                      listStyle: 'disc'
                    }}>
                      <li style={{ marginBottom: '8px' }}>
                        <Text style={{ fontSize: '13px', color: '#605e5c' }}>
                          JSON must include <strong style={{ color: '#323130' }}>name</strong>, <strong style={{ color: '#323130' }}>description</strong>, and <strong style={{ color: '#323130' }}>status</strong>
                        </Text>
                      </li>
                      <li style={{ marginBottom: '8px' }}>
                        <Text style={{ fontSize: '13px', color: '#605e5c' }}>
                          At least one agent with <strong style={{ color: '#323130' }}>name</strong>, <strong style={{ color: '#323130' }}>type</strong>, <strong style={{ color: '#323130' }}>input_key</strong>, and <strong style={{ color: '#323130' }}>deployment_name</strong>
                        </Text>
                      </li>
                      <li style={{ marginBottom: '8px' }}>
                        <Text style={{ fontSize: '13px', color: '#605e5c' }}>
                          Maximum of <strong style={{ color: '#323130' }}>6 agents</strong> per team configuration
                        </Text>
                      </li>
                      <li style={{ marginBottom: '8px' }}>
                        <Text style={{ fontSize: '13px', color: '#605e5c' }}>
                          RAG agents additionally require <strong style={{ color: '#323130' }}>index_name</strong>
                        </Text>
                      </li>
                      <li style={{ marginBottom: '8px' }}>
                        <Text style={{ fontSize: '13px', color: '#605e5c' }}>
                          Starting tasks are optional, but if provided must include <strong style={{ color: '#323130' }}>name</strong> and <strong style={{ color: '#323130' }}>prompt</strong>
                        </Text>
                      </li>
                      {/* <li>
                        <Text style={{ fontSize: '13px', color: '#605e5c' }}>
                          Text fields cannot be empty
                        </Text>
                      </li> */}
                    </ul>
                  </div>
                </div>
              )}
            </DialogBody>
          </DialogContent>
          <DialogActions style={{ 
            padding: '16px 24px',
            backgroundColor: '#ffffff'
          }}>
            <Button 
              appearance="secondary" 
              onClick={handleCancel}
              style={{ 
                padding: '12px 24px',
                marginRight: '12px'
              }}
            >
              Cancel
            </Button>
            <Button 
              appearance="primary" 
              onClick={handleContinue}
              disabled={!tempSelectedTeam}
              style={{ 
                padding: '12px 24px'
              }}
            >
              Continue
            </Button>
          </DialogActions>
        </DialogSurface>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteConfirmOpen} onOpenChange={(event, data) => setDeleteConfirmOpen(data.open)}>
        <DialogSurface>
          <DialogContent>
            <DialogBody>
              <DialogTitle>⚠️ Delete Team Configuration</DialogTitle>
              <div style={{ marginTop: '16px', marginBottom: '20px' }}>
                <Text style={{ display: 'block', marginBottom: '16px' }}>
                  Are you sure you want to delete <strong>"{teamToDelete?.name}"</strong>?
                </Text>
                <div style={{ 
                  padding: '16px', 
                  backgroundColor: '#fff4e6', 
                  border: '1px solid #ffb84d', 
                  borderRadius: '6px'
                }}>
                  <Text style={{ color: '#d83b01' }}>
                    This action cannot be undone and will remove the team for all users.
                  </Text>
                </div>
              </div>
            </DialogBody>
            <DialogActions>
              <Button 
                appearance="secondary" 
                disabled={deleteLoading}
                onClick={() => {
                  setDeleteConfirmOpen(false);
                  setTeamToDelete(null);
                }}
              >
                Cancel
              </Button>
              <Button 
                appearance="primary" 
                disabled={deleteLoading}
                style={{ backgroundColor: '#d13438', color: 'white' }}
                onClick={confirmDeleteTeam}
              >
                {deleteLoading ? 'Deleting...' : 'Delete Team'}
              </Button>
            </DialogActions>
          </DialogContent>
        </DialogSurface>
      </Dialog>
    </>
  );
};

export default TeamSelector;
