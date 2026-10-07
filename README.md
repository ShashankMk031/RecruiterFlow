# RecruiterFlow — Recruiter Bot

A small backend prototype built in Python with FastAPI and SQLite. It matches fictional candidates with job openings using raw, hand-written SQL queries (no ORMs).

---

## How to Run

1. **Set up a virtual environment and install dependencies:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Seed the database:**
   ```bash
   python seed.py
   ```
   This creates the SQLite schema (`recruiterflow.db`) and ingests all candidates, jobs, and normalized skills.

3. **Start the API server:**
   ```bash
   uvicorn main:app --reload
   ```
   Interactive Swagger docs are live at `http://localhost:8000/docs`.

4. **Run the tests:**
   ```bash
   pytest -v test_api.py
   ```

---

## Architecture

### 1. Database & Schema Design
We used Python's standard `sqlite3` library with hand-written DDL and parameterized queries throughout.

The core database decision was **normalizing skills into junction tables** (`skills`, `candidate_skills`, and `job_skills`) rather than storing comma-separated strings or JSON lists. Storing delimited strings violates 1NF and forces slow `LIKE '%skill%'` full-table scans. With junction tables:
- Finding skill overlap between a candidate and a job becomes a clean, indexed `JOIN`.
- SQLite computes set intersections, `COUNT(DISTINCT ...)`, and `GROUP_CONCAT(...)` in a single query pass.
- Foreign keys with `ON DELETE CASCADE` ensure referential integrity.

### 2. Matching Algorithm & Scoring
Matches are scored on a **0 to 100** scale, modeled after how recruiters actually evaluate profiles:

- **Skill Overlap (55 pts max):** This is the primary gate. We take the ratio of matched skills to total required skills (`(matched / total) * 55`). If someone lacks the core skills, experience alone shouldn't qualify them.
- **Experience Fit (30 pts max):** Acts as a threshold. If a candidate meets or exceeds the job's minimum experience, they get a baseline 25 points plus a seniority buffer (+1 pt/yr surplus, capped at 5 pts). If they fall below the minimum, their score drops sharply (`(exp / min_exp) * 12`), ensuring underqualified candidates don't outrank qualified applicants.
- **Availability (10 pts):** Hiring speed matters. Immediate availability scores 10 points, a standard 2-week notice scores 7 points, and passive candidates ("Not looking") score 2 points.
- **Culture / Traits (5 pts):** A light tie-breaker awarded when a candidate's traits intersect with the team's culture keywords.

Every match returns an explainable **reason string** (e.g. `"Full skill match (3/3: deduction, forensics, pattern-recognition); exceeds min experience by 5 yrs (8 vs 3); immediately available"`) so recruiters know exactly why someone is ranked where they are.