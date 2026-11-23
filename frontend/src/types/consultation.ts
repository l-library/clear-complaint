export interface CorrectionReport {
  original: string
  corrected: string
  risks: string[]
  metrics: { label: string; before: number; after: number }[]
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export type WorkspaceTab = 'chat' | 'archive' | 'plans'
export type ConversationType = 'consultation' | 'follow_up'

export interface PatientProfile {
  id: string
  name: string
  age: number
  description: string
}

export interface Conversation {
  id: string
  patientId: string
  type: ConversationType
  title: string
  healthEpisodeId?: string
  followUpPlanId?: string
  status: 'active' | 'completed'
  messages: ChatMessage[]
  draft: string
  createdAt: string
  updatedAt: string
  archivedRecordId?: string
  archivedMessageCount?: number
}

export interface HealthEpisode {
  id: string
  patientId: string
  title: string
  startedAt: string
  status: 'ongoing' | 'resolved'
}

export type RecordSource = 'ai_consultation' | 'medical_document' | 'ai_follow_up'

export interface HealthRecord {
  id: string
  patientId: string
  healthEpisodeId: string
  conversationId?: string
  source: RecordSource
  title: string
  date: string
  summary: string
  confirmation: 'pending' | 'confirmed'
  dataSource: 'demo' | 'local'
  institution?: string
  department?: string
  documentedDiagnosis?: string
  medicalInstructions?: string
  sourceFileName?: string
}

export interface FollowUpPlan {
  id: string
  type: 'follow_up'
  patientId: string
  healthEpisodeId: string
  sourceRecordId?: string
  title: string
  scheduledAt: string
  goal: string
  questions: string[]
  status: 'scheduled' | 'in_progress' | 'completed' | 'paused' | 'cancelled'
  conversationId?: string
}

export interface MedicationPlan {
  id: string
  type: 'medication'
  patientId: string
  healthEpisodeId: string
  sourceRecordId?: string
  title: string
  medicineName: string
  instructions: string
  reminderTimes: string[]
  startDate: string
  endDate: string
  sourceLabel: string
  sourceConfirmed: boolean
  status: 'active' | 'paused' | 'ended'
}

export type HealthPlan = FollowUpPlan | MedicationPlan

export interface MedicationCheckIn {
  id: string
  planId: string
  date: string
  time: string
  outcome: 'taken' | 'skipped'
  recordedAt: string
}

export interface MedicalRecordInput {
  healthEpisodeId: string
  episodeTitle?: string
  title: string
  date: string
  institution: string
  department: string
  documentedDiagnosis: string
  medicalInstructions: string
  summary: string
  sourceFileName?: string
}

export interface FollowUpPlanInput {
  healthEpisodeId: string
  sourceRecordId?: string
  title: string
  scheduledAt: string
  goal: string
  questions: string[]
}

export interface MedicationPlanInput {
  healthEpisodeId: string
  sourceRecordId?: string
  medicineName: string
  instructions: string
  reminderTimes: string[]
  startDate: string
  endDate: string
  sourceLabel: string
  sourceConfirmed: boolean
}

export interface ArchiveRecord {
  id: string
  title: string
  date: string
  summary: string
  complaint: string
  status: string
  messages?: ChatMessage[]
  correction?: CorrectionReport
}
