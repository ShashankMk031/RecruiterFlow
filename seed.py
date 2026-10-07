"""
seed.py - Database initialization and ingestion for RecruiterFlow Bot.

Initializes the SQLite schema using RAW SQL only (built-in sqlite3).
Parses candidates and jobs text, normalizes skills into junction tables,
and seeds the database.
"""

import os
import re
import sqlite3
from typing import Dict, List, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "recruiterflow.db")

# Raw text seed data as specified in the assignment brief
CANDIDATES_RAW_TEXT = """
- Sherlock H. (Exp: 8) | Skills: deduction, pattern-recognition, forensics | Avail: Immediate | Traits: analytical, blunt
- Hermione G. (Exp: 4) | Skills: research, time-management, public-speaking | Avail: 2 weeks | Traits: detail-oriented, overachiever
- Tony S. (Exp: 12) | Skills: systems-design, rapid-prototyping, leadership | Avail: Not looking | Traits: confident, innovative
- Leslie K. (Exp: 6) | Skills: project-management, stakeholder-management, public-speaking | Avail: Immediate | Traits: tenacious, organized
- Ron S. (Exp: 15) | Skills: woodworking, minimalism, negotiation | Avail: Not looking | Traits: stubborn, principled
- Rick S. (Exp: 20) | Skills: systems-design, rapid-prototyping, chemistry | Avail: Immediate | Traits: genius, reckless
- Elle W. (Exp: 3) | Skills: persuasion, research, public-speaking | Avail: Immediate | Traits: optimistic, sharp
- MacGyver (Exp: 10) | Skills: rapid-prototyping, resourcefulness, chemistry, systems-design | Avail: 2 weeks | Traits: calm, improviser
- Sheldon C. (Exp: 9) | Skills: theoretical-analysis, pattern-recognition, research | Avail: Immediate | Traits: rigid, brilliant
- Katniss E. (Exp: 5) | Skills: precision, strategy, crisis-management | Avail: Immediate | Traits: resilient, decisive
- Michael S. (Exp: 11) | Skills: sales, public-speaking, team-building | Avail: Not looking | Traits: enthusiastic, chaotic
- Olivia P. (Exp: 13) | Skills: crisis-management, negotiation, strategy, leadership | Avail: 2 weeks | Traits: decisive, intense
- Ted L. (Exp: 7) | Skills: team-building, optimism, mentorship, public-speaking | Avail: Immediate | Traits: empathetic, persistent
- Miranda P. (Exp: 18) | Skills: leadership, negotiation, stakeholder-management, precision | Avail: Not looking | Traits: demanding, decisive
- Dwight S. (Exp: 9) | Skills: sales, negotiation, security, loyalty | Avail: Immediate | Traits: intense, loyal
"""

JOBS_RAW_TEXT = """
- Backend Detective (Min Exp: 3) | Skills: deduction, pattern-recognition, forensics
- Rapid Prototyping Engineer (Min Exp: 2) | Skills: rapid-prototyping, systems-design
- Developer Relations Lead (Min Exp: 2) | Skills: public-speaking, research
- Engineering Manager, Chaos Team (Min Exp: 5) | Skills: team-building, stakeholder-management, leadership
- Incident Commander (Min Exp: 4) | Skills: crisis-management, strategy, negotiation
- Sales Engineer (Min Exp: 3) | Skills: sales, public-speaking, negotiation
"""

# Rich metadata from the RecruiterFlow assignment brief
CANDIDATE_QUIRKS = {
    "Sherlock H.": "Solves problems by eliminating the impossible; occasionally insufferable in standups.",
    "Hermione G.": "Reads the entire documentation before writing a single line of code.",
    "Tony S.": "Ships an MVP overnight, refuses to write tests.",
    "Leslie K.": "Has a binder for everything, including the binder.",
    "Ron S.": "Refuses to use more than one monitor.",
    "Rick S.": "Solution works, mechanism deeply concerning.",
    "Elle W.": "Underestimated in every standup, correct in every retro.",
    "MacGyver": "Fixes production outages with duct tape and a paperclip metaphor.",
    "Sheldon C.": "Correct 95% of the time, insufferable 100% of the time.",
    "Katniss E.": "Excellent under pressure, terrible with public speaking.",
    "Michael S.": "World's best boss, according to a mug he bought himself.",
    "Olivia P.": "Handles it. Whatever it is.",
    "Ted L.": "Turns every technical setback into a folksy metaphor.",
    "Miranda P.": "Reviews every PR personally. Says nothing. Everyone panics.",
    "Dwight S.": "Assistant to the regional backend engineer.",
}

JOB_METADATA = {
    "Backend Detective": {
        "culture_keywords": "analytical, autonomous",
        "tagline": "We have a bug. We have no leads. We have you.",
    },
    "Rapid Prototyping Engineer": {
        "culture_keywords": "innovative, fast-paced",
        "tagline": "Ship first, document never (kidding — please document).",
    },
    "Developer Relations Lead": {
        "culture_keywords": "energetic, curious",
        "tagline": "Explain complex things to confused humans, cheerfully.",
    },
    "Engineering Manager, Chaos Team": {
        "culture_keywords": "empathetic, organized",
        "tagline": "Herd cats. The cats are senior engineers.",
    },
    "Incident Commander": {
        "culture_keywords": "decisive, calm-under-pressure",
        "tagline": "3am page. You're the one who picks up.",
    },
    "Sales Engineer": {
        "culture_keywords": "enthusiastic, persistent",
        "tagline": "Sell the vision, then go build it.",
    },
}

