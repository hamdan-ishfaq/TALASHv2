# TALASH v3 - CV Extraction Schema Updates

## Overview
Updated `backend/app/schemas/extraction.py` to comprehensively capture all CV data specified in the detailed extraction requirements. The schema now includes explicit LLM instructions to prevent data loss on complex fields and supports all 8 sections of CV analysis.

---

## 1. NEW ENUM: InstitutionType

**Purpose:** Distinguish between School Boards (SSE/HSSC) and Universities (UG/PG/PhD)
**Required for:** Section 3.1 - QS/THE Rankings verification

```python
class InstitutionType(str, Enum):
    SCHOOL_BOARD = "School Board"
    UNIVERSITY = "University"
    COLLEGE = "College"
    TECHNICAL_INSTITUTE = "Technical Institute"
    OTHER = "Other"
```

---

## 2. PERSONAL INFORMATION - CandidateExtraction

### New Fields Added:
| Field | Type | Purpose | Critical For |
|-------|------|---------|--------------|
| `phone` | Optional[str] | Contact number | Verification, Section 4 |
| `linkedin_url` | Optional[str] | LinkedIn profile link | Professional verification |
| `personal_website` | Optional[str] | Portfolio/personal website | Profile verification |
| `other_urls` | Optional[str] | GitHub, ResearchGate, Google Scholar, etc. | Github stars, publication tracking |

### Enhanced:
- `name`: Now explicitly extracted "exactly as stated on the CV"
- `email`: Emphasized as "CRUCIAL for Section 4 (drafting missing-info emails)"
- `summary_of_profile`: Enhanced instruction to focus on key strengths and unique qualities in 2-3 paragraphs

---

## 3. EDUCATION RECORDS - EducationRecordExtraction

### New Fields Added:
| Field | Type | Purpose |
|-------|------|---------|
| `institution_type` | Optional[InstitutionType] | CRUCIAL: Distinguish School Board vs University |
| `start_month` | Optional[int] | Month (1-12) for precise gap calculation |
| `end_month` | Optional[int] | Month (1-12) for precise gap calculation |

### Enhanced:
- `degree_title`: Now emphasizes exact format extraction (e.g., "BS Computer Science")
- `specialization`: Clarifies to extract major/subject specialization
- `institution`: Emphasized as "exact name as it appears on the CV"
- `start_year` / `end_year`: Now marked as "CRUCIAL for gap and overlap detection"
- `marks_percentage`: Clarified as 0-100 scale
- `cgpa_scale`: Added instruction to infer from context if not mentioned

---

## 4. WORK EXPERIENCE - WorkExperienceExtraction

### CRITICAL NEW FIELD:
```python
job_responsibilities: Optional[str] = Field(
    None, 
    description="Complete job description, responsibilities, and achievements listed for this role. 
    CRUCIAL: This text is used in Section 3.9 to determine if claimed skills are actually backed up 
    by work experience. Extract all bullet points or narrative description verbatim."
)
```
**Why Critical:** Section 3.9 compares this against claimed skills to verify if skills are actually evidenced.

### Updated Fields:
- Changed from `start_date`/`end_date` (date objects) to `start_month`/`start_year` and `end_month`/`end_year` (integers)
  - **Reason:** Allows precise month-level gap detection and better overlap analysis
  - **Example:** "Jan 2020 - Mar 2024" → start_month=1, start_year=2020, end_month=3, end_year=2024

### Enhanced Instructions:
- `job_title`: "exactly as stated on the CV"
- `employment_type`: Added list of types (Full-time, Part-time, Contract, Internship, Research Assistant, Freelance)
- `is_current`: Enhanced to catch keywords like "Present", "Ongoing", "Currently"
- `is_academic_role`: Clarified examples (Assistant Professor, Researcher, Lecturer, Post-Doc)
- `overlaps_with_education`: Emphasized importance for simultaneous work-study scenarios

---

## 5. JOURNAL PUBLICATIONS - JournalPublicationExtraction

### New Fields Added:
| Field | Type | Purpose |
|-------|------|---------|
| `doi` | Optional[str] | Digital Object Identifier for verification |
| `volume` | Optional[str] | Journal volume number |
| `issue` | Optional[str] | Journal issue number |
| `pages` | Optional[str] | Page range or article number |

