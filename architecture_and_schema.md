# TALASH v3 System Architecture & Database Schema

Here is a comprehensive breakdown of the entire TALASH v3 project, including the database relationships, the system architecture, and the exact step-by-step flow of how a CV moves through the pipeline.

---

## 1. Database Schema Diagram (ERD)

The system uses a highly normalized relational database built with SQLAlchemy. The `Candidate` table acts as the central hub, with all extracted and analyzed entities linking back to it via foreign keys.

```mermaid
erDiagram
    CANDIDATE {
        int id PK
        string name
        string email
        string status
        string raw_text
        text analysis_json
        text summary
        boolean requires_manual_review
    }

    EDUCATION_RECORD {
        int id PK
        int candidate_id FK
        string degree_title
        string institution
        float cgpa
        int institution_qs_ranking
    }

    WORK_EXPERIENCE {
        int id PK
        int candidate_id FK
        string job_title
        string organization
        boolean is_academic_role
        boolean overlaps_with_education
    }

    JOURNAL_PUBLICATION {
        int id PK
        int candidate_id FK
        string title
        string journal_name
        string issn
        string quartile
        boolean wos_indexed
    }

    CONFERENCE_PUBLICATION {
        int id PK
        int candidate_id FK
        string title
        string conference_name
        string core_ranking
        boolean is_a_star
    }

    SKILL {
        int id PK
        int candidate_id FK
        string skill_name
        string validation_status
    }

    MISSING_INFO_REQUEST {
        int id PK
        int candidate_id FK
        string module_name
        text missing_fields
        text draft_email_body
        string status
    }

    CANDIDATE_ASSESSMENT {
        int id PK
        int candidate_id FK
        float education_score
        float experience_score
        float research_score
        float skill_score
        float overall_rank
        text summary
    }

    CANDIDATE ||--o{ EDUCATION_RECORD : "has"
    CANDIDATE ||--o{ WORK_EXPERIENCE : "has"
    CANDIDATE ||--o{ JOURNAL_PUBLICATION : "has"
    CANDIDATE ||--o{ CONFERENCE_PUBLICATION : "has"
    CANDIDATE ||--o{ SKILL : "has"
    CANDIDATE ||--o{ MISSING_INFO_REQUEST : "has"
    CANDIDATE ||--o| CANDIDATE_ASSESSMENT : "receives"
```

---

## 2. System Architecture

TALASH v3 follows an asynchronous, highly-available microservice architecture.

```mermaid
flowchart TD
    subgraph Frontend [React Frontend]
        UI[Upload & Dashboard UI]
        API_CLIENT[Axios Client]
    end

    subgraph Backend [FastAPI Backend]
        API_ROUTER[API Routers]
        DB_SESSION[SQLAlchemy Session]
    end

    subgraph Message Broker
        REDIS[(Redis Queue)]
    end

    subgraph Background Workers [Celery Workers]
        TASK_QUEUE[cv_tasks.py]
        
        subgraph Stage 1: Extraction
            OPENROUTER[OpenRouter / Gemini API]
            PYDANTIC[Pydantic Validators]
        end
        
        subgraph Stage 2: Analysis & Lookups
            EDU[education_analysis.py]
            EXP[experience_analysis.py]
            RES[research_analysis.py]
            CSV[CSV Lookup Services\nCORE, Scimago, QS]
        end
    end

    subgraph Storage
        DB[(PostgreSQL DB)]
        FILES[Local PDF Storage]
    end

    UI --> API_CLIENT
    API_CLIENT -- "Upload PDF" --> API_ROUTER
    API_ROUTER -- "Save File" --> FILES
    API_ROUTER -- "Trigger Task" --> REDIS
    REDIS -- "Consume Task" --> TASK_QUEUE
    TASK_QUEUE --> Stage1
    Stage1 --> Stage2
    Stage2 --> DB_SESSION
    DB_SESSION --> DB
```

---

## 3. The CV Processing Flow

This maps exactly how a CV transitions from a PDF into HR-validated actionable insights inside our codebase.

```mermaid
sequenceDiagram
    participant User as Recruiter
    participant API as FastAPI Backend
    participant Worker as Celery Worker
    participant LLM as Gemini / OpenRouter
    participant Lookups as CSV Databases
    participant DB as PostgreSQL

    User->>API: Upload candidate_001.pdf
    API->>DB: Create empty Candidate record
    API->>Worker: Dispatch `process_cv_pipeline` task
    API-->>User: Return status: "processing"
    
    rect rgb(30, 41, 59)
    note right of Worker: STAGE 1: Data Extraction
    Worker->>LLM: Send CV Text with Pydantic Schema
    LLM-->>Worker: Return Structured JSON
    Worker->>DB: Save raw extraction
    end

    rect rgb(15, 23, 42)
    note right of Worker: STAGE 2: Enrichment & Validation
    Worker->>Lookups: Check QS_Rankings.xlsx for Universities
    Lookups-->>Worker: Return Institutional Rank
    Worker->>Lookups: Check scimagojr_2025.csv using ISSN
    Lookups-->>Worker: Return Quartile (Q1/Q2/Q3/Q4)
    Worker->>Lookups: Check CORE.csv using Conference Name
    Lookups-->>Worker: Return Core Rank (A*, A, B, C)
    end

    rect rgb(30, 41, 59)
    note right of Worker: STAGE 3: Analysis & Scoring
    Worker->>Worker: Run `education_analysis.py` (Compute Gaps)
    Worker->>Worker: Run `experience_analysis.py` (Verify trajectory)
    Worker->>Worker: Detect Missing Fields (e.g. Missing Dates)
    end
    
    rect rgb(15, 23, 42)
    note right of Worker: STAGE 4: Synthesis
    Worker->>LLM: Send findings to generate Executive Summary & Draft Emails
    LLM-->>Worker: Return Summary & Drafts
    Worker->>DB: Commit Final Scores & Summaries
    Worker->>DB: Update Candidate Status -> "completed"
    end
    
    User->>API: Load Dashboard
    API->>DB: Fetch Analyzed Data
    DB-->>API: Return Scores & Summary
    API-->>User: Display 3D Visualized Dashboard
```
