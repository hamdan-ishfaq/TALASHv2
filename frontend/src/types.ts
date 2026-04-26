export interface DashCandidate {
  candidate_id: number;
  name?: string;
  email?: string;
  status?: string;
  education_score?: number;
  experience_score?: number;
  research_score?: number;
  skill_score?: number;
  overall_rank?: number;
  summary?: string;
  education_count: number;
  experience_count: number;
  journal_count: number;
  conference_count: number;
  skill_count: number;
  supervision_count: number;
  missing_info_count: number;
}

export interface MissingReq {
  id: number;
  module_name: string;
  missing_fields: string[];
  draft_email_subject?: string;
  draft_email_body?: string;
  status: string;
  generated_at?: string;
}

export interface CandidateAssessment {
  education_score?: number;
  experience_score?: number;
  research_score?: number;
  skill_score?: number;
  overall_rank?: number;
  summary?: string;
}

export interface CandidateDetail {
  id: number;
  name?: string;
  email?: string;
  phone?: string;
  linkedin_url?: string;
  status?: string;
  summary?: string;
  education_records: any[];
  work_experiences: any[];
  journal_publications: any[];
  conference_publications: any[];
  supervision_records: any[];
  skills: any[];
  books: any[];
  patents: any[];
  assessments: CandidateAssessment[];
}

export interface UploadQueueItem {
  name: string;
  status: 'queued' | 'processing' | 'done' | 'failed';
  progress: number;
  cid?: number;
}
