/**
 * Client API service for communicating exclusively with the local backend.
 */
import type { AgentResponse, DocumentStatus } from "../types/api";

const API_BASE = (import.meta.env.VITE_API_BASE as string) || "http://127.0.0.1:8000/api";

async function parseErrorReason(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (data && typeof data.detail === "string" && data.detail.trim()) {
      return data.detail.trim();
    }
  } catch {
    // Ignore JSON parse failure and return fallback
  }
  return `STATUS_${res.status}`;
}

export async function uploadDocument(file: File): Promise<DocumentStatus> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/documents`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const reason = await parseErrorReason(res);
    throw new Error(reason);
  }

  return res.json();
}

export async function getStatus(id: string): Promise<DocumentStatus> {
  const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(id)}`, {
    method: "GET",
  });

  if (!res.ok) {
    const reason = await parseErrorReason(res);
    throw new Error(reason);
  }

  return res.json();
}

export async function askQuestion(
  id: string,
  question: string
): Promise<AgentResponse> {
  const res = await fetch(
    `${API_BASE}/documents/${encodeURIComponent(id)}/questions`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ question }),
    }
  );

  if (!res.ok) {
    const reason = await parseErrorReason(res);
    throw new Error(reason);
  }

  return res.json();
}

export async function deleteDocument(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });

  if (!res.ok) {
    const reason = await parseErrorReason(res);
    throw new Error(reason);
  }
}
