from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import date


class EducationalStage(str, Enum):
    SSE = "SSE"
    HSSC = "HSSC"
    UG = "UG"
    PG = "PG"
    PHD = "PhD"
    OTHER = "Other"


class InstitutionType(str, Enum):
    """Distinguishes between School Boards and Universities"""
    SCHOOL_BOARD = "School Board"
    UNIVERSITY = "University"
    COLLEGE = "College"
    TECHNICAL_INSTITUTE = "Technical Institute"
    OTHER = "Other"


class AuthorshipRole(str, Enum):
    FIRST_AUTHOR = "First Author"
    CORRESPONDING_AUTHOR = "Corresponding Author"
    FIRST_AND_CORRESPONDING = "Both First and Corresponding Author"
    CO_AUTHOR = "Other Co-Author"


class QuartileRanking(str, Enum):
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"
    UNKNOWN = "Unknown"


class SupervisionRole(str, Enum):
    MAIN_SUPERVISOR = "Main Supervisor"
    CO_SUPERVISOR = "Co-Supervisor"


class BookAuthorshipRole(str, Enum):
    SOLE_AUTHOR = "Sole Author"
    LEAD_AUTHOR = "Lead Author"
    CO_AUTHOR = "Co-Author"
    CONTRIBUTING_AUTHOR = "Contributing Author"


class InventorRole(str, Enum):
    LEAD_INVENTOR = "Lead Inventor"
    CO_INVENTOR = "Co-Inventor"
    CONTRIBUTING_INNOVATOR = "Contributing Innovator"


class EvidenceStrength(str, Enum):
    STRONGLY_EVIDENCED = "Strongly Evidenced"
    PARTIALLY_EVIDENCED = "Partially Evidenced"
    WEAKLY_EVIDENCED = "Weakly Evidenced"
    UNSUPPORTED = "Unsupported"


class ConferenceRanking(str, Enum):
    A_STAR = "A*"
    A = "A"
    B = "B"
    C = "C"
    UNRANKED = "Unranked"


class EducationRecordExtraction(BaseModel):
    stage: EducationalStage = Field(..., description="The stage of education, such as SSE (matriculation), HSSC (intermediate), UG (undergraduate), PG (postgraduate), or PhD.")
    degree_title: Optional[str] = Field(None, description="Exact title of the degree, e.g., 'BS Computer Science', 'MPhil Mathematics', 'Bachelor of Science'.")
    specialization: Optional[str] = Field(None, description="The specialization or major subject of the degree, e.g., 'Computer Science', 'Electrical Engineering'.")
    institution: Optional[str] = Field(None, description="The exact name of the university, college, or board as it appears on the CV.")
    institution_type: Optional[InstitutionType] = Field(None, description="Classify the institution type: School Board (for SSE/HSSC), University, College, or Technical Institute. This field is crucial for QS/THE ranking verification later.")
    start_year: Optional[int] = Field(None, description="Year the education started (admission year). Extract as integer.")
    start_month: Optional[int] = Field(None, description="Month the education started (1-12) if mentioned alongside the year.")
    end_year: Optional[int] = Field(None, description="Year the education completed (graduation/completion year). Extract as integer.")
    end_month: Optional[int] = Field(None, description="Month the education completed (1-12) if mentioned.")
    marks_percentage: Optional[float] = Field(None, description="Percentage of marks obtained, usually for early stages like SSE/HSSC (0-100 scale).")
    cgpa: Optional[float] = Field(None, description="CGPA obtained if reported. Example: 3.8")
    cgpa_scale: Optional[float] = Field(None, description="Total possible CGPA scale, e.g., 4.0 or 5.0. If not mentioned, infer from context.")
    gap_before_start_months: Optional[int] = Field(None, description="Calculate any gap in months between the last completed education stage and the start of this one. Return 0 if no gap or consecutive.")
    gap_justified_by_experience: Optional[bool] = Field(False, description="Set to true if there is overlapping work or equivalent productive activity (e.g., employment, freelancing) for the calculated gap duration.")
    evidence_text: Optional[str] = Field(None, description="Verbatim CV text that supports this education record.")
    confidence_score: Optional[float] = Field(None, description="Model confidence for this extracted record, 0.0 to 1.0.")


