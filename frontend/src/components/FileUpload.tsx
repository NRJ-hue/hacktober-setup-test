import React, { useState } from "react";
import type { DocumentStatus } from "../types/api";
import { uploadDocument } from "../services/api";

interface FileUploadProps {
  onDocumentUploaded: (status: DocumentStatus) => void;
  disabled?: boolean;
}

function mapReasonCodeToMessage(reasonCode: string): string {
  switch (reasonCode) {
    case "OCR_REQUIRED":
      return "This looks like a scanned PDF; OCR is not supported yet.";
    case "FILE_TOO_LARGE":
      return "The uploaded file exceeds the 10MB file size limit.";
    case "EMPTY_FILE":
      return "The uploaded file is empty.";
    case "CONTENT_TYPE_MISMATCH":
      return "The file content does not match its file extension.";
    case "UNSUPPORTED_FILE_TYPE":
      return "Unsupported file type. Only PDF and TXT files are accepted.";
    case "CORRUPT_PDF":
      return "The PDF file appears to be corrupted or unreadable.";
    case "ENCRYPTED_PDF":
      return "Encrypted or password-protected PDF files cannot be processed.";
    case "INVALID_UTF8":
      return "The text file contains invalid non-UTF-8 characters.";
    case "CONTAINS_NUL_BYTES":
      return "The text file contains invalid binary NUL characters.";
    default:
      return `Upload failed: ${reasonCode}`;
  }
}

export const FileUpload: React.FC<FileUploadProps> = ({
  onDocumentUploaded,
  disabled = false,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setErrorMessage(null);
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
    } else {
      setSelectedFile(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setIsUploading(true);
    setErrorMessage(null);

    try {
      const docStatus = await uploadDocument(selectedFile);
      onDocumentUploaded(docStatus);
    } catch (err: unknown) {
      const reason = err instanceof Error ? err.message : "UPLOAD_ERROR";
      setErrorMessage(mapReasonCodeToMessage(reason));
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="card" style={{ padding: "1.25rem", border: "1px solid #d1d5db", borderRadius: "8px", background: "#ffffff" }}>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <div>
          <label htmlFor="file-input" style={{ display: "block", fontWeight: "600", marginBottom: "0.5rem" }}>
            Upload Legal Document (.pdf, .txt)
          </label>
          <input
            id="file-input"
            type="file"
            accept=".pdf,.txt"
            onChange={handleFileChange}
            disabled={disabled || isUploading}
            aria-describedby={errorMessage ? "file-error-msg" : undefined}
            style={{ width: "100%", padding: "0.5rem", border: "1px solid #9ca3af", borderRadius: "4px" }}
          />
        </div>

        <button
          type="submit"
          disabled={disabled || !selectedFile || isUploading}
          style={{
            alignSelf: "flex-start",
            padding: "0.6rem 1.25rem",
            backgroundColor: disabled || !selectedFile || isUploading ? "#9ca3af" : "#2563eb",
            color: "#ffffff",
            fontWeight: "600",
            border: "none",
            borderRadius: "4px",
            cursor: disabled || !selectedFile || isUploading ? "not-allowed" : "pointer",
          }}
          aria-label="Upload document"
        >
          {isUploading ? "Uploading & Ingesting..." : "Upload Document"}
        </button>

        {errorMessage && (
          <div
            id="file-error-msg"
            role="alert"
            style={{
              padding: "0.75rem",
              background: "#fee2e2",
              color: "#991b1b",
              borderRadius: "4px",
              fontWeight: "500",
            }}
          >
            {errorMessage}
          </div>
        )}
      </form>
    </div>
  );
};
