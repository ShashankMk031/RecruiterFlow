"""
main.py - RecruiterFlow Matchmaking API service.

Built exclusively using RAW SQL via Python's built-in `sqlite3` library.
No ORMs or query builders allowed. Hand-written SQL queries only.
"""

import os
import sqlite3
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Path, Query
from pydantic import BaseModel, Field

from seed import DB_PATH, seed_database


def get_db_connection() -> sqlite3.Connection:
    """Creates a raw SQLite connection with Row factory and FK enforcement."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def calculate_match(
    candidate_exp: int,
    candidate_avail: str,
    candidate_traits: str,
    job_min_exp: int,
    job_culture: str,
    matching_skills: List[str],
    all_required_skills: List[str],
) -> Tuple[int, str]:
    """
    Computes a 0-100 match score and a human-readable explanation string.
    
    Weights:
    - Skill Overlap (0-55 pts): (matched / total_required) * 55
    - Experience Fit (0-30 pts): 
        - If exp >= min_exp: 25 pts base + min(5, (exp - min_exp)) seniority bonus
        - If exp < min_exp: (exp / min_exp) * 12 pts (heavily penalized)
    - Availability (0-10 pts): Immediate (10 pts), 2 weeks (7 pts), Not looking (2 pts)
    - Culture / Trait Alignment (0-5 pts): Keyword match between traits & culture
    """
    matched_count = len(matching_skills)
    total_required = len(all_required_skills)

    # 1. Skill Overlap (0-55 points)
    if total_required > 0:
        skill_ratio = matched_count / total_required
        skill_score = skill_ratio * 55.0
    else:
        skill_score = 55.0

    # 2. Experience Fit (0-30 points)
    if candidate_exp >= job_min_exp:
        extra_years = candidate_exp - job_min_exp
        seniority_bonus = min(5.0, float(extra_years))
        exp_score = 25.0 + seniority_bonus
        if extra_years > 0:
            exp_desc = f"exceeds min experience by {extra_years} yrs ({candidate_exp} vs {job_min_exp})"
        else:
            exp_desc = f"meets exact min experience ({candidate_exp} yrs)"
    else:
        deficit = job_min_exp - candidate_exp
        exp_ratio = candidate_exp / max(1, job_min_exp)
        exp_score = exp_ratio * 12.0
        exp_desc = f"below min experience by {deficit} yrs ({candidate_exp} vs {job_min_exp})"

    # 3. Availability (0-10 points)
    avail_clean = (candidate_avail or "").strip().lower()
    if "immediate" in avail_clean:
        avail_score = 10.0
        avail_desc = "immediately available"
    elif "2 weeks" in avail_clean or "two weeks" in avail_clean:
        avail_score = 7.0
        avail_desc = "standard 2-week notice"
    elif "not looking" in avail_clean:
        avail_score = 2.0
        avail_desc = "passive candidate (not looking)"
    else:
        avail_score = 5.0
        avail_desc = f"availability: {candidate_avail}"

    # 4. Culture / Trait Fit (0-5 points)
    cand_tokens = {
        t.strip().lower() for t in (candidate_traits or "").split(",") if t.strip()
    }
    job_tokens = {
        k.strip().lower() for k in (job_culture or "").split(",") if k.strip()
    }
    culture_overlap = sorted(list(cand_tokens.intersection(job_tokens)))
    if culture_overlap:
        culture_score = 5.0
        culture_desc = f"culture alignment on '{', '.join(culture_overlap)}'"
    else:
        culture_score = 0.0
        culture_desc = ""

    # Aggregate & clamp 0-100
    total = round(skill_score + exp_score + avail_score + culture_score)
    final_score = max(0, min(100, int(total)))

    # Reason construction
    missing_skills = [s for s in all_required_skills if s not in matching_skills]
    if matched_count == total_required and total_required > 0:
        skill_desc = f"Full skill match ({matched_count}/{total_required}: {', '.join(matching_skills)})"
    elif matched_count > 0:
        skill_desc = (
            f"Partial skill match ({matched_count}/{total_required}: {', '.join(matching_skills)}"
            + (f"; missing: {', '.join(missing_skills)}" if missing_skills else "")
            + ")"
        )
    else:
        skill_desc = (
            f"No skill match (0/{total_required}"
            + (f"; missing: {', '.join(missing_skills)}" if missing_skills else "")
            + ")"
        )

    parts = [skill_desc, exp_desc, avail_desc]
    if culture_desc:
        parts.append(culture_desc)

    reason_str = "; ".join(parts) + "."
    return final_score, reason_str


# Lifespan event to automatically ensure the SQLite database is seeded
@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. Auto-seeding...")
        seed_database(DB_PATH)
    yield


app = FastAPI(
    title="RecruiterFlow Bot API",
    description="High-precision candidate & job matching service powered by raw SQLite queries.",
    version="1.0.0",
    lifespan=lifespan,
)


# Pydantic schemas for documentation and validation
class CandidateMatchItem(BaseModel):
    candidate_id: int
    name: str
    experience: int
    availability: str
    traits: str
    quirk: Optional[str]
    matched_skills_count: int
    total_required_skills: int
    matching_skills: List[str]
    missing_skills: List[str]
    score: int = Field(..., ge=0, le=100)
    reason: str


class JobMatchesResponse(BaseModel):
    job_id: int
    title: str
    min_experience: int
    culture_keywords: str
    tagline: str
    required_skills: List[str]
    total_candidates_evaluated: int
    matches: List[CandidateMatchItem]


class JobMatchItem(BaseModel):
    job_id: int
    title: str
    min_experience: int
    culture_keywords: str
    tagline: str
    matched_skills_count: int
    total_required_skills: int
    matching_skills: List[str]
    missing_skills: List[str]
    score: int = Field(..., ge=0, le=100)
    reason: str


class CandidateMatchesResponse(BaseModel):
    candidate_id: int
    name: str
    experience: int
    availability: str
    traits: str
    quirk: Optional[str]
    candidate_skills: List[str]
    total_jobs_evaluated: int
    matches: List[JobMatchItem]


class JobItem(BaseModel):
    id: int
    title: str
    min_experience: int
    culture_keywords: str
    tagline: str
    required_skills: List[str]


class CandidateItem(BaseModel):
    id: int
    name: str
    experience: int
    availability: str
    traits: str
    quirk: Optional[str]
    skills: List[str]


@app.get("/", summary="API Root")
def root():
    return {
        "service": "RecruiterFlow Bot API",
        "version": "1.0.0",
        "endpoints": {
            "job_matches": "/jobs/{id}/matches",
            "candidate_matches": "/candidates/{id}/matches",
            "list_jobs": "/jobs",
            "list_candidates": "/candidates",
            "docs": "/docs",
        },
    }


@app.get(
    "/jobs/{id}/matches",
    response_model=JobMatchesResponse,
    summary="Get ranked candidates for a specific job",
)
def get_job_matches(
    id: int = Path(..., description="The ID of the target job posting")
):
    """
    Ranks candidates for a given job using raw SQL aggregation and matching logic.
    Scores candidates 0-100 based on skill overlap, experience fit, availability, and culture fit.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # 1. Fetch Job info using RAW SQL
        job_query = """
        SELECT 
            j.id, 
            j.title, 
            j.min_experience, 
            j.culture_keywords, 
            j.tagline,
            (SELECT GROUP_CONCAT(s.name) 
             FROM job_skills js 
             JOIN skills s ON s.id = js.skill_id 
             WHERE js.job_id = j.id) AS required_skills_list
        FROM jobs j
        WHERE j.id = ?;
        """
        cursor.execute(job_query, (id,))
        job_row = cursor.fetchone()

        if not job_row:
            raise HTTPException(status_code=404, detail=f"Job with id {id} not found")

        required_skills = [
            s.strip()
            for s in (job_row["required_skills_list"] or "").split(",")
            if s.strip()
        ]

        # 2. Query candidates with skill overlap calculation using RAW SQL
        matching_query = """
        SELECT 
            c.id AS candidate_id,
            c.name,
            c.experience,
            c.availability,
            c.traits,
            c.quirk,
            COUNT(DISTINCT js.skill_id) AS matching_skills_count,
            GROUP_CONCAT(DISTINCT s.name) AS matching_skills_list
        FROM candidates c
        LEFT JOIN candidate_skills cs ON cs.candidate_id = c.id
        LEFT JOIN job_skills js ON js.skill_id = cs.skill_id AND js.job_id = ?
        LEFT JOIN skills s ON s.id = js.skill_id
        GROUP BY c.id
        ORDER BY matching_skills_count DESC, c.experience DESC, c.id ASC;
        """
        cursor.execute(matching_query, (id,))
        candidate_rows = cursor.fetchall()

        matches = []
        for row in candidate_rows:
            matching_skills = [
                s.strip()
                for s in (row["matching_skills_list"] or "").split(",")
                if s.strip()
            ]
            missing_skills = [
                s for s in required_skills if s not in matching_skills
            ]

            score, reason = calculate_match(
                candidate_exp=row["experience"],
                candidate_avail=row["availability"],
                candidate_traits=row["traits"],
                job_min_exp=job_row["min_experience"],
                job_culture=job_row["culture_keywords"],
                matching_skills=matching_skills,
                all_required_skills=required_skills,
            )

            matches.append(
                CandidateMatchItem(
                    candidate_id=row["candidate_id"],
                    name=row["name"],
                    experience=row["experience"],
                    availability=row["availability"],
                    traits=row["traits"] or "",
                    quirk=row["quirk"] or "",
                    matched_skills_count=len(matching_skills),
                    total_required_skills=len(required_skills),
                    matching_skills=matching_skills,
                    missing_skills=missing_skills,
                    score=score,
                    reason=reason,
                )
            )

        # Sort primarily by score DESC, then matched skills count DESC, then exp DESC
        matches.sort(
            key=lambda m: (m.score, m.matched_skills_count, m.experience),
            reverse=True,
        )

        return JobMatchesResponse(
            job_id=job_row["id"],
            title=job_row["title"],
            min_experience=job_row["min_experience"],
            culture_keywords=job_row["culture_keywords"] or "",
            tagline=job_row["tagline"] or "",
            required_skills=required_skills,
            total_candidates_evaluated=len(matches),
            matches=matches,
        )
    finally:
        conn.close()