class JournalPublicationExtraction(BaseModel):
    title: str = Field(..., description="Complete title of the journal publication.")
    authors: Optional[str] = Field(None, description="Comma-separated list of ALL authors exactly as they appear on the paper, in order. This is crucial for co-author network analysis.")
    journal_name: Optional[str] = Field(None, description="The complete and exact name of the journal (e.g., 'IEEE Transactions on Pattern Analysis and Machine Intelligence').")
    issn: Optional[str] = Field(None, description="The ISSN (International Standard Serial Number) of the journal if provided on the CV.")
    doi: Optional[str] = Field(None, description="The Digital Object Identifier (DOI) if provided. Usually in format like '10.1234/example'.")
    year: Optional[int] = Field(None, description="Year of publication. Extract as integer.")
    volume: Optional[str] = Field(None, description="Volume number of the journal issue if mentioned.")
    issue: Optional[str] = Field(None, description="Issue number of the journal if mentioned.")
    pages: Optional[str] = Field(None, description="Page range or article number if mentioned.")
    wos_indexed: Optional[bool] = Field(False, description="Determine if the journal is Web of Science (WoS) indexed. Check if explicitly mentioned or if the journal name is recognizable as WoS-indexed.")
    scopus_indexed: Optional[bool] = Field(False, description="Determine if the journal is Scopus indexed. Check if explicitly mentioned or recognizable.")
    quartile: Optional[QuartileRanking] = Field(QuartileRanking.UNKNOWN, description="Quartile ranking of the journal (Q1=top tier, Q2, Q3, Q4, or Unknown if not mentioned). This is crucial for research ranking.")
    impact_factor: Optional[float] = Field(None, description="Impact Factor of the journal if explicitly reported.")
    authorship_role: Optional[AuthorshipRole] = Field(None, description="The role of the candidate among the authors: Check if they are First, Corresponding, Both, or Other Co-Author.")
    author_position: Optional[int] = Field(None, description="The 1-based position of the candidate in the author list. e.g., 1 if first author, 2 if second, etc.")
    topic_category: Optional[str] = Field(None, description="Categorize the main topic or research domain of this publication (e.g., 'Machine Learning', 'Computer Vision', 'NLP').")
    is_with_student: Optional[bool] = Field(False, description="Set to true if any co-authors appear to be students the candidate is or was supervising based on explicit markers in the CV.")
    abstract_or_summary: Optional[str] = Field(None, description="Extract if a brief summary, abstract, or key findings are provided for the paper. CRITICAL for Section 3.6 topic variability cluster analysis.")
    keywords: List[str] = Field(default_factory=list, description="Extract any keywords, tags, or research domains explicitly listed under the publication. Essential for topical analysis.")
    author_affiliations: List[str] = Field(default_factory=list, description="Extract universities, institutions, or countries of co-authors if mentioned (e.g., ['MIT', 'Stanford University', 'Germany']. CRITICAL for Section 3.7 collaboration analysis (internal/external/national/international).")
    source_verification_url: Optional[str] = Field(None, description="External verification URL for the journal paper, if available.")
    confidence_score: Optional[float] = Field(None, description="Model confidence for this extracted record, 0.0 to 1.0.")


class ConferencePublicationExtraction(BaseModel):
    title: str = Field(..., description="Complete title of the conference paper.")
    authors: Optional[str] = Field(None, description="Comma-separated list of ALL authors in order, exactly as they appear on the paper. This is crucial for co-author network analysis.")
    conference_name: Optional[str] = Field(None, description="The complete and exact name of the conference (e.g., 'IEEE/CVF Conference on Computer Vision and Pattern Recognition').")
    year: Optional[int] = Field(None, description="Year the paper was published or presented.")
    conference_series: Optional[str] = Field(None, description="The numerical series or edition of the conference, e.g., '28th', '2023rd', if mentioned.")
    conference_location: Optional[str] = Field(None, description="Geographic location where the conference was held (if mentioned).")
    core_ranking: Optional[ConferenceRanking] = Field(ConferenceRanking.UNRANKED, description="The CORE ranking of the conference: A* (top tier), A (excellent), B (good), C (acceptable), or Unranked. This is crucial for research ranking.")
    indexed_in: Optional[str] = Field(None, description="Where the proceedings are indexed (e.g., 'Scopus', 'IEEE Xplore', 'ACM Digital Library', 'Springer', 'others').")
    doi: Optional[str] = Field(None, description="The DOI of the conference paper if provided.")
    authorship_role: Optional[AuthorshipRole] = Field(None, description="The candidate's authorship role among the authors: First, Corresponding, Both, or Other Co-Author.")
    author_position: Optional[int] = Field(None, description="1-based position of the candidate in the author list.")
    topic_category: Optional[str] = Field(None, description="Main topic or research domain of the paper (e.g., 'Computer Vision', 'NLP', 'Robotics').")
    is_with_student: Optional[bool] = Field(False, description="Set to true if any co-authors are explicitly noted as students the candidate supervised.")
    abstract_or_summary: Optional[str] = Field(None, description="Extract if a brief summary, abstract, or key findings are provided for the paper. CRITICAL for Section 3.6 topic variability cluster analysis.")
    keywords: List[str] = Field(default_factory=list, description="Extract any keywords, tags, or research domains explicitly listed under the publication. Essential for topical analysis.")
    publisher: Optional[str] = Field(None, description="Publisher of the conference proceedings if stated in the citation (e.g., 'IEEE', 'ACM', 'Springer', 'Elsevier'). CRITICAL for Section 3.2.ii verification that proceedings are published in recognized platforms.")
    author_affiliations: List[str] = Field(default_factory=list, description="Extract universities, institutions, or countries of co-authors if mentioned (e.g., ['MIT', 'Stanford University', 'Germany']. CRITICAL for Section 3.7 collaboration analysis (internal/external/national/international).")
    source_verification_url: Optional[str] = Field(None, description="External verification URL for the conference paper, if available.")
    confidence_score: Optional[float] = Field(None, description="Model confidence for this extracted record, 0.0 to 1.0.")


