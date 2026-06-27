/**
 * Sentinel API client
 *
 * 對應 backend routes/sentinel_patients.py + sentinel.py.
 * 用 apiClient (axios) 但不依賴 firebase auth (dev bypass).
 */
import { apiClient } from '@/lib/api';

export interface PatientCard {
  id: string;
  name: string;
  gender: string | null;
  date_of_birth: string | null;
  phone: string | null;
  id_number: string | null;
  flag_count: number;
  chronic_count: number;
  has_red_flag: boolean;
}

export interface PatientSearchResponse {
  items: PatientCard[];
  total: number;
  clinic_id: string;
}

export interface HeartFlag {
  id: string;
  flag_type: string;
  severity: string | null;
  content: string;
  confidence_status: string;
  flag_source: string;
}

export interface HeartProblem {
  id: string;
  problem_name: string;
  icd10_code: string | null;
  control_status: string;
  diagnosed_at: string | null;
}

export interface HeartMedication {
  id: string;
  medication_name: string;
  category: string;
  dosage: string | null;
  frequency: string | null;
  is_active: boolean;
}

export interface HeartBaseline {
  id: string;
  category: string;
  value_text: string;
  measured_at: string | null;
}

export interface HeartLayerSummary {
  flags: HeartFlag[];
  problems: HeartProblem[];
  medications: HeartMedication[];
  baselines: HeartBaseline[];
}

export interface VitalSigns {
  blood_pressure_systolic?: number;
  blood_pressure_diastolic?: number;
  heart_rate?: number;
  respiratory_rate?: number;
  temperature_c?: number;
  oxygen_saturation?: number;
}

export interface LabResult {
  name: string;
  value: number | string;
  unit: string;
  reference_range?: string | null;
  is_abnormal?: boolean | null;
}

export interface PrescriptionItem {
  drug_name: string;
  drug_code?: string | null;
  unit?: string | null;
  usage_text?: string | null;
  daily_dose?: number | null;
  days?: number | null;
  total_quantity?: number | null;
}

export interface AiDraftSummary {
  id: string;
  agent_type: 'intake' | 'triage' | 'audit' | 'education';
  status: string;
  payload: any;
  accepted_at?: string | null;
}

export interface VisitTimelineItem {
  id: string;
  visit_date: string;
  chief_complaint: string | null;
  hpi: string | null;            // 現病史 (Phase 2.4c)
  physical_exam: string | null;  // 查體
  diagnosis: string | null;
  status: string;
  vital_signs?: VitalSigns | null;
  lab_results?: LabResult[] | null;
  xray_findings?: string | null;
  ecg_findings?: string | null;
  prescription_items?: PrescriptionItem[];   // Phase 2.4d
  ai_drafts?: AiDraftSummary[];               // Phase 4.2d
}

export interface PatientDetail {
  id: string;
  name: string;
  gender: string | null;
  date_of_birth: string | null;
  phone: string | null;
  id_number: string | null;
  clinic_id: string;
  heart_layer: HeartLayerSummary;
  visits: VisitTimelineItem[];
}

export async function searchPatients(q: string = ''): Promise<PatientSearchResponse> {
  const { data } = await apiClient.get<PatientSearchResponse>('/v1/sentinel/patients', {
    params: q.trim() ? { q: q.trim() } : {},
  });
  return data;
}

export async function getPatientDetail(patientId: string): Promise<PatientDetail> {
  const { data } = await apiClient.get<PatientDetail>(`/v1/sentinel/patients/${patientId}`);
  return data;
}

// Phase 4.1 新就診
export interface AiDraftInput {
  agent_type: 'intake' | 'triage' | 'audit' | 'education';
  payload: Record<string, any>;
}

export interface NewVisitInput {
  chief_complaint: string;
  hpi?: string;
  physical_exam?: string;
  diagnosis?: string;
  visit_date?: string;
  vital_signs?: {
    blood_pressure_systolic?: number;
    blood_pressure_diastolic?: number;
    heart_rate?: number;
    respiratory_rate?: number;
    temperature_c?: number;
    oxygen_saturation?: number;
  };
  free_notes?: string;
  ai_drafts?: AiDraftInput[];  // Phase 4.2c
}

export interface NewVisitResponse {
  visit_id: string;
  patient_id: string;
  visit_date: string;
  status: string;
  ai_drafts_saved?: number;
}

export async function createVisit(
  patientId: string,
  payload: NewVisitInput
): Promise<NewVisitResponse> {
  const { data } = await apiClient.post<NewVisitResponse>(
    `/v1/sentinel/patients/${patientId}/visits`,
    payload
  );
  return data;
}

// ─── Phase 4.2a: Sentinel agent 4 件套 ───────────────────────

