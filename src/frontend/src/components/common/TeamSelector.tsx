// TeamSelector — header (search + errors) stays fixed; only the list scrolls.

import React, { useEffect, useMemo, useState } from "react";
import {
  Spinner, Text, Input, Body1, Body1Strong, Card, Tooltip, Button,
  Dialog, DialogSurface, DialogContent, DialogBody, DialogActions, DialogTitle, Tag
} from "@fluentui/react-components";
import {
  Delete20Regular, RadioButton20Filled, RadioButton20Regular, Search20Regular,
  WindowConsole20Regular, Desktop20Regular, BookmarkMultiple20Regular, Person20Regular,
  Building20Regular, Document20Regular, Database20Regular, Play20Regular, Shield20Regular,
  Globe20Regular, Clipboard20Regular, Code20Regular, Wrench20Regular
} from "@fluentui/react-icons";
import { TeamConfig } from "../../models/Team";
import { TeamService } from "../../services/TeamService";

const getIconFromString = (iconString: string): React.ReactNode => {
  const iconMap: Record<string, React.ReactNode> = {
    Terminal: <WindowConsole20Regular />, MonitorCog: <Desktop20Regular />,
    BookMarked: <BookmarkMultiple20Regular />, Search: <Search20Regular />,
    Robot: <Person20Regular />, Code: <Code20Regular />, Play: <Play20Regular />,
    Shield: <Shield20Regular />, Globe: <Globe20Regular />, Person: <Person20Regular />,
    Database: <Database20Regular />, Document: <Document20Regular />, Wrench: <Wrench20Regular />,
    TestTube: <Clipboard20Regular />, Building: <Building20Regular />, Desktop: <Desktop20Regular />,
    default: <Person20Regular />,
  };
  return iconMap[iconString] || iconMap.default;
};

interface Props {
  isOpen: boolean;
  refreshKey: number;
  selectedTeam: TeamConfig | null;
  onTeamSelect: (team: TeamConfig | null) => void;
}

