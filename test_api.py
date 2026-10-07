"""
test_api.py - Automated test suite for RecruiterFlow API.
"""

import os
import pytest
from fastapi.testclient import TestClient
from main import app, DB_PATH
from seed import seed_database


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    seed_database(DB_PATH)


client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "RecruiterFlow Bot API"
    assert "job_matches" in data["endpoints"]


def test_list_jobs():
    response = client.get("/jobs")
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 6
    job_titles = [j["title"] for j in jobs]
    assert "Backend Detective" in job_titles
    assert "Rapid Prototyping Engineer" in job_titles


def test_list_candidates():
    response = client.get("/candidates")
    assert response.status_code == 200
    candidates = response.json()
    assert len(candidates) == 15
    candidate_names = [c["name"] for c in candidates]
    assert "Sherlock H." in candidate_names
    assert "Tony S." in candidate_names


def test_job_matches_backend_detective():
    response = client.get("/jobs/1/matches")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == 1
    assert data["title"] == "Backend Detective"
    assert set(data["required_skills"]) == {"deduction", "pattern-recognition", "forensics"}
    
    matches = data["matches"]
    assert len(matches) == 15
    
    # Sherlock H. must be top match with perfect score 100
    top = matches[0]
    assert top["candidate_id"] == 1
    assert top["name"] == "Sherlock H."
    assert top["matched_skills_count"] == 3
    assert top["score"] == 100
    assert "deduction" in top["matching_skills"]
    assert "Full skill match" in top["reason"]

    # Sheldon C. should have 1 skill match
    sheldon = next(m for m in matches if m["name"] == "Sheldon C.")
    assert sheldon["matched_skills_count"] == 1
    assert sheldon["matching_skills"] == ["pattern-recognition"]
    assert sheldon["score"] > 50


def test_job_matches_rapid_prototyping():
    response = client.get("/jobs/2/matches")
    assert response.status_code == 200
    data = response.json()
    
    top_candidates = [m["name"] for m in data["matches"][:3]]
    # Rick S., Tony S., and MacGyver all have 2/2 matching skills
    assert "Rick S." in top_candidates
    assert "Tony S." in top_candidates
    assert "MacGyver" in top_candidates


def test_candidate_matches_sherlock():
    response = client.get("/candidates/1/matches")
    assert response.status_code == 200
    data = response.json()
    assert data["candidate_id"] == 1
    assert data["name"] == "Sherlock H."
    
    top_job = data["matches"][0]
    assert top_job["job_id"] == 1
    assert top_job["title"] == "Backend Detective"
    assert top_job["score"] == 100
    assert top_job["matched_skills_count"] == 3


def test_candidate_matches_hermione():
    # Hermione G.: research, time-management, public-speaking
    # DevRel Lead: public-speaking, research
    response = client.get("/candidates/2/matches")
    assert response.status_code == 200
    data = response.json()
    
    top_job = data["matches"][0]
    assert top_job["title"] == "Developer Relations Lead"
    assert top_job["matched_skills_count"] == 2


def test_nonexistent_ids():
    res_job = client.get("/jobs/999/matches")
    assert res_job.status_code == 404
    assert "not found" in res_job.json()["detail"].lower()

    res_cand = client.get("/candidates/999/matches")
    assert res_cand.status_code == 404
    assert "not found" in res_cand.json()["detail"].lower()
