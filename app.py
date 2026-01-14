import streamlit as st
import spacy
from io import BytesIO
import fitz  # PyMuPDF
import docx
import pandas as pd
import matplotlib.pyplot as plt

st.markdown("""
<style>
/* App background */
.stApp {
    background-color: #F4F6F9;  /* soft neutral grey */
}

/* Main content container */
.block-container {
    background-color: #FFFFFF;
    padding: 2.5rem 2.5rem 3rem 2.5rem;
    border-radius: 16px;
    box-shadow: 0 8px 25px rgba(0,0,0,0.05);
}

/* Headings */
h1, h2, h3 {
    color: #1F3A5F;
    font-family: 'Segoe UI', sans-serif;
    font-weight: 600;
}

/* Body text */
p, span, label {
    color: #34495E;
    font-family: 'Segoe UI', sans-serif;
}

/* Buttons */
.stButton > button {
    background-color:#F4F6F9;
    color: white;
    border-radius: 10px;
    border: none;
    padding: 0.6rem 1.3rem;
    font-weight: 1000;
    transition: 0.25s ease;
}
.stButton > button:hover {
    background-color: #e1e4e8;
    transform: translateY(-1px);
}

/* Inputs */
input, textarea {
    border-radius: 8px !important;
    border: 1px solid #D5DBDB !important;
    padding: 0.4rem 0.6rem;
}

/* Tables */
[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
}

/* Sidebar (optional) */
section[data-testid="stSidebar"] {
    background-color: #EEF1F5;
}
</style>
""", unsafe_allow_html=True)


# -------------------
# Simple User Database
# -------------------
USER_CREDENTIALS = {
    "admin": "1234",
    "hruser": "password"
}

# -------------------
# Load NLP Model
# -------------------
nlp = spacy.load("en_core_web_sm")

# -------------------
# Utility Functions
# -------------------
def preprocess_text(text):
    """Clean and preprocess resume text using SpaCy"""
    doc = nlp(text)
    tokens = [token.lemma_ for token in doc if not token.is_stop and not token.is_punct]
    return " ".join(tokens)


def score_resume(resume_text, required_keywords):
    """Calculate keyword match score"""
    resume_text = resume_text.lower()
    match_count = sum(1 for keyword in required_keywords if keyword in resume_text)
    return round(match_count / len(required_keywords), 2) if required_keywords else 0.0


def extract_text_from_pdf(uploaded_file):
    """Extract text content from a PDF file"""
    uploaded_file.seek(0)  # reset file pointer
    file_bytes = uploaded_file.read()
    if not file_bytes:
        return ""
    pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in pdf_document:
        text += page.get_text()
    return text


def extract_text_from_docx(uploaded_file):
    """Extract text content from a DOCX file"""
    uploaded_file.seek(0)  # reset file pointer
    file_bytes = uploaded_file.read()
    if not file_bytes:
        return ""
    doc_obj = docx.Document(BytesIO(file_bytes))
    return "\n".join(p.text for p in doc_obj.paragraphs)



from spacy.matcher import Matcher

# Create matcher once (not inside the function)
matcher = Matcher(nlp.vocab)

# Common job title patterns
job_title_patterns = [
    # e.g., "Data Analyst", "Software Engineer"
    [{"POS": "PROPN"}, {"POS": "PROPN"}],

    # e.g., "Senior Data Analyst"
    [{"POS": "ADJ"}, {"POS": "PROPN"}, {"POS": "PROPN"}],

    # e.g., "Project Manager at"
    [{"POS": "PROPN"}, {"POS": "PROPN"}, {"LOWER": "at"}],

    # e.g., "Engineer at Petronas"
    [{"POS": "PROPN"}, {"LOWER": "at"}, {"POS": "PROPN"}],

    # e.g., “Software Engineer – 2021–2023”
    [{"POS": "PROPN"}, {"POS": "PROPN"}, {"IS_PUNCT": True}, {"IS_DIGIT": True}],
]

matcher.add("JOB_TITLES", job_title_patterns)


