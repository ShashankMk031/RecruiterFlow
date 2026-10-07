-- ============================================================================
-- RecruiterFlow - Part 2: The SQL Detective Challenge
-- File: sql_detective.sql
-- ============================================================================

-- Question 1:
-- List all currently open job postings, along with the name of the recruiter who owns each one.
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


-- Question 2:
-- For each job posting, how many applicants reached the Final interview stage?
SELECT 
    jp.id AS job_posting_id,
    jp.title,
    COUNT(DISTINCT CASE WHEN i.stage = 'Final' THEN i.applicant_id END) AS final_stage_applicants
FROM job_postings jp
LEFT JOIN interviews i ON jp.id = i.job_posting_id
GROUP BY jp.id, jp.title
ORDER BY jp.id;


-- Question 3:
-- Find every person who effectively applied to more than one job posting. 
-- Careful — the data isn't as clean as it looks (handles casing in email and distinct applicant records).
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


-- Question 4:
-- For each recruiter, compute their Final-stage conversion rate (passed ÷ total Final-stage interviews),
-- but only include recruiters with at least 3 Final-stage interviews.
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


-- Question 5 (Bonus):
-- Using a window function, find the recruiter with the most successful placements (passed at Final stage) per department.
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
