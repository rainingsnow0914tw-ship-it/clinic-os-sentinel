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

export interface VisitTimelineItem {
  id: string;
  visit_date: string;
  chief_complaint: string | null;
  diagnosis: string | null;
  status: string;
  vital_signs?: VitalSigns | null;
  lab_results?: LabResult[] | null;
  xray_findings?: string | null;
  ecg_findings?: string | null;
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