### Enhanced Instructions:
- `authors`: Emphasized as "ALL authors exactly as they appear" - crucial for co-author network analysis
- `journal_name`: Now requires "complete and exact name" (e.g., "IEEE Transactions on Pattern Analysis...")
- `issn`: Clarified to extract from CV if provided
- `wos_indexed` / `scopus_indexed`: Enhanced to check if explicitly mentioned OR recognizable by journal name
- `quartile`: **Marked as CRUCIAL for research ranking** in Section 3.2
- `authorship_role`: Enhanced instructions for determining role from author position
- `author_position`: Now numeric 1-indexed position in author list
- `topic_category`: Expanded examples (Machine Learning, Computer Vision, NLP, etc.)

---

## 6. CONFERENCE PUBLICATIONS - ConferencePublicationExtraction

### New Fields Added:
| Field | Type | Purpose |
|-------|------|---------|
| `conference_location` | Optional[str] | Geographic location of conference |
| `doi` | Optional[str] | DOI of conference paper |

### Enhanced Instructions:
- `authors`: "ALL authors in order, exactly as they appear" - crucial for network analysis
- `conference_name`: "complete and exact name" (e.g., "IEEE/CVF Conference on Computer Vision...")
- `conference_series`: Enhanced instruction to extract "28th", "2023rd" format if present
- `core_ranking`: **Marked as CRUCIAL for research ranking** (A* = top tier)
- `indexed_in`: Examples: Scopus, IEEE Xplore, ACM Digital Library, Springer, others
- `authorship_role`: Clarified role determination
- `topic_category`: Examples: Computer Vision, NLP, Robotics, etc.

---

## 7. STUDENT SUPERVISION - SupervisionRecordExtraction

### New Field Added:
```python
thesis_title: Optional[str] = Field(None, description="Title of the student's thesis or research project if mentioned on the CV.")
```

### Reordered for Clarity:
1. `student_name` (moved first for readability)
2. `student_level`
3. `completion_year`
4. `supervision_role`
5. `thesis_title` (NEW)
6. `publications_with_student`

---

## 8. BOOKS - BookExtraction

### Enhanced Instructions:
- `title`: Now requires "complete title exactly as listed on the CV"
- `authors`: "complete list of ALL authors in order" - crucial for co-authorship analysis
- `isbn`: Clarified as "ISBN-10 or ISBN-13"
- `publisher`: Added examples (Springer, IEEE, Academic Press)
- `year`: As integer
- `online_link`: Specified as "URL to book's page or online verification (Amazon, Google Books, publisher website)"
- `authorship_role`: Examples: Sole Author, Lead Author, Co-Author, Contributing Author

---

## 9. PATENTS - PatentExtraction

### New Field Added:
```python
date_granted: Optional[date] = Field(None, description="The date the patent was granted, if already granted.")
```

### Enhanced Instructions:
- `title`: "official title as listed on the CV"
- `inventors`: "ALL inventors in order exactly as they appear" - crucial for inventor network analysis
- `patent_no`: "Extract exactly as written" (e.g., "US12345678", "IN201721005678")
- `country_of_filing`: "List ALL countries if multiple" (USA, UK, China, International)
- `date_filed`: As date object if available
- `date_granted`: NEW - separate from filed date for granted patents
- `status`: Add missing "Expired" option alongside Granted, Pending, Filed
- `online_link`: Examples: USPTO, WIPO, Google Patents
- `inventor_role`: Examples: Lead Inventor, Co-Inventor, Contributing Innovator

---

## 10. SKILLS - SkillExtraction

### New Fields Added:
| Field | Type | Purpose |
|-------|------|---------|
| `proficiency_level` | Optional[str] | Beginner, Intermediate, Advanced, Expert |
| `years_of_experience` | Optional[int] | Years of experience with skill |
| `work_evidence` | Optional[str] | Specific job responsibility text demonstrating skill |
| `research_evidence` | Optional[str] | Publication titles/methods demonstrating skill |

