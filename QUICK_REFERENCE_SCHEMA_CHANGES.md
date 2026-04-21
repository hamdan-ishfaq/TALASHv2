# ⚡ Quick Reference: Schema Updates Summary

## All NEW Fields Added (by Section)

### 1. PERSONAL INFORMATION
| Field | Type | Purpose |
|-------|------|---------|
| `phone` | Optional[str] | Contact number for verification & follow-up |
| `linkedin_url` | Optional[str] | LinkedIn profile verification |
| `personal_website` | Optional[str] | Portfolio/personal site link |
| `other_urls` | Optional[str] | GitHub, ResearchGate, Google Scholar links |

**Impact:** Section 4 (missing-info emails) now has complete contact info

---

### 2. EDUCATION RECORDS  
| Field | Type | Purpose |
|-------|------|---------|
| `institution_type` | Optional[InstitutionType] | CRUCIAL: School Board vs University for QS/THE rankings |
| `start_month` | Optional[int] | Precise month for gap calculation |
| `end_month` | Optional[int] | Precise month for gap calculation |

**Impact:** Section 3.1 - Precise gap detection and ranking validation

**Enum Added:**
```
InstitutionType: SCHOOL_BOARD, UNIVERSITY, COLLEGE, TECHNICAL_INSTITUTE, OTHER
```

---

### 3. WORK EXPERIENCE
| Field | Type | Notes |
|-------|------|-------|
| `job_responsibilities` | Optional[str] | ⚠️ **CRITICAL** - Complete job descriptions for skill validation |
| `start_month`/`end_month` | Optional[int] | Changed from date objects for precision |

**Impact:** Section 3.9 - This field is used to verify if claimed skills are actually backed by work

**Changed Fields:**
- `start_date`/`end_date` → `start_month`, `start_year`, `end_month`, `end_year` (integers)
  - Allows month-level gap and overlap detection
  - Example: "Jan 2020" = start_month=1, start_year=2020

---

### 4. JOURNAL PUBLICATIONS
| Field | Type | Purpose |
|-------|------|---------|
| `doi` | Optional[str] | Digital Object Identifier for verification |
| `volume` | Optional[str] | Journal volume number |
| `issue` | Optional[str] | Journal issue number |
| `pages` | Optional[str] | Page range or article number |

**Impact:** Section 3.2 & 3.6 - Better publication tracking and verification

---

### 5. CONFERENCE PUBLICATIONS
| Field | Type | Purpose |
|-------|------|---------|
| `conference_location` | Optional[str] | Where conference was held |
| `doi` | Optional[str] | Conference paper DOI |

**Impact:** Section 3.2 & 3.7 - Better venue verification

---

### 6. STUDENT SUPERVISION
| Field | Type | Purpose |
|-------|------|---------|
| `thesis_title` | Optional[str] | Title of student's thesis/research |

**Impact:** Section 3.3 - Better tracking of supervised research

---

### 7. PATENTS
| Field | Type | Purpose |
|-------|------|---------|
| `date_granted` | Optional[date] | Separate from filing date for granted patents |

**Impact:** Section 3.5 - Distinguish pending vs granted patents

---

### 8. SKILLS - Multiple NEW Fields
| Field | Type | Purpose |
|-------|------|---------|
| `proficiency_level` | Optional[str] | Beginner/Intermediate/Advanced/Expert |
| `years_of_experience` | Optional[int] | Years with this skill |
| `work_evidence` | Optional[str] | Specific job responsibility showing skill |
| `research_evidence` | Optional[str] | Publications showing skill |

**Impact:** Section 3.9 - Complete skill validation with evidence tracking

---

## All ENHANCED Fields (Improved LLM Instructions)

### Enhanced to Extract "EXACTLY AS WRITTEN":
- `name` - Full name as stated on CV
- `degree_title` - Exact degree name format
- `institution` - Exact institution name
- `authors` (Publications) - ALL authors in order
- `inventors` (Patents) - ALL inventors in order
- `patent_no` - Exactly as written on patent
- `conference_name` - Complete exact name

### Enhanced with Examples:
- `employment_type` - Full-time, Part-time, Contract, Internship, Research Assistant, Freelance
- `job_responsibilities` - All bullet points or narrative verbatim
- `topic_category` - Machine Learning, Computer Vision, NLP, Robotics, etc.
- `indexed_in` - Scopus, IEEE Xplore, ACM, Springer, others

### Enhanced with Special Parsing Rules:
- `is_current` - Catch keywords: Present, Ongoing, Currently
- `wos_indexed` / `scopus_indexed` - Check if explicitly mentioned OR recognizable by name
- `authorship_role` - Determine from author position + "corresponding" marker
- `start_year`/`end_year` - Extract as integers for precise gap detection

---

## Critical Fields for LLM (Don't Skip!)

