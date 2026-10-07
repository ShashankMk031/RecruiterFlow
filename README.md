# RecruiterFlow — Recruiter Bot Backend

A lightweight candidate-job matchmaking service built with **FastAPI** and **SQLite3**, utilizing hand-written raw SQL exclusively (zero ORMs).

## Setup & Running Locally

1. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. **Install dependencies:**
   ```bash
   pip install fastapi "uvicorn[standard]"
   ```
3. **Initialize and seed the database:**
   ```bash
   python seed.py
   ```
4. **Start the API server:**
   ```bash
   uvicorn main:app --reload
   ```
- Interactive Swagger UI: `http://localhost:8000/docs`
- Endpoints:
  - `GET /jobs/{id}/matches` — Ranked candidate matches for a job
  - `GET /candidates/{id}/matches` — Ranked job matches for a candidate

---

## Design Decisions & Trade-offs

### Schema Design: Normalized Skills Junction Table
Rather than storing skills as denormalized comma-separated strings or JSON blobs, we normalized them into dedicated `skills`, `candidate_skills`, and `job_skills` tables. Storing delimited strings in rows violates First Normal Form (1NF), prevents B-tree index utilization, and necessitates inefficient `LIKE '%skill%'` full-table scans. Using indexed foreign keys on junction tables allows SQLite to perform relational set intersections and aggregations (`COUNT(DISTINCT ...)`, `GROUP_CONCAT(...)`) directly in the database engine with minimal overhead.

### Matching Algorithm: Scoring & Weighting
The matching algorithm scores matches on a 0–100 scale, reflecting real-world recruitment mechanics:
- **Skill Overlap (55 pts max):** Computed as `(matched_skills / total_required_skills) * 55`. Technical capability is the primary gate—seniority cannot compensate for an absence of core competencies.
- **Experience Fit (30 pts max):** Functions as a qualification gate. Candidates meeting or exceeding the minimum experience receive a 25-point baseline plus a seniority bonus (+1 pt/yr surplus, capped at 5 pts). Underqualified candidates are penalized heavily (`(exp / min_exp) * 12`), ensuring they cannot outrank qualified applicants.
- **Availability (10 pts) & Culture (5 pts):** Act as tie-breakers. High hiring velocity candidates (`Immediate`: 10 pts, `2 weeks`: 7 pts) score higher than passive candidates (`Not looking`: 2 pts). Keyword alignment between candidate traits and team culture awards up to 5 points.

Each match outputs an explainable, human-readable reason string summarizing skill coverage, experience delta, availability, and culture alignment.

---

## AI Tools Used

<!-- EDIT THIS SECTION: Detail your AI tools usage below -->
- **Tools Used:** [e.g., ChatGPT / Claude / GitHub Copilot / Antigravity]
- **Where & How:** [e.g., Assisted in scaffolding boilerplate, formulating regex patterns for ingestion, and sanity-checking SQL window functions. Architecture, SQL queries, DDL normalization, and scoring weights were designed, verified, and debugged manually.]
