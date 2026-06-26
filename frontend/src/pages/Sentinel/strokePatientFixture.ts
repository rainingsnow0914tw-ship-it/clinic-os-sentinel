/**
 * 中風老人 demo fixture
 * 對應 backend/tests/fixtures/stroke_patient.py
 *
 * 71 歲澳門男性,2 年前缺血性中風,慢性病:高血壓 + 第二型糖尿病 + 心房顫動。
 * 長期服 warfarin(抗凝血)+ amlodipine(降壓)+ metformin(降糖)+ 銀杏(成分不明)。
 */
import type {
  HeartFlag,
  HeartProblem,
  HeartMedication,
  IntakeRequest,
  TriageRequest,
  AuditRequest,
  EducationRequest,
} from "@/lib/sentinelApi";

export const STROKE_FLAGS: HeartFlag[] = [
  {
    type: "major_history",
    content: "2024 年缺血性中風(左側 MCA),後遺左側肢體輕度無力",
    severity: "red",
    source: "verified",
  },
  {
    type: "allergy",
    content: "磺胺類藥物過敏(疹+喉嚨腫)",
    severity: "red",
    source: "verified",
  },
  {
    type: "interaction_note",
    content: "長期 follow up 配合度良好,獨居",
    severity: "info",
    source: "self_report",
  },
];

export const STROKE_PROBLEMS: HeartProblem[] = [
  {
    name: "原發性高血壓",
    diagnosed_at: "2018-03-15",
    control_status: "controlled",
    medications: ["amlodipine 5mg"],
  },
  {
    name: "第二型糖尿病",
    diagnosed_at: "2020-09-01",
    control_status: "unstable",
    medications: ["metformin 500mg bid"],
  },
  {
    name: "心房顫動(永久性)",
    diagnosed_at: "2023-11-20",
    control_status: "controlled",
    medications: ["warfarin 3mg"],
  },
];

export const STROKE_MEDICATIONS: HeartMedication[] = [
  { name: "warfarin 3mg", category: "chronic_disease_med", composition_certain: true, for_problem: "心房顫動" },
  { name: "amlodipine 5mg", category: "chronic_disease_med", composition_certain: true, for_problem: "高血壓" },
  { name: "metformin 500mg", category: "chronic_disease_med", composition_certain: true, for_problem: "糖尿病" },
  { name: "銀杏(某品牌複方)", category: "supplement", composition_certain: false, for_problem: null },
];

export const INTAKE_SAMPLE: IntakeRequest = {
  raw_dictation:
    "病人 71 歲男性,主訴最近一兩週特別疲倦,沒什麼力氣。" +
    "晚上睡覺有時會被自己抽動驚醒,左手最近拿筷子比較不穩。" +
    "他說可能是天氣熱關係。順便問為什麼吃 3B 丸後便祕? " +
    "今早血壓 145 / 88。",
  chief_complaint_hint: "疲倦、左手無力",
};

export const TRIAGE_SAMPLE: TriageRequest = {
  working_hypothesis: "高血壓追蹤 + 老年人疲倦感",
  flags: STROKE_FLAGS,
  problems: STROKE_PROBLEMS,
  medications: STROKE_MEDICATIONS,
};

export const AUDIT_SAMPLE: AuditRequest = {
  new_prescription: ["ibuprofen 400mg"],
  flags: STROKE_FLAGS,
  long_term_medications: STROKE_MEDICATIONS,
  problems: STROKE_PROBLEMS,
};

export const EDUCATION_SAMPLE: EducationRequest = {
  diagnosis: "高血壓 + 第二型糖尿病 + 心房顫動 + 中風後遺長期管理",
  patient_habits: {
    diet: "愛吃煎炸食物、口味重",
    exercise: "幾乎不運動,獨居",
    sleep: "近期睡眠淺,常被抽動驚醒",
  },
  patient_name_hint: "陳先生",
};
