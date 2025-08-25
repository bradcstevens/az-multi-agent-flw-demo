// DEV NOTE: Dialog shell for Team Settings
// - Children = trigger (your "Current team" tile)
// - Tabs: Teams | Upload Team
// - Holds tempSelectedTeam; "Continue" commits to parent

import React, { useEffect, useState } from "react";
import {
  Button,
  Dialog,
  DialogTrigger,
  DialogSurface,
  DialogTitle,
  DialogContent,
  DialogBody,
  DialogActions,
  Body1Strong,
  TabList,
  Tab,
} from "@fluentui/react-components";
import { Settings20Regular } from "@fluentui/react-icons";
import { TeamConfig } from "../../models/Team";
import TeamSelector from "./TeamSelector";
import TeamUploadTab from "./TeamUploadTab";
import { Dismiss } from "@/coral/imports/bundleicons";

interface TeamSettingsButtonProps {
  onTeamSelect?: (team: TeamConfig | null) => void;
  selectedTeam?: TeamConfig | null;
  children?: React.ReactNode; // trigger
}

const TeamSettingsButton: React.FC<TeamSettingsButtonProps> = ({
  onTeamSelect,
  selectedTeam,
  children,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"teams" | "upload">("teams");
  const [tempSelectedTeam, setTempSelectedTeam] = useState<TeamConfig | null>(
    null
  );
  const [refreshKey, setRefreshKey] = useState(0); // bump to refresh TeamSelector

  useEffect(() => {
    if (isOpen) {
      setTempSelectedTeam(selectedTeam ?? null);
    } else {
      setActiveTab("teams");
    }
  }, [isOpen, selectedTeam]);

  return (
    <Dialog open={isOpen} onOpenChange={(_, d) => setIsOpen(d.open)}>
      <DialogTrigger disableButtonEnhancement>
        {children ?? (
          <Button
            icon={<Settings20Regular />}
            appearance="subtle"
            style={{ width: "100%" }}
          >
            Settings
          </Button>
        )}
      </DialogTrigger>

      <DialogSurface
        style={{
          maxWidth: "728px",
          width: "90vw",
          minWidth: "500px",
          margin: "24px auto",
          alignSelf: "center",
          height: "728px",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <DialogTitle style={{display:'flex', justifyContent:'space-between'}}>
          <Body1Strong>Select a Team</Body1Strong>
          <Button appearance="subtle" icon={<Dismiss/>} onClick={() => setIsOpen(false)}></Button>
        </DialogTitle>

        <TabList
          selectedValue={activeTab}
          onTabSelect={(_, data) =>
            setActiveTab(data.value as "teams" | "upload")
          }
          style={{width:'calc(100% + 16px)', margin:'8px 0 0 0', alignSelf:'center'}}
        >
          <Tab value="teams">Teams</Tab>
          <Tab value="upload">Upload team</Tab>
        </TabList>

        <DialogContent style={{ margin:'16px 0', height: "100%", boxSizing:'border-box', }}>
          <DialogBody
            style={{  display: "flex", flex: 1,height: "100%", flexDirection: "column",boxSizing:'border-box' }}
          >
            {activeTab === "teams" ? (
              <TeamSelector
                isOpen={isOpen}
                refreshKey={refreshKey}
                selectedTeam={tempSelectedTeam}
                onTeamSelect={setTempSelectedTeam}
              />
            ) : (
              <TeamUploadTab
                onUploaded={() => {
                  setActiveTab("teams");
                  setRefreshKey((k) => k + 1);
                }}
              />
            )}
          </DialogBody>
        </DialogContent>

        <DialogActions style={{display:'flex', justifyContent:'flex-end'}}>
          {/* <Button appearance="secondary" onClick={() => setIsOpen(false)}>
            Cancel
          </Button> */}
          <Button
            appearance="primary"
            onClick={() => {
              onTeamSelect?.(tempSelectedTeam ?? null);
              setIsOpen(false);
            }}
            disabled={!tempSelectedTeam}
          >
            Continue
          </Button>
        </DialogActions>
      </DialogSurface>
    </Dialog>
  );
};

export default TeamSettingsButton;
