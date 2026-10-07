# RecruiterFlow - Recruiter Bot Backend Prototype

A high-performance candidate-to-job matching service built with **FastAPI** and **SQLite3**, adhering strictly to **100% hand-written raw SQL** (zero ORMs, zero query builders).

---

## Table of Contents
1. [Project Overview](#project-overview)
2. [Constraints & Philosophy](#constraints--philosophy)
3. [Setup & Quick Start](#setup--quick-start)
4. [Database Schema (DDL)](#database-schema-ddl)
5. [The Matching Algorithm: Design & Trade-offs](#the-matching-algorithm-design--trade-offs)
6. [API Endpoints & curl Examples](#api-endpoints--curl-examples)
7. [Running Tests](#running-tests)
8. [Part 2: SQL Detective Challenge Solutions](#part-2-sql-detective-challenge-solutions)
9. [Notes on AI Tool Usage](#notes-on-ai-tool-usage)

---

## Project Overview

RecruiterFlow prototypes **Recruiter Bot**: a backend service that ingests candidate profiles and job postings, then computes ranked bilateral matches:
- **`GET /jobs/{id}/matches`**: Ranks candidates for a specific job opening.
- **`GET /candidates/{id}/matches`**: Ranks open jobs for a specific candidate.

Each match outputs an exact **0–100 score** and an informative, human-readable **reason** explaining the rating.

---

## Constraints & Philosophy

- **Zero ORM Policy**: Every query, table creation, join, aggregation, and insertion is hand-written SQL using Python’s native `sqlite3` driver.
- **Normalized Relational Model**: Skills are stored in a dedicated table with junction tables (`candidate_skills` and `job_skills`) to enable high-speed set operations and database-level aggregations (`COUNT(DISTINCT ...)`, `GROUP_CONCAT(...)`).
- **Parameterized SQL**: All query inputs use `?` parameterization to prevent SQL injection.
- **Foreign Key Integrity**: Enforced via `PRAGMA foreign_keys = ON;`.

---

## Setup & Quick Start

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.12)

### 2. Create and Activate Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Initialize and Seed the Database
Run the seed script to create the schema and ingest the candidate and job data:
```bash
python seed.py
```
*Output:*
```text
Initializing database at: .../recruiterflow.db
Successfully seeded database:
 - Candidates: 15
 - Jobs:       6
 - Unique Skills: 27
```

*(Note: If you run the API server before running `seed.py`, `main.py`'s lifespan automatically detects a missing database and seeds it automatically).*

### 5. Start the API Server
```bash
uvicorn main:app --reload --port 8000
```
- API Base URL: `http://localhost:8000`
- Interactive Swagger UI: `http://localhost:8000/docs`
- Alternative ReDoc: `http://localhost:8000/redoc`

---

## Database Schema (DDL)

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    experience INTEGER NOT NULL,
    availability TEXT NOT NULL,
    traits TEXT,
    quirk TEXT
);

CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    min_experience INTEGER NOT NULL,
    culture_keywords TEXT,
    tagline TEXT
);

CREATE TABLE skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE candidate_skills (
    candidate_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    PRIMARY KEY (candidate_id, skill_id),
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
);

CREATE TABLE job_skills (
    job_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    PRIMARY KEY (job_id, skill_id),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
);

CREATE INDEX idx_candidate_skills_cand ON candidate_skills(candidate_id);
CREATE INDEX idx_candidate_skills_skill ON candidate_skills(skill_id);
CREATE INDEX idx_job_skills_job ON job_skills(job_id);
CREATE INDEX idx_job_skills_skill ON job_skills(skill_id);
```

---

## The Matching Algorithm: Design & Trade-offs

A hiring matchmaking algorithm must reflect real-world recruitment mechanics: hard gates, primary qualifications, and practical hiring velocity.

### Scoring Breakdown (100 Points Total)

| Factor | Weight | Formulation | Rationale |
| :--- | :---: | :--- | :--- |
| **Skill Overlap** | **55 pts** | `(matched_skills / total_required_skills) * 55` | The primary functional qualifier. If a candidate lacks core skills, experience alone cannot compensate. |
| **Experience Fit** | **30 pts** | • If `exp >= min_exp`: `25 + min(5, (exp - min_exp))` pts<br>• If `exp < min_exp`: `(exp / min_exp) * 12` pts | Minimum experience acts as a qualification gate: candidates meeting the bar receive a solid baseline (25 pts) with a gentle seniority bonus (+1 pt/yr up to 5 pts). Candidates under the minimum are penalised heavily (max 12 pts). |
| **Availability** | **10 pts** | • `Immediate`: 10 pts<br>• `2 weeks`: 7 pts<br>• `Not looking`: 2 pts | Time-to-fill is a critical recruiting metric. Passive candidates ("Not looking") require heavy headhunting friction, while active candidates represent high close probability. |
| **Culture / Trait Fit** | **5 pts** | `+5 pts` if candidate traits intersect job culture keywords | Provides a qualitative tie-breaker based on work-style alignment without overriding hard technical skills. |

### Score Bands
- **95 – 100**: *Flawless Match* (100% skill coverage, exceeds experience bar, immediate start, culture aligned).
- **80 – 94**: *Strong Candidate* (Full skill coverage but standard notice or passive, or slight experience gap).
- **50 – 79**: *Partial Match* (Partial skill coverage, potential training candidate).
- **Below 50**: *Mismatched* (Zero or negligible skill overlap).

### Reason String Engineering
Every match output generates a deterministic, human-readable reason string summarizing all evaluation criteria:
- **Skill breakdown**: e.g., `Full skill match (3/3: deduction, forensics, pattern-recognition)` or `Partial skill match (1/3: pattern-recognition; missing: deduction, forensics)`.
- **Experience analysis**: e.g., `exceeds min experience by 5 yrs (8 vs 3)` or `below min experience by 2 yrs (2 vs 4)`.
- **Availability state**: e.g., `immediately available` vs `passive candidate (not looking)`.
- **Culture tags**: e.g., `culture alignment on 'analytical'`.

---

## API Endpoints & curl Examples

### 1. Get Ranked Candidates for a Job
`GET /jobs/{id}/matches`

```bash
curl -s http://localhost:8000/jobs/1/matches | jq
```

**Sample Response (`Backend Detective`, ID: 1):**
```json
{
  "job_id": 1,
  "title": "Backend Detective",
  "min_experience": 3,
  "culture_keywords": "analytical, autonomous",
  "tagline": "We have a bug. We have no leads. We have you.",
  "required_skills": [
    "deduction",
    "pattern-recognition",
    "forensics"
  ],
  "total_candidates_evaluated": 15,
  "matches": [
    {
      "candidate_id": 1,
      "name": "Sherlock H.",
      "experience": 8,
      "availability": "Immediate",
      "traits": "analytical, blunt",
      "quirk": "Solves problems by eliminating the impossible; occasionally insufferable in standups.",
      "matched_skills_count": 3,
      "total_required_skills": 3,
      "matching_skills": [
        "deduction",
        "pattern-recognition",
        "forensics"
      ],
      "missing_skills": [],
      "score": 100,
      "reason": "Full skill match (3/3: deduction, pattern-recognition, forensics); exceeds min experience by 5 yrs (8 vs 3); immediately available; culture alignment on 'analytical'."
    },
    {
      "candidate_id": 9,
      "name": "Sheldon C.",
      "experience": 9,
      "availability": "Immediate",
      "traits": "rigid, brilliant",
      "quirk": "Correct 95% of the time, insufferable 100% of the time.",
      "matched_skills_count": 1,
      "total_required_skills": 3,
      "matching_skills": [
        "pattern-recognition"
      ],
      "missing_skills": [
        "deduction",
        "forensics"
      ],
      "score": 58,
      "reason": "Partial skill match (1/3: pattern-recognition; missing: deduction, forensics); exceeds min experience by 6 yrs (9 vs 3); immediately available."
    }
  ]
}
```

---

### 2. Get Ranked Jobs for a Candidate
`GET /candidates/{id}/matches`

```bash
curl -s http://localhost:8000/candidates/1/matches | jq
```

**Sample Response (`Sherlock H.`, ID: 1):**
```json
{
  "candidate_id": 1,
  "name": "Sherlock H.",
  "experience": 8,
  "availability": "Immediate",
  "traits": "analytical, blunt",
  "quirk": "Solves problems by eliminating the impossible; occasionally insufferable in standups.",
  "candidate_skills": [
    "deduction",
    "pattern-recognition",
    "forensics"
  ],
  "total_jobs_evaluated": 6,
  "matches": [
    {
      "job_id": 1,
      "title": "Backend Detective",
      "min_experience": 3,
      "culture_keywords": "analytical, autonomous",
      "tagline": "We have a bug. We have no leads. We have you.",
      "matched_skills_count": 3,
      "total_required_skills": 3,
      "matching_skills": [
        "deduction",
        "pattern-recognition",
        "forensics"
      ],
      "missing_skills": [],
      "score": 100,
      "reason": "Full skill match (3/3: deduction, pattern-recognition, forensics); exceeds min experience by 5 yrs (8 vs 3); immediately available; culture alignment on 'analytical'."
    }
  ]
}
```

---

### 3. List All Jobs & Candidates
- `GET /jobs` - Returns all 6 jobs with required skills.
- `GET /candidates` - Returns all 15 candidates with their skills, experience, and availability.

---

## Running Tests

Run the automated test suite using `pytest`:
```bash
pytest -v test_api.py
```

All 8 tests cover:
- Root endpoint verification
- Job & Candidate listings
- Top-ranked candidate queries (`Sherlock H.` for `Backend Detective`, `Rick S.` / `Tony S.` for `Rapid Prototyping Engineer`)
- Top-ranked job queries (`Hermione G.` matching `Developer Relations Lead`)
- 404 error handling for non-existent IDs

---

## Part 2: SQL Detective Challenge Solutions

The queries are provided in [`sql_detective.sql`](file:///Users/shashankmk/Downloads/RecruiterFlow/sql_detective.sql).

### Question 1: List all currently open job postings with recruiter names
```sql
SELECT 
    jp.id AS job_posting_id,
    jp.title,
    jp.department,
    jp.opened_date,
    r.name AS recruiter_name
FROM job_postings jp
JOIN recruiters r ON jp.recruiter_id = r.id
WHERE jp.status = 'open'
ORDER BY jp.id;
```

### Question 2: For each job posting, how many applicants reached the Final interview stage?
```sql
SELECT 
    jp.id AS job_posting_id,
    jp.title,
    COUNT(DISTINCT CASE WHEN i.stage = 'Final' THEN i.applicant_id END) AS final_stage_applicants
FROM job_postings jp
LEFT JOIN interviews i ON jp.id = i.job_posting_id
GROUP BY jp.id, jp.title
ORDER BY jp.id;
```

### Question 3: Find every person who effectively applied to more than one job posting
*Insight*: The data contains subtle irregularities: `Ananya Rao` appears as two separate applicant records (`id: 1` with `ananya.rao@mail.com` and `id: 2` with `Ananya.Rao@mail.com`). Normalizing email via `LOWER(TRIM(a.email))` correctly consolidates her applications across postings.
```sql
SELECT 
    LOWER(TRIM(a.email)) AS normalized_email,
    MIN(a.full_name) AS full_name,
    COUNT(DISTINCT i.job_posting_id) AS distinct_jobs_applied,
    GROUP_CONCAT(DISTINCT i.job_posting_id) AS applied_job_posting_ids
FROM applicants a
JOIN interviews i ON a.id = i.applicant_id
GROUP BY LOWER(TRIM(a.email))
HAVING COUNT(DISTINCT i.job_posting_id) > 1
ORDER BY full_name;
```
*Identified Persons*:
1. `Ananya Rao` (applied to Job Postings 1 and 4)
2. `Ben Turner` (applied to Job Postings 1 and 3)
3. `Elena Popescu` (applied to Job Postings 2 and 7)

### Question 4: Final-stage conversion rate per recruiter (minimum 3 Final interviews)
```sql
SELECT 
    r.id AS recruiter_id,
    r.name AS recruiter_name,
    COUNT(CASE WHEN i.stage = 'Final' AND i.outcome = 'passed' THEN 1 END) AS passed_final_interviews,
    COUNT(CASE WHEN i.stage = 'Final' THEN 1 END) AS total_final_interviews,
    ROUND(
        CAST(COUNT(CASE WHEN i.stage = 'Final' AND i.outcome = 'passed' THEN 1 END) AS FLOAT) / 
        COUNT(CASE WHEN i.stage = 'Final' THEN 1 END), 
        4
    ) AS final_conversion_rate
FROM recruiters r
JOIN job_postings jp ON r.id = jp.recruiter_id
JOIN interviews i ON jp.id = i.job_posting_id
WHERE i.stage = 'Final'
GROUP BY r.id, r.name
HAVING COUNT(CASE WHEN i.stage = 'Final' THEN 1 END) >= 3
ORDER BY final_conversion_rate DESC;
```
*Results*:
- `Priya Shah`: 3 passed / 4 total = **0.7500 (75%)**
- `Daniel Ortiz`: 2 passed / 4 total = **0.5000 (50%)**

### Question 5 (Bonus): Recruiter with most successful placements per department using window function
```sql
WITH department_placements AS (
    SELECT 
        jp.department,
        r.id AS recruiter_id,
        r.name AS recruiter_name,
        COUNT(CASE WHEN i.stage = 'Final' AND i.outcome = 'passed' THEN 1 END) AS successful_placements
    FROM recruiters r
    JOIN job_postings jp ON r.id = jp.recruiter_id
    JOIN interviews i ON jp.id = i.job_posting_id
    WHERE i.stage = 'Final' AND i.outcome = 'passed'
    GROUP BY jp.department, r.id, r.name
),
ranked_placements AS (
    SELECT 
        department,
        recruiter_id,
        recruiter_name,
        successful_placements,
        DENSE_RANK() OVER (PARTITION BY department ORDER BY successful_placements DESC) AS rnk
    FROM department_placements
)
SELECT 
    department,
    recruiter_id,
    recruiter_name,
    successful_placements
FROM ranked_placements
WHERE rnk = 1
ORDER BY department;
```
*Results*:
- `Data`: Fatima Al-Sayed (1 placement)
- `Engineering`: Priya Shah (3 placements)

---

## Notes on AI Tool Usage

As requested in the take-home prompt guidelines:
- **AI Coding Assistant**: Antigravity AI pair programmer was utilized to accelerate regex text parsing patterns, scaffold the raw SQL queries, review edge cases in the scoring algorithm, and draft the automated test suite.
- **Architectural Control**: Schema design, scoring mathematics (skill weighting vs. experience gating), SQLite-specific constraint handling (`PRAGMA foreign_keys`), and SQL query structures were formulated and verified step-by-step.
