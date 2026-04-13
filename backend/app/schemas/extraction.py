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
    degree_title: Optional[str] = Field(None, description="Exact title of the degree, e.g., 'BS Computer Science', 'MPhil Mathematics'.")
    specialization: Optional[str] = Field(None, description="The specialization or major subject of the degree.")
    institution: Optional[str] = Field(None, description="The name of the university or institution.")
    board_or_university: Optional[str] = Field(None, description="The board (for SSE/HSSC) or university name.")
    start_year: Optional[int] = Field(None, description="Year the education started.")
    end_year: Optional[int] = Field(None, description="Year the education completed.")
    marks_percentage: Optional[float] = Field(None, description="Percentage of marks obtained, usually for early stages like SSE/HSSC.")
    cgpa: Optional[float] = Field(None, description="CGPA obtained if reported. Example: 3.8")
    cgpa_scale: Optional[float] = Field(None, description="Total possible CGPA scale, e.g., 4.0 or 5.0")
    gap_before_start_months: Optional[int] = Field(None, description="Calculate any gap in months between the last completed education stage and the start of this one. Return 0 if no gap or consecutive.")
    gap_justified_by_experience: Optional[bool] = Field(False, description="Set to true if there is overlapping work or equivalent productive activity (e.g., employment, freelancing) for the calculated gap duration.")


class JournalPublicationExtraction(BaseModel):
    title: str = Field(..., description="Title of the journal publication.")
    authors: Optional[str] = Field(None, description="Comma-separated list of authors exactly as they appear on the paper.")
    journal_name: Optional[str] = Field(None, description="The full name of the journal.")
    issn: Optional[str] = Field(None, description="The ISSN of the journal if provided.")
    year: Optional[int] = Field(None, description="Year of publication.")
    wos_indexed: Optional[bool] = Field(False, description="Determine or infer if the journal is Web of Science (WoS) indexed by the context if possible, default to False.")
    scopus_indexed: Optional[bool] = Field(False, description="Determine or infer if the journal is Scopus indexed, default to False.")
    quartile: Optional[QuartileRanking] = Field(QuartileRanking.UNKNOWN, description="Quartile ranking of the journal if explicitly mentioned or broadly recognized, e.g., Q1, Q2.")
    impact_factor: Optional[float] = Field(None, description="Impact Factor of the journal if explicitly reported.")
    authorship_role: Optional[AuthorshipRole] = Field(None, description="Determine the role of the candidate in the author list based on order and 'corresponding' markers.")
    author_position: Optional[int] = Field(None, description="The 1-based index position of the candidate in the author list. e.g., 1 if they are the first author.")
    topic_category: Optional[str] = Field(None, description="Categorize the main topic or theme of this publication into a broad domain like 'Machine Learning', 'Computer Vision'.")
    is_with_student: Optional[bool] = Field(False, description="Determine if any of the co-authors appear to be students the candidate is or was supervising based on explicit markers.")


class ConferencePublicationExtraction(BaseModel):
    title: str = Field(..., description="Title of the conference paper.")
    authors: Optional[str] = Field(None, description="Comma-separated list of authors.")
    conference_name: Optional[str] = Field(None, description="Full name of the conference.")
    year: Optional[int] = Field(None, description="Year the paper was published or presented.")
    conference_series: Optional[str] = Field(None, description="The numerical series or edition of the conference, e.g., '28th IEEE Conference'.")
    core_ranking: Optional[ConferenceRanking] = Field(ConferenceRanking.UNRANKED, description="The CORE ranking of the conference (A*, A, B, C) if mentioned or discernible.")
    indexed_in: Optional[str] = Field(None, description="Where the proceedings are indexed (e.g., 'Scopus', 'IEEE Xplore', 'ACM', 'Springer').")
    authorship_role: Optional[AuthorshipRole] = Field(None, description="The candidate's authorship role.")
    author_position: Optional[int] = Field(None, description="1-based index of the candidate among the authors.")
    topic_category: Optional[str] = Field(None, description="Main topic or theme of the paper, categorized appropriately.")
    is_with_student: Optional[bool] = Field(False, description="True if a co-author is explicitly denoted as or likely a supervised student.")


class SupervisionRecordExtraction(BaseModel):
    student_level: Optional[str] = Field(None, description="The degree level of the supervised student (e.g., 'MS', 'MPhil', 'PhD').")
    student_name: Optional[str] = Field(None, description="The full name of the supervised student.")
    completion_year: Optional[int] = Field(None, description="The year the student graduated or completed their thesis/research.")
    supervision_role: Optional[SupervisionRole] = Field(None, description="Did the candidate act as the Main Supervisor or Co-Supervisor?")
    publications_with_student: Optional[int] = Field(0, description="Count of publications in the candidate's list that are co-authored with this specific student.")