DDL_STATEMENTS = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS candidate_skills;
DROP TABLE IF EXISTS job_skills;
DROP TABLE IF EXISTS skills;
DROP TABLE IF EXISTS candidates;
DROP TABLE IF EXISTS jobs;

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
"""


def parse_candidates_text(raw_text: str) -> List[Dict]:
    """
    Parses candidate text lines with the format:
    - Name (Exp: X) | Skills: a, b, c | Avail: Y | Traits: d, e
    """
    candidates = []
    line_pattern = re.compile(
        r"^[-\s]*"
        r"(?P<name>[^(\n]+?)\s*"
        r"\(Exp:\s*(?P<exp>\d+)\)\s*\|\s*"
        r"Skills:\s*(?P<skills>[^|\n]+?)\s*\|\s*"
        r"Avail:\s*(?P<avail>[^|\n]+?)\s*\|\s*"
        r"Traits:\s*(?P<traits>[^\n]+)"
        r"$",
        re.MULTILINE,
    )

    for match in line_pattern.finditer(raw_text):
        data = match.groupdict()
        name = data["name"].strip()
        experience = int(data["exp"].strip())
        skills = [s.strip().lower() for s in data["skills"].split(",") if s.strip()]
        availability = data["avail"].strip()
        traits = data["traits"].strip()
        quirk = CANDIDATE_QUIRKS.get(name, "")

        candidates.append(
            {
                "name": name,
                "experience": experience,
                "skills": skills,
                "availability": availability,
                "traits": traits,
                "quirk": quirk,
            }
        )
    return candidates


def parse_jobs_text(raw_text: str) -> List[Dict]:
    """
    Parses jobs text lines with the format:
    - Title (Min Exp: X) | Skills: a, b, c
    """
    jobs = []
    line_pattern = re.compile(
        r"^[-\s]*"
        r"(?P<title>[^(\n]+?)\s*"
        r"\(Min Exp:\s*(?P<min_exp>\d+)\)\s*\|\s*"
        r"Skills:\s*(?P<skills>[^\n]+)"
        r"$",
        re.MULTILINE,
    )

    for match in line_pattern.finditer(raw_text):
        data = match.groupdict()
        title = data["title"].strip()
        min_experience = int(data["min_exp"].strip())
        skills = [s.strip().lower() for s in data["skills"].split(",") if s.strip()]
        meta = JOB_METADATA.get(title, {})

        jobs.append(
            {
                "title": title,
                "min_experience": min_experience,
                "skills": skills,
                "culture_keywords": meta.get("culture_keywords", ""),
                "tagline": meta.get("tagline", ""),
            }
        )
    return jobs


def init_db(db_path: str = DB_PATH) -> None:
    """Executes DDL statements to recreate the database tables."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.executescript(DDL_STATEMENTS)
        conn.commit()
    finally:
        conn.close()


def get_or_create_skill_id(cursor: sqlite3.Cursor, skill_name: str) -> int:
    """Gets existing skill_id or inserts skill and returns new ID using RAW SQL."""
    cursor.execute("SELECT id FROM skills WHERE name = ?", (skill_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO skills (name) VALUES (?)", (skill_name,))
    return cursor.lastrowid


def seed_database(db_path: str = DB_PATH) -> Tuple[int, int, int]:
    """
    Initializes DDL and ingests parsed candidates, jobs, and junction skill tables.
    Returns (num_candidates, num_jobs, num_skills).
    """
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        candidates_data = parse_candidates_text(CANDIDATES_RAW_TEXT)
        jobs_data = parse_jobs_text(JOBS_RAW_TEXT)

        # Ingest Candidates & candidate_skills
        for cand in candidates_data:
            cursor.execute(
                """
                INSERT INTO candidates (name, experience, availability, traits, quirk)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    cand["name"],
                    cand["experience"],
                    cand["availability"],
                    cand["traits"],
                    cand["quirk"],
                ),
            )
            cand_id = cursor.lastrowid

            for skill in cand["skills"]:
                skill_id = get_or_create_skill_id(cursor, skill)
                cursor.execute(
                    """
                    INSERT INTO candidate_skills (candidate_id, skill_id)
                    VALUES (?, ?)
                    """,
                    (cand_id, skill_id),
                )

        # Ingest Jobs & job_skills
        for job in jobs_data:
            cursor.execute(
                """
                INSERT INTO jobs (title, min_experience, culture_keywords, tagline)
                VALUES (?, ?, ?, ?)
                """,
                (
                    job["title"],
                    job["min_experience"],
                    job["culture_keywords"],
                    job["tagline"],
                ),
            )
            job_id = cursor.lastrowid

            for skill in job["skills"]:
                skill_id = get_or_create_skill_id(cursor, skill)
                cursor.execute(
                    """
                    INSERT INTO job_skills (job_id, skill_id)
                    VALUES (?, ?)
                    """,
                    (job_id, skill_id),
                )

        cursor.execute("SELECT COUNT(*) FROM candidates")
        c_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM jobs")
        j_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM skills")
        s_count = cursor.fetchone()[0]

        conn.commit()
        return c_count, j_count, s_count
    finally:
        conn.close()


if __name__ == "__main__":
    print(f"Initializing database at: {DB_PATH}")
    c_count, j_count, s_count = seed_database()
    print(f"Successfully seeded database:")
    print(f" - Candidates: {c_count}")
    print(f" - Jobs:       {j_count}")
    print(f" - Unique Skills: {s_count}")