export interface IntakeFinding {
  section: string;
  text: string;
}
export interface IntakeResponse {
  findings: IntakeFinding[];
  summary: string;
  model_used: string;
}

export interface TriageDifferential {
  name: string;
  reason: string;
  references?: string[];
}
export interface TriageResponse {
  has_conflict: boolean;
  conflict_summary: string;
  differentials: TriageDifferential[];
  closing_note: string;
  model_used: string;
}

export interface AuditContextualRisk {
  drug: string;
  risk: string;
  triggered_by: string;
  source_url?: string | null;
  needs_confirmation: boolean;
}
export interface AuditRuleFinding {
  drug_a: string;
  drug_b: string;
  severity: string;
  evidence: string;
  recommendation?: string;
}
export interface AuditResponse {
  rule_engine_findings: AuditRuleFinding[];
  contextual_risks: AuditContextualRisk[];
  unknowns: string[];
  closing_note: string;
  model_used: string;
}

export interface EducationResponse {
  advice: string;
  model_used: string;
}

// Mapper: backend heart_layer -> sentinel schema input
function toSentinelFlags(flags: HeartFlag[]) {
  // valid sentinel schema flag types
  const allowed = new Set(['allergy', 'pregnancy', 'major_history', 'medical_directive', 'interaction_note', 'origin']);
  return flags
    .filter((f) => allowed.has(f.flag_type))
    .map((f) => ({
      type: f.flag_type,
      content: f.content,
      severity: f.severity,
      source: f.flag_source,
    }));
}

function toSentinelProblems(problems: HeartProblem[]) {
  return problems.map((p) => ({
    name: p.problem_name,
    diagnosed_at: p.diagnosed_at,
    control_status: ['controlled', 'unstable', 'worsening'].includes(p.control_status)
      ? p.control_status
      : null,
    medications: [],
  }));
}

function toSentinelMeds(meds: HeartMedication[]) {
  return meds.map((m) => ({
    name: m.medication_name,
    category: ['chronic_disease_med', 'supplement', 'tcm'].includes(m.category)
      ? m.category
      : 'chronic_disease_med',
    composition_certain: true,
  }));
}

export async function runIntake(rawDictation: string, chiefComplaintHint?: string): Promise<IntakeResponse> {
  const { data } = await apiClient.post<IntakeResponse>('/v1/sentinel/intake', {
    raw_dictation: rawDictation,
    chief_complaint_hint: chiefComplaintHint,
  });
  return data;
}

export async function runTriage(
  workingHypothesis: string,
  flags: HeartFlag[],
  problems: HeartProblem[],
  meds: HeartMedication[]
): Promise<TriageResponse> {
  const { data } = await apiClient.post<TriageResponse>('/v1/sentinel/triage', {
    working_hypothesis: workingHypothesis,
    flags: toSentinelFlags(flags),
    problems: toSentinelProblems(problems),
    medications: toSentinelMeds(meds),
  });
  return data;
}

export async function runEducation(
  diagnosis: string,
  patientNameHint?: string
): Promise<EducationResponse> {
  const { data } = await apiClient.post<EducationResponse>('/v1/sentinel/education', {
    diagnosis,
    patient_habits: {},
    patient_name_hint: patientNameHint,
  });
  return data;
}

export async function runAudit(
  newPrescription: string[],
  flags: HeartFlag[],
  meds: HeartMedication[],
  problems: HeartProblem[]
): Promise<AuditResponse> {
  const { data } = await apiClient.post<AuditResponse>('/v1/sentinel/audit', {
    new_prescription: newPrescription,
    flags: toSentinelFlags(flags),
    long_term_medications: toSentinelMeds(meds),
    problems: toSentinelProblems(problems),
  });
  return data;
}

// ─── Phase 6: Mode A/B review ─────────────────────────────────

export type ReviewModeKind = 'at_the_time' | 'hindsight';

export interface ReviewModeInfo {
  mode: ReviewModeKind;
  heart_layer_source: string;   // snapshot:before_visit / snapshot:after_visit / fallback:current
  summary_text: string;
}

export interface ReviewResponse {
  visit_id: string;
  mode: ReviewModeInfo;
  intake: IntakeResponse | null;
  triage: TriageResponse | null;
  audit: AuditResponse | null;
  education: EducationResponse | null;
  skipped: string[];
  mode_disclaimer: string;
}

export async function reviewVisit(
  visitId: string,
  mode: ReviewModeKind
): Promise<ReviewResponse> {
  const { data } = await apiClient.post<ReviewResponse>(
    `/v1/sentinel/visits/${visitId}/review`,
    { mode }
  );
  return data;
}
