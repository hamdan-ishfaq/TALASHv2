from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    phone = Column(String(50), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    personal_website = Column(String(500), nullable=True)
    other_urls = Column(Text, nullable=True)
    file_hash = Column(String(64), unique=True, index=True, nullable=True)
    file_path = Column(String(500), nullable=True)
    raw_text = Column(Text, nullable=True)
    raw_extraction_json = Column(Text, nullable=True)
    analysis_json = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    education_records = relationship("EducationRecord", back_populates="candidate", cascade="all, delete-orphan")
    work_experiences = relationship("WorkExperience", back_populates="candidate", cascade="all, delete-orphan")
    journal_publications = relationship("JournalPublication", back_populates="candidate", cascade="all, delete-orphan")
    conference_publications = relationship("ConferencePublication", back_populates="candidate", cascade="all, delete-orphan")
    supervision_records = relationship("SupervisionRecord", back_populates="candidate", cascade="all, delete-orphan")
    books = relationship("Book", back_populates="candidate", cascade="all, delete-orphan")
    patents = relationship("Patent", back_populates="candidate", cascade="all, delete-orphan")
    skills = relationship("Skill", back_populates="candidate", cascade="all, delete-orphan")
    extraction_runs = relationship("ExtractionRun", back_populates="candidate", cascade="all, delete-orphan")
    publication_authors = relationship("PublicationAuthor", back_populates="candidate", cascade="all, delete-orphan")
    education_gaps = relationship("EducationGap", back_populates="candidate", cascade="all, delete-orphan")
    employment_gaps = relationship("EmploymentGap", back_populates="candidate", cascade="all, delete-orphan")
    institution_rankings = relationship("InstitutionRanking", back_populates="candidate", cascade="all, delete-orphan")
    topic_clusters = relationship("TopicCluster", back_populates="candidate", cascade="all, delete-orphan")
    collaboration_edges = relationship("CollaborationEdge", back_populates="candidate", cascade="all, delete-orphan")
    assessments = relationship("CandidateAssessment", back_populates="candidate", cascade="all, delete-orphan")
    missing_information_requests = relationship("MissingInformationRequest", back_populates="candidate", cascade="all, delete-orphan")


class EducationRecord(Base):
    __tablename__ = "education_records"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)

    stage = Column(String(255), nullable=True)  # SSE, HSSC, UG, PG, PHD
    institution_type = Column(String(100), nullable=True)
    degree_title = Column(String(255), nullable=True)
    specialization = Column(String(255), nullable=True)
    institution = Column(String(255), nullable=True)
    board_or_university = Column(String(255), nullable=True)

    start_year = Column(Integer, nullable=True)
    start_month = Column(Integer, nullable=True)
    end_year = Column(Integer, nullable=True)
    end_month = Column(Integer, nullable=True)

    marks_percentage = Column(Float, nullable=True)
    cgpa = Column(Float, nullable=True)
    cgpa_scale = Column(Float, nullable=True)
    normalized_cgpa = Column(Float, nullable=True)

    institution_the_ranking = Column(Integer, nullable=True)
    institution_qs_ranking = Column(Integer, nullable=True)
    institution_ranking_source = Column(String(100), nullable=True)
    institution_ranking_year = Column(Integer, nullable=True)
    institution_ranking_value = Column(String(100), nullable=True)

    gap_before_start_months = Column(Integer, nullable=True)
    gap_justified_by_experience = Column(Boolean, default=False)
    evidence_text = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)

    candidate = relationship("Candidate", back_populates="education_records")


class WorkExperience(Base):
    __tablename__ = "work_experiences"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)

    job_title = Column(String(500), nullable=True)
    organization = Column(String(500), nullable=True)
    location = Column(String(255), nullable=True)
    employment_type = Column(String(100), nullable=True)

    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    start_month = Column(Integer, nullable=True)
    start_year = Column(Integer, nullable=True)
    end_month = Column(Integer, nullable=True)
    end_year = Column(Integer, nullable=True)
    is_current = Column(Boolean, nullable=False, default=False)

    is_academic_role = Column(Boolean, nullable=True)
    overlaps_with_education = Column(Boolean, nullable=True)
    job_responsibilities = Column(Text, nullable=True)
    evidence_text = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)

    candidate = relationship("Candidate", back_populates="work_experiences")