class SupervisionRecordExtraction(BaseModel):
    student_name: Optional[str] = Field(None, description="The full name of the supervised student, exactly as mentioned in the CV.")
    student_level: Optional[str] = Field(None, description="The degree level of the supervised student: 'MS' (Master's), 'MPhil', 'PhD', or other advanced degree designation.")
    completion_year: Optional[int] = Field(None, description="The year the student graduated, completed their thesis, or finished their research (as integer).")
    supervision_role: Optional[SupervisionRole] = Field(None, description="Did the candidate serve as the Main Supervisor, Co-Supervisor, or another supervisory role?")
    thesis_title: Optional[str] = Field(None, description="Title of the student's thesis or research project if mentioned on the CV.")
    publications_with_student: Optional[int] = Field(0, description="Count of publications in the candidate's publication list that are co-authored with this specific student.")
    evidence_text: Optional[str] = Field(None, description="Verbatim CV text that supports this supervision record.")
    confidence_score: Optional[float] = Field(None, description="Model confidence for this extracted record, 0.0 to 1.0.")


class CareerBreak(BaseModel):
    reason: str = Field(..., description="The stated reason for the break (e.g., 'Sabbatical', 'Maternity Leave', 'Paternity Leave', 'Medical Leave', 'Family/Personal Leave', 'Research Break').")
    start_year: Optional[int] = Field(None, description="Year the career break began.")
    end_year: Optional[int] = Field(None, description="Year the career break ended or is expected to end.")


class BookExtraction(BaseModel):
    title: str = Field(..., description="Complete title of the book as listed on the CV.")
    authors: Optional[str] = Field(None, description="Complete list of all authors in order, exactly as they appear. Crucial for co-authorship analysis.")
    isbn: Optional[str] = Field(None, description="The ISBN (International Standard Book Number) if provided on the CV. Can be ISBN-10 or ISBN-13.")
    publisher: Optional[str] = Field(None, description="The name of the publisher (e.g., 'Springer', 'IEEE', 'Academic Press').")
    year: Optional[int] = Field(None, description="Year of publication as integer.")
    online_link: Optional[str] = Field(None, description="URL link to the book's page or online verification (e.g., Amazon, Google Books, publisher website) if provided on the CV.")
    authorship_role: Optional[BookAuthorshipRole] = Field(None, description="The candidate's contribution level: Sole Author, Lead Author, Co-Author, or Contributing Author.")
    evidence_text: Optional[str] = Field(None, description="Verbatim CV text that supports this book record.")
    confidence_score: Optional[float] = Field(None, description="Model confidence for this extracted record, 0.0 to 1.0.")


class PatentExtraction(BaseModel):
    title: str = Field(..., description="Official title of the patent as listed on the CV.")
    inventors: Optional[str] = Field(None, description="Complete list of ALL inventors/innovators in order, exactly as they appear on the patent documentation. Crucial for inventor network analysis.")
    patent_no: Optional[str] = Field(None, description="The official patent number (e.g., 'US12345678', 'IN201721005678'). Extract exactly as written.")
    country_of_filing: Optional[str] = Field(None, description="Country or countries where the patent was filed or granted (e.g., 'USA', 'UK', 'China', 'International'). If multiple, list all.")
    date_filed: Optional[date] = Field(None, description="The date the patent was filed. Extract as date if available.")
    date_granted: Optional[date] = Field(None, description="The date the patent was granted, if it is already granted. Extract as date if available.")
    status: Optional[str] = Field(None, description="Current status of the patent: 'Granted', 'Pending', 'Filed', 'Expired', or other status if mentioned.")
    online_link: Optional[str] = Field(None, description="Verifiable online link to the patent (e.g., USPTO, WIPO, Google Patents) if provided on the CV.")
    inventor_role: Optional[InventorRole] = Field(None, description="The candidate's role among the inventors: Lead Inventor, Co-Inventor, or Contributing Innovator.")
    evidence_text: Optional[str] = Field(None, description="Verbatim CV text that supports this patent record.")
    confidence_score: Optional[float] = Field(None, description="Model confidence for this extracted record, 0.0 to 1.0.")