### Enhanced Instructions:
- `name`: "exact name as listed on the CV" - examples provided
- `category`: Expanded options: Technical, Domain, Soft Skill, Other
- `proficiency_level`: Catch if mentioned (often not specified)
- `years_of_experience`: Extract from phrases like "5+ years of Python"
- `evidenced_in_work`: Should be true if skill appears in job descriptions
- `evidenced_in_research`: Should be true if skill aligns with publication methods
- `strength_of_evidence`: **CRITICAL synthesis logic:**
  - **Strongly Evidenced:** Appears in BOTH work AND research
  - **Partially Evidenced:** Appears in ONE (work or research)
  - **Weakly Evidenced:** Mentioned but not clearly backed up
  - **Unsupported:** Claimed but no evidence found

---

## Key Improvements for LLM Extraction

### 1. Explicit Field Descriptions
Each field now has:
- **What to extract:** Exact format and examples
- **Why it matters:** Critical section/analysis if applicable
- **How to extract:** Special parsing instructions for complex fields

### 2. Date/Time Precision
- Changed from `date` objects to separate `month`/`year` integers
- Allows precise month-level gap/overlap detection
- Prevents ambiguity (e.g., mid-year employment overlaps)

### 3. Complete Lists
- `authors`, `inventors`: Now explicitly "ALL" and "in order"
- Prevents partial extraction and enables network analysis

### 4. Evidence Tracking
- Skills now linked back to work descriptions and publications
- Publications linked to supervised students
- Work linked to education timeline

### 5. Standardization & Vocabulary
- Explicit enums for all categorical fields
- Prevents variations like "Full Time", "fulltime", "FT"
- Examples provided for each enum value

---

## Missing-Info Email Support (Section 4)

The schema now supports drafting emails by requiring:
1. **`email`** - Recipient address
2. **Complete name** - For salutation
3. **Contact info** - phone, linkedin for follow-up
4. **Profile summary** - To reference their strengths
5. **Skill gaps** - To ask about missing technical skills
6. **Experience gaps** - Dates to ask about employment breaks

---

## Cross-Reference Example

### Before:
- Skills extracted as simple list with no backing
- Publications extracted but not linked to supervision
- Experience extracted but responsibilities missing

### After:
Example: "Python" skill
```json
{
  "name": "Python",
  "category": "Technical",
  "proficiency_level": "Advanced",
  "years_of_experience": 7,
  "evidenced_in_work": true,
  "work_evidence": "Led development of data pipeline using Python pandas and scikit-learn",
  "evidenced_in_research": true,
  "research_evidence": "Machine Learning Models for CV Fraud Detection (2023, 2024)",
  "strength_of_evidence": "Strongly Evidenced"
}
```

---

## Files Modified
- **`backend/app/schemas/extraction.py`** - Complete overhaul with:
  - 1 new enum: `InstitutionType`
  - 10+ new fields across multiple models
  - Enhanced descriptions on 40+ existing fields
  - Better instructions for LLM extraction

---

## Deployment Notes

### For LLM Configuration:
When sending extraction prompts to the LLM (Groq/OpenRouter/Ollama), include:
1. The full Pydantic schema definition
2. Explicit instruction to extract ALL fields where data exists
3. Examples of correct extraction formats
4. Flag critical fields: email, institution, job_responsibilities, authors, inventors

### For Database Migrations:
The working database models may need updates if not already tracking:
- `phone` number in Candidate table
- `institution_type` in EducationRecord
- `job_responsibilities` in WorkExperience  
- `doi` in JournalPublication and ConferencePublication
- `proficiency_level`, `years_of_experience` in Skill

The current ORM models in `backend/app/models/models.py` may need enhancement to match this comprehensive schema.

---

## Next Steps

1. **Test with Llama 3.1 8B**: Run extraction against test CVs to verify all fields are captured
2. **Database Sync**: Verify ORM models align with new schema fields
3. **LLM Prompt Engineering**: Fine-tune extraction prompts to emphasize critical fields
4. **Validation Rules**: Add cross-field validation (e.g., authors should not be empty for publications)
5. **Missing-Info Generation**: Build logic to generate Section 4 missing-info email drafts based on extracted data
