def score_resume(resume_text, required_keywords):
    resume_text = resume_text.lower()
    match_count = sum(1 for keyword in required_keywords if keyword in resume_text)
    return round(match_count / len(required_keywords), 2) if required_keywords else 0.0

def score_sections(clean_resume, skills, roles):
    skills_score = score_resume(clean_resume, skills)
    roles_score = score_resume(clean_resume, roles)
    overall_score = score_resume(clean_resume, skills + roles)
    return skills_score, roles_score, overall_score