class JournalPublication(Base):
    __tablename__ = "journal_publications"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)

    title = Column(String(1000), nullable=False)
    authors = Column(Text, nullable=True)
    journal_name = Column(String(500), nullable=True)
    issn = Column(String(50), nullable=True)
    doi = Column(String(255), nullable=True)
    year = Column(Integer, nullable=True)
    volume = Column(String(100), nullable=True)
    issue = Column(String(100), nullable=True)
    pages = Column(String(100), nullable=True)

    wos_indexed = Column(Boolean, default=False, nullable=True)
    scopus_indexed = Column(Boolean, default=False, nullable=True)
    quartile = Column(String(50), nullable=True)
    impact_factor = Column(Float, nullable=True)

    authorship_role = Column(String(100), nullable=True)  # First Author, Corresponding Author, etc.
    author_position = Column(Integer, nullable=True)

    topic_category = Column(String(255), nullable=True)
    is_with_student = Column(Boolean, default=False, nullable=True)
    abstract_or_summary = Column(Text, nullable=True)
    keywords_json = Column(Text, nullable=True)
    author_affiliations_json = Column(Text, nullable=True)
    source_verification_url = Column(String(1000), nullable=True)
    confidence_score = Column(Float, nullable=True)

    candidate = relationship("Candidate", back_populates="journal_publications")


class ConferencePublication(Base):
    __tablename__ = "conference_publications"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)

    title = Column(String(1000), nullable=False)
    authors = Column(Text, nullable=True)
    conference_name = Column(String(500), nullable=True)
    year = Column(Integer, nullable=True)
    conference_series = Column(String(255), nullable=True)
    conference_location = Column(String(255), nullable=True)
    publisher = Column(String(255), nullable=True)
    doi = Column(String(255), nullable=True)

    is_a_star = Column(Boolean, default=False, nullable=True)
    core_ranking = Column(String(50), nullable=True)

    indexed_in = Column(String(255), nullable=True)  # Scopus, IEEE, ACM, Springer

    authorship_role = Column(String(100), nullable=True)
    author_position = Column(Integer, nullable=True)

    topic_category = Column(String(255), nullable=True)
    is_with_student = Column(Boolean, default=False, nullable=True)
    abstract_or_summary = Column(Text, nullable=True)
    keywords_json = Column(Text, nullable=True)
    author_affiliations_json = Column(Text, nullable=True)
    source_verification_url = Column(String(1000), nullable=True)
    confidence_score = Column(Float, nullable=True)

    candidate = relationship("Candidate", back_populates="conference_publications")


class SupervisionRecord(Base):
    __tablename__ = "supervision_records"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)

    student_level = Column(String(100), nullable=True)  # MS, PhD
    student_name = Column(String(255), nullable=True)
    completion_year = Column(Integer, nullable=True)

    supervision_role = Column(String(100), nullable=True)  # Main Supervisor, Co-Supervisor
    publications_with_student = Column(Integer, default=0, nullable=True)
    thesis_title = Column(Text, nullable=True)
    evidence_text = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)

    candidate = relationship("Candidate", back_populates="supervision_records")


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)

    title = Column(String(1000), nullable=False)
    authors = Column(Text, nullable=True)
    isbn = Column(String(100), nullable=True)
    publisher = Column(String(255), nullable=True)
    year = Column(Integer, nullable=True)
    online_link = Column(String(1000), nullable=True)

    authorship_role = Column(String(100), nullable=True)  # Sole Author, Lead Author, Co-Author
    evidence_text = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)

    candidate = relationship("Candidate", back_populates="books")


class Patent(Base):
    __tablename__ = "patents"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)

    patent_no = Column(String(255), nullable=True)
    title = Column(String(1000), nullable=False)
    inventors = Column(Text, nullable=True)
    date_filed = Column(Date, nullable=True)
    date_granted = Column(Date, nullable=True)
    country_of_filing = Column(String(255), nullable=True)
    online_link = Column(String(1000), nullable=True)

    inventor_role = Column(String(100), nullable=True)  # Lead Inventor, Co-Inventor
    status = Column(String(100), nullable=True)
    evidence_text = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)

    candidate = relationship("Candidate", back_populates="patents")


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)

    name = Column(String(500), nullable=False)
    category = Column(String(255), nullable=True)
    proficiency_level = Column(String(100), nullable=True)
    years_of_experience = Column(Integer, nullable=True)
    evidenced_in_work = Column(Boolean, default=False, nullable=True)
    evidenced_in_research = Column(Boolean, default=False, nullable=True)
    work_evidence = Column(Text, nullable=True)
    research_evidence = Column(Text, nullable=True)
    strength_of_evidence = Column(String(100), nullable=True)  # Strongly, Partially, Weakly Evidenced
    confidence_score = Column(Float, nullable=True)

    candidate = relationship("Candidate", back_populates="skills")


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    model_name = Column(String(255), nullable=False)
    prompt_version = Column(String(100), nullable=True)
    run_type = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default="started")
    raw_response_json = Column(Text, nullable=True)
    parsed_ok = Column(Boolean, default=False, nullable=False)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    candidate = relationship("Candidate", back_populates="extraction_runs")


