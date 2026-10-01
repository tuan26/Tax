export type Customer = {
  id: string;
  name: string;
  business_day_cutoff: string;
  pending_items?: number;
  pending_records?: number;
  open_findings?: number;
};

export type Evidence = {
  ref: string;
  kind: "text" | "attachment";
  text: string | null;
  attachment_id?: string;
  mime_type?: string;
  file_name?: string | null;
  sent_at: string | null;
  business_date: string | null;
  source_type: string;
};

export type FieldName = "transaction_type" | "amount" | "document_date" | "posting_date" | "description";

export type RecordFields = {
  transaction_type: "INCOME" | "EXPENSE" | null;
  amount: number | null;
  document_date: string | null;
  posting_date: string | null;
  description: string | null;
};

export type LedgerRecord = {
  id: string;
  group_id: string;
  fields: RecordFields;
  fields_ai: Record<string, { value: unknown; candidates?: unknown[] }>;
  decision_confidence: Record<string, number | null>;
  confirmed: boolean;
  review_required: boolean;
  review_reasons: string[];
  evidence_items: string[];
  evidence_kind: "document" | "bank_transfer_screenshot" | "self_declared";
  sent_date: string | null;
  status: string;
  evidence: Evidence[] | null;
  counted?: boolean;
  matched_document_ids?: string[];
  matched_payment_ids?: string[];
};

export type QueueItem = {
  type: "ambiguous_link" | "unmatched";
  decision_id: string;
  item_ref: string;
  role: string | null;
  reason: string | null;
  text: string | null;
  attachment_id: string | null;
  mime_type: string | null;
  sent_at: string | null;
  business_date: string | null;
  source_type: string;
  candidates: { choice: string; records: (LedgerRecord | null)[] }[];
};

export type QueueGroup = {
  group_id: string;
  partition_candidates: string[][][] | null;
  record: LedgerRecord | null;
};

export type Queue = { items: QueueItem[]; groups: QueueGroup[]; records: LedgerRecord[] };

export type MatchCriterion = { criterion: "amount" | "date" | "type"; ok: boolean | null; detail: string };

export type Finding = {
  id: string;
  rule_id: string;
  severity: "check" | "confirm";
  title: string;
  detail: string;
  amount: number | null;
  status: "OPEN" | "REQUESTED" | "RESOLVED" | "DISMISSED";
  resolution: "matched" | "has_document" | "no_longer_applies" | null;
  resolution_note: string | null;
  requested_at: string | null;
  decided_at: string | null;
  record: LedgerRecord | null;
  match?: { id: string; evidence: MatchCriterion[]; document: LedgerRecord };
};

export type Candidate = {
  record_id: string;
  fields: RecordFields;
  evidence: MatchCriterion[];
  evidence_detail: Evidence[];
  score: number;
};
