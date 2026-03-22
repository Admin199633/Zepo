/**
 * HTTP API DTOs — typed mirrors of backend response models.
 * Source of truth: backend/api/auth_router.py, clubs_router.py, tables_router.py
 */

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface RegisterBody {
  username: string;
  password: string;
  display_name: string;
}

export interface LoginBody {
  username: string;
  password: string;
}

export interface TokenResponse {
  token: string;
  user_id: string;
  expires_at: number;
  display_name: string;
}

// Legacy OTP types (used by simulation tests only)
export interface OtpRequestBody {
  phone_number: string;
}

export interface OtpVerifyBody {
  phone_number: string;
  code: string;
  display_name?: string;
}

// ---------------------------------------------------------------------------
// Clubs
// ---------------------------------------------------------------------------

export interface HouseRuleConfig {
  rule_id: string;
  params?: Record<string, unknown>;
}

export interface TableConfigInput {
  starting_stack?: number;
  small_blind?: number;
  big_blind?: number;
  turn_timer_seconds?: number;
  max_players?: number;
  house_rules?: HouseRuleConfig[];
}

export interface CreateClubBody {
  name: string;
  table_config?: TableConfigInput;
}

export interface CreateClubResponse {
  club_id: string;
  table_id: string;
  invite_code: string;
}

export interface ClubDTO {
  club_id: string;
  name: string;
  owner_id: string;
  invite_code: string;
  member_count: number;
}

export interface JoinClubBody {
  invite_code: string;
}

export interface JoinClubResponse {
  club_id: string;
  table_id: string;
}

// ---------------------------------------------------------------------------
// Tables
// ---------------------------------------------------------------------------

export interface TableConfigDTO {
  starting_stack: number;
  small_blind: number;
  big_blind: number;
  turn_timer_seconds: number;
  max_players: number;
  house_rules: string[];
}

export interface RecentHandDTO {
  hand_id: string;
  hand_number: number;
  pot_total: number;
  winner_ids: string[];
  phase_reached: string;
  timestamp: number;
}

export interface TableInfoDTO {
  table_id: string;
  config: TableConfigDTO;
  recent_hands: RecentHandDTO[];
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

export interface ApiErrorDetail {
  error: string;
  message: string;
}

export interface ApiErrorResponse {
  detail: ApiErrorDetail;
}
