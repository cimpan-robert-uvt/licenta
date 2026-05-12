import json
import os
import re

from google import genai
from django.conf import settings


DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_MODEL = getattr(settings, "GEMINI_MODEL", DEFAULT_GEMINI_MODEL)

DEFAULT_MODEL_FALLBACKS = [
    # "gemini-2.5-flash",
    # "gemini-2.5-flash-lite",
    # "gemini-3-flash-preview",
    # "gemini-3.1-flash-lite-preview",
]
MODEL_FALLBACKS = getattr(settings, "GEMINI_MODEL_FALLBACKS", DEFAULT_MODEL_FALLBACKS)


def get_gemini_client():
    """Inițializează clientul Gemini folosind cheia din settings."""
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _should_try_next_model(exc):
    message = str(exc or "")
    status_code = getattr(exc, "status_code", None)
    if status_code in {429, 503}:
        return True

    return any(
        token in message
        for token in (
            "NOT_FOUND",
            "RESOURCE_EXHAUSTED",
            "UNAVAILABLE",
            "high demand",
        )
    )


def generate_with_project_model(client, contents, model_name=None):
    """Generează conținut folosind modelul configurat centralizat."""
    requested_model = model_name or GEMINI_MODEL

    candidates = [requested_model]
    for fallback in MODEL_FALLBACKS:
        if fallback and fallback not in candidates:
            candidates.append(fallback)

    last_error = None
    for idx, candidate in enumerate(candidates):
        try:
            return client.models.generate_content(
                model=candidate,
                contents=contents,
            )
        except Exception as exc:
            last_error = exc
            is_last = idx == len(candidates) - 1
            if is_last or not _should_try_next_model(exc):
                raise

    if last_error:
        raise last_error

    raise RuntimeError("Nu s-a putut genera răspuns de la niciun model Gemini.")


# def test_gemini_connection():
#     client = get_gemini_client()
#     try:
#         response = generate_with_project_model(
#             client,
#             contents="Salut! Te rog confirma ca aceasta conexiune cu noul pachet google-genai functioneaza.",
#         )
#         return f"Model activ: {GEMINI_MODEL}\n{response.text}"
#     except Exception as e:
#         return f"Eroare la conectare Gemini (New SDK): {str(e)}"


def _extract_json_text(raw_text):
    text = (raw_text or "").strip()
    if not text:
        return "{}"

    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    return text


def _serialize_offers(offers_list):
    serialized = []
    for offer in offers_list:
        serialized.append(
            {
                "offer_id": offer.id,
                "title": offer.title,
                "description": offer.description,
                "requirements": offer.requirements,
                "location": offer.location,
                "duration_weeks": offer.duration_weeks,
                "start_date": offer.start_date.isoformat()
                if offer.start_date
                else None,
            }
        )
    return serialized


def _build_manual_cv_text(student_cv):
    lines = []
    lines.append(f"Oraș: {student_cv.city or ''}")
    lines.append(f"Rezumat: {student_cv.resume or ''}")

    lines.append("\nEducație:")
    for edu in student_cv.education.all():
        lines.append(
            f"- {edu.school_name or ''} | {edu.start_date or ''} - {edu.end_date or ''} | {edu.details or ''}"
        )

    lines.append("\nExperiență:")
    for exp in student_cv.experience.all():
        lines.append(
            f"- {exp.institution_name or ''} | {exp.start_date or ''} - {exp.end_date or ''} | {exp.details or ''}"
        )

    lines.append("\nAbilități:")
    for skill in student_cv.skills.all():
        lines.append(f"- {skill.skill_name or ''} ({skill.get_skill_type_display()})")

    return "\n".join(lines)


def _safe_int(value, default=0):
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _clamp_score(value):
    return max(0, min(100, value))


def _is_pdf_path(value):
    return (
        isinstance(value, str)
        and value.lower().endswith(".pdf")
        and os.path.exists(value)
    )


def _empty_evidence_profile():
    return {
        "has_pdf": False,
        "resume_chars": 0,
        "skills_count": 0,
        "experience_count": 0,
        "education_count": 0,
    }


def _count_non_empty(queryset, field_name):
    return (
        queryset.exclude(**{f"{field_name}__isnull": True})
        .exclude(**{field_name: ""})
        .count()
    )


