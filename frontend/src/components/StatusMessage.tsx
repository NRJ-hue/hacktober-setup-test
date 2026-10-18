import React from "react";
import type { AgentResponseStatus } from "../types/api";

interface StatusMessageProps {
  status?: AgentResponseStatus | null;
  limitation?: string | null;
  errorMessage?: string | null;
  professionalReviewRecommended?: boolean;
}

export const StatusMessage: React.FC<StatusMessageProps> = ({
  status,
  limitation,
  errorMessage,
  professionalReviewRecommended,
}) => {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginBottom: "1.25rem" }}>
      {/* Persistent Disclaimer Banner */}
      <div
        role="note"
        aria-label="Legal Disclaimer"
        style={{
          padding: "0.75rem 1rem",
          background: "#fef3c7",
          border: "1px solid #fcd34d",
          borderRadius: "6px",
          color: "#92400e",
          fontSize: "0.875rem",
          lineHeight: "1.4",
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
        }}
      >
        <span aria-hidden="true" style={{ fontSize: "1.1rem" }}>
          ⚠️
        </span>
        <span>
          <strong>Notice:</strong> Preliminary document understanding only, not legal advice. Consider a qualified legal professional.
        </span>
      </div>

      {/* Professional Review Recommended Banner */}
      {professionalReviewRecommended && (
        <div
          role="status"
          style={{
            padding: "0.6rem 0.9rem",
            background: "#eff6ff",
            border: "1px solid #bfdbfe",
            borderRadius: "6px",
            color: "#1e40af",
            fontSize: "0.85rem",
          }}
        >
          <strong>Professional Review Recommended:</strong> One or more findings in this analysis indicate complex obligations or legal risks requiring formal review.
        </div>
      )}

      {/* Abstained Status */}
      {status === "abstained" && (
        <div
          role="alert"
          style={{
            padding: "0.85rem 1rem",
            background: "#f3f4f6",
            border: "1px solid #d1d5db",
            borderRadius: "6px",
            color: "#1f2937",
          }}
        >
          <div style={{ fontWeight: "700", marginBottom: "0.25rem", color: "#374151" }}>
            The assistant abstained from answering.
          </div>
          <p style={{ margin: 0, fontSize: "0.875rem", color: "#4b5563", lineHeight: "1.4" }}>
            {limitation || "The document did not contain sufficient relevant evidence to answer this question reliably."}
          </p>
        </div>
      )}

      {/* Refused Status */}
      {status === "refused" && (
        <div
          role="alert"
          style={{
            padding: "0.85rem 1rem",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: "6px",
            color: "#991b1b",
          }}
        >
          <div style={{ fontWeight: "700", marginBottom: "0.25rem" }}>
            The request was refused.
          </div>
          <p style={{ margin: 0, fontSize: "0.875rem", color: "#b91c1c", lineHeight: "1.4" }}>
            {limitation || errorMessage || "The request could not be processed due to safety or policy constraints."}
          </p>
        </div>
      )}

      {/* Error Status */}
      {(status === "error" || errorMessage) && status !== "refused" && (
        <div
          role="alert"
          style={{
            padding: "0.85rem 1rem",
            background: "#fff1f2",
            border: "1px solid #ffe4e6",
            borderRadius: "6px",
            color: "#9f1239",
          }}
        >
          <div style={{ fontWeight: "700", marginBottom: "0.25rem" }}>
            An error occurred.
          </div>
          <p style={{ margin: 0, fontSize: "0.875rem", color: "#be123c", lineHeight: "1.4" }}>
            {limitation || errorMessage || "An unexpected error occurred while analyzing the document."}
          </p>
        </div>
      )}
    </div>
  );
};