class WorkExperienceExtraction(BaseModel):
    job_title: Optional[str] = Field(None, description="The specific job title or role held, exactly as stated on the CV (e.g., 'Senior Software Engineer', 'Research Scientist').")
    organization: Optional[str] = Field(None, description="The complete name of the company, university, or organization.")
    location: Optional[str] = Field(None, description="Geographic location or city where the job was held.")
    employment_type: Optional[str] = Field(None, description="Type of employment: 'Full-time', 'Part-time', 'Contract', 'Internship', 'Research Assistant', 'Freelance', or other.")
    start_month: Optional[int] = Field(None, description="Month when employment started (1-12).")
    start_year: Optional[int] = Field(None, description="Year when employment started. Extract as integer. CRUCIAL for gap and overlap detection.")
    end_month: Optional[int] = Field(None, description="Month when employment ended (1-12).")
    end_year: Optional[int] = Field(None, description="Year when employment ended. Extract as integer. CRUCIAL for gap and overlap detection.")
    is_current: Optional[bool] = Field(False, description="Set to true if the candidate currently holds this position (indicated by 'Present', 'Ongoing', 'Currently', or similar keywords).")
    job_responsibilities: Optional[str] = Field(None, description="Complete job description, responsibilities, and achievements listed for this role. CRUCIAL: This text is used in Section 3.9 to determine if claimed skills are actually backed up by work experience. Extract all bullet points or narrative description verbatim.")
    is_academic_role: Optional[bool] = Field(False, description="Set to true if the role is academic (e.g., Assistant Professor, Researcher, Lecturer, Post-Doc) rather than corporate.")
    overlaps_with_education: Optional[bool] = Field(False, description="Analyze date ranges: set to true if this employment overlaps with periods when the candidate was formally studying. This indicates simultaneous work and study.")
    evidence_text: Optional[str] = Field(None, description="Verbatim CV text that supports this work experience.")
    confidence_score: Optional[float] = Field(None, description="Model confidence for this extracted record, 0.0 to 1.0.")


class SkillExtraction(BaseModel):
    name: str = Field(..., description="The exact name of the skill as listed on the CV (e.g., 'Python', 'Machine Learning', 'Project Management', 'Leadership').")
    category: Optional[str] = Field(None, description="Categorize the skill as 'Technical' (programming, tools, frameworks), 'Domain' (field-specific expertise), 'Soft Skill' (communication, leadership), or 'Other'.")
    proficiency_level: Optional[str] = Field(None, description="If mentioned, extract the proficiency level: 'Beginner', 'Intermediate', 'Advanced', 'Expert', or leave blank if not specified.")
    years_of_experience: Optional[int] = Field(None, description="If the CV mentions how many years of experience with this skill, extract as integer.")
    evidenced_in_work: Optional[bool] = Field(False, description="Set to true if this skill is explicitly mentioned in job descriptions or work responsibilities extracted from the CV.")
    evidenced_in_research: Optional[bool] = Field(False, description="Set to true if this skill aligns with methods or technologies used in the candidate's research publications.")
    work_evidence: Optional[str] = Field(None, description="If evidenced in work, provide the specific job responsibility text that demonstrates this skill.")
    research_evidence: Optional[str] = Field(None, description="If evidenced in research, provide the publication titles or methods that demonstrate this skill.")
    strength_of_evidence: Optional[EvidenceStrength] = Field(EvidenceStrength.UNSUPPORTED, description="Synthesize evidence: Strongly Evidenced (appears in work AND research), Partially Evidenced (appears in one), Weakly Evidenced (mentioned but not clearly backed), or Unsupported (claimed but not evidenced).")
    confidence_score: Optional[float] = Field(None, description="Model confidence for this extracted record, 0.0 to 1.0.")