def _build_cv_contents_and_profile(client, cv_data, prompt):
    """Build request contents and evidence profile from any supported CV input type."""
    profile = _empty_evidence_profile()

    if hasattr(cv_data, "pdf_file"):
        student_cv = cv_data
        profile["has_pdf"] = bool(student_cv.pdf_file)
        profile["resume_chars"] = len((student_cv.resume or "").strip())

        if student_cv.pdf_file:
            try:
                uploaded_file = client.files.upload(file=student_cv.pdf_file.path)
            except Exception:
                uploaded_file = client.files.upload(file=student_cv.pdf_file.file)
            return [uploaded_file, prompt], profile

        profile["skills_count"] = _count_non_empty(student_cv.skills, "skill_name")
        profile["experience_count"] = _count_non_empty(student_cv.experience, "details")
        profile["education_count"] = _count_non_empty(student_cv.education, "details")

        cv_text = _build_manual_cv_text(student_cv)
        return f"CV student:\n{cv_text}\n\n{prompt}", profile

    if _is_pdf_path(cv_data):
        profile["has_pdf"] = True
        uploaded_file = client.files.upload(file=cv_data)
        return [uploaded_file, prompt], profile

    text = (cv_data or "").strip() if isinstance(cv_data, str) else ""
    profile["resume_chars"] = len(text)
    return f"CV student:\n{text}\n\n{prompt}", profile


def _compute_weighted_score(item):
    """Compute a more granular score from optional subscores returned by the model."""
    raw_score = _clamp_score(_safe_int(item.get("score", item.get("scor", 0))))

    components = [
        ("skills_match", 0.50),
        ("experience_match", 0.30),
        ("education_match", 0.20),
    ]

    weighted_sum = 0.0
    present_components = 0

    for key, weight in components:
        if key in item and item.get(key) is not None:
            component_score = _clamp_score(_safe_int(item.get(key), default=0))
            weighted_sum += component_score * weight
            present_components += 1

    if present_components >= 2:
        return _clamp_score(int(round(weighted_sum)))

    return raw_score


def _score_cap_from_evidence(profile):
    if profile.get("has_pdf"):
        return None

    resume_chars = profile.get("resume_chars", 0)
    skills_count = profile.get("skills_count", 0)
    experience_count = profile.get("experience_count", 0)
    education_count = profile.get("education_count", 0)

    evidence_points = 0
    evidence_points += min(resume_chars, 500) / 10.0
    evidence_points += min(skills_count, 8) * 7
    evidence_points += min(experience_count, 5) * 8
    evidence_points += min(education_count, 4) * 4

    if evidence_points < 20:
        return 20
    if evidence_points < 35:
        return 35
    return None


def _apply_evidence_caps(payload, profile):
    cap = _score_cap_from_evidence(profile)
    if cap is None:
        return payload

    results = None
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            results = payload.get("results", [])
        elif isinstance(payload.get("matches"), list):
            results = payload.get("matches", [])

    if not isinstance(results, list):
        return payload

    for item in results:
        if not isinstance(item, dict):
            continue
        base = _clamp_score(_safe_int(item.get("score", item.get("scor", 0))))
        capped = min(base, cap)
        item["score"] = capped
        item["scor"] = capped

        if cap <= 20:
            normalized = (
                "CV-ul conține foarte puține informații relevante "
                "pentru evaluarea potrivirii (ex: rezumat foarte scurt, fără experiență/abilități detaliate)."
            )
        else:
            justification = (
                item.get("justificare")
                or item.get("explanation")
                or item.get("justification")
                or ""
            )
            if isinstance(justification, str) and justification.strip():
                normalized = (
                    f"{justification.strip()} "
                    "Scorul este limitat deoarece CV-ul conține informații puține pentru evaluare precisă."
                ).strip()
            else:
                normalized = (
                    "Scorul este limitat deoarece CV-ul conține informații puține "
                    "pentru evaluare precisă."
                )

        item["justificare"] = normalized
        item["explanation"] = normalized
        item["justification"] = normalized

    return payload


def _post_process_matches_payload(parsed_payload):
    candidate_keys = (
        "results",
        "matches",
        "top_internships",
        "recommendations",
        "recommended_offers",
        "offers",
        "items",
    )

    if isinstance(parsed_payload, list):
        results = parsed_payload
        container = {"results": results}
    elif isinstance(parsed_payload, dict):
        results = None
        for key in candidate_keys:
            value = parsed_payload.get(key)
            if isinstance(value, list):
                results = value
                break

        if results is None:
            for value in parsed_payload.values():
                if not isinstance(value, list) or not value:
                    continue
                if all(isinstance(item, dict) for item in value):
                    probe = value[0]
                    if any(
                        k in probe for k in ("offer_id", "score", "scor", "justificare")
                    ):
                        results = value
                        break

        if results is None:
            return parsed_payload
        container = parsed_payload

        container["results"] = results
        if "matches" not in container:
            container["matches"] = results
    else:
        return parsed_payload

    for item in results:
        if not isinstance(item, dict):
            continue
        final_score = _compute_weighted_score(item)
        item["score"] = final_score
        item["scor"] = final_score

        for text_key in ["justificare", "explanation", "justification"]:
            if text_key in item and isinstance(item[text_key], str):
                item[text_key] = item[text_key].replace("**", "")

    return container


