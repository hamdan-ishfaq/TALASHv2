# TALASH v3 - PHASE 3 IMPLEMENTATION PLAN
## Complete Working Web Application with Full Module Integration
**Date**: May 11, 2026  
**Target Deadline**: End of Semester  
**Status**: Phase 1 & 2 Complete → Phase 3 Implementation

---

## TABLE OF CONTENTS
1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Phase 3 Scope & Requirements](#phase-3-scope--requirements)
4. [Detailed Component Implementation Guide](#detailed-component-implementation-guide)
5. [Architecture Decisions & Design Patterns](#architecture-decisions--design-patterns)
6. [Database & Data Flow](#database--data-flow)
7. [Frontend Implementation Details](#frontend-implementation-details)
8. [Backend Enhancement Requirements](#backend-enhancement-requirements)
9. [Testing & Validation Strategy](#testing--validation-strategy)
10. [Deployment & DevOps](#deployment--devops)
11. [Risk Assessment & Mitigation](#risk-assessment--mitigation)
12. [Timeline & Milestones](#timeline--milestones)

---

## EXECUTIVE SUMMARY

Phase 3 transforms the existing TALASH prototype into a **complete, production-ready web application** with:
- ✅ **Full functional module implementation** (all 9 modules from spec Section 3)
- ✅ **Multi-candidate batch processing** with real-time dashboard
- ✅ **Comprehensive graphical analytics** (charts, tables, comparisons)
- ✅ **Automated missing-information email drafting**
- ✅ **End-to-end pipeline integration** (CV upload → Analysis → Reports)
- ✅ **Robust error handling & quality assurance**

**Key deliverables:**
- Working backend with complete API surface
- React frontend with 4+ views (Upload, Dashboard, Detail, Reports)
- PostgreSQL database with 15+ normalized tables
- Celery+Redis async processing
- Docker containerized deployment
- Comprehensive documentation

---

## CURRENT STATE ANALYSIS

### ✅ WHAT'S ALREADY IMPLEMENTED (Phase 1 & 2)

#### Backend Infrastructure
```
✅ FastAPI application (main.py) with CORS middleware
✅ PostgreSQL database with ORM (SQLAlchemy)
✅ Celery + Redis for async task processing
✅ 15+ normalized database models (Candidate, Education, Work, Publication, etc.)
✅ LLM integration layer (OpenRouter, Groq, Gemini)
✅ PDF parsing & text extraction (PyMuPDF, pdfplumber)
```

#### Extraction & Analysis Services (Phase 2)
```
✅ Module 1: CV Extraction (extractor.py)
  - PDF text extraction
  - Structured data extraction (education, experience, publications, skills)
  - Pydantic schema validation
  - Error flagging & metadata logging

✅ Module 2: Education Analysis (education_analysis.py)
  - CGPA/marks normalization
  - Gap detection (with thresholds)
  - QS ranking lookup
  - Institution quality assessment
  - Database persistence

✅ Module 2: Experience Analysis (experience_analysis.py)
  - Timeline consistency checking
  - Employment gap detection
  - Career progression assessment
  - Overlap detection (education/employment)
  - Gap justification analysis

✅ Module 2: Summary Generation (summary_generator.py)
  - Weighted scoring (education, research, experience, skills)
  - LLM-based narrative generation
  - Overall rank calculation
  - Missing info detection
```

#### External Data Sources
```
✅ QS Rankings lookup (qs_lookup.py) — 2026 XLSX file
✅ Scimago lookup (scimago_lookup.py) — 2025 CSV file
✅ CORE database lookup (core_lookup.py) — CSV file
✅ Crossref/OpenAlex async enrichment (research_enrichment.py)
✅ Conference ranking via CORE API
```

#### API Routes (Partial)
```
✅ POST /upload — file upload & queueing
✅ POST /analysis/education/{id} — run education analysis
✅ POST /analysis/experience/{id} — run experience analysis
✅ POST /analysis/summary/{id} — generate summary
✅ GET /analysis/dashboard — candidate list with scores
✅ GET /analysis/missing-info/{id} — missing info requests
✅ POST /api/admin/flush-incomplete — database cleanup
```

#### Frontend (Minimal)
```
✅ React + TypeScript setup
✅ 4 core components: Upload, Dashboard, Detail, Shared
✅ Basic navigation & routing
✅ Simple styling (CSS)
✅ Axios HTTP client
```

#### DevOps & Deployment
```
✅ Docker Compose (db, redis, backend, worker, flower)
✅ PostgreSQL 15 container
✅ Redis alpine container
✅ Celery worker with Flower monitoring
```

---

### ❌ WHAT'S MISSING (Phase 3 Requirements)

#### CRITICAL MISSING MODULES
```
❌ Module 3: Full Research Profile Analysis
   - Journal publication quality scoring (with WoS/Scopus verification)
   - Conference publication ranking (A* status, CORE ranking)
   - Publication topic variability analysis
   - Co-author collaboration network analysis

❌ Module 3.3: Student Supervision Analysis
   - MS/PhD student supervision counting
   - Supervision role classification (main vs co-supervisor)
   - Publications with supervised students
   
❌ Module 3.4: Books & Patents
   - Book metadata extraction & verification
   - Patent identification & analysis
   - ISBN & patent number verification

❌ Module 3.6: Topic Variability & Clustering
   - Publication topic/keyword extraction
   - Topic cluster assignment (ML or LLM-based)
   - Diversity scoring

❌ Module 3.7: Co-author Analysis
   - Collaboration network graph construction
   - Recurring collaborator identification
   - Collaboration pattern analysis
   - Network diversity metrics
```

#### MISSING BACKEND FEATURES
```
❌ Missing-information email generation pipeline
   - Personalized draft emails per candidate
   - Template-based generation
   - Candidate-specific field detection
   - Email body composition & formatting

❌ Batch analysis endpoints
   - /analysis/research/batch
   - /analysis/skills/batch
   - /analysis/full-pipeline/batch

❌ Skill alignment service
   - Skill extraction from experience & research
   - Evidence mapping (work vs research)
   - Job description matching

❌ Candidate ranking & comparison service
   - Quantifiable ranking module
   - Multi-criteria scoring
   - Benchmarking across candidates

❌ Report generation & export
   - PDF report export
   - Excel export with proper formatting
   - Comparative candidate reports
```

#### MISSING FRONTEND FEATURES
```
❌ Research analysis visualization
   - Publication quality breakdown chart
   - Journal quartile distribution
   - Conference ranking distribution
   - Co-author network graph

❌ Topic variability visualization
   - Research topic pie chart
   - Topic diversity score visualization
   - Publication timeline by topic

❌ Skills dashboard
   - Skills summary card
   - Evidence strength visualization
   - Skill-to-job alignment chart

❌ Missing information view
   - Draft email preview
   - Personalized field lists
   - Email send interface

❌ Comparative dashboard
   - Multi-candidate comparison table
   - Score benchmarking
   - Ranking visualization

❌ Advanced filtering & search
   - Filter by education level, institution ranking
   - Filter by publication count/quality
   - Filter by experience type
   - Search by skill or topic
```

#### MISSING DATA QUALITY FEATURES
```
❌ Input validation enhancement
   - ISBN validation
   - Patent number format checking
   - DOI validation
   - Email format validation

❌ Duplicate detection
   - Publication duplicate detection (by title/DOI)
   - Author name normalization
   - Institution name normalization

❌ Data reconciliation
   - Cross-reference education dates with experience
   - Validate publication dates against CV dates
   - Check author affiliations against institutions
```

#### MISSING DOCUMENTATION & TESTING
```
❌ API documentation (Swagger/OpenAPI)
❌ Database schema documentation
❌ Component testing (unit + integration)
❌ End-to-end testing scenarios
❌ API endpoint testing
❌ UI component testing
```

---

## PHASE 3 SCOPE & REQUIREMENTS

### Functional Requirements (from Spec Section 4)

#### FR1: CV Upload & Folder Monitoring
- **Status**: ✅ Mostly Complete
- **Remaining Work**:
  - Enhance folder monitoring for batch CSV imports (if needed)
  - Add drag-and-drop support (⚠️ Check if already in frontend)
  - Implement bulk upload progress tracking
  - Add file size validation (e.g., max 10MB per CV)

#### FR2: Automatic CV Parsing & Analysis Engine
- **Status**: ✅ Partially Complete (Phase 2)
- **Remaining Work**:
  - Implement full pipeline for **all 9 modules**
  - Add task queue status tracking
  - Implement automatic error recovery with retry logic
  - Add LLM response caching to reduce API calls

#### FR3: Graphical Dashboard
- **Status**: ⚠️ Minimal Implementation
- **Remaining Work**:
  - Multi-candidate comparison table (PRIORITY)
  - Score summary cards
  - Publication breakdown charts (pie/bar)
  - Education quality visualization
  - Experience timeline
  - Skills matrix
  - Topic variability distribution
  - Co-author network graph (optional but impressive)

#### FR4: Missing Information Detection
- **Status**: ⚠️ Partial (education/experience only)
- **Remaining Work**:
  - Detect missing fields across **ALL modules**
  - Generate personalized, module-specific email drafts
  - Email preview with edit capability
  - Send/archive email tracking

#### FR5: Structured Reporting
- **Status**: ❌ Not Started
- **Remaining Work**:
  - Candidate summary report (text + metrics)
  - PDF export functionality
  - Excel export (tabular format)
  - Comparative candidate report

---

## DETAILED COMPONENT IMPLEMENTATION GUIDE

### PHASE 3A: COMPLETE RESEARCH PROFILE ANALYSIS (Week 1-2)

#### 3A.1: Journal Publication Quality Scoring

**File**: `backend/app/services/research_analysis.py` (ENHANCE existing)

**What's needed:**
1. **Journal Legitimacy & WoS/Scopus Verification**
   - Query WoS API or cached database
   - Query Scopus API or cached database
   - Extract Impact Factor (if available)
   - Store results in `JournalPublication` table

2. **Quartile Ranking Logic**
   ```python
   def score_journal_quality(journal: JournalPublication) -> float:
       """
       Scoring matrix:
       - Q1 + WoS indexed       : 8.0 pts
       - Q1 + Scopus only       : 7.0 pts
       - Q1 unindexed           : 5.5 pts
       - Q2 + indexed           : 5.0 pts
       - Q2 unindexed           : 4.0 pts
       - Q3 + indexed           : 3.0 pts
       - Q3 unindexed           : 2.0 pts
       - Q4                     : 1.0 pts
       - Unranked but verified  : 1.5 pts
       - Unranked/unverified    : 0.5 pts
       """
   ```

3. **Authorship Role Impact**
   ```python
   AUTHORSHIP_MULTIPLIERS = {
       "first_author": 1.0,           # 100% weight
       "corresponding_author": 0.9,    # 90% weight
       "first_and_corresponding": 1.0,
       "co_author": 0.6,              # 60% weight
       "unknown": 0.5                 # 50% weight
   }
   ```

**New Classes/Functions to Add:**
```python
class JournalVerificationResult:
    journal_name: str
    issn: Optional[str]
    is_legitimate: bool
    wos_indexed: bool
    scopus_indexed: bool
    quartile: Optional[str]
    impact_factor: Optional[float]
    verification_url: str
    confidence: float

async def verify_journal_wos_scopus(issn: str, journal_name: str) -> JournalVerificationResult:
    """Verify journal through WoS/Scopus APIs"""
    
async def get_impact_factor(issn: str) -> Optional[float]:
    """Query Impact Factor from external service"""
```

**Database Updates:**
```sql
-- Already in schema, but ensure populated:
ALTER TABLE journal_publications 
  ADD CONSTRAINT check_wos_scopus CHECK (wos_indexed IS NOT NULL);
```

---

#### 3A.2: Conference Publication Ranking

**File**: `backend/app/services/research_analysis.py` (ENHANCE)

**What's needed:**
1. **A* Ranking Status** (from CORE database)
   ```python
   def get_a_star_status(conference_name: str, year: int) -> Optional[bool]:
       """Query CORE database for A* ranking"""
   ```

2. **Conference Maturity Assessment**
   ```python
   def assess_conference_maturity(
       conference_name: str,
       year: int,
       series_edition: Optional[str]
   ) -> dict:
       """
       Output example:
       {
           "ordinal_edition": "28th",
           "age_years": 27,
           "maturity_label": "Mature (27+ yrs, est. 1999)",
           "is_recurring": True
       }
       """
   ```

3. **Indexing Status** (Scopus, IEEE, ACM, Springer)
   - Store in `ConferencePublication.indexed_in`
   - Use research_enrichment.py async APIs

4. **Scoring Conference Papers**
   ```python
   def score_conference_paper(
       conf: ConferencePublication,
       authorship_multiplier: float
   ) -> float:
       """
       Scoring matrix:
       - A* conference           : 10.0 pts
       - A conference            : 7.0 pts
       - B conference            : 5.0 pts
       - C conference            : 2.0 pts
       - Unranked but indexed    : 1.0 pts
       - Unranked/unindexed      : 0.5 pts
       
       Multiply by authorship_multiplier (1.0 for first/corresponding, 0.6 for co-author)
       """
   ```

**New Database Columns** (if not present):
```sql
ALTER TABLE conference_publications 
  ADD COLUMN IF NOT EXISTS core_ranking VARCHAR(10);  -- A*, A, B, C
ALTER TABLE conference_publications 
  ADD COLUMN IF NOT EXISTS is_mature BOOLEAN DEFAULT FALSE;
ALTER TABLE conference_publications 
  ADD COLUMN IF NOT EXISTS maturity_years INTEGER;
```

---

#### 3A.3: Research Publication Topic Variability (Module 3.6)

**File**: `backend/app/services/llm_analysis.py` + NEW `backend/app/services/topic_analysis.py`

**Architecture:**
```
Publication Keywords/Abstracts 
  ↓
LLM-based Topic Assignment (or keyword clustering)
  ↓
TopicCluster table storage
  ↓
Diversity Scoring
  ↓
Research Profile Interpretation
```

**Implementation:**

1. **Extract Topics from Publications**
   ```python
   async def extract_publication_topics(
       publication_id: int,
       publication_type: str,  # "journal" or "conference"
       title: str,
       abstract: Optional[str],
       keywords: Optional[list[str]]
   ) -> list[str]:
       """
       Use LLM to extract research topics/domains
       Example output: ["Machine Learning", "Computer Vision", "Robotics"]
       """
   ```

2. **Cluster Publications**
   ```python
   class TopicCluster:
       id: int
       candidate_id: int
       cluster_name: str  # e.g., "Machine Learning"
       publication_ids: list[int]
       publication_count: int
       percentage: float
       
   def cluster_publications(
       candidate_id: int,
       publications: list[JournalPublication | ConferencePublication]
   ) -> list[TopicCluster]:
       """Assign publications to topic clusters"""
   ```

3. **Compute Diversity Score**
   ```python
   def compute_topic_diversity(
       candidate_id: int,
       topic_clusters: list[TopicCluster]
   ) -> dict:
       """
       Output:
       {
           "diversity_score": 0.45,  # 0 (focused) to 1.0 (very diverse)
           "entropy": 2.1,
           "dominant_topics": ["Machine Learning", "NLP"],
           "topic_distribution": {
               "Machine Learning": 35,
               "Computer Vision": 25,
               "Robotics": 20,
               ...
           },
           "interpretation": "Moderate specialization with focus on ML"
       }
       """
   ```

**Prompts to Create:**
```python
TOPIC_EXTRACTION_PROMPT = """
You are a research scientist analyzing academic publications.

For each publication, identify 2-4 primary research topics/domains.

Example:
Title: "Deep Learning for Autonomous Vehicles"
Keywords: neural networks, computer vision, autonomous driving
Topics: ["Deep Learning", "Computer Vision", "Autonomous Systems"]

Publication:
Title: {title}
Abstract: {abstract}
Keywords: {keywords}

Return a JSON array of 2-4 topics. Be consistent across publications.
"""
```

**Database Schema** (already exists, verify):
```python
class TopicCluster(Base):
    __tablename__ = "topic_clusters"
    
    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    publication_type = Column(String(50))
    publication_id = Column(Integer)
    cluster_name = Column(String(255))
    cluster_score = Column(Float)
    assigned_by = Column(String(100))  # "llm" or "keyword"
    created_at = Column(DateTime, default=datetime.utcnow)
```

---

#### 3A.4: Co-Author Analysis & Collaboration Patterns (Module 3.7)

**File**: NEW `backend/app/services/collaboration_analysis.py`

**Implementation Steps:**

1. **Extract Publication Authors**
   ```python
   def extract_publication_authors(
       candidate_id: int,
       pub_id: int,
       pub_type: str,  # "journal" or "conference"
       authors_text: str
   ) -> list[PublicationAuthor]:
       """
       Parse author list, normalize names, identify candidate
       
       Output:
       [
           PublicationAuthor(author_name="John Smith", is_candidate=True, is_corresponding=True),
           PublicationAuthor(author_name="Jane Doe", is_candidate=False, affiliation="MIT"),
           ...
       ]
       """
   ```

2. **Build Collaboration Network**
   ```python
   @dataclass
   class CollaborationStats:
       unique_coauthors: int
       recurring_collaborators: list[str]  # appeared in 2+ papers
       collaboration_frequency: dict[str, int]  # author → count
       average_team_size: float
       international_collaborations: int
       student_collaborations: int
       
   def analyze_collaboration_network(
       candidate_id: int
   ) -> CollaborationStats:
       """Build graph of all co-authorships"""
   ```

3. **Identify Collaboration Patterns**
   ```python
   def classify_collaboration_patterns(
       stats: CollaborationStats
   ) -> dict:
       """
       Output:
       {
           "pattern_type": "stable_network" | "broad_reach" | "isolated",
           "description": "Works regularly with a stable group of collaborators",
           "collaboration_score": 0.75,  # 0-1.0
           "network_diversity": "moderate",
           "strength_indicators": [
               "Has worked with 25+ unique collaborators",
               "12 recurring collaborators (2+ publications)"
           ]
       }
       """
   ```

4. **Store Edges in Database**
   ```python
   def store_collaboration_edges(
       candidate_id: int,
       publications: list  # mix of journal and conference
   ):
       """Create CollaborationEdge rows for each co-authorship"""
       # Already in schema: CollaborationEdge
   ```

**Database Schema** (already exists):
```python
class CollaborationEdge(Base):
    __tablename__ = "collaboration_edges"
    
    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    coauthor_name = Column(String(255))
    coauthor_affiliation = Column(String(255))
    publication_id = Column(Integer)
    publication_type = Column(String(50))  # "journal" | "conference"
    edge_weight = Column(Float)  # how many times collaborated
    is_recurring = Column(Boolean, default=False)
    created_at = Column(DateTime)
```

---

### PHASE 3B: SUPERVISION, BOOKS, PATENTS (Week 2)

#### 3B.1: Student Supervision Analysis (Module 3.3)

**File**: NEW `backend/app/services/supervision_analysis.py`

**Key Points:**
- Most CVs don't list supervised students explicitly
- Need to ask candidate for this information
- Extract if mentioned in CV (look for keywords: "supervised", "mentored", "advisor")

**Implementation:**
```python
def extract_supervision_from_cv(raw_text: str) -> list[dict]:
    """
    Use LLM to extract supervision information from CV raw text
    
    Output:
    [
        {
            "student_name": "Ahmed Ali",
            "student_level": "PhD",
            "completion_year": 2023,
            "supervision_role": "main_supervisor",
            "thesis_title": "Deep Learning for Medical Imaging"
        },
        ...
    ]
    """
    pass

def analyze_supervision(
    candidate_id: int,
    db: Session
) -> dict:
    """
    Aggregate supervision stats
    
    Output:
    {
        "total_supervised": 5,
        "ms_students": 2,
        "phd_students": 3,
        "main_supervisor": 4,
        "co_supervisor": 1,
        "publications_with_students": 7,
        "strength_score": 7.5,  # 0-10
        "interpretation": "Strong supervisory record with 5 students and significant publications"
    }
    """
```

**Missing Info Email** (if not provided):
```
Subject: Additional Information Needed — Student Supervision

Dear [Candidate Name],

Thank you for submitting your CV for consideration. To provide a comprehensive 
profile assessment, we need additional information about your supervisory record:

• Names and graduation years of MS/PhD students supervised as main supervisor
• Names and graduation years of MS/PhD students supervised as co-supervisor
• Thesis titles (if available)

Please reply with this information at your earliest convenience.

Best regards,
TALASH Recruitment System
```

---

#### 3B.2: Books Authored / Co-Authored (Module 3.4)

**File**: `backend/app/services/extractor.py` (already extracts) + NEW validation

**Implementation:**
```python
async def verify_book_metadata(book: Book) -> dict:
    """
    Verify book details against external sources
    - Check ISBN validity
    - Confirm publisher & publication date
    - Verify online link accessibility
    """
    
def validate_isbn(isbn: str) -> bool:
    """Check ISBN-13 checksum"""
    # ISBN validation logic
    
async def lookup_book_on_google_books(
    title: str,
    authors: list[str],
    year: int
) -> Optional[dict]:
    """Query Google Books API for verification"""
```

---

#### 3B.3: Patents Analysis (Module 3.5)

**File**: NEW `backend/app/services/patent_analysis.py`

**Implementation:**
```python
async def verify_patent_metadata(patent: Patent) -> dict:
    """
    Verify patent details:
    - Valid patent number format (e.g., US7234567B2)
    - Query patent office database (USPTO, WIPO, etc.)
    - Confirm filing/grant dates
    - Extract inventor list and roles
    """
    
def validate_patent_number(patent_no: str, country: str) -> bool:
    """
    Validate format based on country:
    - USA: US[7-8 digits]B[1-2] or similar
    - UK: GB[8 digits]B
    - WO: WO[10 digits]A[1]
    """
```

---

### PHASE 3C: SKILL ALIGNMENT SERVICE (Week 2)

**File**: NEW `backend/app/services/skill_alignment.py`

**Architecture:**
```
Extract Skills from CV
  ↓
Map Skills to Work Experiences
  ↓
Map Skills to Research Publications
  ↓
Assess Evidence Strength
  ↓
(Optional) Compare against Job Description
```

**Implementation:**

```python
def assess_skill_evidence(
    skill: Skill,
    candidate_id: int,
    db: Session
) -> dict:
    """
    Determine where skill is evidenced
    
    Output:
    {
        "skill_name": "Machine Learning",
        "work_evidence": [
            "Senior ML Engineer at Google (2020-2023)",
            "ML Research Lead at Meta (2023-present)"
        ],
        "research_evidence": [
            "12 publications on deep learning",
            "Supervised 3 PhD students in ML"
        ],
        "strength_of_evidence": "Strongly Evidenced",
        "confidence": 0.95,
        "interpretation": "Extensive practical and research experience"
    }
    """

def align_skills_to_job_description(
    candidate_id: int,
    job_description: str,
    db: Session
) -> dict:
    """
    Compare candidate skills to job posting
    
    Output:
    {
        "job_required_skills": ["Python", "ML", "Statistics"],
        "candidate_skills": ["Python", "Deep Learning", "TensorFlow"],
        "matched_skills": ["Python"],
        "missing_skills": ["Statistics"],
        "bonus_skills": ["Deep Learning", "TensorFlow"],
        "alignment_score": 0.65,  # 0-1.0
        "recommendation": "Good match, but missing statistical analysis background"
    }
    """
```

---

### PHASE 3D: MISSING INFORMATION EMAIL GENERATION (Week 2-3)

**File**: NEW `backend/app/services/missing_information_service.py`

**This is CRITICAL for Phase 3** ✅

**Implementation:**

```python
def detect_missing_information(
    candidate_id: int,
    db: Session
) -> dict[str, list[str]]:
    """
    Scan all modules and identify missing/incomplete information
    
    Output:
    {
        "education": [],  # OK
        "experience": ["Employment gaps not explained"],
        "research": ["No journal impact factors found"],
        "supervision": ["No supervision records found"],
        "books": [],
        "patents": [],
        "skills": ["Limited skill details"],
        "contact": ["Phone number missing"]
    }
    """

def generate_personalized_missing_info_email(
    candidate_id: int,
    missing_info: dict[str, list[str]],
    candidate_email: str,
    candidate_name: str,
    db: Session
) -> MissingInformationRequest:
    """
    Generate a personalized email draft
    
    Logic:
    1. List only the modules with missing info
    2. Be specific about what's missing
    3. Explain WHY this information matters
    4. Provide guidance on how to provide it
    5. Include deadline (optional)
    
    Example output:
    
    Subject: Additional Information Needed for Profile Assessment
    
    Dear Dr. Ahmed Hassan,
    
    Thank you for submitting your CV. We are conducting a comprehensive 
    profile assessment for the faculty position in Computer Science.
    
    To complete your evaluation, we need the following additional information:
    
    📚 **Research Publications:**
    - Impact factors for journal articles (if available)
    - Conference ranking/A* status for conference papers
    - DOI or verified publication links
    
    👨‍🎓 **Supervision:**
    - Names and graduation years of MS/PhD students supervised
    - Thesis titles (if available)
    - Your supervision role (main supervisor vs co-supervisor)
    
    💼 **Professional Experience:**
    - Clarification of employment gaps between [dates]
    - Brief description of gap justification (e.g., furthering education, research)
    
    Please reply to this email with the requested information. If any information 
    is not applicable, please let us know.
    
    Deadline: [+10 days from now]
    
    Best regards,
    TALASH Recruitment System
    Faculty of Computing
    """
    
    # Store in database
    request = MissingInformationRequest(
        candidate_id=candidate_id,
        module_name="comprehensive",
        missing_fields_json=json.dumps(missing_info),
        draft_email_subject=subject,
        draft_email_body=body,
        status="draft"
    )
    db.add(request)
    db.commit()
    return request
```

**Template System:**
```python
MISSING_INFO_TEMPLATES = {
    "education": """
    📚 Educational records:
    - CGPA/marks for {missing_count} degree(s)
    - Institution names or board details
    - Start/end years if missing
    """,
    
    "experience": """
    💼 Employment history:
    - Unexplained gaps between {dates_list}
    - Job responsibilities for {count} position(s)
    - End dates for current/recent roles
    """,
    
    "research": """
    🔬 Research publications:
    - Impact factors or journal rankings
    - DOI numbers for verification
    - Conference A* status
    - Clarification of authorship role (first/corresponding/co-author)
    """,
    
    "supervision": """
    👨‍🎓 Student supervision:
    - MS/PhD students supervised (names and years)
    - Thesis titles (if available)
    - Your supervision role (main/co-supervisor)
    """,
    
    "skills": """
    🎯 Professional skills:
    - Proficiency levels or years of experience
    - Specific projects or evidence of skill application
    """,
    
    "contact": """
    📞 Contact information:
    - Phone number for communication
    - Secondary email address (if applicable)
    """
}
```

**Database Model** (already exists):
```python
class MissingInformationRequest(Base):
    __tablename__ = "missing_information_requests"
    
    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    module_name = Column(String(100))  # "comprehensive" or specific module
    missing_fields_json = Column(Text)
    draft_email_subject = Column(String(255))
    draft_email_body = Column(Text)
    status = Column(String(50), default="draft")  # draft, sent, archived, resolved
    generated_at = Column(DateTime)
    sent_at = Column(DateTime, nullable=True)
```

---

### PHASE 3E: BATCH ANALYSIS & FULL PIPELINE (Week 3)

#### 3E.1: Batch Analysis Endpoints

**File**: `backend/app/routers/analysis_router.py` (ENHANCE)

```python
@router.post("/analysis/full-pipeline/batch")
async def batch_full_pipeline(
    candidate_ids: Optional[list[int]] = None,  # if None, process all pending
    skip_extraction: bool = False,  # if True, skip CV extraction
    db: Session = Depends(get_db)
) -> dict:
    """
    Run complete analysis pipeline for multiple candidates
    
    Pipeline:
    1. Education analysis
    2. Experience analysis
    3. Research analysis (journals + conferences + topics + co-authors)
    4. Supervision analysis
    5. Skills alignment
    6. Summary generation
    7. Missing info detection & email generation
    
    Returns:
    {
        "total_candidates": 5,
        "completed": 4,
        "failed": 1,
        "task_ids": ["task-1", "task-2", ...],
        "results": [
            {
                "candidate_id": 1,
                "status": "completed",
                "scores": {
                    "education": 8.5,
                    "experience": 7.2,
                    "research": 8.9,
                    "skills": 7.5,
                    "overall": 8.0
                }
            },
            ...
        ]
    }
    """
```

#### 3E.2: Celery Task Orchestration

**File**: `backend/worker/cv_tasks.py` (ENHANCE)

```python
from celery import chain, group, chord

@celery_app.task
def run_full_pipeline(candidate_id: int):
    """
    Orchestrate all analysis tasks in sequence
    
    Order matters:
    1. Education → detects gaps
    2. Experience → detects overlaps with education
    3. Research → enriches publications
    4. Supervision → uses publication data
    5. Skills → uses work & research data
    6. Summary → aggregates all scores
    7. Missing Info → identifies gaps
    """
    
    # Use Celery chains for sequential execution
    pipeline = chain(
        run_education_analysis_task.s(candidate_id),
        run_experience_analysis_task.s(candidate_id),
        run_research_analysis_task.s(candidate_id),
        run_supervision_analysis_task.s(candidate_id),
        run_skills_analysis_task.s(candidate_id),
        run_summary_generation_task.s(candidate_id),
        run_missing_info_detection_task.s(candidate_id),
    )
    
    result = pipeline.apply_async()
    return {"candidate_id": candidate_id, "task_id": result.id}
```

---

### PHASE 3F: FRONTEND DASHBOARD & VISUALIZATION (Week 2-4)

#### 3F.1: Frontend Architecture Refactor

**Current State:** 4 components in 1 folder  
**Target State:** Proper component organization

```
frontend/src/
├── components/
│   ├── views/
│   │   ├── UploadView.tsx
│   │   ├── DashboardView.tsx
│   │   ├── DetailView.tsx
│   │   └── ReportsView.tsx (NEW)
│   ├── charts/
│   │   ├── ScoreCard.tsx (NEW)
│   │   ├── EducationChart.tsx (NEW)
│   │   ├── ResearchChart.tsx (NEW)
│   │   ├── ExperienceTimeline.tsx (NEW)
│   │   ├── SkillsMatrix.tsx (NEW)
│   │   ├── TopicDistribution.tsx (NEW)
│   │   └── CollaborationNetwork.tsx (NEW - optional)
│   ├── tables/
│   │   ├── CandidateComparison.tsx (NEW)
│   │   ├── PublicationTable.tsx (NEW)
│   │   ├── SkillsTable.tsx (NEW)
│   │   └── MissingInfoTable.tsx (NEW)
│   └── shared/
│       ├── StatusBadge.tsx
│       ├── ScoreBadge.tsx
│       ├── LoadingSpinner.tsx
│       └── Modal.tsx (NEW)
├── hooks/
│   ├── useApi.ts (NEW)
│   ├── useAuth.ts (NEW - if needed)
│   └── usePagination.ts (NEW)
├── services/
│   ├── api.ts (NEW - centralized API client)
│   └── chart-utils.ts (NEW)
├── types/
│   ├── index.ts (enhanced)
│   └── api.ts (NEW)
└── App.tsx (with routing)
```

#### 3F.2: Core Dashboard Features

**Dashboard Layout (Wire structure):**
```
┌─ Navigation Bar ──────────────────────────────┐
│  TALASH | Upload | Dashboard | Reports       │
└───────────────────────────────────────────────┘

┌─ Summary Cards (Row 1) ────────────────────────┐
│ ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐       │
│ │Total │  │ Avg  │  │Top   │  │Below │       │
│ │Cands │  │Score │  │Score │  │Avg   │       │
│ │  12  │  │  7.5 │  │ 9.2  │  │  5.1 │       │
│ └──────┘  └──────┘  └──────┘  └──────┘       │
└───────────────────────────────────────────────┘

┌─ Filters & Controls (Row 2) ───────────────────┐
│ [Search] [Filter by Status ▾] [Sort By ▾]    │
│ [Export to CSV] [Export to PDF]               │
└───────────────────────────────────────────────┘

┌─ Candidate Comparison Table (Row 3) ──────────┐
│ Name | Email | Status | Education | Exp | Res│
│      |       |        | Score     |Score|Score│
│ [Rows with pagination]                        │
└───────────────────────────────────────────────┘

┌─ Score Distribution Chart (Row 4) ────────────┐
│     ╱╲                                        │
│    ╱  ╲   Overall Score Distribution           │
│   ╱    ╲  [Bar chart: 9.0-10 | 8-9 | 7-8...]│
│  ╱      ╲ N = 12 candidates                   │
└───────────────────────────────────────────────┘
```

**Key Components to Build:**

1. **ScoreCard Component** (reusable)
```typescript
interface ScoreCardProps {
  title: string;
  score: number;
  maxScore?: number;
  color?: "success" | "warning" | "danger";
  icon?: React.ReactNode;
}

export const ScoreCard: React.FC<ScoreCardProps> = ({ title, score, ... }) => {
  const percentage = (score / (maxScore || 10)) * 100;
  const bgColor = percentage >= 8 ? "green" : percentage >= 6 ? "yellow" : "red";
  
  return (
    <div className={`score-card score-${bgColor}`}>
      <h3>{title}</h3>
      <div className="score-display">{score}/10</div>
      <div className="progress-bar">
        <div style={{width: `${percentage}%`}}/>
      </div>
    </div>
  );
};
```

2. **Research Publication Breakdown Chart** (using Chart.js or Recharts)
```typescript
interface ResearchChartProps {
  journals: { count: number; q1: number; q2: number; q3: number; q4: number };
  conferences: { count: number; aStar: number; aRank: number; bRank: number };
}

export const ResearchChart: React.FC<ResearchChartProps> = ({ journals, conferences }) => {
  // Pie chart: J1 25%, J2 15%, J3 10%, J4 5%, Conf-A* 30%, Conf-A 15%
};
```

3. **Topic Variability Visualization**
```typescript
interface TopicChartProps {
  topics: Array<{ name: string; count: number; percentage: number }>;
  diversityScore: number;
}

export const TopicChart: React.FC<TopicChartProps> = ({ topics, diversityScore }) => {
  // Pie/Donut chart with diversity score badge
};
```

4. **Skills Alignment Matrix**
```typescript
interface SkillsMatrixProps {
  skills: Array<{
    name: string;
    workEvidenced: boolean;
    researchEvidenced: boolean;
    evidenceStrength: "Strong" | "Partial" | "Weak" | "Unsupported";
  }>;
}

export const SkillsMatrix: React.FC<SkillsMatrixProps> = ({ skills }) => {
  // Table with color-coded evidence columns
};
```

5. **Candidate Comparison Table**
```typescript
const CandidateComparisonTable: React.FC<{ candidates: DashCandidate[] }> = (...) => {
  // Table with sortable columns, filters
  // Columns: Name, Email, Education Score, Research Score, Experience Score, Overall, Actions
};
```

---

#### 3F.3: Detail View Enhancements

**Current:** `CandidateDetailView.tsx`  
**Enhance to include:**

```typescript
export const CandidateDetailView: React.FC<{ candidateId: number }> = (...) => {
  const [detail, setDetail] = useState<CandidateDetail>(null);
  const [activeTab, setActiveTab] = useState<
    "overview" | "education" | "experience" | "research" | "skills" | "reports"
  >("overview");
  
  return (
    <div className="detail-view">
      {/* Tabs */}
      <div className="tabs">
        <Tab name="Overview" onClick={() => setActiveTab("overview")} />
        <Tab name="Education" onClick={() => setActiveTab("education")} />
        <Tab name="Experience" onClick={() => setActiveTab("experience")} />
        <Tab name="Research" onClick={() => setActiveTab("research")} />
        <Tab name="Skills" onClick={() => setActiveTab("skills")} />
        <Tab name="Reports" onClick={() => setActiveTab("reports")} />
      </div>
      
      {/* Tab Content */}
      {activeTab === "overview" && <OverviewTab {...detail} />}
      {activeTab === "education" && <EducationTab {...detail} />}
      {activeTab === "experience" && <ExperienceTab {...detail} />}
      {activeTab === "research" && <ResearchTab {...detail} />}
      {activeTab === "skills" && <SkillsTab {...detail} />}
      {activeTab === "reports" && <ReportsTab {...detail} />}
    </div>
  );
};
```

**OverviewTab Content:**
```
┌─ Candidate Header ────────────────────┐
│ Name: Dr. Ahmed Hassan                │
│ Email: ahmed@example.com              │
│ Phone: +92-300-1234567               │
│ Location: Lahore, Pakistan           │
│ Status: ✅ Completed                 │
└───────────────────────────────────────┘

┌─ Score Summary (4 cards) ──────────────┐
│ Education: 8.5  │  Experience: 7.2    │
│ Research: 8.9   │  Skills: 7.5        │
│ ────────────────────────────────────  │
│ OVERALL SCORE: 8.0                    │
└───────────────────────────────────────┘

┌─ Executive Summary ────────────────────┐
│ Dr. Ahmed Hassan is a highly qualified│
│ academic candidate with strong        │
│ research output in machine learning...│
│                                       │
│ [Full paragraph text...]              │
└───────────────────────────────────────┘

┌─ Key Strengths & Concerns ────────────┐
│ ✓ Strong publication record (25 papers)
│ ✓ Mature research network (40+ coauthors)
│ ✓ Good institutional background (MIT)  │
│ ⚠ Small supervison record (2 students)│
│ ⚠ Recent graduate (2 yrs experience)  │
└───────────────────────────────────────┘

┌─ Missing Information ─────────────────┐
│ ⚠ Supervision details not provided    │
│ ⚠ Patent information not found        │
│ [Draft email button]                  │
└───────────────────────────────────────┘
```

**ResearchTab Content:**
```
┌─ Publication Quality Charts ──────────┐
│  Journals                              │
│  ┌─────────────────────────────────┐  │
│  │ Q1 ████████ 8 papers           │  │
│  │ Q2 ███████ 7 papers            │  │
│  │ Q3 ███ 3 papers                │  │
│  │ Q4 ██ 2 papers                 │  │
│  │ Unranked █ 1 paper             │  │
│  └─────────────────────────────────┘  │
│                                       │
│  Conferences                           │
│  ┌─────────────────────────────────┐  │
│  │ A* ██████ 4 papers             │  │
│  │ A  ████ 3 papers               │  │
│  │ B  ██████ 5 papers             │  │
│  │ C  ██ 2 papers                 │  │
│  └─────────────────────────────────┘  │
└───────────────────────────────────────┘

┌─ Topic Distribution ──────────────────┐
│           Research Topics              │
│        Machine Learning               │
│            /    \                     │
│          35%    30%                   │
│          ML    NLP                    │
│                                       │
│       Diversity Score: 0.62 (Moderate)│
└───────────────────────────────────────┘

┌─ Publications Table ──────────────────┐
│ Title | Venue | Year | Quartile | Auth│
│       |       |      |          |Role │
│ [clickable rows → full details]       │
└───────────────────────────────────────┘

┌─ Co-author Network ───────────────────┐
│  [Interactive graph showing authors]  │
│  Node size = collaboration frequency  │
│  Color = collaboration strength       │
└───────────────────────────────────────┘
```

---

### PHASE 3G: API ENHANCEMENTS (Week 3)

#### 3G.1: New Endpoints Required

```python
# Analysis Endpoints
POST   /analysis/research/{candidate_id}          # Run research analysis
GET    /analysis/research/{candidate_id}          # Get research results
POST   /analysis/research/batch                   # Batch research analysis

POST   /analysis/supervision/{candidate_id}       # Run supervision analysis
GET    /analysis/supervision/{candidate_id}       # Get supervision results

POST   /analysis/skills/{candidate_id}            # Run skills analysis
GET    /analysis/skills/{candidate_id}            # Get skills results
POST   /analysis/skills/batch                     # Batch skills analysis

POST   /analysis/full-pipeline/{candidate_id}     # Run all analyses sequentially
POST   /analysis/full-pipeline/batch              # Batch full pipeline

# Candidate Management Endpoints
GET    /candidates                                 # List all candidates (with pagination)
GET    /candidates/{candidate_id}                  # Get full candidate details
GET    /candidates/{candidate_id}/summary          # Get candidate summary
DELETE /candidates/{candidate_id}                  # Delete candidate

# Reporting Endpoints
GET    /reports/dashboard                         # Dashboard data
GET    /reports/comparison                        # Multi-candidate comparison
GET    /reports/export/pdf/{candidate_id}         # Export PDF report
GET    /reports/export/excel/batch                # Batch Excel export

# Missing Information Endpoints
GET    /missing-info/{candidate_id}               # Get missing info requests
POST   /missing-info/{candidate_id}/draft         # Generate draft email
POST   /missing-info/{candidate_id}/send          # Send email
GET    /missing-info/{candidate_id}/history       # Get email history

# Task Monitoring
GET    /tasks/{task_id}/status                    # Check task status
GET    /tasks/{task_id}/logs                      # Get task execution logs
POST   /tasks/{task_id}/cancel                    # Cancel running task
```

---

### PHASE 3H: EXCEL & PDF EXPORT (Week 3-4)

#### 3H.1: Excel Export Service

**File**: NEW `backend/app/services/excel_exporter.py` (already partially exists)

**Sheets Required:**
1. **Summary Sheet**
   - Candidate name, email, contact
   - Overall scores (education, experience, research, skills)
   - Summary text
   - Status flags

2. **Education Sheet**
   - Institution, degree, marks/CGPA
   - Ranking information
   - Gap analysis
   - Progression assessment

3. **Experience Sheet**
   - Job titles, organizations, dates
   - Employment type
   - Career progression
   - Gap analysis

4. **Publications Sheet**
   - Journal and conference papers (separate tabs or grouped)
   - Metadata (ISSN, DOI, quartile, indexing)
   - Authorship role
   - Topic assignment

5. **Skills Sheet**
   - Skill name, category, evidence strength
   - Work evidence, research evidence

6. **Supervision, Books, Patents** (optional)

#### 3H.2: PDF Report Generation

**File**: NEW `backend/app/services/pdf_exporter.py`

**Use Library**: `reportlab` or `weasyprint`

**Template:**
```
┌─────────────────────────────────────┐
│        TALASH CANDIDATE REPORT       │
│    Talent Acquisition & Learning    │
│   Automation for Smart Hiring       │
└─────────────────────────────────────┘

Date: May 15, 2026
Candidate: Dr. Ahmed Hassan
Report Version: 1.0

═══════════════════════════════════════
EXECUTIVE SUMMARY
═══════════════════════════════════════

Dr. Ahmed Hassan is a highly qualified academic...

Overall Assessment Score: 8.0/10

Key Strengths:
- Strong publication record
- Excellent educational background
- Relevant professional experience

Areas for Discussion:
- Supervision experience

═══════════════════════════════════════
DETAILED ANALYSIS
═══════════════════════════════════════

1. EDUCATIONAL PROFILE
   Score: 8.5/10
   [Details...]

2. PROFESSIONAL EXPERIENCE
   Score: 7.2/10
   [Details...]

3. RESEARCH PROFILE
   Score: 8.9/10
   [Details with charts...]

4. SKILLS ASSESSMENT
   Score: 7.5/10
   [Details...]

═══════════════════════════════════════
RECOMMENDATIONS
═══════════════════════════════════════

Suitable for: [Faculty positions in ML/AI]
Suitable experience level: [Senior Lecturer]
Recommended for: [Shortlist/Interview]

═══════════════════════════════════════
APPENDIX: DETAILED DATA
═══════════════════════════════════════

[Tables of all extracted data]
```

---

## ARCHITECTURE DECISIONS & DESIGN PATTERNS

### Design Pattern: Service Layer Pattern

**Benefits:**
- Separation of concerns (API logic vs business logic)
- Testability (services can be tested independently)
- Reusability (services used by multiple routers)
- Maintainability

**Structure:**
```
routers/                    # FastAPI routes (thin, just HTTP handling)
  ├── upload.py
  ├── analysis_router.py
  └── admin.py

services/                   # Business logic (thick, detailed implementation)
  ├── extractor.py         # CV extraction
  ├── education_analysis.py
  ├── experience_analysis.py
  ├── research_analysis.py
  ├── supervision_analysis.py
  ├── skills_analysis.py
  ├── summary_generator.py
  ├── missing_information_service.py
  ├── topic_analysis.py
  ├── collaboration_analysis.py
  ├── skill_alignment.py
  └── excel_exporter.py
```

**Pattern:** `Service → Database Models → ORM (SQLAlchemy)`

### Design Pattern: LLM Router Pattern

**Current Implementation:** `llm_router.py`

**Supports Multiple Providers:**
- OpenRouter (Free Tier)
- Groq (High speed, free tier)
- Google Gemini (Free tier)
- Ollama (Local deployment)

**Usage:**
```python
from app.services.llm_router import llm_router

# Structured output (Pydantic models)
client, model = llm_router.get_structured_client()
response = client.beta.messages.create(
    model=model,
    max_tokens=1024,
    response_model=CandidateExtraction,
    messages=[{"role": "user", "content": cv_text}]
)

# Text output
response_text = analysis_llm_call(prompt, context_json)
```

**Key Advantage:** Easy provider switching via environment variable

### Design Pattern: Async/Await for External APIs

**Used in:**
- `research_enrichment.py` — Crossref, OpenAlex
- `qs_lookup.py` — Could be async
- `core_lookup.py` — Could be async

**Pattern:**
```python
async def enrich_publication(pub: JournalPublication) -> JournalPublication:
    """Async enrichment with timeout handling"""
    try:
        async with aiohttp.ClientSession() as session:
            wos_status = await verify_wos_indexing(session, pub.issn)
            scopus_status = await verify_scopus_indexing(session, pub.issn)
            impact_factor = await get_impact_factor(session, pub.issn)
            
        pub.wos_indexed = wos_status
        pub.scopus_indexed = scopus_status
        pub.impact_factor = impact_factor
        return pub
    except asyncio.TimeoutError:
        logger.warning(f"Timeout enriching publication {pub.id}")
        return pub  # Return with partial data
    except Exception as e:
        logger.error(f"Error enriching {pub.id}: {e}")
        return pub
```

### Design Pattern: Celery Task Orchestration

**Sequential Pipeline with Celery Chains:**
```python
from celery import chain

pipeline = chain(
    task1.s(arg1),           # Task 1
    task2.s(arg1),           # Task 2 waits for Task 1
    task3.s(arg1),           # Task 3 waits for Task 2
)
result = pipeline.apply_async()
```

**Parallel Processing with Celery Groups:**
```python
from celery import group

# Process multiple candidates in parallel
jobs = group([analyze_candidate.s(cid) for cid in candidate_ids])
result = jobs.apply_async()
```

**Error Handling:**
```python
@celery_app.task(bind=True, max_retries=3)
def analyze_candidate(self, candidate_id):
    try:
        # ... analysis logic
    except Exception as exc:
        # Retry up to 3 times with exponential backoff
        raise self.retry(exc=exc, countdown=60 * 2 ** self.request.retries)
```

---

## DATABASE & DATA FLOW

### Data Flow Diagram

```
1. CV UPLOAD
   ┌─────────────┐
   │ PDF File    │
   └──────┬──────┘
          │
          ↓
   ┌──────────────────────┐
   │ Hash Check           │
   │ (Duplicate Detection)│
   └──────┬───────────────┘
          │
          ↓ (Not duplicate)
   ┌──────────────────────┐
   │ Save to Disk         │
   │ Create DB Record     │
   │ Queue Celery Task    │
   └──────┬───────────────┘

2. EXTRACTION (Worker)
   ┌──────────────────────┐
   │ Extract Text (PyMuPDF)
   │ Sanitize             │
   └──────┬───────────────┘
          │
          ↓
   ┌──────────────────────┐
   │ LLM Extraction       │
   │ (OpenRouter)         │
   │ Pydantic Validation  │
   └──────┬───────────────┘
          │
          ↓
   ┌──────────────────────┐
   │ Parse & Insert:      │
   │ - Education          │
   │ - Experience         │
   │ - Publications       │
   │ - Skills             │
   │ - Books/Patents      │
   └──────┬───────────────┘

3. ANALYSIS (Chain of Tasks)
   ┌──────────────────────┐      ┌──────────────────────┐
   │ Education Analysis   │ ───→ │ Gap Detection        │
   │ (Groq LLM)          │      │ QS Ranking Lookup    │
   └──────────────────────┘      └──────────────────────┘
          │
          ↓
   ┌──────────────────────┐      ┌──────────────────────┐
   │ Experience Analysis  │ ───→ │ Timeline Analysis    │
   │ (Groq LLM)          │      │ Career Progression   │
   └──────────────────────┘      └──────────────────────┘
          │
          ↓
   ┌──────────────────────┐      ┌──────────────────────┐
   │ Research Analysis    │ ───→ │ Journal Scoring      │
   │ (Groq LLM)          │      │ Conference Ranking   │
   │ + Research Enrichment│      │ Topic Clustering     │
   │ (Async APIs)        │      │ Co-author Analysis   │
   └──────────────────────┘      └──────────────────────┘
          │
          ↓
   ┌──────────────────────┐
   │ Summary Generation   │
   │ (Groq LLM)          │
   │ Overall Ranking     │
   └──────────────────────┘
          │
          ↓
   ┌──────────────────────┐
   │ Missing Info Email   │
   │ Generation          │
   └──────────────────────┘

4. FRONTEND ACCESS
   ┌──────────────────────┐
   │ /analysis/dashboard  │ ───→ Dashboard View
   │ /candidates/{id}     │ ───→ Detail View
   │ /reports/export      │ ───→ PDF/Excel
   └──────────────────────┘
```

### Database Normalization & Foreign Keys

**Fully normalized 3NF schema:**

```
Candidate (root entity)
├── EducationRecord (1:M) — education_records
├── WorkExperience (1:M) — work_experiences
├── JournalPublication (1:M) — journal_publications
├── ConferencePublication (1:M) — conference_publications
├── SupervisionRecord (1:M) — supervision_records
├── Book (1:M) — books
├── Patent (1:M) — patents
├── Skill (1:M) — skills
├── EducationGap (1:M) — education_gaps
├── EmploymentGap (1:M) — employment_gaps
├── InstitutionRanking (1:M) — institution_rankings
├── TopicCluster (1:M) — topic_clusters
├── CollaborationEdge (1:M) — collaboration_edges
├── CandidateAssessment (1:M) — candidate_assessments
└── MissingInformationRequest (1:M) — missing_information_requests
```

---

## FRONTEND IMPLEMENTATION DETAILS

### React Component Hierarchy

```
App
├── Navigation
├── Router / View Management
└── Main Content Area
    ├── UploadView
    │   ├── DragDropZone
    │   └── FileList
    ├── DashboardView
    │   ├── SummaryCards (4x)
    │   ├── FilterRow
    │   └── CandidateComparisonTable
    │       └── Pagination
    ├── DetailView
    │   ├── DetailHeader
    │   ├── ScoreSummary
    │   ├── TabNavigation
    │   └── TabContent (dynamic)
    │       ├── OverviewTab
    │       ├── EducationTab
    │       ├── ExperienceTab
    │       ├── ResearchTab
    │       │   ├── PublicationQualityChart
    │       │   ├── TopicDistributionChart
    │       │   ├── PublicationTable
    │       │   └── CollaborationNetwork (optional)
    │       ├── SkillsTab
    │       │   └── SkillsMatrix
    │       └── ReportsTab
    │           ├── ExportButtons
    │           └── DraftEmailPreview
    └── LoadingSpinner
```

### Styling Strategy

**Current**: Plain CSS in `index.css`  
**Recommendation**: Keep it simple, extend existing

```css
/* Color Scheme */
:root {
  --primary: #2563eb;      /* Blue */
  --success: #10b981;      /* Green */
  --warning: #f59e0b;      /* Amber */
  --danger: #ef4444;       /* Red */
  --dark: #1f2937;         /* Dark Gray */
  --light: #f3f4f6;        /* Light Gray */
  --text-primary: #111827;
  --text-secondary: #6b7280;
  --text-muted: #9ca3af;
  --border: #e5e7eb;
}

/* Score-based Colors */
.score-excellent { color: var(--success); }      /* 8.5-10 */
.score-good { color: var(--primary); }           /* 7.0-8.5 */
.score-fair { color: var(--warning); }           /* 5.5-7.0 */
.score-poor { color: var(--danger); }            /* <5.5 */
```

### Responsive Design

```css
/* Breakpoints */
@media (max-width: 768px) {
  .table { font-size: 12px; }
  .score-card { flex: 1 1 100%; }
  .chart { height: 300px; }
}
```

---

## BACKEND ENHANCEMENT REQUIREMENTS

### LLM Optimization

**Current Issue:** Free tier APIs have rate limits & costs  
**Solutions:**

1. **Response Caching**
   ```python
   @functools.lru_cache(maxsize=1000)
   def get_journal_quartile(issn: str) -> Optional[str]:
       """Cache journal lookups for 24 hours"""
   ```

2. **Batch Processing**
   ```python
   def batch_enrich_publications(pubs: list[JournalPublication]) -> list[JournalPublication]:
       """Batch API calls to reduce overhead"""
   ```

3. **Fallback Logic**
   ```python
   def get_journal_info(issn: str):
       try:
           return wos_api.lookup(issn)  # Primary
       except:
           return scopus_api.lookup(issn)  # Secondary
       except:
           return cached_db.lookup(issn)  # Fallback
   ```

### Error Handling & Validation

**Implement comprehensive error tracking:**
```python
class ExtractionError(Exception):
    """Custom exception for extraction failures"""
    def __init__(self, candidate_id: int, module: str, reason: str):
        self.candidate_id = candidate_id
        self.module = module
        self.reason = reason

class ExtractionRun(Base):
    # Already in schema:
    status = Column(String(50))  # "started", "completed", "failed"
    error_message = Column(Text)
    parsed_ok = Column(Boolean)
```

**Validation rules:**
- CGPA must be 0-4.0 or normalized
- Marks must be 0-100
- Years must be 1900-2099
- Email must match regex pattern
- Phone must be 10-15 digits
- DOI format: 10.xxxx/yyyy

### Database Query Optimization

**Add indexes for common queries:**
```python
# In models.py
class Candidate(Base):
    __table_args__ = (
        Index('idx_candidate_status', 'status'),
        Index('idx_candidate_email', 'email'),
        Index('idx_candidate_created_at', 'created_at'),
    )

class JournalPublication(Base):
    __table_args__ = (
        Index('idx_jp_candidate_wos', 'candidate_id', 'wos_indexed'),
        Index('idx_jp_candidate_quartile', 'candidate_id', 'quartile'),
    )
```

---

## TESTING & VALIDATION STRATEGY

### Unit Tests

**File Structure:**
```
tests/
├── unit/
│   ├── test_education_analysis.py
│   ├── test_experience_analysis.py
│   ├── test_research_analysis.py
│   ├── test_skill_alignment.py
│   └── test_excel_exporter.py
└── integration/
    ├── test_end_to_end_pipeline.py
    └── test_api_endpoints.py
```

**Example Test:**
```python
def test_cgpa_normalization():
    from app.services.education_analysis import _normalise_cgpa
    
    # Test CGPA on 4.0 scale
    assert _normalise_cgpa(3.5, 4.0, None) == 3.5
    
    # Test CGPA on 5.0 scale
    assert _normalise_cgpa(3.5, 5.0, None) == 2.8
    
    # Test marks percentage
    assert _normalise_cgpa(None, None, 85.0) == 3.4
```

### Integration Tests

**Test full pipeline with sample CVs:**
```python
def test_full_pipeline():
    """End-to-end test with sample CV"""
    db = SessionLocal()
    
    # Upload sample CV
    cv_path = "test_data/sample_cv.pdf"
    candidate = create_candidate_from_file(cv_path, db)
    
    # Run full pipeline
    run_full_pipeline(candidate.id)
    
    # Verify results
    assert candidate.status == "completed"
    assert len(candidate.education_records) > 0
    assert len(candidate.work_experiences) > 0
    assert candidate.summary is not None
```

### Regression Testing

**Track API responses against baseline:**
```python
def test_dashboard_api():
    """Verify dashboard endpoint returns expected structure"""
    response = client.get("/analysis/dashboard")
    
    assert response.status_code == 200
    data = response.json()
    assert "candidates" in data
    assert isinstance(data["candidates"], list)
    if data["candidates"]:
        c = data["candidates"][0]
        assert all(k in c for k in ["candidate_id", "name", "status", "overall_rank"])
```

---

## DEPLOYMENT & DEVOPS

### Docker Compose Enhancements

**Current Setup:** ✅ Mostly good

**Recommended Additions:**
```yaml
services:
  # Add PgAdmin for database management
  pgadmin:
    image: dpage/pgadmin4:latest
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@admin.com
      PGADMIN_DEFAULT_PASSWORD: admin
    ports:
      - "5050:80"
    depends_on:
      - db

  # Add Prometheus for monitoring (optional)
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
```

### Environment Variables

**Create `.env` file:**
```bash
# Database
DATABASE_URL=postgresql+psycopg2://talash:talash@db:5432/talash
REDIS_URL=redis://redis:6379/0

# LLM Configuration
LLM_PROVIDER=openrouter  # or groq, gemini, ollama
OPENROUTER_API_KEY=sk-xxxxx
GROQ_API_KEY=gsk-xxxxx
GEMINI_API_KEY=xxxxx

# External APIs
CROSSREF_EMAIL=your-email@example.com  # Required by Crossref API

# Security
SECRET_KEY=your-secret-key-here
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Logging
LOG_LEVEL=INFO
DEBUG=False

# Frontend
REACT_APP_API_URL=http://localhost:8000
```

### Production Checklist

- [ ] Database backups configured
- [ ] SSL/HTTPS enabled (nginx reverse proxy)
- [ ] Rate limiting implemented
- [ ] Error monitoring (Sentry or similar)
- [ ] Application metrics (Prometheus)
- [ ] Logging aggregation (ELK stack)
- [ ] Database connection pooling
- [ ] Celery task monitoring (Flower)
- [ ] API documentation (Swagger UI)
- [ ] Security headers configured

---

## RISK ASSESSMENT & MITIGATION

### High-Risk Areas

| Risk | Impact | Probability | Mitigation |
|------|--------|------------|-----------|
| LLM API cost overruns | Budget exceeded | Medium | Implement caching, batch processing, rate limiting |
| Research data verification timeout | Slow analysis | Medium | Async + timeout handling, partial data acceptance |
| Database performance degradation | Slow queries | Low | Index optimization, query analysis |
| Missing publication data | Incomplete analysis | Medium | Email generation for missing info, data sampling |
| Email delivery failure | Communication breaks | Low | Retry logic, fallback notification methods |
| Duplicate CV processing | Incorrect results | Low | File hash verification (already done) |

### Data Quality Issues

**Issue:** Different candidates report same publication differently  
**Mitigation:**
- Store original extracted values
- Normalize publication data (DOI, ISSN matching)
- Flag conflicting metadata

**Issue:** Education/experience dates incomplete or incorrect  
**Mitigation:**
- Use "nullable but preferred" approach
- Offer email-based clarification
- Display confidence scores

---

## TIMELINE & MILESTONES

### Week-by-Week Breakdown

**WEEK 1: Research Profile Analysis (Complete Modules 3A)**
- [ ] Monday-Tuesday: Journal scoring + WoS/Scopus verification
- [ ] Tuesday-Wednesday: Conference ranking (A*, CORE)
- [ ] Wednesday-Thursday: Topic clustering & diversity scoring
- [ ] Thursday-Friday: Co-author analysis & collaboration patterns
- [ ] Friday: Testing & code review

**WEEK 2: Remaining Analysis Modules (3B-3E)**
- [ ] Monday: Supervision, books, patents modules
- [ ] Monday-Tuesday: Skill alignment service
- [ ] Tuesday-Wednesday: Missing information email generation ⭐ CRITICAL
- [ ] Wednesday-Thursday: Batch analysis endpoints & Celery orchestration
- [ ] Thursday-Friday: Testing & debugging

**WEEK 3: Frontend Dashboard & Visualization (3F)**
- [ ] Monday: Component structure reorganization
- [ ] Monday-Tuesday: Score cards & summary cards
- [ ] Tuesday-Wednesday: Charts (education, research, skills, topics)
- [ ] Wednesday-Thursday: Comparison tables & detail views
- [ ] Thursday-Friday: Styling, responsiveness, testing

**WEEK 4: Export, Polish, Documentation (3G-3H)**
- [ ] Monday: Excel & PDF export services
- [ ] Monday-Tuesday: API documentation (Swagger)
- [ ] Tuesday-Wednesday: Database schema documentation
- [ ] Wednesday-Thursday: Integration testing & end-to-end verification
- [ ] Thursday-Friday: Final polish, demo preparation

### Deliverables Checklist

**By End of Week 1:**
- [ ] All research analysis modules implemented
- [ ] Publication quality scoring working
- [ ] Topic clustering functioning
- [ ] Co-author analysis complete

**By End of Week 2:**
- [ ] Supervision, books, patents modules
- [ ] Skill alignment service
- [ ] Missing information email generation (CRITICAL)
- [ ] Full pipeline orchestration with Celery
- [ ] All backend logic complete

**By End of Week 3:**
- [ ] Complete React frontend with all views
- [ ] All charts and visualizations
- [ ] Dashboard fully functional
- [ ] Detail views with all tabs
- [ ] Responsive design working

**By End of Week 4:**
- [ ] PDF/Excel export working
- [ ] Complete API documentation
- [ ] All tests passing
- [ ] Docker containers ready for deployment
- [ ] Demo scenario prepared

---

## QUICK REFERENCE: KEY FILES TO EDIT/CREATE

### BACKEND FILES TO MODIFY

```python
# Analysis Services (MODIFY)
backend/app/services/research_analysis.py      # Add journal/conference scoring
backend/app/services/education_analysis.py     # Enhance gap analysis
backend/app/services/experience_analysis.py    # Enhance timeline analysis
backend/app/services/summary_generator.py      # Enhance weighting

# NEW Analysis Services (CREATE)
backend/app/services/topic_analysis.py
backend/app/services/collaboration_analysis.py
backend/app/services/supervision_analysis.py
backend/app/services/skill_alignment.py
backend/app/services/missing_information_service.py
backend/app/services/pdf_exporter.py

# API Routes (MODIFY)
backend/app/routers/analysis_router.py         # Add batch endpoints

# Worker Tasks (MODIFY)
backend/worker/cv_tasks.py                     # Add orchestration chains
```

### FRONTEND FILES TO MODIFY/CREATE

```typescript
// MODIFY
frontend/src/App.tsx                           # Add ReportsView
frontend/src/types.ts                          # Extend interfaces

// CREATE Components
frontend/src/components/views/ReportsView.tsx
frontend/src/components/charts/ScoreCard.tsx
frontend/src/components/charts/ResearchChart.tsx
frontend/src/components/charts/TopicChart.tsx
frontend/src/components/tables/CandidateComparison.tsx
frontend/src/components/tables/PublicationTable.tsx
frontend/src/services/api.ts
frontend/src/hooks/useApi.ts
```

---

## NEXT STEPS

1. **Immediate**: Create session notes with implementation checklist
2. **This Week**: Start Week 1 tasks (research analysis)
3. **Next Week**: Begin frontend work (parallel to backend)
4. **Final Week**: Integration, testing, deployment

---

**Document Status**: Complete Phase 3 Implementation Plan  
**Last Updated**: May 11, 2026  
**Author**: TALASH Development Team  
**Approval**: Pending Instructor Review
