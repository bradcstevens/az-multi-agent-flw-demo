// DEV NOTE: Upload tab
// - Drag & drop or click to browse
// - Validates JSON; uploads; shows progress/errors
// - onUploaded() => parent refreshes Teams and switches tab

import React, { useRef, useState } from "react";
import { Button, Body1, Body1Strong, Spinner, Text } from "@fluentui/react-components";
import { AddCircle24Color, AddCircleColor, ArrowUploadRegular, DocumentAdd20Color, DocumentAddColor } from "@fluentui/react-icons";
import { TeamService } from "../../services/TeamService";

interface Props {
  onUploaded: () => void;
}

const TeamUploadTab: React.FC<Props> = ({ onUploaded }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const validateTeamConfig = (data: any): { isValid: boolean; errors: string[] } => {
    const errors: string[] = [];
    if (!data || typeof data !== "object") errors.push("JSON file cannot be empty and must contain a valid object");
    if (!data?.name || !String(data.name).trim()) errors.push("Team name is required and cannot be empty");
    if (!data?.description || !String(data.description).trim()) errors.push("Team description is required and cannot be empty");
    if (!data?.status || !String(data.status).trim()) errors.push("Team status is required and cannot be empty");
    if (!Array.isArray(data?.agents) || data.agents.length === 0) {
      errors.push("Team must have at least one agent");
    } else {
      data.agents.forEach((agent: any, i: number) => {
        if (!agent || typeof agent !== "object") errors.push(`Agent ${i + 1}: Invalid object`);
        if (!agent?.name || !String(agent.name).trim()) errors.push(`Agent ${i + 1}: name required`);
        if (!agent?.type || !String(agent.type).trim()) errors.push(`Agent ${i + 1}: type required`);
        if (!agent?.input_key || !String(agent.input_key).trim()) errors.push(`Agent ${i + 1}: input_key required`);
        if (!agent?.deployment_name || !String(agent.deployment_name).trim()) errors.push(`Agent ${i + 1}: deployment_name required`);
        if (String(agent.type).toLowerCase() === "rag" && (!agent?.index_name || !String(agent.index_name).trim())) {
          errors.push(`Agent ${i + 1}: index_name required for RAG agents`);
        }
      });
    }
    return { isValid: errors.length === 0, errors };
  };

  const processFile = async (file: File) => {
    setError(null);
    setUploadLoading(true);
    setUploadMessage("Reading and validating team configuration...");

    try {
      if (!file.name.toLowerCase().endsWith(".json")) {
        throw new Error("Please upload a valid JSON file");
      }

      const content = await file.text();
      let teamData: any;
      try {
        teamData = JSON.parse(content);
      } catch {
        throw new Error("Invalid JSON format. Please check your file syntax");
      }

      setUploadMessage("Validating team configuration structure...");
      const validation = validateTeamConfig(teamData);
      if (!validation.isValid) {
        throw new Error(
          `Team configuration validation failed:\n\n${validation.errors.map((e) => `• ${e}`).join("\n")}`
        );
      }

      setUploadMessage("Uploading team configuration...");
      const result = await TeamService.uploadCustomTeam(file);

      if (result.success) {
        setUploadMessage("Team uploaded successfully!");
        setTimeout(() => {
          setUploadMessage(null);
          onUploaded();
        }, 200);
      } else if (result.raiError) {
        throw new Error("❌ Content Safety Check Failed\n\nYour team configuration doesn't meet content guidelines.");
      } else if (result.modelError) {
        throw new Error("🤖 Model Deployment Validation Failed\n\nVerify deployment_name values and access to AI services.");
      } else if (result.searchError) {
        throw new Error("🔍 RAG Search Configuration Error\n\nVerify search index names and access.");
      } else {
        throw new Error(result.error || "Failed to upload team configuration");
      }
    } catch (err: any) {
      setError(err.message || "Failed to upload team configuration");
      setUploadMessage(null);
    } finally {
      setUploadLoading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div style={{  }}>










      {/* Drag & drop zone (also clickable) */}
      <div
        onDrop={(e) => {
          e.preventDefault();
          const file = e.dataTransfer.files?.[0];
          if (file) processFile(file);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          e.dataTransfer.dropEffect = "copy";
        }}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        style={{
          border: "1px dashed var(--colorNeutralStroke1)",
          height:'100%',
          borderRadius: 8,
          padding: 24,
          textAlign: "center",
          background: "var(--colorNeutralBackground2)",
          cursor: "pointer",
          userSelect: "none",
          display:'flex',
          flexDirection:'column',
          justifyContent:'center',
          alignContent:'center',
          alignItems:'center',
          flex: 1
        }}
      >

        <ArrowUploadRegular style={{ fontSize: 28 }} />
        <br/>
        <Body1Strong style={{  }}>
          Drag & drop your team JSON here
        </Body1Strong>
        <Body1 style={{ color: "var(--colorNeutralForeground3)" }}>
          or click to browse
        </Body1>
        <input
          ref={inputRef}
          type="file"
          accept=".json"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) processFile(f);
          }}
          style={{ display: "none" }}
        />
      </div>

      {/* Status + errors */}
      {uploadMessage && (
        <div style={{ color: "#107c10", marginTop: 16, padding: 12, backgroundColor: "#f3f9f3",
          border: "1px solid #c6e7c6", borderRadius: 4, display: "flex", alignItems: "center", gap: 8 }}>
          <Spinner size="extra-small" />
          <Text>{uploadMessage}</Text>
        </div>
      )}

      {error && (
        <div style={{ color: "#d13438", marginTop: 16, padding: 12, backgroundColor: "#fdf2f2",
          border: "1px solid #f5c6cb", borderRadius: 4 }}>
          <Text style={{ whiteSpace: "pre-line" }}>{error}</Text>
        </div>
      )}



      {/* Requirements */}
      <div style={{ marginTop: 16, padding: 12, backgroundColor: "rgba(255,255,255,0.05)",
        border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8 }}>
        <Body1Strong style={{ display: "block", marginBottom: 8 }}>Upload requirements</Body1Strong>
        <Body1 style={{ color: "var(--colorNeutralForeground3)" }}>
          • JSON must include <strong>name</strong>, <strong>description</strong>, and <strong>status</strong>
          <br />• At least one agent with <strong>name</strong>, <strong>type</strong>, <strong>input_key</strong>, and <strong>deployment_name</strong>
          <br />• RAG agents additionally require <strong>index_name</strong>
          <br />• Starting tasks are optional, but if provided must include <strong>name</strong> and <strong>prompt</strong>
          <br />• Text fields cannot be empty
        </Body1>
      </div>



    </div>
  );
};

export default TeamUploadTab;