def get_smart_matches(cv_data, offers_list):
    client = get_gemini_client()
    offers_payload = _serialize_offers(offers_list)
    offers_json = json.dumps(offers_payload, ensure_ascii=False)

    prompt = (
        "Compară acest CV (PDF sau text) cu lista de oferte de internship "
        f"{offers_json}. "
        "Returnează un JSON cu top 10 rezultate. Fiecare rezultat trebuie să conțină obligatoriu: "
        "offer_id, scor (0-100) și justificare. "
        "Include și sub-scoruri obligatorii (0-100): skills_match, experience_match, education_match. "
        "Dacă CV-ul are informații foarte puține sau vagi, scorul trebuie să fie mic (de exemplu <=20) și justificarea trebuie să menționeze lipsa informațiilor. "
        "Calculează scorul final pe baza acestor sub-scoruri și evită rotunjirea în trepte de 5. "
        "Scorurile trebuie să fie suficient de granulare (diferențe de 1-2 puncte când candidații sunt apropiați). "
        "Justificarea trebuie să fie o propoziție scurtă în română și să explice concret potrivirea. "
        "Folosește exact cheia justificare. Poți include opțional și explanation. "
        "Răspunde strict cu JSON valid."
    )

    request_contents, evidence_profile = _build_cv_contents_and_profile(
        client, cv_data, prompt
    )
    response = generate_with_project_model(
        client,
        contents=request_contents,
    )

    json_text = _extract_json_text(response.text)
    parsed = json.loads(json_text)
    processed = _post_process_matches_payload(parsed)
    return _apply_evidence_caps(processed, evidence_profile)


def get_career_guidance(student_cv, journal_entries, user_context=""):
    client = get_gemini_client()

    journal_text_lines = []
    for entry in journal_entries:
        journal_text_lines.append(f"Săptămâna {entry.week_number}: {entry.content}")
    journal_text = (
        "\n\n".join(journal_text_lines)
        if journal_text_lines
        else "Nicio intrare în jurnal."
    )

    prompt = (
        "Ești un consilier de carieră experimentat. "
        "Analizează următoarele informații:\n\n"
    )

    cv_data = student_cv
    has_pdf = False
    if student_cv.pdf_file:
        pdf_path = getattr(student_cv.pdf_file, "path", None)
        if pdf_path and os.path.exists(pdf_path):
            has_pdf = True

    if has_pdf:
        prompt += "CV: atașat ca fișier PDF.\n\n"
    else:
        cv_text = _build_manual_cv_text(student_cv)
        prompt += f"CV:\n{cv_text}\n\n"
        cv_data = cv_text

    prompt += f"Activități din stagiu:\n{journal_text}\n\n"

    if user_context.strip():
        prompt += f"Context personal adăugat de student: {user_context}\n\n"

    prompt += (
        "Pe baza acestor informații, propune 2-3 direcții de carieră potrivite pentru student. "
        "Răspunde cu 2-3 propoziții libere, fără prefix sau formatare specială, "
        "text plăcut de citit care să îl inspire și să îi ofere perspective concrete. "
        "Dacă informațiile sunt prea puține sau generale, menționează: "
        "Informațiile disponibile sunt limitate pentru recomandări precise, dar pe baza activităților observate... "
        "Fără introducere sau concluzie. Maxim 150 de cuvinte în total. Răspunde în română."
        "Nu folosi formatare Markdown pentru text (fără bold, fără asteriscuri). "
    )

    request_contents, _ = _build_cv_contents_and_profile(client, cv_data, prompt)

    response = generate_with_project_model(
        client,
        contents=request_contents,
    )

    raw_text = response.text.replace("**", "").strip()

    if raw_text.startswith("```json") or raw_text.startswith("{"):
        try:
            json_string = _extract_json_text(raw_text)
            parsed_dict = json.loads(json_string)

            if isinstance(parsed_dict, dict):
                clean_text = " ".join(str(v) for v in parsed_dict.values())
            else:
                clean_text = str(parsed_dict)
        except Exception:
            clean_text = raw_text.replace("'", "").replace('"', "").strip()
    else:
        clean_text = raw_text.replace("```", "").strip()

    return clean_text