class PublicationAuthor(Base):
    __tablename__ = "publication_authors"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    publication_type = Column(String(50), nullable=False)  # journal / conference
    publication_id = Column(Integer, nullable=False)
    author_order = Column(Integer, nullable=True)
    author_name = Column(String(255), nullable=False)
    is_candidate = Column(Boolean, default=False, nullable=False)
    is_corresponding = Column(Boolean, default=False, nullable=False)
    affiliation = Column(String(255), nullable=True)
    normalized_author_key = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="publication_authors")


class EducationGap(Base):
    __tablename__ = "education_gaps"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    from_stage = Column(String(100), nullable=True)
    to_stage = Column(String(100), nullable=True)
    gap_months = Column(Integer, nullable=True)
    gap_start = Column(Date, nullable=True)
    gap_end = Column(Date, nullable=True)
    justified_by_work = Column(Boolean, default=False, nullable=False)
    justification_text = Column(Text, nullable=True)
    evidence_work_experience_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="education_gaps")


class EmploymentGap(Base):
    __tablename__ = "employment_gaps"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    gap_type = Column(String(100), nullable=True)
    gap_start = Column(Date, nullable=True)
    gap_end = Column(Date, nullable=True)
    gap_months = Column(Integer, nullable=True)
    justified = Column(Boolean, default=False, nullable=False)
    justification_text = Column(Text, nullable=True)
    related_education_id = Column(Integer, nullable=True)
    related_career_break_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="employment_gaps")


class InstitutionRanking(Base):
    __tablename__ = "institution_rankings"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    institution_name = Column(String(255), nullable=False)
    institution_type = Column(String(100), nullable=True)
    source = Column(String(50), nullable=False)  # THE or QS
    source_year = Column(Integer, nullable=True)
    rank_value = Column(String(100), nullable=True)
    rank_band = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    url = Column(String(1000), nullable=True)
    verified_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="institution_rankings")


class TopicCluster(Base):
    __tablename__ = "topic_clusters"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    publication_type = Column(String(50), nullable=False)
    publication_id = Column(Integer, nullable=False)
    cluster_name = Column(String(255), nullable=False)
    cluster_score = Column(Float, nullable=True)
    assigned_by = Column(String(100), nullable=True)
    model_version = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="topic_clusters")


class CollaborationEdge(Base):
    __tablename__ = "collaboration_edges"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    coauthor_name = Column(String(255), nullable=False)
    coauthor_affiliation = Column(String(255), nullable=True)
    publication_id = Column(Integer, nullable=False)
    publication_type = Column(String(50), nullable=False)
    edge_weight = Column(Float, nullable=True)
    is_recurring = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="collaboration_edges")


class CandidateAssessment(Base):
    __tablename__ = "candidate_assessments"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    assessment_version = Column(String(100), nullable=True)
    education_strength_score = Column(Float, nullable=True)
    research_strength_score = Column(Float, nullable=True)
    experience_strength_score = Column(Float, nullable=True)
    skill_alignment_score = Column(Float, nullable=True)
    overall_rank = Column(Float, nullable=True)
    overall_summary = Column(Text, nullable=True)
    missing_sections_json = Column(Text, nullable=True)
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="assessments")


class MissingInformationRequest(Base):
    __tablename__ = "missing_information_requests"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    module_name = Column(String(100), nullable=False)
    missing_fields_json = Column(Text, nullable=True)
    draft_email_subject = Column(String(255), nullable=True)
    draft_email_body = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="draft")
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)

    candidate = relationship("Candidate", back_populates="missing_information_requests")