# -----------------------------------------------------
# UPDATED process_resume() with improved job-title NLP
# -----------------------------------------------------
def process_resume(uploaded_file, skills, roles):

    # --- Extract text ---
    if uploaded_file.name.endswith(".pdf"):
        resume_text = extract_text_from_pdf(uploaded_file)
    elif uploaded_file.name.endswith(".docx"):
        resume_text = extract_text_from_docx(uploaded_file)
    else:
        return None

    # --- Preprocess text ---
    clean_resume = preprocess_text(resume_text)
    doc = nlp(resume_text)

    # --- Named Entity Extraction (PERSON + ORG) ---
    entities = [ent.text.lower() for ent in doc.ents if ent.label_ in ["PERSON", "ORG"]]

    # ---------------------------------------------------------
    # NEW: Smart Job Title Detection using SpaCy Matcher
    # ---------------------------------------------------------
    matches = matcher(doc)
    job_titles = []

    for match_id, start, end in matches:
        span = doc[start:end]
        text = span.text.strip().lower()

        # Filter out too-short titles (e.g., 1-word noise)
        if len(text.split()) >= 2:
            job_titles.append(text)

    # Remove duplicates
    job_titles = list(set(job_titles))

    # ---------------------------------------------------------
    # Old rule-based method kept as backup
    # ---------------------------------------------------------
    for sent in doc.sents:
        if " as " in sent.text.lower():
            parts = sent.text.lower().split(" as ")
            if len(parts) > 1:
                title = parts[1].split(",")[0].split(".")[0].strip()
                if len(title.split()) >= 1:
                    job_titles.append(title)

    # Combine and clean for scoring
    combined_text = clean_resume + " " + " ".join(entities + job_titles)

    # --- Scoring ---
    skills_score = score_resume(combined_text, skills)
    roles_score = score_resume(combined_text, roles)

    # --- Weighting (role = 2x importance) ---
    role_weight = 2.0
    skill_weight = 1.0

    weighted_score = (
        (roles_score * role_weight) + (skills_score * skill_weight)
    ) / (role_weight + skill_weight)

    return {
        "Candidate": uploaded_file.name,
        "Skills Match (%)": skills_score * 100,
        "Role Match (%)": roles_score * 100,
        "Overall Match (%)": weighted_score * 100,
        # optional debugging to check extraction:
        # "Extracted Job Titles": job_titles
    }