class BookExtraction(BaseModel):
    title: str = Field(..., description="Title of the book.")
    authors: Optional[str] = Field(None, description="All authors of the book.")
    isbn: Optional[str] = Field(None, description="The ISBN of the book if provided.")
    publisher: Optional[str] = Field(None, description="The publisher of the book.")
    year: Optional[int] = Field(None, description="Year of publication.")
    online_link: Optional[str] = Field(None, description="A verifiable link to the book or publication page if present.")
    authorship_role: Optional[BookAuthorshipRole] = Field(None, description="The contribution level of the candidate for this book.")


class PatentExtraction(BaseModel):
    title: str = Field(..., description="Title of the patent.")
    inventors: Optional[str] = Field(None, description="All inventors listed on the patent.")
    patent_no: Optional[str] = Field(None, description="The official patent number if provided.")
    date_filed: Optional[date] = Field(None, description="The precise or calculated date the patent was filed or issued.")
    country_of_filing: Optional[str] = Field(None, description="The country or region where the patent was filed.")
    online_link: Optional[str] = Field(None, description="A verifiable online link to the patent if present.")
    inventor_role: Optional[InventorRole] = Field(None, description="The candidate's contribution level among the inventors.")
    status: Optional[str] = Field(None, description="The current status of the patent (e.g., 'Granted', 'Pending').")


class WorkExperienceExtraction(BaseModel):
    job_title: Optional[str] = Field(None, description="The specific job title or role held.")
    organization: Optional[str] = Field(None, description="The name of the company or academic institution.")
    location: Optional[str] = Field(None, description="The geographic location of the job.")
    employment_type: Optional[str] = Field(None, description="Type of employment (e.g., 'Full-time', 'Part-time', 'Contract').")
    start_date: Optional[date] = Field(None, description="When the employment started. Parse from standard date strings. If only year/month is given, default to the first of that month.")
    end_date: Optional[date] = Field(None, description="When the employment ended. Omit if it is listed as 'Present' or current.")
    is_current: Optional[bool] = Field(False, description="True if the candidate currently holds this position (indicated by 'Present' or similar keyword).")
    is_academic_role: Optional[bool] = Field(False, description="True if the role is academic (e.g., Professor, Researcher, Lecturer) rather than strictly corporate.")
    overlaps_with_education: Optional[bool] = Field(False, description="Analyze the dates and return true if this employment overlaps with periods of the candidate's formal education.")


class SkillExtraction(BaseModel):
    name: str = Field(..., description="The name of the skill, e.g., 'Machine Learning', 'Leadership', 'Python'.")
    category: Optional[str] = Field(None, description="A broad categorization, e.g., 'Technical', 'Soft Skill'.")
    evidenced_in_work: Optional[bool] = Field(False, description="Set to true if this skill is explicitly mentioned or naturally utilized in the candidate's extracted work experiences.")
    evidenced_in_research: Optional[bool] = Field(False, description="Set to true if this skill aligns closely with the topics or methods identified in their research publications.")
    strength_of_evidence: Optional[EvidenceStrength] = Field(EvidenceStrength.UNSUPPORTED, description="Synthesize the evidence from work and research to determine how strongly supported this skill claim is.")


class CandidateExtraction(BaseModel):
    name: str = Field(..., description="Full name of the candidate.")
    email: Optional[str] = Field(None, description="Email address of the candidate.")
    summary_of_profile: Optional[str] = Field(None, description="A professional, synthesized 3-paragraph executive summary of the candidate's overall profile, strengths, and experience level.")
    education_records: List[EducationRecordExtraction] = Field(default_factory=list, description="Extracted records of formal education progression.")
    work_experiences: List[WorkExperienceExtraction] = Field(default_factory=list, description="Extracted professional work experience history.")
    journal_publications: List[JournalPublicationExtraction] = Field(default_factory=list, description="All research papers explicitly published in journals.")
    conference_publications: List[ConferencePublicationExtraction] = Field(default_factory=list, description="All research papers explicitly published in conference proceedings.")
    supervision_records: List[SupervisionRecordExtraction] = Field(default_factory=list, description="Records denoting supervision or co-supervision of advanced degree students.")
    books: List[BookExtraction] = Field(default_factory=list, description="Extracted records for books authored.")
    patents: List[PatentExtraction] = Field(default_factory=list, description="Extracted records for filed or granted patents.")
    skills: List[SkillExtraction] = Field(default_factory=list, description="Skills listed along with analytical validation against the candidate's broader profile.")
