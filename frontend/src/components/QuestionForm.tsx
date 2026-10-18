import React, { useState } from "react";

interface QuestionFormProps {
  onSubmitQuestion: (question: string) => Promise<void>;
  isLoading: boolean;
}

const MAX_QUESTION_CHARS = 1000;

export const QuestionForm: React.FC<QuestionFormProps> = ({
  onSubmitQuestion,
  isLoading,
}) => {
  const [question, setQuestion] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || isLoading) return;
    await onSubmitQuestion(trimmed);
  };

  return (
    <div
      style={{
        padding: "1.25rem",
        border: "1px solid #d1d5db",
        borderRadius: "8px",
        background: "#ffffff",
      }}
    >
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <label
          htmlFor="question-textarea"
          style={{ fontWeight: "600", color: "#1f2937" }}
        >
          Ask a question about this document
        </label>
        <textarea
          id="question-textarea"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={MAX_QUESTION_CHARS}
          disabled={isLoading}
          rows={4}
          placeholder="e.g. What is the notice period for terminating the lease?"
          style={{
            width: "100%",
            padding: "0.75rem",
            border: "1px solid #9ca3af",
            borderRadius: "4px",
            fontFamily: "inherit",
            fontSize: "0.95rem",
            boxSizing: "border-box",
          }}
          aria-describedby="question-counter"
        />
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span
            id="question-counter"
            style={{
              fontSize: "0.85rem",
              color: question.length >= MAX_QUESTION_CHARS ? "#dc2626" : "#4b5563",
            }}
          >
            {question.length} / {MAX_QUESTION_CHARS} characters
          </span>
          <button
            type="submit"
            disabled={isLoading || !question.trim()}
            style={{
              padding: "0.6rem 1.25rem",
              backgroundColor: isLoading || !question.trim() ? "#9ca3af" : "#2563eb",
              color: "#ffffff",
              fontWeight: "600",
              border: "none",
              borderRadius: "4px",
              cursor: isLoading || !question.trim() ? "not-allowed" : "pointer",
            }}
            aria-label="Submit question"
          >
            {isLoading ? "Analyzing Document..." : "Ask Question"}
          </button>
        </div>
      </form>
    </div>
  );
};