# -------------------
def login_page():

    # --- Page Title ---
    st.markdown(
        """
        <h1 style='text-align:center; margin-bottom:10px;'> AI Resume Screening </h1>
        <p style='text-align:center; margin-top:-10px; color:gray;'>
            Please sign in to access the system
        </p>
        """,
        unsafe_allow_html=True
    )

    # --- Login Card (no extra container) ---
    st.markdown(
        """
        <style>
            .login-card {
                background-color: #ffffff;
                padding: 30px;
                border-radius: 12px;
                width: 380px;
                margin: 20px auto;     /* <-- space only here */
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            }
            .animated-button {
                display: inline-block;
                padding: 12px 24px;
                border-radius: 8px;
                background: #2E86C1;
                color: white;
                text-align: center;
                font-size: 16px;
                cursor: pointer;
                width: 100%;
                transition: 0.3s ease;
                border: none;
            }
            .animated-button:hover {
                background: #1B4F72;
                transform: scale(1.03);
            }
            .animated-button:active {
                transform: scale(0.97);
            }
        </style>

    
        """,
        unsafe_allow_html=True
    )

    username = st.text_input("👤 Username")
    password = st.text_input("🔒 Password", type="password")

    login_button = st.button("Access Resume Screening", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # --- Login Logic ---
    if login_button:
        if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
            st.session_state["logged_in"] = True
            st.session_state["user"] = username
            st.session_state["page"] = "upload"
            st.success(f"✅ Welcome, {username}!")
            st.rerun()
        else:
            st.error("Invalid username or password")

# -------------------
# Upload Page
# -------------------

def upload_page():
    st.title("Applicant Resume Upload")
    st.write(f"Hello, **{st.session_state['user']}** ")

    st.markdown("""
    ###  Upload Candidate Resumes
    Upload resumes and specify the required skills and job role keywords.
    """)

    uploaded_files = st.file_uploader(
        "Upload Resumes (PDF/DOCX)",
        type=["pdf", "docx"],
        accept_multiple_files=True
    )

    skills_input = st.text_input("Required Skills", placeholder="e.g. Python, SQL")
    role_input = st.text_input("Job Role Keywords", placeholder="e.g. Data Analyst")

    col1, col2 = st.columns(2)

    with col1:
        if st.button(" Process Resumes"):
            if not uploaded_files:
                st.error("Please upload at least one resume.")
            elif not skills_input and not role_input:
                st.error("Please enter required skills or role keywords.")
            else:
                # --- PROGRESS BAR IMPLEMENTATION ---
                skills = [s.strip().lower() for s in skills_input.split(",") if s.strip()]
                roles = [r.strip().lower() for r in role_input.split(",") if r.strip()]
                
                # 1. Create the progress bar object
                progress_bar = st.progress(0, text="Starting analysis...")
                all_results = []
                
                # 2. Loop through files and update bar
                total_files = len(uploaded_files)
                for i, uploaded_file in enumerate(uploaded_files):
                    # Update message and percentage
                    msg = f"Analyzing {uploaded_file.name} ({i+1}/{total_files})"
                    progress_bar.progress((i + 1) / total_files, text=msg)
                    
                    # Process the file
                    result = process_resume(uploaded_file, skills, roles)
                    if result:
                        all_results.append(result)
                
                # 3. Store data in session state so results_page can use it
                st.session_state["results_data"] = all_results
                st.session_state["skills_input"] = skills_input
                st.session_state["role_input"] = role_input
                st.session_state["uploaded_files"] = uploaded_files
                
                # 4. Clean up and move to results
                progress_bar.empty()
                st.session_state["page"] = "results"
                st.rerun()

    with col2:
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()



# -------------------
# Results Page
# -------------------
def results_page():
    # --- 1. TOP HEADER NAVIGATION ---
    col_logo, col_user = st.columns([4, 1.2])
    with col_logo:
        st.markdown("<h1 style='margin-top:-10px;'> AI Resume Screening</h1>", unsafe_allow_html=True)
    with col_user:
        st.write(f"Welcome, **{st.session_state['user']}**")
        if st.button("Logout", key="logout_top", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    st.subheader("Screening Results")
    
    # --- 2. DATA RETRIEVAL (USE CACHED RESULTS) ---
    skills = [s.strip().lower() for s in st.session_state["skills_input"].split(",") if s.strip()]
    roles = [r.strip().lower() for r in st.session_state["role_input"].split(",") if r.strip()]

    # Use the data processed in the upload page instead of re-processing
    results = st.session_state.get("results_data", [])

    if not results:
        st.warning("No resumes found. Please go back and upload.")
        return

    df = pd.DataFrame(results)


    # --- 3. BLUE STATUS BAR ---
    st.markdown(f"""
        <div style="background-color: #E8F4FD; border-radius: 10px; padding: 15px; display: flex; align-items: center; margin-bottom: 25px; border: 1px solid #D1E9FA;">
            <span style="font-size: 20px; margin-right: 15px;">ℹ️</span>
            <span style="color: #1A5276; font-family: sans-serif; font-size: 16px;">
                AI has analyzed <b>{len(df)} resumes</b> and ranked candidates based on your criteria.
            </span>
        </div>
    """, unsafe_allow_html=True)

    # --- 4. SORT AND FILTER CONTROLS ---
    col_sort, col_filter, col_spacer, col_actions = st.columns([1.5, 1.5, 1.5, 2.5])
    with col_sort:
        sort_option = st.selectbox("Sort by", ["Overall Match", "Skills Match", "Role Match"])
    with col_filter:
        filter_option = st.selectbox("Filter", ["All Candidates", "Qualified (>= 60%)", "Top 5 Only"])
    with col_actions:
        st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True) 
        act_col1, act_col2 = st.columns(2)
        with act_col1: st.button("📥 Export", use_container_width=True)
        with act_col2:
            if st.button("🔄 New", use_container_width=True):
                st.session_state["page"] = "upload"
                st.rerun()

    # Logic for Sorting/Filtering
    sort_map = {"Overall Match": "Overall Match (%)", "Skills Match": "Skills Match (%)", "Role Match": "Role Match (%)"}
    df = df.sort_values(by=sort_map[sort_option], ascending=False).reset_index(drop=True)
    if filter_option == "Qualified (>= 60%)": df = df[df["Overall Match (%)"] >= 60]
    elif filter_option == "Top 5 Only": df = df.head(5)

    # --- 5. TOP CANDIDATE CARDS ---
    if not df.empty:
        card_col1, card_col2 = st.columns(2)
        for i, col in enumerate([card_col1, card_col2]):
            if i < len(df):
                val = df.iloc[i]
                label = "Top Match" if i == 0 else "Runner Up"
                color = "#2E86C1" if i == 0 else "#5D6D7E"
                bg = "#f0f8ff" if i == 0 else "#ffffff"
                with col:
                    st.markdown(f"""
                        <div style="border: 2px solid {color}; border-radius: 15px; padding: 20px; background-color: {bg}; min-height: 250px;">
                            <span style="background-color: {color}; color: white; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold;">{label}</span>
                            <h3 style="margin: 10px 0;">{val['Candidate']}</h3>
                            <div style="text-align: center; margin: 20px 0;">
                                <h1 style="color: {color}; margin:0;">{val['Overall Match (%)']:.0f}%</h1>
                                <p style="color: gray; margin:0;">Overall Match</p>
                            </div>
                            <hr style="border: 0.5px solid #ddd;">
                            <p style="margin: 5px 0;"> <b>Skills:</b> {val['Skills Match (%)']:.0f}%</p>
                            <p style="margin: 5px 0;"> <b>Role:</b> {val['Role Match (%)']:.0f}%</p>
                        </div>
                    """, unsafe_allow_html=True)

    # --- 6. FULL RANKING TABLE ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Candidate Ranking Detail")
    st.dataframe(df.style.background_gradient(subset=["Overall Match (%)"], cmap="Blues").format("{:.0f}%", subset=["Skills Match (%)", "Role Match (%)", "Overall Match (%)"]), use_container_width=True, hide_index=True)

    # --- 7. RESTORED DROPDOWN DETAILS (The Yes/No Calculation Tables) ---
    st.markdown("---")
    st.subheader("Detailed Match Breakdown")
    for i, row in df.iterrows():
        with st.expander(f" View matching details for {row['Candidate']}"):
            # We need to re-extract or find the text to show the Yes/No
            # Finding the original file object from session state
            original_file = next((f for f in st.session_state["uploaded_files"] if f.name == row["Candidate"]), None)
            
            if original_file:
                # Get the text for this specific candidate
                if original_file.name.endswith(".pdf"): text = extract_text_from_pdf(original_file).lower()
                else: text = extract_text_from_docx(original_file).lower()

                # --- Calculation Summary ---
                st.write(f"**Overall Formula:** (({row['Role Match (%)']:.0f}% × 2) + ({row['Skills Match (%)']:.0f}% × 1)) ÷ 3")
                
                # --- Skill Table ---
                st.write("###  Skills Found")
                skill_data = {
                    "Skill Keyword": skills,
                    "Found": [" Yes" if s in text else "No" for s in skills],
                    "Points": [1 if s in text else 0 for s in skills]
                }
                st.table(pd.DataFrame(skill_data))

                # --- Role Table ---
                st.write("###  Roles Found")
                role_data = {
                    "Role Keyword": roles,
                    "Found": ["Yes" if r in text else "No" for r in roles],
                    "Points": [2 if r in text else 0 for r in roles]
                }
                st.table(pd.DataFrame(role_data))





# -------------------
# App Control Flow
# -------------------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "page" not in st.session_state:
    st.session_state["page"] = "login"

if not st.session_state["logged_in"]:
    login_page()
else:
    if st.session_state["page"] == "upload":
        upload_page()
    elif st.session_state["page"] == "results":
        results_page()

