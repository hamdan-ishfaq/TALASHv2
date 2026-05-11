# TALASH v3 - TECHNICAL ARCHITECTURE & DESIGN DECISIONS

**Purpose**: Explain the architectural decisions, rationale, and how to extend the system correctly  
**Audience**: Development team implementing Phase 3  
**Date**: May 11, 2026  

---

## TABLE OF CONTENTS
1. [Overall Architecture](#overall-architecture)
2. [Database Design Rationale](#database-design-rationale)
3. [Backend Service Layer](#backend-service-layer)
4. [LLM Integration Strategy](#llm-integration-strategy)
5. [Async Processing with Celery](#async-processing-with-celery)
6. [Frontend Architecture](#frontend-architecture)
7. [Do's and Don'ts](#dos-and-donts)
8. [Code Patterns to Follow](#code-patterns-to-follow)

---

## OVERALL ARCHITECTURE

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        TALASH v3 Architecture                   │
└─────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│  FRONTEND (React + TypeScript)                                    │
│  - UploadView, DashboardView, DetailView, ReportsView           │
│  - Communicates via REST API (Axios)                             │
│  - Port: 3000                                                    │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP REST
                         ↓
┌───────────────────────────────────────────────────────────────────┐
│  BACKEND API SERVER (FastAPI + Python)                           │
│  - Routers: upload, analysis, admin                              │
│  - Services: extraction, analysis, reporting                     │
│  - ORM: SQLAlchemy                                               │
│  - Port: 8000                                                    │
└────────────────┬──────────────────────┬───────────────────────────┘
                 │ SQL                  │ Task Queue (AMQP)
                 ↓                      ↓
         ┌───────────────┐      ┌──────────────────┐
         │  PostgreSQL   │      │ Redis Broker     │
         │  Database     │      │ (Celery Broker)  │
         │  Port: 5432   │      │ Port: 6379       │
         └───────────────┘      └──────┬───────────┘
                                       │ Consume Tasks
                                       ↓
                                ┌──────────────────┐
                                │ Celery Worker    │
                                │ (Background Jobs)│
                                │ Port: 5555       │
                                │ (Flower Monitor) │
                                └──────────────────┘
                                       │ SQL
                                       ↓
                                   (Database)
```

### Key Design Principles

1. **Separation of Concerns**: API layer (routers) vs business logic (services)
2. **Async-First**: Long-running tasks use Celery, not blocking API calls
3. **Data Integrity**: Normalized database schema, all relationships via FK
4. **Extensibility**: Services added without modifying existing code
5. **Observability**: Detailed logging at every stage
6. **Idempotency**: Operations are repeatable without side effects

---

## DATABASE DESIGN RATIONALE

### Why Full Normalization (3NF)?

**Decision**: Use 3NF normalized schema with 15+ tables  
**Rationale**:
- Eliminates data duplication (one institution = one record)
- Enables complex queries (e.g., "all papers from Q1 journals")
- Supports future enhancements (e.g., publication impact analysis)
- Maintains data integrity via foreign keys

**Alternative Considered**: Denormalized JSON (single Candidate table with JSON columns)  
**Why Rejected**: 
- Harder to query
- Difficult to join across entities
- Violates relational database principles

### Entity Relationship Structure

**Root Entity**: `Candidate` (acts as hub)

```
Candidate (1 root)
├── EducationRecord (1:many)
├── WorkExperience (1:many)
├── JournalPublication (1:many)
├── ConferencePublication (1:many)
├── SupervisionRecord (1:many)
├── Book (1:many)
├── Patent (1:many)
├── Skill (1:many)
├── EducationGap (1:many)       [Computed from EducationRecord]
├── EmploymentGap (1:many)      [Computed from WorkExperience]
├── InstitutionRanking (1:many) [Reference data]
├── TopicCluster (1:many)       [Computed from publications]
├── CollaborationEdge (1:many)  [Computed from publications]
├── CandidateAssessment (1:many)[Computed scores]
└── MissingInformationRequest (1:many) [Audit trail]
```

**Rationale for Design**:
- `EducationGap`, `EmploymentGap`, `TopicCluster`, `CollaborationEdge`: **Computed entities** that improve query performance (redundant but necessary)
- `InstitutionRanking`, `CandidateAssessment`, `MissingInformationRequest`: **Audit tables** that track analysis results

### Why Store Extracted Data + Computed Analysis?

**Extracted Data** (from Phase 1):
```python
JournalPublication.title         # Extracted from CV
JournalPublication.authors       # Extracted from CV
JournalPublication.journal_name  # Extracted from CV
```

**Computed Analysis** (from Phase 2-3):
```python
JournalPublication.wos_indexed   # Looked up via API
JournalPublication.quartile      # Retrieved from Scimago/JCR
JournalPublication.impact_factor # Retrieved from external source
```

**Rationale**: 
- Keeps audit trail of what was extracted vs what was verified
- Allows re-processing without re-parsing PDF
- Enables incremental updates (e.g., add WoS data later)

### Storing Confidence Scores

**Pattern Used Throughout**:
```python
Column(Float, name="confidence_score")  # 0.0 (low) to 1.0 (high)
```

**Rationale**:
- Indicates reliability of extracted/computed data
- Low confidence → flag for manual review
- Enables filtering: show only high-confidence data

**Example**:
```python
# Trust this education record (high confidence)
education.confidence_score = 0.95

# Don't fully trust this publication (extracted but unverified)
publication.confidence_score = 0.40
```

---

## BACKEND SERVICE LAYER

### Service Tier Architecture

**Why Service Layer?**

```
❌ BAD: Router directly manipulates database
@router.post("/analyze")
def analyze(candidate_id: int, db: Session):
    records = db.query(EducationRecord).filter(...)
    for record in records:
        # Complex business logic...
        # Scoring logic...
        # Gap detection...
    db.commit()

✅ GOOD: Router delegates to service
@router.post("/analyze")
def analyze(candidate_id: int, db: Session):
    result = run_education_analysis(candidate_id, db)
    return result
```

**Benefits**:
1. **Testability**: Services can be unit tested without routers
2. **Reusability**: Services used by routers AND Celery tasks
3. **Maintainability**: Business logic centralized
4. **Clarity**: Router stays thin, service is detailed

### Service Pattern

**Standard Service Function Signature**:
```python
from sqlalchemy.orm import Session
from dataclasses import dataclass

@dataclass
class AnalysisResult:
    """Result of analysis (returned to caller)"""
    candidate_id: int
    score: float
    interpretation: str
    warnings: list[str] = None

def run_analysis(
    candidate_id: int,
    db: Session,
    skip_cache: bool = False
) -> AnalysisResult:
    """
    Run analysis and return structured result.
    
    Args:
        candidate_id: PK of candidate
        db: Database session (typically from SessionLocal())
        skip_cache: Force re-computation (ignore cached results)
    
    Returns:
        AnalysisResult with computed scores
    
    Side Effects:
        - Inserts/updates database records
        - May call external APIs
        - Logs progress
    """
    logger.info(f"[ANALYSIS] Starting for candidate {candidate_id}")
    
    # 1. Load candidate & related data
    candidate = db.query(Candidate).filter_by(id=candidate_id).first()
    if not candidate:
        raise ValueError(f"Candidate {candidate_id} not found")
    
    # 2. Perform computation
    records = db.query(EducationRecord).filter_by(candidate_id=candidate_id).all()
    score = _compute_score(records)
    
    # 3. Persist results
    assessment = CandidateAssessment(
        candidate_id=candidate_id,
        education_strength_score=score
    )
    db.add(assessment)
    db.commit()
    
    logger.info(f"[ANALYSIS] Complete for candidate {candidate_id}: score={score}")
    
    # 4. Return result
    return AnalysisResult(
        candidate_id=candidate_id,
        score=score,
        interpretation=f"Score indicates {grade} performance"
    )
```

### Key Pattern: Helper Functions

```python
# Private helper functions (prefixed with _)
def _normalise_cgpa(
    cgpa: Optional[float],
    cgpa_scale: Optional[float],
    marks_percentage: Optional[float],
) -> Optional[float]:
    """Convert CGPA/percentage to 0-4.0 scale"""
    # Internal implementation details...

# Public API
def run_education_analysis(...) -> EducationAnalysisResult:
    normalized_cgpa = _normalise_cgpa(...)  # Use helper
    # ... rest of logic
```

**Rationale**: Helpers are implementation details, main function is API contract

### Async vs Sync Service Functions

**Use Sync** for simple lookups:
```python
def get_education_records(candidate_id: int, db: Session) -> list[EducationRecord]:
    """Simple database query - no async needed"""
    return db.query(EducationRecord).filter_by(candidate_id=candidate_id).all()
```

**Use Async** for external API calls:
```python
async def verify_wos_indexing(issn: str) -> bool:
    """Call external WoS API - use async to avoid blocking"""
    async with aiohttp.ClientSession() as session:
        response = await session.get(f"https://api.wos.com/issn/{issn}")
        return response.status == 200
```

**Call from sync function**:
```python
def enrich_journal_publication(journal: JournalPublication) -> JournalPublication:
    """Sync function that calls async external APIs"""
    wos_status = asyncio.run(verify_wos_indexing(journal.issn))
    journal.wos_indexed = wos_status
    return journal
```

---

## LLM INTEGRATION STRATEGY

### Provider Abstraction Layer

**Current**: `llm_router.py` provides unified interface

```python
from app.services.llm_router import llm_router

# Get LLM client
client, model_name = llm_router.get_structured_client()
# OR
client, model_name = llm_router.get_text_client()

# Use client to make requests
response = client.messages.create(
    model=model_name,
    max_tokens=2000,
    messages=[...],
    response_model=CandidateExtraction  # Pydantic model
)
```

**Benefits**:
- Easy provider switching (set env var: `LLM_PROVIDER=groq`)
- Single point of rate-limiting/retry logic
- Support for different model capabilities

### When to Use LLM vs Rules

**Use LLM for**:
- Narrative text generation (summaries, interpretations)
- Semantic understanding (extracting concepts from text)
- Classification (categorizing skills, research topics)
- Complex reasoning (gap justification, progression assessment)

**Use Rules for**:
- Data validation (CGPA 0-4.0, year 1900-2099)
- Simple calculations (normalization, averaging)
- Pattern matching (regex for email, DOI)
- Database operations (aggregations, counts)

**Example** (from education_analysis.py):
```python
# Rules: Calculate gap months
gap_months = _months_between(date1, date2)

# LLM: Interpret gap in context
if gap_months > GAP_THRESHOLD_MONTHS:
    interpretation = analysis_llm_call(
        prompt=f"""
        This candidate has a {gap_months} month gap in their education.
        Their employment history shows: {work_history}.
        Is this gap justified? Provide 1-2 sentence explanation.
        """
    )
```

### Response Validation with Pydantic

**Always use Pydantic schemas**:
```python
from pydantic import BaseModel, Field

class JournalPublicationExtraction(BaseModel):
    """Schema returned by LLM extraction"""
    title: str = Field(..., description="Paper title")
    authors: list[str] = Field(default_factory=list)
    journal_name: str = Field(...)
    year: Optional[int] = Field(None)
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Deep Learning for Medical Imaging",
                "authors": ["Ahmed Hassan", "Jane Smith"],
                "journal_name": "IEEE TMI",
                "year": 2023
            }
        }

# Use with LLM
response = client.messages.create(
    model=model_name,
    response_model=JournalPublicationExtraction,
    messages=[{"role": "user", "content": "..."}]
)

# Pydantic validates response structure
assert isinstance(response, JournalPublicationExtraction)
assert response.title  # Not empty
```

**Benefits**:
- Type safety (Python checks types)
- Auto-validation (Pydantic rejects invalid responses)
- Self-documenting (schema is API contract)
- JSON schema generation (for API docs)

---

## ASYNC PROCESSING WITH CELERY

### Task Queue Architecture

**Why Celery (not just background threads)?**

```
❌ Threading (bad for long-running tasks):
- Blocks API server
- Limited to server memory
- No retry logic
- No task monitoring

✅ Celery (good for long-running tasks):
- Distributed (scales to multiple workers)
- Persistent (tasks survive server restart)
- Retryable (built-in retry with backoff)
- Monitorable (Flower web UI)
```

### Celery Task Patterns

**Simple Task**:
```python
from celery import shared_task

@celery_app.task(bind=True)
def simple_task(self, candidate_id: int):
    """Simple background job"""
    db = SessionLocal()
    candidate = db.query(Candidate).get(candidate_id)
    # ... do work ...
    db.close()
```

**Task with Retry**:
```python
@celery_app.task(bind=True, max_retries=3)
def task_with_retry(self, candidate_id: int):
    """Task that retries on failure"""
    try:
        # ... potentially failing operation ...
        result = external_api_call()
    except SomeError as exc:
        # Retry in 120 seconds, exponential backoff
        raise self.retry(exc=exc, countdown=120 * 2 ** self.request.retries)
```

**Chained Tasks** (sequential):
```python
from celery import chain

pipeline = chain(
    task1.s(arg1),   # Task 1 runs first
    task2.s(),       # Task 2 waits for Task 1 result
    task3.s(),       # Task 3 waits for Task 2 result
)
result = pipeline.apply_async()
result.get()  # Wait for completion
```

**Grouped Tasks** (parallel):
```python
from celery import group

jobs = group([
    task_for_candidate.s(cid) 
    for cid in [1, 2, 3, 4, 5]
])
results = jobs.apply_async()  # All run in parallel
results.get()  # Wait for all
```

### Task Patterns in TALASH

**Pattern 1: Simple analysis task**
```python
@celery_app.task
def run_education_analysis_task(candidate_id: int):
    """Run education analysis in background"""
    from app.services.education_analysis import run_education_analysis
    db = SessionLocal()
    result = run_education_analysis(candidate_id, db)
    db.close()
    return asdict(result)  # Convert dataclass to dict for serialization
```

**Pattern 2: Full pipeline (chained)**
```python
def run_full_pipeline(candidate_id: int):
    """Orchestrate all analyses in sequence"""
    from celery import chain
    
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
    return {"pipeline_id": result.id, "status": "started"}
```

### Task Monitoring

**Check task status**:
```python
from celery.result import AsyncResult

task_id = "abc123def456"
result = AsyncResult(task_id, app=celery_app)

if result.ready():
    output = result.get()  # Task complete, get result
else:
    state = result.state  # "PENDING", "PROGRESS", "SUCCESS", "FAILURE"
```

**Flower Web UI** (included in docker-compose):
```
Visit: http://localhost:5555
Shows: Active tasks, completed tasks, failed tasks, task history
```

---

## FRONTEND ARCHITECTURE

### Component Organization

**Goal**: Scalable, maintainable React structure

```
frontend/src/
├── App.tsx                      # Root component with routing
├── types.ts                     # Shared TypeScript interfaces
├── index.css                    # Global styles
│
├── components/
│   ├── views/                   # Page-level components
│   │   ├── UploadView.tsx
│   │   ├── DashboardView.tsx
│   │   ├── DetailView.tsx
│   │   └── ReportsView.tsx
│   ├── charts/                  # Data visualization
│   │   ├── ScoreCard.tsx
│   │   ├── ResearchChart.tsx
│   │   ├── TopicChart.tsx
│   │   └── ExperienceTimeline.tsx
│   ├── tables/                  # Data tables
│   │   ├── CandidateComparison.tsx
│   │   ├── PublicationTable.tsx
│   │   └── SkillsMatrix.tsx
│   └── shared/                  # Reusable utilities
│       ├── StatusBadge.tsx
│       ├── ScoreBadge.tsx
│       └── LoadingSpinner.tsx
│
├── hooks/                       # Custom React hooks
│   ├── useApi.ts               # API calls with caching
│   ├── useFetch.ts             # Generic fetch hook
│   └── usePagination.ts        # Pagination logic
│
├── services/                    # API client & utilities
│   ├── api.ts                  # Axios wrapper
│   └── chart-utils.ts          # Charting helpers
│
└── index.tsx                    # React DOM render
```

### Component Pattern

**Functional component with TypeScript**:
```typescript
import React, { useState, useEffect } from 'react';
import axios from 'axios';

// Define props interface
interface MyComponentProps {
  candidateId: number;
  onSelect?: (id: number) => void;
}

// Define component
export const MyComponent: React.FC<MyComponentProps> = ({ candidateId, onSelect }) => {
  // State
  const [data, setData] = useState<MyType | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Effects
  useEffect(() => {
    loadData();
  }, [candidateId]);

  // Functions
  const loadData = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`/api/data/${candidateId}`);
      setData(response.data);
    } catch (err) {
      setError('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  // Render
  return (
    <div className="my-component">
      {loading && <Spinner />}
      {error && <ErrorBanner message={error} />}
      {data && <DataDisplay data={data} />}
    </div>
  );
};
```

### State Management Philosophy

**Keep it simple**: 
- Use React `useState` for local component state
- Pass state up via callbacks (prop drilling)
- No Redux (unless absolutely necessary for Phase 4+)

**Example**:
```typescript
// Parent component
const [selectedId, setSelectedId] = useState(null);

return (
  <>
    <DashboardTable onSelect={setSelectedId} />
    {selectedId && <DetailView candidateId={selectedId} />}
  </>
);
```

### API Integration Pattern

**Create `useApi` custom hook**:
```typescript
export function useApi<T>(
  url: string,
  deps: any[] = []
): { data: T | null; loading: boolean; error: string | null } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    axios.get(url)
      .then(res => setData(res.data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, deps);

  return { data, loading, error };
}

// Usage in component
const MyComponent: React.FC<{ id: number }> = ({ id }) => {
  const { data, loading, error } = useApi(`/api/candidates/${id}`, [id]);
  
  return (
    <>
      {loading && <Spinner />}
      {error && <Error msg={error} />}
      {data && <Display data={data} />}
    </>
  );
};
```

---

## DO'S AND DON'Ts

### ✅ DO

**1. Always use service layer**
```python
# ✅ Good
result = run_education_analysis(candidate_id, db)

# ❌ Bad
def analyze_endpoint(candidate_id):
    records = db.query(Education).filter(...)
    # ... business logic in router ...
```

**2. Log extensively**
```python
# ✅ Good
logger.info(f"[STAGE-1] Processing candidate {cid}")
logger.debug(f"Found {len(records)} education records")
logger.warning(f"CGPA normalization failed for {cid}")

# ❌ Bad
print(f"Processing candidate")  # Don't use print()
```

**3. Use dataclasses for returns**
```python
# ✅ Good
@dataclass
class AnalysisResult:
    score: float
    interpretation: str
    flags: list = field(default_factory=list)

def analyze(...) -> AnalysisResult:
    return AnalysisResult(score=8.5, interpretation="...", flags=[])

# ❌ Bad
def analyze(...) -> dict:
    return {"score": 8.5}  # Untyped, no validation
```

**4. Validate inputs early**
```python
# ✅ Good
def analyze(candidate_id: int, db: Session) -> AnalysisResult:
    if candidate_id <= 0:
        raise ValueError(f"Invalid candidate ID: {candidate_id}")
    
    candidate = db.query(Candidate).get(candidate_id)
    if not candidate:
        raise ValueError(f"Candidate {candidate_id} not found")
    # ... proceed with confidence

# ❌ Bad
def analyze(candidate_id, db):  # No type hints
    candidate = db.query(Candidate).get(candidate_id)
    if candidate:  # Assumes it exists
        # ... will crash if None
```

**5. Close database sessions**
```python
# ✅ Good (with try/finally)
db = SessionLocal()
try:
    candidate = db.query(Candidate).get(1)
    # ... use candidate ...
finally:
    db.close()

# ✅ Good (with context manager)
with SessionLocal() as db:
    candidate = db.query(Candidate).get(1)
    # ... use candidate ...
# Automatically closed

# ❌ Bad (session leak)
db = SessionLocal()
candidate = db.query(Candidate).get(1)
# ... no close() call, connection leak!
```

**6. Use async for external APIs**
```python
# ✅ Good
async def enrich_publication(pub: JournalPublication):
    async with aiohttp.ClientSession() as session:
        wos = await verify_wos(session, pub.issn)
        scopus = await verify_scopus(session, pub.issn)
    return wos, scopus

# ❌ Bad (blocking calls in sync context)
def enrich_publication(pub):
    wos = requests.get(f"https://wos.com/{pub.issn}")  # Blocks!
    scopus = requests.get(...)  # Blocks!
```

**7. Use Celery for long-running tasks**
```python
# ✅ Good (deferred to worker)
@celery_app.task
def analyze_candidate(candidate_id: int):
    db = SessionLocal()
    run_full_pipeline(candidate_id, db)
    db.close()

# In router:
task = analyze_candidate.delay(candidate_id)
return {"task_id": task.id, "status": "queued"}

# ❌ Bad (blocks API call)
@router.post("/analyze/{id}")
def analyze_endpoint(id: int, db: Session):
    run_full_pipeline(id, db)  # Takes 30 seconds!
    return {"status": "done"}  # User waits...
```

---

### ❌ DON'T

**1. Don't modify database without committing**
```python
# ❌ Bad
record = db.query(Record).get(1)
record.value = 100
# ... forgot to db.commit() ...
# Change is lost!

# ✅ Good
record = db.query(Record).get(1)
record.value = 100
db.commit()  # Explicitly commit
```

**2. Don't catch all exceptions**
```python
# ❌ Bad
try:
    do_something()
except:  # Catches EVERYTHING (keyboard interrupt, etc)
    pass

# ✅ Good
try:
    do_something()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
except ConnectionError as e:
    logger.error(f"Connection failed: {e}")
```

**3. Don't use mutable defaults**
```python
# ❌ Bad
def add_item(item, list=[]):
    list.append(item)
    return list
# All calls share same list!

# ✅ Good
def add_item(item, list=None):
    if list is None:
        list = []
    list.append(item)
    return list

# Or use dataclass with field(default_factory=[])
```

**4. Don't query in a loop**
```python
# ❌ Bad (N+1 query problem)
candidates = db.query(Candidate).all()
for candidate in candidates:
    education = db.query(EducationRecord).filter(...).all()  # N queries!

# ✅ Good (load relationships)
candidates = db.query(Candidate).options(
    joinedload(Candidate.education_records)
).all()
for candidate in candidates:
    education = candidate.education_records  # Already loaded!
```

**5. Don't trust user input**
```python
# ❌ Bad
def analyze(candidate_id: int):
    query = f"SELECT * FROM candidates WHERE id = {candidate_id}"
    db.execute(query)  # SQL injection!

# ✅ Good
def analyze(candidate_id: int):
    candidate = db.query(Candidate).filter_by(id=candidate_id).first()
    # Parameterized query, safe from SQL injection
```

**6. Don't make API calls in synchronous context without async**
```python
# ❌ Bad (blocks entire thread)
def process_publication(pub):
    response = requests.get(f"https://api.wos.com/{pub.issn}")  # BLOCKS!

# ✅ Good
async def process_publication(pub):
    async with aiohttp.ClientSession() as session:
        response = await session.get(...)  # Non-blocking

# Call from sync context:
result = asyncio.run(process_publication(pub))
```

**7. Don't store sensitive data in logs**
```python
# ❌ Bad
logger.info(f"Processing user with API key: {api_key}")  # Exposed!

# ✅ Good
logger.info(f"Processing user with API key: {api_key[:4]}...")  # Masked
```

---

## CODE PATTERNS TO FOLLOW

### Pattern 1: Service with Result Dataclass

```python
# services/my_analysis.py
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from app.models.models import Candidate

@dataclass
class MyAnalysisResult:
    candidate_id: int
    score: float
    interpretation: str
    warnings: list[str] = field(default_factory=list)
    confidence: float = 1.0

def run_my_analysis(
    candidate_id: int,
    db: Session
) -> MyAnalysisResult:
    """Run analysis and return typed result."""
    logger.info(f"[ANALYSIS] Starting for candidate {candidate_id}")
    
    # 1. Validate input
    candidate = db.query(Candidate).get(candidate_id)
    if not candidate:
        raise ValueError(f"Candidate {candidate_id} not found")
    
    # 2. Perform analysis
    score = _compute_score(candidate, db)
    interpretation = _interpret_score(score)
    warnings = _detect_warnings(candidate, db)
    
    # 3. Persist results
    assessment = CandidateAssessment(
        candidate_id=candidate_id,
        my_analysis_score=score
    )
    db.add(assessment)
    db.commit()
    
    logger.info(f"[ANALYSIS] Complete: score={score}")
    
    return MyAnalysisResult(
        candidate_id=candidate_id,
        score=score,
        interpretation=interpretation,
        warnings=warnings,
        confidence=0.95
    )

def _compute_score(candidate: Candidate, db: Session) -> float:
    """Helper: compute score from data."""
    # ... implementation ...

def _interpret_score(score: float) -> str:
    """Helper: provide interpretation."""
    if score >= 8.5: return "Excellent"
    if score >= 7.0: return "Good"
    return "Fair"

def _detect_warnings(candidate: Candidate, db: Session) -> list[str]:
    """Helper: detect issues."""
    warnings = []
    # ... check for missing data, anomalies ...
    return warnings
```

### Pattern 2: API Endpoint that Delegates to Service

```python
# routers/analysis_router.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_db
from app.services.my_analysis import run_my_analysis, MyAnalysisResult

router = APIRouter(prefix="/analysis", tags=["analysis"])

class MyAnalysisResponse(BaseModel):
    """Response schema for API"""
    candidate_id: int
    score: float
    interpretation: str
    warnings: list[str]
    
    class Config:
        from_attributes = True  # Convert dataclass to response

@router.post("/my-analysis/{candidate_id}", response_model=MyAnalysisResponse)
async def run_analysis_endpoint(
    candidate_id: int,
    db: Session = Depends(get_db)
) -> MyAnalysisResponse:
    """Run analysis and return results."""
    try:
        result = run_my_analysis(candidate_id, db)
        return MyAnalysisResponse(**asdict(result))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Analysis failed")
```

### Pattern 3: Celery Task Orchestration

```python
# worker/cv_tasks.py
from celery import chain, group
from app.worker import celery_app
from app.services import (
    run_education_analysis,
    run_experience_analysis,
    run_research_analysis,
    run_summary_generation,
    run_missing_info_detection
)

@celery_app.task
def run_education_analysis_task(candidate_id: int):
    """Task wrapper for education analysis"""
    db = SessionLocal()
    try:
        result = run_education_analysis(candidate_id, db)
        return asdict(result)
    finally:
        db.close()

@celery_app.task
def run_full_pipeline(candidate_id: int):
    """Orchestrate all analyses in sequence"""
    pipeline = chain(
        run_education_analysis_task.s(candidate_id),
        run_experience_analysis_task.s(candidate_id),
        run_research_analysis_task.s(candidate_id),
        run_summary_generation_task.s(candidate_id),
        run_missing_info_detection_task.s(candidate_id),
    )
    result = pipeline.apply_async()
    return {"pipeline_id": result.id, "status": "started"}
```

### Pattern 4: React Component with Custom Hook

```typescript
// hooks/useApi.ts
export function useApi<T>(
  url: string,
  options: RequestInit = {}
): { data: T | null; loading: boolean; error: string | null; refetch: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get(url, options);
      setData(response.data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [url, options]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

// Usage in component
const MyComponent: React.FC<{ candidateId: number }> = ({ candidateId }) => {
  const { data, loading, error, refetch } = useApi(`/api/candidates/${candidateId}`);

  return (
    <div>
      {loading && <Spinner />}
      {error && <Error message={error} />}
      {data && (
        <>
          <Display data={data} />
          <button onClick={refetch}>Refresh</button>
        </>
      )}
    </div>
  );
};
```

---

## SUMMARY: KEY TAKEAWAYS

1. **Architecture is layered**: Routers → Services → ORM → Database
2. **Services are reusable**: Called from routers AND Celery tasks
3. **Database is normalized**: 3NF with 15+ tables
4. **LLM calls are cached**: To reduce API costs
5. **Long tasks are async**: Use Celery, not blocking threads
6. **Logging is extensive**: Every significant operation logged
7. **Errors are handled explicitly**: Catch specific exceptions
8. **Frontend is reactive**: Use hooks and state management
9. **Code is typed**: Python type hints + TypeScript
10. **Tests are comprehensive**: Unit + integration + regression

---

**Document Status**: Complete Technical Architecture Guide  
**Last Updated**: May 11, 2026  
**For**: Phase 3 Development Team