### 🔴 RED (Most Important - Prevent Data Loss):
1. **`email`** - Required for Section 4 missing-info emails
2. **`job_responsibilities`** - CRUCIAL for Section 3.9 skill validation
3. **`authors`** / **`inventors`** - ALL of them, in order - for network analysis
4. **`institution_type`** - For QS/THE ranking verification

### 🟠 ORANGE (Important - Used in Analysis):
5. **`phone`** - Contact info extraction
6. **`proficiency_level`** - Skills assessment
7. **`start_month`** / **`end_month`** - Gap/overlap detection
8. **`quartile`** (journals) - Research ranking
9. **`core_ranking`** (conferences) - Research ranking

### 🟡 YELLOW (Useful - Context & Validation):
10. Topic categorization, evidence tracking, URL extraction

---

## Schema Validation Checklist for LLM

Before prompting Llama 3.1 8B, ensure the extraction schema includes:

- [ ] `InstitutionType` enum defined
- [ ] `CandidateExtraction` has: email, phone, linkedin_url, personal_website, other_urls
- [ ] `EducationRecordExtraction` has: institution_type, start_month, end_month
- [ ] `WorkExperienceExtraction` has: start_month, start_year, end_month, end_year, job_responsibilities
- [ ] `JournalPublicationExtraction` has: doi, volume, issue, pages
- [ ] `ConferencePublicationExtraction` has: conference_location, doi
- [ ] `SupervisionRecordExtraction` has: thesis_title
- [ ] `PatentExtraction` has: date_granted (separate from date_filed)
- [ ] `SkillExtraction` has: proficiency_level, years_of_experience, work_evidence, research_evidence

✅ **All items checked? Schema is ready for Llama 3.1 extraction!**

---

## For Database Update

Current ORM models in [backend/app/models/models.py](backend/app/models/models.py) may need:

### Candidate Table:
```sql
ALTER TABLE candidate ADD COLUMN phone VARCHAR(20);
ALTER TABLE candidate ADD COLUMN linkedin_url VARCHAR(255);
ALTER TABLE candidate ADD COLUMN personal_website VARCHAR(255);
ALTER TABLE candidate ADD COLUMN other_urls TEXT;
```

### EducationRecord Table:
```sql
ALTER TABLE education_record ADD COLUMN institution_type VARCHAR(50);
ALTER TABLE education_record ADD COLUMN start_month INT CHECK (start_month BETWEEN 1 AND 12);
ALTER TABLE education_record ADD COLUMN end_month INT CHECK (end_month BETWEEN 1 AND 12);
```

### WorkExperience Table:
```sql
ALTER TABLE work_experience 
  RENAME COLUMN start_date TO deprecated_start_date;
ALTER TABLE work_experience 
  RENAME COLUMN end_date TO deprecated_end_date;
  
ALTER TABLE work_experience ADD COLUMN start_month INT CHECK (start_month BETWEEN 1 AND 12);
ALTER TABLE work_experience ADD COLUMN start_year INT;
ALTER TABLE work_experience ADD COLUMN end_month INT CHECK (end_month BETWEEN 1 AND 12);
ALTER TABLE work_experience ADD COLUMN end_year INT;
ALTER TABLE work_experience ADD COLUMN job_responsibilities TEXT;
```

### JournalPublication Table:
```sql
ALTER TABLE journal_publication ADD COLUMN doi VARCHAR(100);
ALTER TABLE journal_publication ADD COLUMN volume VARCHAR(20);
ALTER TABLE journal_publication ADD COLUMN issue VARCHAR(20);
ALTER TABLE journal_publication ADD COLUMN pages VARCHAR(50);
```

### ConferencePublication Table:
```sql
ALTER TABLE conference_publication ADD COLUMN conference_location VARCHAR(100);
ALTER TABLE conference_publication ADD COLUMN doi VARCHAR(100);
```

### Patent Table:
```sql
ALTER TABLE patent ADD COLUMN date_granted DATE;
```

### Skill Table:
```sql
ALTER TABLE skill ADD COLUMN proficiency_level VARCHAR(50);
ALTER TABLE skill ADD COLUMN years_of_experience INT;
ALTER TABLE skill ADD COLUMN work_evidence TEXT;
ALTER TABLE skill ADD COLUMN research_evidence TEXT;
```

---

## Implementation Priority

### Phase 1 (Critical):
1. ✅ Update schema definition (DONE)
2. Test extraction with Llama 3.1 on sample CVs
3. Fine-tune LLM prompts to capture new fields
4. Validate extracted data quality

### Phase 2 (Database):
5. Add database columns for new fields
6. Update ORM models to match schema
7. Create database migration script
8. Test data persistence

### Phase 3 (Analysis):
9. Implement Section 3.9 skill validation (job_responsibilities vs skills)
10. Implement Section 4 missing-info email generation (email, gaps)
11. Implement co-author network analysis (authors field)
12. Implement publication ranking (quartile, core_ranking)
