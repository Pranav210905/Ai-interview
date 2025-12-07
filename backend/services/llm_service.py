import json
from groq import Groq
from backend.config import get_settings, get_settingsgpt
from openai import OpenAI


def get_client():
    """Lazy initialization of Groq client to avoid loading settings at import time."""
    settings = get_settings()
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is required. Please set it in your .env file or environment variables.")
    
    return Groq(api_key=settings.groq_api_key)

def get_clientgpt():
    """Lazy initialization of Groq client to avoid loading settings at import time."""
    settingsgpt = get_settingsgpt()
    if not settingsgpt.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required. Please set it in your.env file or environment variables.")

    return OpenAI(api_key=settingsgpt.openai_api_key)

def generate_questions(job_description: str, resume_text: str, duration_seconds: int) -> list:
    client = get_client()
    system_prompt = """You are an expert interviewer. Produce ONLY valid JSON:
{"questions":[{"id":"q1", "text":"...", "estimated_seconds":90}]}
Questions must be tailored to the job description and resume."""

    user_prompt = f"""Job Description:
{job_description}

Resume:
{resume_text}

Interview Duration (seconds): {duration_seconds}"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2000,
        )
    except Exception as e:
        raise ValueError(
            f"Error calling Groq API: {str(e)}. Please check your GROQ_API_KEY and try again."
        ) from e

    content = response.choices[0].message.content.strip()

    try:
        result = json.loads(content)
        return result.get("questions", [])
    except json.JSONDecodeError:
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        result = json.loads(content)
        return result.get("questions", [])

def evaluate_answer(question: str, transcript: str, reference_answer: str) -> dict:
    client = get_clientgpt()
    #client = get_client()
    system_prompt = """You are an expert technical interviewer evaluating candidate responses.
Evaluate the candidate's answer on these dimensions (1-10 each):

1. **Relevance** – Does it directly answer the question?
2. **Technical Accuracy** – Are the facts, methods, or concepts correct?
3. **Depth** – Does it show understanding and reasoning or just surface-level points?
4. **Communication Clarity** – Is it clear, structured, and confident?
5. **Overall Fit** – Based on the job role, does this reflect the expected competence?

Return ONLY strict JSON in this format:
{
  "scores": {
    "relevance": int,
    "accuracy": int,
    "depth": int,
    "clarity": int,
    "fit": int
  },
  "total_score": int,
  "feedback": ["specific, short feedback points"],
  "comparison_summary": "how this differs from the ideal answer"
}
"""

    user_prompt = f"""Question: {question}
Candidate's Answer: {transcript}
Ideal Reference Answer: {reference_answer}
Give objective scoring, not polite feedback. Penalize vague or incorrect answers heavily.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        #model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,
        max_tokens=1500,
    )

    content = response.choices[0].message.content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON if wrapped in code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        return json.loads(content)


def generate_reference_answer(question: str, jd: str, resume: str):
    client = get_client()
    system_prompt = """You are an interview expert. Write a high-quality, ideal answer to the interview question below, considering the candidate's resume and the job description. Keep it concise and professional."""
    user_prompt = f"""Job Description: {jd}
Resume Summary: {resume}
Question: {question}"""
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.5,
        max_tokens=500,
    )
    return response.choices[0].message.content.strip()
