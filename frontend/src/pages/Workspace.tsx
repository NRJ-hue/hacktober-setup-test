import React, { useState } from "react";
import type { AgentResponse, DocumentStatus } from "../types/api";
import { askQuestion, deleteDocument } from "../services/api";
import { FileUpload } from "../components/FileUpload";
import { QuestionForm } from "../components/QuestionForm";
import { FindingCard } from "../components/FindingCard";
import { StatusMessage } from "../components/StatusMessage";

export const Workspace: React.FC = () => {
  const [docStatus, setDocStatus] = useState<DocumentStatus | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [isAsking, setIsAsking] = useState<boolean>(false);
  const [agentResponse, setAgentResponse] = useState<AgentResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleUploadSuccess = (status: DocumentStatus) => {
    setDocStatus(status);
    setAgentResponse(null);
    setErrorMessage(null);
  };

  const handleDelete = async () => {
    if (!docStatus?.document_id) return;
    setIsDeleting(true);
    try {
      await deleteDocument(docStatus.document_id);
    } catch (err) {
      // Even if network or delete error, reset the local UI state
      console.warn("Delete document returned error:", err);
    } finally {
      setDocStatus(null);
      setAgentResponse(null);
      setErrorMessage(null);
      setIsDeleting(false);
    }
  };

  const handleAsk = async (question: string) => {
    if (!docStatus?.document_id) return;
    setIsAsking(true);
    setErrorMessage(null);
    setAgentResponse(null);

    try {
      const response = await askQuestion(docStatus.document_id, question);
      setAgentResponse(response);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "QUESTION_FAILED";
      setErrorMessage(msg);
    } finally {
      setIsAsking(false);
    }
  };

  return (
    <main
      style={{
        maxWidth: "960px",
        margin: "0 auto",
        padding: "2rem 1rem",
        fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        color: "#111827",
      }}
    >
      <header style={{ marginBottom: "2rem" }}>
        <h1 style={{ margin: "0 0 0.5rem 0", fontSize: "1.75rem", color: "#111827" }}>
          Legal Document Assistant
        </h1>
        <p style={{ margin: 0, color: "#4b5563", fontSize: "1rem" }}>
          Upload legal documents for grounded extraction, evidence citation, and plain-language explanation.
        </p>
      </header>

      {/* Persistent Disclaimer Banner */}
      <StatusMessage
        status={agentResponse?.status}
        limitation={agentResponse?.limitation}
        errorMessage={errorMessage}
        professionalReviewRecommended={agentResponse?.professional_review_recommended}
      />

      {/* Upload Phase or Active Document Phase */}
      {!docStatus ? (
        <section aria-labelledby="upload-section-title">
          <h2 id="upload-section-title" style={{ fontSize: "1.25rem", marginBottom: "1rem" }}>
            Step 1: Upload a Document
          </h2>
          <FileUpload onDocumentUploaded={handleUploadSuccess} />
        </section>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
          {/* Active Document Info Bar */}
          <section
            aria-labelledby="doc-details-title"
            style={{
              padding: "1rem 1.25rem",
              background: "#f9fafb",
              border: "1px solid #e5e7eb",
              borderRadius: "8px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "1rem",
            }}
          >
            <div>
              <h2 id="doc-details-title" style={{ margin: "0 0 0.25rem 0", fontSize: "1rem", fontWeight: "700" }}>
                Active Document Session
              </h2>
              <div style={{ fontSize: "0.85rem", color: "#4b5563" }}>
                <span>ID: <code>{docStatus.document_id.slice(0, 8)}...</code></span>
                {docStatus.page_count !== null && (
                  <span style={{ marginLeft: "1rem" }}>Pages: {docStatus.page_count}</span>
                )}
                {docStatus.chunk_count !== null && (
                  <span style={{ marginLeft: "1rem" }}>Chunks: {docStatus.chunk_count}</span>
                )}
              </div>
            </div>

            <button
              type="button"
              onClick={handleDelete}
              disabled={isDeleting}
              aria-label="Delete active document and reset session"
              style={{
                padding: "0.5rem 1rem",
                borderRadius: "6px",
                border: "1px solid #dc2626",
                background: "#ffffff",
                color: "#dc2626",
                fontWeight: "600",
                fontSize: "0.875rem",
                cursor: isDeleting ? "not-allowed" : "pointer",
              }}
            >
              {isDeleting ? "Deleting..." : "Delete document"}
            </button>
          </section>

          {/* Question Form */}
          <section aria-labelledby="question-section-title">
            <h2 id="question-section-title" style={{ fontSize: "1.25rem", marginBottom: "0.75rem" }}>
              Step 2: Ask a Question
            </h2>
            <QuestionForm onSubmitQuestion={handleAsk} isLoading={isAsking} />
          </section>

          {/* Results Container with aria-live="polite" */}
          <section
            aria-live="polite"
            aria-atomic="false"
            aria-labelledby="results-section-title"
            style={{ minHeight: "100px" }}
          >
            <h2 id="results-section-title" style={{ fontSize: "1.25rem", marginBottom: "1rem" }}>
              Analysis Results
            </h2>

            {isAsking && (
              <div
                role="status"
                style={{
                  padding: "1.5rem",
                  textAlign: "center",
                  background: "#f9fafb",
                  borderRadius: "8px",
                  border: "1px dashed #d1d5db",
                  color: "#4b5563",
                }}
              >
                Analyzing document passages and synthesizing grounded response...
              </div>
            )}

            {!isAsking && !agentResponse && !errorMessage && (
              <div style={{ color: "#6b7280", fontStyle: "italic", fontSize: "0.95rem" }}>
                Submit a question above to analyze the loaded document.
              </div>
            )}

            {agentResponse && (
              <div>
                {/* Answer Summary */}
                {agentResponse.answer && (
                  <div
                    style={{
                      marginBottom: "1.5rem",
                      padding: "1.25rem",
                      background: "#f0fdf4",
                      borderRadius: "8px",
                      border: "1px solid #bbf7d0",
                    }}
                  >
                    <h3 style={{ margin: "0 0 0.5rem 0", color: "#166534", fontSize: "1.1rem" }}>
                      Summary Answer
                    </h3>
                    <p style={{ margin: 0, color: "#14532d", lineHeight: "1.6", fontSize: "1rem" }}>
                      {agentResponse.answer}
                    </p>
                  </div>
                )}

                {/* Findings List */}
                {agentResponse.findings && agentResponse.findings.length > 0 ? (
                  <div>
                    <h3 style={{ fontSize: "1.1rem", marginBottom: "1rem", color: "#1f2937" }}>
                      Identified Findings ({agentResponse.findings.length})
                    </h3>
                    {agentResponse.findings.map((finding, idx) => (
                      <FindingCard key={`${finding.title}-${idx}`} finding={finding} />
                    ))}
                  </div>
                ) : (
                  agentResponse.status === "answered" && (
                    <div style={{ color: "#4b5563", fontStyle: "italic", fontSize: "0.95rem" }}>
                      No specific obligation or risk findings were extracted for this question.
                    </div>
                  )
                )}
              </div>
            )}
          </section>
        </div>
      )}
    </main>
  );
};
