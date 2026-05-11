export interface DashCandidate {
  candidate_id: number;
  name?: string;
  email?: string;
  status?: string;
  analysis_healthy?: boolean | null;
  education_score?: number;
  experience_score?: number;
  research_score?: number;
  skill_score?: number;
  jd_alignment_score?: number;
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
  id?: number;
  education_score?: number;
  experience_score?: number;
  research_score?: number;
  skill_score?: number;
  jd_alignment_score?: number;
  overall_rank?: number;
  summary?: string;
}

export interface PipelineMetrics {
  research_audit?: {
    grade?: string;
    enrichment_audit?: { warnings?: string[]; errors?: string[]; skipped?: boolean };
    warnings_head?: string[];
  };
  topic_variability?: {
    theme_counts?: Record<string, number>;
    dominant_theme?: string | null;
    dominant_share_pct?: number;
    diversity_score?: number;
    publication_count?: number;
    source?: string;
    topic_trend_by_year?: { year: number | null; year_label?: string; dominant_theme: string; publication_count: number }[];
    topic_stability_note?: string;
  };
  collaboration?: {
    unique_coauthors?: number;
    recurring_collaborators?: number;
    avg_coauthors_per_paper?: number;
    top_collaborators?: { name: string; shared_papers: number }[];
    affiliations_populated?: number;
    inferred_region_diversity?: number;
    international_collaboration_hint?: string;
  };
  ip_format_checks?: {
    books_checked?: number;
    books_with_valid_isbn?: number;
    patents_checked?: number;
    patents_with_plausible_number?: number;
  };
  skill_alignment?: {
    evidence_score?: number;
    jd_score?: number | null;
    jd_skills_matched?: number;
    jd_publication_hits?: number;
  };
  verification_links?: {
    books?: { id: number; open_library_json?: string | null; google_books_search?: string | null }[];
    patents?: { id: number; google_patents_search?: string | null }[];
  };
  missing_info_modules?: string[];
  summary?: {
    overall_rank?: number;
    skill_score?: number;
    executive_summary?: string;
  };
}

export interface GapRecord {
  from_stage?: string | null;
  to_stage?: string | null;
  gap_months?: number | null;
  justified?: boolean | null;
  justification?: string | null;
  gap_type?: string | null;
  gap_start?: string | null;
  gap_end?: string | null;
}

export interface CandidateDetail {
  id: number;
  name?: string;
  email?: string;
  phone?: string;
  linkedin_url?: string;
  status?: string;
  summary?: string;
  target_job_description?: string | null;
  analysis_health?: {
    healthy: boolean;
    pipeline_error?: string | null;
    detail?: string;
  };
  education_gaps?: GapRecord[];
  employment_gaps?: GapRecord[];
  education_records: any[];
  work_experiences: any[];
  journal_publications: any[];
  conference_publications: any[];
  supervision_records: any[];
  skills: any[];
  books: any[];
  patents: any[];
  assessments: CandidateAssessment[];
  pipeline_metrics?: PipelineMetrics;
}

export interface UploadQueueItem {
  name: string;
  status: 'queued' | 'processing' | 'done' | 'failed';
  progress: number;
  cid?: number;
}
