import React from "react";
import type { Finding } from "../types/api";
import { EvidenceViewer } from "./EvidenceViewer";

interface FindingCardProps {
  finding: Finding;
}

export const FindingCard: React.FC<FindingCardProps> = ({ finding }) => {
  return (
    <article
      style={{
        border: "1px solid #e5e7eb",
        borderRadius: "8px",
        padding: "1.25rem",
        background: "#ffffff",
        boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
        marginBottom: "1rem",
      }}
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: "1rem",
          marginBottom: "1rem",
          flexWrap: "wrap",
        }}
      >
        <h4 style={{ margin: 0, fontSize: "1.1rem", color: "#111827" }}>
          {finding.title}
        </h4>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <span
            style={{
              padding: "0.2rem 0.6rem",
              background: "#e0e7ff",
              color: "#3730a3",
              borderRadius: "9999px",
              fontSize: "0.75rem",
              fontWeight: "600",
              textTransform: "uppercase",
            }}
          >
            {finding.category.replace(/_/g, " ")}
          </span>
          {finding.escalation_required && (
            <span
              style={{
                padding: "0.2rem 0.6rem",
                background: "#fee2e2",
                color: "#991b1b",
                borderRadius: "9999px",
                fontSize: "0.75rem",
                fontWeight: "700",
              }}
            >
              Escalation Required
            </span>
          )}
        </div>
      </header>

      {/* Document quote */}
      <div style={{ marginBottom: "1rem" }}>
        <div
          style={{
            fontSize: "0.8rem",
            fontWeight: "700",
            textTransform: "uppercase",
            color: "#4b5563",
            marginBottom: "0.25rem",
          }}
        >
          Document says
        </div>
        <blockquote
          style={{
            margin: 0,
            padding: "0.75rem 1rem",
            background: "#f9fafb",
            borderLeft: "4px solid #3b82f6",
            fontStyle: "italic",
            color: "#1f2937",
            borderRadius: "0 4px 4px 0",
          }}
        >
          {finding.explicit_text}
        </blockquote>
      </div>

      {/* Plain language explanation */}
      <div style={{ marginBottom: "1rem" }}>
        <div
          style={{
            fontSize: "0.8rem",
            fontWeight: "700",
            textTransform: "uppercase",
            color: "#4b5563",
            marginBottom: "0.25rem",
          }}
        >
          Plain-language explanation (AI)
        </div>
        <p style={{ margin: 0, color: "#374151", lineHeight: "1.5" }}>
          {finding.plain_language_explanation}
        </p>
      </div>

      {/* Possible concern / interpretation if present */}
      {finding.interpretation_or_concern && (
        <div style={{ marginBottom: "1rem" }}>
          <div
            style={{
              fontSize: "0.8rem",
              fontWeight: "700",
              textTransform: "uppercase",
              color: "#92400e",
              marginBottom: "0.25rem",
            }}
          >
            Possible concern (AI interpretation, not legal advice)
          </div>
          <p
            style={{
              margin: 0,
              padding: "0.5rem 0.75rem",
              background: "#fef3c7",
              color: "#78350f",
              borderRadius: "4px",
              lineHeight: "1.4",
            }}
          >
            {finding.interpretation_or_concern}
          </p>
        </div>
      )}

      {/* Uncertainty note if present */}
      {finding.uncertainty && (
        <div style={{ marginTop: "0.5rem" }}>
          <div
            style={{
              fontSize: "0.75rem",
              fontWeight: "600",
              color: "#6b7280",
              marginBottom: "0.2rem",
            }}
          >
            Note on Uncertainty:
          </div>
          <p style={{ margin: 0, fontSize: "0.85rem", color: "#6b7280", fontStyle: "italic" }}>
            {finding.uncertainty}
          </p>
        </div>
      )}

      {/* Citations / Evidence */}
      <EvidenceViewer citations={finding.evidence} />
    </article>
  );
};
