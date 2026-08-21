export type UserRole = 'guardian' | 'care_provider' | 'center' | 'admin'

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  provider_specialty?: string | null
  verification_status: 'verified' | 'unverified' | 'rejected'
  auth_provider: string
  created_at: string
}

export interface AuthResponse {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  user: User
}

export interface ChildProfile {
  id: string
  first_name: string
  preferred_name?: string | null
  birth_date?: string | null
  gender?: string | null
  conditions: string[]
  needs: string[]
  support_requirements: string[]
  services: string[]
  summary?: string | null
  guardian_type?: 'primary' | 'secondary' | null
  access_role: 'guardian' | 'care_provider'
  access_permissions: string[]
  created_at: string
  updated_at: string
}

export interface ChildInput {
  first_name: string
  preferred_name?: string
  birth_date?: string
  gender?: string
  conditions: string[]
  needs: string[]
  support_requirements: string[]
  services: string[]
  summary?: string
}

export interface CareInvitation {
  id: string
  child_id: string
  child_name: string
  email: string
  target_role: 'guardian' | 'care_provider'
  role_label?: string | null
  permissions: string[]
  status: string
  access_expires_at?: string | null
  invitation_expires_at: string
  created_at: string
}

export interface CareTeamMember {
  membership_id: string
  membership_kind: 'guardian' | 'care_provider'
  user_id: string
  full_name: string
  email: string
  account_role: string
  role_label?: string | null
  verification_status: string
  guardian_type?: 'primary' | 'secondary' | null
  permissions: string[]
  access_status: 'active' | 'revoked'
  expires_at?: string | null
  is_primary_guardian: boolean
}

export interface CareTeamOverview {
  child_id: string
  members: CareTeamMember[]
  pending_invitations: CareInvitation[]
}

export type ReportVisibility = 'care_team' | 'restricted'

export interface ReportVersion {
  id: string
  version_number: number
  original_filename: string
  content_type: string
  size_bytes: number
  sha256: string
  notes?: string | null
  uploaded_by_user_id: string
  uploaded_by_name: string
  created_at: string
}

export interface ChildReport {
  id: string
  child_id: string
  title: string
  report_type: string
  report_date?: string | null
  source_label?: string | null
  visibility: ReportVisibility
  allowed_user_ids: string[]
  created_by_user_id: string
  created_by_name: string
  is_archived: boolean
  created_at: string
  updated_at: string
  versions: ReportVersion[]
}

export interface ReportAIResult {
  summary: string
  key_findings: string[]
  needs: string[]
  recommendations: string[]
  follow_up_actions: string[]
  goal_mentions: string[]
  source_language: string
  evidence: string[]
  limitations: string[]
  safety_note: string
}

export interface ReportAIAnalysis {
  id: string
  child_id: string
  report_id: string
  report_version_id: string
  report_version_number: number
  provider: string
  model: string
  analysis_status: 'completed' | 'failed'
  review_status: 'draft' | 'approved' | 'rejected'
  result: ReportAIResult
  error_message?: string | null
  created_by_user_id: string
  created_by_name: string
  reviewed_by_user_id?: string | null
  reviewed_by_name?: string | null
  reviewed_at?: string | null
  created_at: string
  updated_at: string
}

export interface VoiceNote {
  id: string
  child_id: string
  title: string
  original_filename: string
  content_type: string
  size_bytes: number
  duration_seconds?: number | null
  transcription_status: 'not_started' | 'completed' | 'failed'
  review_status: 'not_started' | 'draft' | 'approved' | 'rejected'
  transcript_draft?: string | null
  transcript_final?: string | null
  transcript_language?: string | null
  stt_provider?: string | null
  stt_model?: string | null
  error_message?: string | null
  created_by_user_id: string
  created_by_name: string
  reviewed_by_user_id?: string | null
  reviewed_by_name?: string | null
  reviewed_at?: string | null
  created_at: string
  updated_at: string
}

export type GoalStatus = 'new' | 'in_progress' | 'completed' | 'paused'

export interface GoalUpdate {
  id: string
  actor_user_id: string
  actor_name: string
  note?: string | null
  progress_percent: number
  status: GoalStatus
  created_at: string
}

export interface ChildGoal {
  id: string
  child_id: string
  title: string
  description?: string | null
  category?: string | null
  status: GoalStatus
  progress_percent: number
  start_date?: string | null
  target_date?: string | null
  assigned_to_user_id?: string | null
  assigned_to_name?: string | null
  created_by_user_id: string
  created_by_name: string
  created_at: string
  updated_at: string
  updates: GoalUpdate[]
}

export type FollowUpDisplayStatus = 'upcoming' | 'today' | 'overdue' | 'completed'

export interface FollowUpItem {
  id: string
  child_id: string
  title: string
  note?: string | null
  due_date?: string | null
  status: 'open' | 'completed'
  display_status: FollowUpDisplayStatus
  source_type: 'manual' | 'report_ai' | string
  source_id?: string | null
  source_label?: string | null
  created_by_user_id: string
  created_by_name: string
  completed_by_user_id?: string | null
  completed_by_name?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
}

export interface FollowUpSuggestion {
  analysis_id: string
  report_id: string
  report_title: string
  action_index: number
  action_text: string
  extracted_due_date?: string | null
  already_added: boolean
}

export interface NotificationItem {
  event_key: string
  notification_type: 'invitation' | 'report' | 'goal' | 'message' | 'follow_up' | string
  title: string
  body: string
  child_id?: string | null
  entity_type?: string | null
  entity_id?: string | null
  occurred_at: string
  is_read: boolean
  url: string
}

export type TimelineEventType = 'profile' | 'team' | 'report' | 'goal' | 'follow_up'

export interface TimelineEvent {
  id: string
  event_type: TimelineEventType
  title: string
  description?: string | null
  actor_user_id?: string | null
  actor_name?: string | null
  occurred_at: string
  data: Record<string, unknown>
}

export interface ConversationParticipant {
  user_id: string
  full_name: string
  role_label?: string | null
}

export interface ChatMessage {
  id: string
  conversation_id: string
  sender_user_id: string
  sender_name: string
  body: string
  created_at: string
}

export interface CareConversation {
  id: string
  child_id: string
  kind: 'direct' | 'group'
  title: string
  participants: ConversationParticipant[]
  last_message?: ChatMessage | null
  created_at: string
  updated_at: string
}

export interface AssistantSource {
  index: number
  source_type: 'profile' | 'report' | 'goal' | 'goal_update' | 'voice' | string
  source_id: string
  title: string
  snippet: string
  occurred_at?: string | null
}

export interface AssistantMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources: AssistantSource[]
  created_at: string
}

export interface AssistantThread {
  id: string
  child_id: string
  title: string
  created_at: string
  updated_at: string
  last_message?: AssistantMessage | null
}

export interface AssistantAnswer {
  thread: AssistantThread
  user_message: AssistantMessage
  assistant_message: AssistantMessage
}
