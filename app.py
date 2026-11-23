import streamlit as st
import json
import requests
import re

# -----------------------------
# LOAD SCHEME DATABASE
# -----------------------------

with open("schemes.json", "r", encoding="utf-8") as file:
    schemes = json.load(file)


# -----------------------------
# TOKENIZE TEXT
# -----------------------------

def tokenize(text):
    text = text.lower()
    words = re.findall(r"\w+", text)
    return set(words)


# -----------------------------
# FIND RELEVANT SCHEME
# -----------------------------

def find_scheme(question):
    question_words = tokenize(question.lower())

    # Detect SC-related questions
    sc_query = (
        "sc" in question_words
        or ("scheduled" in question_words and "caste" in question_words)
    )

    aliases = {
        "sc": ["scheduled", "caste", "post", "matric", "scholarship"],
        "scheduled": ["sc", "caste", "scholarship", "student"],
        "caste": ["sc", "scheduled", "scholarship"],
        "college": ["student", "scholarship", "education"],
        "scholarship": ["student", "financial", "education"],
        "student": ["college", "scholarship"],
    }

    expanded_words = set(question_words)

    for word in question_words:
        if word in aliases:
            expanded_words.update(aliases[word])

    results = []

    for scheme in schemes:

        title_text = " ".join([
            scheme.get("title_en", ""),
            scheme.get("title_kn", "")
        ])

        keyword_text = " ".join([
            str(scheme.get("keywords_en", [])),
            str(scheme.get("keywords_kn", []))
        ])

        other_text = " ".join([
            scheme.get("summary_en", ""),
            scheme.get("summary_kn", ""),
            scheme.get("eligibility_en", ""),
            scheme.get("eligibility_kn", ""),
            scheme.get("documents_en", ""),
            scheme.get("documents_kn", ""),
            scheme.get("steps_en", ""),
            scheme.get("steps_kn", "")
        ])

        title_words = tokenize(title_text)
        keyword_words = tokenize(keyword_text)
        other_words = tokenize(other_text)

        title_score = len(expanded_words.intersection(title_words))
        keyword_score = len(expanded_words.intersection(keyword_words))
        other_score = len(expanded_words.intersection(other_words))

        total_score = (
            title_score * 3 +
            keyword_score * 2 +
            other_score
        )

        # Prioritize the SC-specific scheme for SC questions
        scheme_identity = (
            title_text.lower() + " " + keyword_text.lower()
        )

        if sc_query and (
            "scheduled caste" in scheme_identity
            or "post-matric scholarship for sc" in scheme_identity
            or "pms-sc" in scheme_identity
        ):
            total_score += 100

        if total_score > 0:
            results.append((total_score, scheme))
# Direct priority for SC scholarship questions
    if "sc" in question_words:
        for scheme in schemes:
            title = scheme.get("title_en", "").lower()
            keywords = str(scheme.get("keywords_en", [])).lower()

            if "scheduled caste" in title or "pms-sc" in title or "scheduled caste" in keywords:
                return scheme
    results.sort(key=lambda item: item[0], reverse=True)

    if results:
        return results[0][1]

    return None


# -----------------------------
# GENERATE AI EXPLANATION
# -----------------------------

def generate_answer(question, scheme, language):

    if language == "Kannada":
        language_instruction = "Kannada"
    else:
        language_instruction = "English"

    context = json.dumps(
        scheme,
        ensure_ascii=False,
        indent=2
    )

    prompt = f"""
You are Civic Pulse, a reliable multilingual government
information assistant.

Your task is to help citizens understand government
schemes in simple and clear language.

Answer strictly in {language_instruction}.

Use ONLY the scheme information provided below.
Do not use your own assumptions or invent facts.

SCHEME INFORMATION:
{context}

USER QUESTION:
{question}

RULES:
1. Answer the user's exact question directly.
2. Use simple, easy-to-understand language.
3. Do not invent eligibility rules, benefits, amounts,
   deadlines, required documents or application procedures.
4. If a requested detail is missing, clearly state that
   it is not available in the provided information.
5. Do not assume a person is eligible for a scheme.
6. Recommend checking the official source for confirmation.
7. Keep the answer helpful, clear and reasonably concise.
8. Do not switch languages. Answer only in the
   language specified above.

Provide a factual and trustworthy explanation.
"""

    try:

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2:3b",
                "prompt": prompt,
                "stream": False
            },
            timeout=180
        )

        response.raise_for_status()

        data = response.json()

        return data.get("response", "No response received.")

    except requests.exceptions.RequestException as e:

        return (
            "Unable to connect to the AI service. "
            "Please check whether Ollama is running."
        )


# -----------------------------
# CIVIC PULSE USER INTERFACE
# -----------------------------

st.set_page_config(
    page_title="Civic Pulse",
    page_icon="🏛️",
    layout="centered"
)

st.title("🏛️ Civic Pulse")

st.subheader(
    "Multilingual Policy, Rights & Scheme Explainer"
)

st.write(
    "Ask questions about government schemes "
    "in simple language."
)

st.info(
    "Civic Pulse is a prototype. "
    "Please verify scheme information using official sources."
)


# -----------------------------
# LANGUAGE SELECTION
# -----------------------------

language = st.selectbox(
    "Choose your language",
    ["English", "Kannada"]
)


# -----------------------------
# USER QUESTION
# -----------------------------

question = st.text_area(
    "Enter your question",
    placeholder=(
        "Example: I am an SC student studying in college. "
        "Is there any scholarship available for me?"
    )
)


# -----------------------------
# SUBMIT QUESTION
# -----------------------------

if st.button("Get Explanation"):

    if not question.strip():

        st.warning("Please enter a question.")

    else:

        matched_scheme = find_scheme(question)

        if matched_scheme is None:

            st.warning(
                "No matching scheme was found in the "
                "current database. Please try different "
                "keywords or check the official portal."
            )

        else:

            st.success("Relevant scheme found!")

            if language == "Kannada":
                scheme_title = matched_scheme.get(
                    "title_kn",
                    matched_scheme.get("title_en", "")
                )
            else:
                scheme_title = matched_scheme.get(
                    "title_en",
                    matched_scheme.get("title_kn", "")
                )

            st.subheader(scheme_title)

            with st.spinner("Generating explanation..."):

                answer = generate_answer(
                    question,
                    matched_scheme,
                    language
                )

            st.markdown("### AI Explanation")

            st.write(answer)

            source_url = matched_scheme.get("source_url")

            if source_url:

                st.markdown(
                    f"**Official source:** [Visit website]({source_url})"
                )

            st.caption(
                "Please confirm the latest eligibility, "
                "deadlines and requirements on the official website."
            )