const TeamSelector: React.FC<Props> = ({ isOpen, refreshKey, selectedTeam, onTeamSelect }) => {
  const [teams, setTeams] = useState<TeamConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Delete dialog state
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [teamToDelete, setTeamToDelete] = useState<TeamConfig | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const loadTeams = async () => {
    setLoading(true);
    setError(null);
    try {
      const teamsData = await TeamService.getUserTeams();
      setTeams(Array.isArray(teamsData) ? teamsData : []);
    } catch (err: any) {
      setTeams([]);
      setError(err?.message ?? "Failed to load teams.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) loadTeams();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, refreshKey]);

  const filtered = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return teams.filter(
      (t) => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q)
    );
  }, [teams, searchQuery]);

  const handleDeleteTeam = (team: TeamConfig, e: React.MouseEvent) => {
    e.stopPropagation();
    setTeamToDelete(team);
    setDeleteConfirmOpen(true);
  };

  const confirmDeleteTeam = async () => {
    if (!teamToDelete || deleteLoading) return;
    if (teamToDelete.protected) {
      setError("This team is protected and cannot be deleted.");
      setDeleteConfirmOpen(false);
      setTeamToDelete(null);
      return;
    }
    setDeleteLoading(true);
    try {
      const ok = await TeamService.deleteTeam(teamToDelete.id);
      if (ok) setTeams((list) => list.filter((t) => t.id !== teamToDelete.id));
      else setError("Failed to delete team configuration.");
    } catch (err: any) {
      setError(err?.message ?? "Failed to delete team configuration.");
    } finally {
      setDeleteLoading(false);
      setDeleteConfirmOpen(false);
      setTeamToDelete(null);
    }
  };

  return (
    // -------- Outer container: no scroll here, we manage it in the list wrapper
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        maxHeight: "min(65vh, 560px)", // controls overall body height inside dialog
        minHeight: 0,
        overflow: "hidden",            // prevent outer scroll; list will scroll
      }}
    >
      {/* Header (non-scrollable): search + error */}
      <div style={{ flex: "0 0 auto" }}>
        <div style={{ margin: "0 0 16px 0" }}>
          <Input
            placeholder="Search teams"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            contentBefore={<Search20Regular />}
            style={{ width: "100%", borderRadius: 8, padding: 12 }}
            appearance="filled-darker"
          />
        </div>

        {error && (
          <div
            style={{
              color: "#d13438",
              margin: "0 0 12px 0",
              padding: 12,
              backgroundColor: "#fdf2f2",
              border: "1px solid #f5c6cb",
              borderRadius: 4,
            }}
          >
            <Text style={{ whiteSpace: "pre-line" }}>{error}</Text>
          </div>
        )}
      </div>

      {/* Scrollable list area */}
      <div
        style={{
          flex: "1 1 auto",
          minHeight: 0,
          overflowY: "auto",
          paddingRight: 4, // small gutter so scrollbar doesn't overlap content
        }}
      >
        {loading ? (
          <div style={{ display: "flex", justifyContent: "center", padding: 32 }}>
            <Spinner label="Loading teams..." />
          </div>
        ) : filtered.length > 0 ? (
          <div style={{ marginBottom: 24 }}>
            {filtered.map((team) => {
              const isSelected = selectedTeam?.team_id === team.team_id;
              return (
                <Card
                  key={team.team_id}
                  onClick={() => onTeamSelect(team)}
                  style={{
                    border: isSelected
                      ? "1px solid var(--colorBrandBackground)"
                      : "1px solid var(--colorNeutralStroke1)",
                    borderRadius: 8,
                    backgroundColor: isSelected
                      ? "var(--colorBrandBackground2)"
                      : "var(--colorNeutralBackground1)",
                    padding: 20,
                    marginBottom: 8,
                    boxShadow: "none"
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
                    {isSelected ? (
                      <RadioButton20Filled style={{ color: "var(--colorBrandStroke1)" }} />
                    ) : (
                      <RadioButton20Regular />
                    )}

                    <div style={{ flex: 1, minWidth: 0 }}>
                      <Body1Strong>{team.name}</Body1Strong>
                      <br />
                      <Body1 style={{ color: "var(--colorNeutralForeground2)" }}>
                        {team.description}
                      </Body1>
                    </div>

                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, flex: 1 }}>
                      {team.agents.map((a) => (
                        <Tag
                          key={a.input_key}
                          icon={getIconFromString(a.icon || "default")}
                          appearance="filled"
                          size="small"
                        >
                          {a.name}
                        </Tag>
                      ))}
                    </div>

                    <Tooltip content="Delete team" relationship="label">
                      <Button
                        icon={<Delete20Regular />}
                        appearance="transparent"
                        onClick={(e) => handleDeleteTeam(team, e)}
                        style={{ color: "var(--colorNeutralForeground3)" }}
                      />
                    </Tooltip>
                  </div>
                </Card>
              );
            })}
          </div>
        ) : teams.length === 0 ? (
          <div style={{ textAlign: "center", padding: "32px 16px" }}>
            <Text size={400} style={{ color: "#666", marginBottom: 8 }}>
              No teams available
            </Text>
            <Text size={300} style={{ color: "#888" }}>
              Use the Upload tab to add a JSON team configuration
            </Text>
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "32px 16px" }}>
            <Text size={400} style={{ color: "#666", marginBottom: 8 }}>
              No teams match your search
            </Text>
            <Text size={300} style={{ color: "#888" }}>
              Try a different term
            </Text>
          </div>
        )}
      </div>

      {/* Delete confirmation (outside scroll; modal anyway) */}
      <Dialog open={deleteConfirmOpen} onOpenChange={(_, d) => setDeleteConfirmOpen(d.open)}>
        <DialogSurface>
          <DialogContent>
            <DialogBody>
              <DialogTitle>⚠️ Delete Team Configuration</DialogTitle>
              <div style={{ marginTop: 16, marginBottom: 20 }}>
                <Text style={{ display: "block", marginBottom: 16 }}>
                  Are you sure you want to delete <strong>"{teamToDelete?.name}"</strong>?
                </Text>
                <div style={{ padding: 16, backgroundColor: "#fff4e6", border: "1px solid #ffb84d", borderRadius: 6 }}>
                  <Text weight="semibold" style={{ color: "#d83b01", display: "block", marginBottom: 8 }}>
                    Important Notice:
                  </Text>
                  <Text style={{ lineHeight: 1.4, color: "#323130" }}>
                    This team configuration is shared across users. Deleting it removes it for everyone.
                  </Text>
                </div>
              </div>
            </DialogBody>
            <DialogActions>
              <Button appearance="secondary" disabled={deleteLoading} onClick={() => setDeleteConfirmOpen(false)}>
                Cancel
              </Button>
              <Button
                appearance="primary"
                disabled={deleteLoading}
                style={{ backgroundColor: "#d13438", color: "white" }}
                onClick={confirmDeleteTeam}
              >
                {deleteLoading ? "Deleting..." : "Delete for Everyone"}
              </Button>
            </DialogActions>
          </DialogContent>
        </DialogSurface>
      </Dialog>
    </div>
  );
};

export default TeamSelector;