@app.get(
    "/candidates/{id}/matches",
    response_model=CandidateMatchesResponse,
    summary="Get ranked jobs for a specific candidate",
)
def get_candidate_matches(
    id: int = Path(..., description="The ID of the candidate")
):
    """
    Ranks open jobs for a given candidate using raw SQL aggregation and matching logic.
    Scores jobs 0-100 from the candidate's perspective.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # 1. Fetch Candidate info using RAW SQL
        candidate_query = """
        SELECT 
            c.id, 
            c.name, 
            c.experience, 
            c.availability, 
            c.traits, 
            c.quirk,
            (SELECT GROUP_CONCAT(s.name) 
             FROM candidate_skills cs 
             JOIN skills s ON s.id = cs.skill_id 
             WHERE cs.candidate_id = c.id) AS candidate_skills_list
        FROM candidates c
        WHERE c.id = ?;
        """
        cursor.execute(candidate_query, (id,))
        cand_row = cursor.fetchone()

        if not cand_row:
            raise HTTPException(
                status_code=404, detail=f"Candidate with id {id} not found"
            )

        candidate_skills = [
            s.strip()
            for s in (cand_row["candidate_skills_list"] or "").split(",")
            if s.strip()
        ]

        # 2. Query jobs with skill overlap calculation using RAW SQL
        matching_query = """
        SELECT 
            j.id AS job_id,
            j.title,
            j.min_experience,
            j.culture_keywords,
            j.tagline,
            (SELECT COUNT(*) FROM job_skills WHERE job_id = j.id) AS total_required_skills,
            (SELECT GROUP_CONCAT(s2.name) 
             FROM job_skills js2 
             JOIN skills s2 ON s2.id = js2.skill_id 
             WHERE js2.job_id = j.id) AS required_skills_list,
            COUNT(DISTINCT cs.skill_id) AS matching_skills_count,
            GROUP_CONCAT(DISTINCT s.name) AS matching_skills_list
        FROM jobs j
        LEFT JOIN job_skills js ON js.job_id = j.id
        LEFT JOIN candidate_skills cs ON cs.skill_id = js.skill_id AND cs.candidate_id = ?
        LEFT JOIN skills s ON s.id = cs.skill_id
        GROUP BY j.id
        ORDER BY matching_skills_count DESC, j.id ASC;
        """
        cursor.execute(matching_query, (id,))
        job_rows = cursor.fetchall()

        matches = []
        for row in job_rows:
            required_skills = [
                s.strip()
                for s in (row["required_skills_list"] or "").split(",")
                if s.strip()
            ]
            matching_skills = [
                s.strip()
                for s in (row["matching_skills_list"] or "").split(",")
                if s.strip()
            ]
            missing_skills = [
                s for s in required_skills if s not in matching_skills
            ]

            score, reason = calculate_match(
                candidate_exp=cand_row["experience"],
                candidate_avail=cand_row["availability"],
                candidate_traits=cand_row["traits"],
                job_min_exp=row["min_experience"],
                job_culture=row["culture_keywords"],
                matching_skills=matching_skills,
                all_required_skills=required_skills,
            )

            matches.append(
                JobMatchItem(
                    job_id=row["job_id"],
                    title=row["title"],
                    min_experience=row["min_experience"],
                    culture_keywords=row["culture_keywords"] or "",
                    tagline=row["tagline"] or "",
                    matched_skills_count=len(matching_skills),
                    total_required_skills=len(required_skills),
                    matching_skills=matching_skills,
                    missing_skills=missing_skills,
                    score=score,
                    reason=reason,
                )
            )

        matches.sort(
            key=lambda m: (m.score, m.matched_skills_count, -m.min_experience),
            reverse=True,
        )

        return CandidateMatchesResponse(
            candidate_id=cand_row["id"],
            name=cand_row["name"],
            experience=cand_row["experience"],
            availability=cand_row["availability"],
            traits=cand_row["traits"] or "",
            quirk=cand_row["quirk"] or "",
            candidate_skills=candidate_skills,
            total_jobs_evaluated=len(matches),
            matches=matches,
        )
    finally:
        conn.close()


@app.get("/jobs", response_model=List[JobItem], summary="List all jobs")
def list_jobs():
    """Lists all available jobs with their required skills using RAW SQL."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = """
        SELECT 
            j.id, 
            j.title, 
            j.min_experience, 
            j.culture_keywords, 
            j.tagline,
            (SELECT GROUP_CONCAT(s.name) 
             FROM job_skills js 
             JOIN skills s ON s.id = js.skill_id 
             WHERE js.job_id = j.id) AS required_skills_list
        FROM jobs j
        ORDER BY j.id ASC;
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        results = []
        for r in rows:
            req_skills = [
                s.strip()
                for s in (r["required_skills_list"] or "").split(",")
                if s.strip()
            ]
            results.append(
                JobItem(
                    id=r["id"],
                    title=r["title"],
                    min_experience=r["min_experience"],
                    culture_keywords=r["culture_keywords"] or "",
                    tagline=r["tagline"] or "",
                    required_skills=req_skills,
                )
            )
        return results
    finally:
        conn.close()


@app.get(
    "/candidates",
    response_model=List[CandidateItem],
    summary="List all candidates",
)
def list_candidates():
    """Lists all candidates with their skills using RAW SQL."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = """
        SELECT 
            c.id, 
            c.name, 
            c.experience, 
            c.availability, 
            c.traits, 
            c.quirk,
            (SELECT GROUP_CONCAT(s.name) 
             FROM candidate_skills cs 
             JOIN skills s ON s.id = cs.skill_id 
             WHERE cs.candidate_id = c.id) AS skills_list
        FROM candidates c
        ORDER BY c.id ASC;
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        results = []
        for r in rows:
            skills = [
                s.strip()
                for s in (r["skills_list"] or "").split(",")
                if s.strip()
            ]
            results.append(
                CandidateItem(
                    id=r["id"],
                    name=r["name"],
                    experience=r["experience"],
                    availability=r["availability"],
                    traits=r["traits"] or "",
                    quirk=r["quirk"] or "",
                    skills=skills,
                )
            )
        return results
    finally:
        conn.close()
