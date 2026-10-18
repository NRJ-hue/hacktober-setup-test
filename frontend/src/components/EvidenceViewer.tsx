import React from "react";
import type { Citation, SourceType } from "../types/api";

const SOURCE_TYPE_LABELS: Record<SourceType, string> = {
  contract: "Contract",
  legislation: "Legislation",
  judgment: "Court judgment",
};

interface EvidenceViewerProps {
  citations: Citation[];
}

export const EvidenceViewer: React.FC<EvidenceViewerProps> = ({ citations }) => {
  if (!citations || citations.length === 0) {
    return (
      <div style={{ marginTop: "0.75rem", fontSize: "0.85rem", color: "#6b7280" }}>
        No citations recorded for this finding.
      </div>
    );
  }

  return (
    <div style={{ marginTop: "1rem", borderTop: "1px solid #f3f4f6", paddingTop: "0.75rem" }}>
      <h5
        style={{
          margin: "0 0 0.5rem 0",
          fontSize: "0.85rem",
          fontWeight: "700",
          color: "#374151",
          textTransform: "uppercase",
          letterSpacing: "0.025em",
        }}
      >
        Supporting Evidence & Citations ({citations.length})
      </h5>
      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {citations.map((c, idx) => {
          const typeLabel = SOURCE_TYPE_LABELS[c.source_type] || c.source_type;
          const locParts: string[] = [typeLabel];
          if (c.page !== null) locParts.push(`p. ${c.page}`);
          if (c.section) locParts.push(`§ ${c.section}`);

          return (
            <li
              key={`${c.source_id}-${idx}`}
              style={{
                padding: "0.6rem 0.75rem",
                background: "#f9fafb",
                borderRadius: "6px",
                border: "1px solid #e5e7eb",
                fontSize: "0.85rem",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: "0.5rem",
                  marginBottom: "0.35rem",
                  flexWrap: "wrap",
                }}
              >
                <span style={{ fontWeight: "600", color: "#1f2937" }}>
                  {locParts.join(" • ")}
                  <span style={{ fontWeight: "normal", color: "#6b7280", marginLeft: "0.4rem" }}>
                    ({c.source_id})
                  </span>
                </span>
                <span
                  style={{
                    padding: "0.15rem 0.5rem",
                    borderRadius: "9999px",
                    fontSize: "0.75rem",
                    fontWeight: "600",
                    background: c.verified ? "#dcfce7" : "#fee2e2",
                    color: c.verified ? "#166534" : "#991b1b",
                    border: `1px solid ${c.verified ? "#86efac" : "#fca5a5"}`,
                  }}
                >
                  {c.verified ? "Verified against document" : "Not verified"}
                </span>
              </div>
              <blockquote
                style={{
                  margin: 0,
                  padding: "0.35rem 0.6rem",
                  background: "#ffffff",
                  borderLeft: "3px solid #9ca3af",
                  fontStyle: "italic",
                  color: "#374151",
                  borderRadius: "0 4px 4px 0",
                }}
              >
                {c.quote}
              </blockquote>
            </li>
          );
        })}
      </ul>
    </div>
  );
};
