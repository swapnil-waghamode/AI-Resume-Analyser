import json
import os
from dotenv import load_dotenv

import streamlit as st 
from docx import Document
from pypdf import PdfReader
from openai import OpenAI 

# Load .env variables
load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL")

# Report Section 

REPORT_SECTIONS = [
  ("strengths","Strengths"),
  ("gaps","Gaps"),
  ("missing_or_weak_skills","Missing or Weak Skills"),
  ("improvement_suggestions","Improvement Suggestion"),
  ("overall_summary", "Overall Summary"),
]

# Extracting resume text

def extract_resume_text(uploaded_file):
  """Return the plain text of an uploaded PDF or DOCX resume"""

  file_name = uploaded_file.name.lower()

  # If file is pdf
  if file_name.endswith(".pdf"):
    reader = PdfReader(uploaded_file)

    pages = []

    # appending pdf text data from page to pages list
    for page in reader.pages:
      pages.append(page.extract_text() or "")  # if pdf has nothing then ""

    return "\n".join(pages).strip()


  # if file is docx
  if file_name.endswith(".docx"):

    document = Document(uploaded_file)

    paragraphs = []

    for p in document.paragraphs:
      paragraphs.append(p.text or "")

    return "\n".join(paragraphs).strip()

  return "NO INPUT WAS GIVEN AS CV, ask the user for it."


# Resume Analyse

def analyse_resume(resume_text, job_description):
  """LLM call #1 : turn the resume and JD into structured JSON"""

  client = OpenAI(
    api_key= API_KEY
  )

  instructions = """You compare resume against job descriptions.

  Reply with JSON only, using exactly these keys. Every value is list of short strings.

  {
    "candidate_skills" : [],
    "candidate_experience" : [],
    "candidate_qualification" : [],
    "requidred_skills" : [],
    "preferred_skills" : [],
    "matching_skills" : [],
    "missing_skills" : [],
    "gaps" : []
      
  }

  Rules:
  - Use only information that actually appears in the resume or the job description.
  - Never invent skills, employers, job titles, dates etc.
  - "missing_skills" means the job description asks for it and the resume does not mention it.
  - Leave a list empty when text gives you nothing to put in it.

"""

  user_message = f"""
                  Compare this resume against this job description and reply with JSON.

                  RESUME:
                  {resume_text}

                  JOB_DESCRIPTION:
                  {job_description}
   

"""

  response = client.responses.create(
    model= MODEL,
    instructions= instructions,
    input= user_message,
    text = {"format": {"type": "json_object"}}
  )

  return json.loads(response.output_text)


# Final Report ------
def generate_final_report(structured_analysis):
  """LLM call #2 : turn the structured JSON into readable report."""

  client = OpenAI(api_key=API_KEY)

  instructions = """You write short, honest resume feedback for a candidate.

      You receive JSON that was built from a resume and a job description.
      Reply with JSON only, using exactly these keys. Every value is a string.

      {
        "strengths": "",
        "gaps": "",
        "missing_or_weak_skills": "",
        "improvement_suggestions": "",
        "overall_summary": ""
      }

      Rules:
      - Write the first four values as Markdown bullet lists, one point per line ("- point").
      - Write "overall_summary" as one short paragraph.
      - Never leave a value empty. If a section has nothing to report, say so in one bullet,
        such as "- Nothing further was identified from the provided resume."
      - Put specific tools and technologies in "missing_or_weak_skills", and put experience,
        qualifications and responsibilities in "gaps", so the two do not repeat each other.
      - Base everything on the JSON you are given, and do not invent anything new.
      - Never use the words "lacks", "lacking", "no experience", "no exposure",
        "does not know" or "does not have" anywhere, including the overall summary.
        You only know what this one resume mentions, not what the candidate can really do.
        Write "Apache Airflow was not identified in the provided resume" and
        "The resume does not show the 3+ years of analytics experience the role asks for".
      - Do not give a numeric score or a percentage.
"""

  user_message = f"""
                Turn this structured data into resume feedback and reply with JSON.
                {json.dumps(structured_analysis, indent= 2)}
"""

  response = client.responses.create(
    model= MODEL,
    instructions= instructions,
    input= user_message,
    text = {"format": {"type": "json_object"}}
  )

  report =  json.loads(response.output_text)

  # iterating over report section and getting value for respective key
  for key, _ in REPORT_SECTIONS:

    value = report.get(key)

    if isinstance(value, list):
      value = "\n".join("- " + str(point) for point in value)

    report[key] = value or "Nothing was reported for this section."


  return report

# report download functionality

def create_downloadable_report(final_report):

  """Build the markdown text for resume_analysis.md download."""

  lines = ["# Resume Analysis"]

  for key, heading in REPORT_SECTIONS:

    lines.append(f"## {heading}")
    lines.append(final_report[key])

  return "\n\n".join(lines)



def main():

  st.set_page_config(page_title = "AI Resume Analyzer")
  st.title("AI Resume Analyzer")

  st.write(
    "Upload your resume and paste a JOB Description to identify strengths, "
    "gaps and improvement opportunities."
  )

  uploaded_file = st.file_uploader("Upload your resume", type = ["pdf","docx"])
  job_description = st.text_area("Paste your Job Description", height=200)

  if st.button("Analyze Resume"):

    if uploaded_file is None:
      st.warning("Please upload your resume.")
      st.stop() 

    if not job_description:
      st.warning("Please paste job description.")
      st.stop()

    # getting resume data from extract_resume_text function by pasing file

    resume_text = extract_resume_text(uploaded_file)

    if not resume_text:
      st.warning("No text could be read from your resume file, try different format.")

    if not API_KEY:
      st.error("no api key found in .env file.")

    with st.spinner("Analyze your resume..."):

      try:
        structured_analysis = analyse_resume(resume_text,job_description)
        final_report = generate_final_report(structured_analysis)
      except Exception as error:
        print(f"The analysis failed :{error}")
        st.stop()


    st.session_state["final_report"] = final_report

    if "final_report" in st.session_state:

      final_report = st.session_state["final_report"]

      st.divider()

      st.subheader("Resume Analysis")

      for key,heading in REPORT_SECTIONS:

        st.markdown("### " + heading)
        st.markdown(final_report[key])

      st.download_button(
        "Download Report",
        data = create_downloadable_report(final_report),
        file_name="resume_analysis.md",
      )


if __name__ == "__main__":
  main()