class CoreProfileExtraction(BaseModel):
    name: str = Field(..., description="Full name of the candidate as stated on the CV.")
    email: Optional[str] = Field(None, description="Email address of the candidate.")
    phone: Optional[str] = Field(None, description="Phone number of the candidate (any format).")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL if provided on the CV.")
    personal_website: Optional[str] = Field(None, description="Personal website or portfolio URL if provided on the CV.")
    other_urls: Optional[str] = Field(None, description="Comma-separated list of other professional URLs if provided.")
    summary_of_profile: Optional[str] = Field(None, description="Professional summary of the candidate profile.")
    education: List[EducationRecordExtraction] = Field(default_factory=list, description="Extracted education records.")
    experience: List[WorkExperienceExtraction] = Field(default_factory=list, description="Extracted work experience records.")


class PublicationExtractionBundle(BaseModel):
    journal: Optional[JournalPublicationExtraction] = Field(None, description="Populate when the publication is a journal paper.")
    conference: Optional[ConferencePublicationExtraction] = Field(None, description="Populate when the publication is a conference paper.")


class AcademicProfileExtraction(BaseModel):
    publications: List[PublicationExtractionBundle] = Field(
        default_factory=list,
        description=(
            "Journal/conference publications represented as bundles. Publications may come from flattened "
            "PDF tables where headers and row values are merged; reconstruct records using nearby explicit "
            "signals like paper title, venue, year, volume/issue, pages, and author strings."
        ),
    )
    supervision: List[SupervisionRecordExtraction] = Field(default_factory=list, description="Supervision/co-supervision records.")
    books: List[BookExtraction] = Field(default_factory=list, description="Books authored or co-authored by the candidate.")


class SkillsAndIPExtraction(BaseModel):
    patents: List[PatentExtraction] = Field(default_factory=list, description="Filed/granted patent records.")
    skills: List[SkillExtraction] = Field(default_factory=list, description="Extracted skill records.")


class CandidateExtraction(BaseModel):
    name: str = Field(..., description="Full name of the candidate as stated on the CV.")
    email: Optional[str] = Field(None, description="Email address of the candidate. CRUCIAL for Section 4 (drafting missing-info emails). Extract exactly as written on the CV.")
    phone: Optional[str] = Field(None, description="Phone number of the candidate (any format). Extract exactly as written, including country code if present.")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL if provided on the CV.")
    personal_website: Optional[str] = Field(None, description="Personal website or portfolio URL if provided on the CV.")
    other_urls: Optional[str] = Field(None, description="Comma-separated list of other professional URLs (GitHub, ResearchGate, Google Scholar, etc.) if provided.")
    summary_of_profile: Optional[str] = Field(None, description="A professional, synthesized 2-3 paragraph executive summary of the candidate's overall profile, key strengths, research focus, and experience level. Focus on what makes them unique.")
    education_records: List[EducationRecordExtraction] = Field(default_factory=list, description="Extracted records of formal education progression from earliest to latest. Include all degrees listed.")
    work_experiences: List[WorkExperienceExtraction] = Field(default_factory=list, description="Extracted professional work experience history in reverse chronological order (most recent first). Include all positions listed.")
    journal_publications: List[JournalPublicationExtraction] = Field(default_factory=list, description="All research papers explicitly published in peer-reviewed journals. Separate these from conference papers.")
    conference_publications: List[ConferencePublicationExtraction] = Field(default_factory=list, description="All research papers presented at or published in conference proceedings. Separate these from journal papers.")
    supervision_records: List[SupervisionRecordExtraction] = Field(default_factory=list, description="Records denoting supervision or co-supervision of advanced degree students (MS, MPhil, PhD). Extract all mentions.")
    books: List[BookExtraction] = Field(default_factory=list, description="Extracted records for books authored or co-authored by the candidate.")
    patents: List[PatentExtraction] = Field(default_factory=list, description="Extracted records for filed or granted patents. Include both granted and pending patents if mentioned.")
    skills: List[SkillExtraction] = Field(default_factory=list, description="Skills listed by the candidate along with analytical validation against their work experience and research publications.")
    career_breaks: List[CareerBreak] = Field(default_factory=list, description="Explicitly stated career breaks or gaps with explanations (e.g., Sabbatical, Maternity Leave, Medical Leave). CRITICAL for Section 3.8 gap justification analysis to distinguish between explained gaps and unexplained employment gaps.")
    raw_llm_response: Optional[str] = Field(None, description="Optional raw model response preserved for auditability.")
    llm_model_name: Optional[str] = Field(None, description="Model used for extraction (e.g., 'talash-primary', 'groq/llama-3.3-70b-versatile')")
    llm_provider: Optional[str] = Field(None, description="Provider name (e.g., 'litellm-router')")
