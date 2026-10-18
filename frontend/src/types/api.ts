/**
 * TypeScript API interfaces mirroring canonical Pydantic schemas in backend/app/models/schemas.py.
 */

export type SourceType = "contract" | "legislation" | "judgment";

export type FindingCategory =
  | "obligation"
  | "right"
  | "deadline"
  | "penalty"
  | "termination"
  | "ambiguity"
  | "missing_information"
  | "potential_legal_concern"
  | "other";

export type AgentResponseStatus = "answered" | "abstained" | "refused" | "error";

export type DocumentProcessingStatus = "processing" | "ready" | "failed" | "deleted";

export interface Citation {
  source_id: string;
  source_type: SourceType;
  page: number | null;
  section: string | null;
  quote: string;
  verified: boolean;
}

export interface Finding {
  title: string;
  category: FindingCategory;
  explicit_text: string;
  plain_language_explanation: string;
  interpretation_or_concern: string | null;
  evidence: Citation[];
  uncertainty: string | null;
  escalation_required: boolean;
}

export interface AgentResponse {
  answer: string;
  findings: Finding[];
  evidence_sufficient: boolean;
  limitation: string | null;
  professional_review_recommended: boolean;
  status: AgentResponseStatus;
}

export interface DocumentStatus {
  document_id: string;
  status: DocumentProcessingStatus;
  page_count: number | null;
  chunk_count: number | null;
  message: string | null;
}

export interface QuestionRequest {
  question: string;
}
