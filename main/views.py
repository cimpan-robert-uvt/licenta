import logging
import os
from uuid import uuid4

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import FileResponse, HttpResponse
from django.contrib.auth.hashers import check_password
from django.core.files.base import ContentFile
from django.core.cache import cache
from django.core.mail import send_mail
from django.db.models import Q
from django.forms import modelformset_factory
from django.utils import timezone
from django.urls import reverse
from .models import (
    InternshipOffer,
    Application,
    Internship,
    JournalEntry,
    CompatibilityMatch,
    CareerAnalysis,
)
from .forms import InternshipOfferForm
from .utils_api import get_smart_matches, get_career_guidance
from .utils_pdf import generate_pdf
from accounts.models import (
    StudentCV,
    CVEducation,
    CVExperience,
    CVSkill,
    StudentProfile,
    User,
)
from accounts.forms import StudentCVForm, CVEducationForm, CVExperienceForm, CVSkillForm


logger = logging.getLogger(__name__)

SMART_MATCH_ERROR_MESSAGE = "Serviciul este momentan indisponibil. Rezultatele existente au fost păstrate. Te rugăm să încerci din nou mai târziu."


def is_company(user):
    return user.is_authenticated and user.role == "company"


def _smart_match_lock_key(user_id):
    return f"smart_match_running_{user_id}"


def _career_analysis_lock_key(user_id, internship_id):
    return f"career_analysis_running_{user_id}_{internship_id}"


def _journal_pdf_context(internship):
    entries = internship.journal_entries.all().order_by("week_number", "created_at")
    company_profile = getattr(internship.company, "company_profile", None)
    signed_by_name = (
        (
            getattr(internship.journal_confirmed_by, "get_full_name", lambda: "")()
            or ""
        ).strip()
        if internship.journal_confirmed_by
        else ""
    )
    if not signed_by_name:
        signed_by_name = (
            (getattr(company_profile, "contact_person", "") or "").strip()
            if company_profile
            else ""
        )
    if not signed_by_name:
        signed_by_name = (
            (internship.company.get_full_name() or "").strip()
            if internship.company
            else ""
        )

    return {
        "internship": internship,
        "student": internship.student,
        "company": internship.company,
        "company_profile": company_profile,
        "entries": entries,
        "journal_submitted_at": internship.journal_submitted_at,
        "journal_confirmed_at": internship.journal_confirmed_at,
        "signed_by_name": signed_by_name,
    }


def _can_access_journal_pdf(request, internship):
    if not request.user.is_authenticated:
        return False
    return request.user == internship.student or request.user == internship.company


def _get_internship_application(internship):
    return (
        Application.objects.filter(
            student=internship.student,
            offer=internship.offer,
        )
        .order_by("-applied_at")
        .first()
    )


def _redirect_to_application_or_company_dashboard(internship):
    application = _get_internship_application(internship)
    if application:
        return redirect("view_candidate_application", application_id=application.id)
    return redirect("company_candidates")


def _notify_students_about_new_offer(request, offer):
    company_profile = getattr(offer.company, "company_profile", None)
    if not company_profile or not company_profile.domain:
        return 0

    students = (
        StudentProfile.objects.select_related("user")
        .filter(
            domain=company_profile.domain,
            receive_offer_notifications=True,
            user__is_active=True,
        )
        .exclude(user__email__isnull=True)
        .exclude(user__email="")
    )

    if not students.exists():
        return 0

    offer_url = request.build_absolute_uri(reverse("offer_details", args=[offer.pk]))
    domain_label = company_profile.get_domain_display()
    company_name = (
        company_profile.company_name.strip() if company_profile.company_name else ""
    )
    sender_name = (
        company_name or offer.company.get_full_name().strip() or offer.company.username
    )
    subject = f"Anunț nou în domeniul {domain_label}"

    sent_count = 0
    for student_profile in students:
        student_user = student_profile.user
        recipient_email = (student_user.email or "").strip()
        if not recipient_email:
            continue

        full_name = student_user.get_full_name().strip() or student_user.username
        message = (
            f"Bună, {full_name}!\n\n"
            f"A fost publicat un nou anunț în domeniul {domain_label}:\n"
            f"{offer.title}\n\n"
            f"Companie: {sender_name}\n"
            f"Îl poți vedea aici: {offer_url}\n\n"
            "Dacă nu mai dorești astfel de notificări, le poți dezactiva din pagina de profil."
        )
        try:
            send_mail(subject, message, None, [recipient_email])
            sent_count += 1
        except Exception:
            logger.exception(
                "Failed to send new offer notification to student %s for offer %s",
                student_user.id,
                offer.id,
            )

    return sent_count


@login_required
def serve_protected_cv(request, cv_id):
    cv = get_object_or_404(StudentCV, pk=cv_id)

    can_view = request.user == cv.user or request.user.role == "company"
    if not can_view:
        return _forbidden_page(request, "Nu ai permisiunea să vizualizezi acest CV.")

    if not cv.pdf_file:
        return _forbidden_page(request, "Acest CV nu are un fișier PDF încărcat.")

    return FileResponse(cv.pdf_file.open("rb"), content_type="application/pdf")


def _smart_match_error_redirect(request):
    messages.warning(request, SMART_MATCH_ERROR_MESSAGE)
    return redirect("smart_match")


def _forbidden_page(request, message, title="Acces restricționat"):
    return render(
        request,
        "main/forbidden_page.html",
        {
            "page_title": title,
            "error_message": message,
        },
        status=403,
    )


def _extract_match_explanation(item, offer_obj):
    for key in (
        "justificare",
        "explanation",
        "justification",
        "motiv",
        "motivatie",
        "reason",
        "description",
        "details",
    ):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return f"Potrivire identificată pentru oferta {offer_obj.title}, dar AI nu a returnat o justificare explicită."


def has_applicable_cv(cv):
    if not cv:
        return False

    if bool(cv.pdf_file):
        return True

    return bool((cv.resume or "").strip())


def _has_student_identification_data(user):
    profile = getattr(user, "student_profile", None)
    if not profile:
        return False

    cnp = (profile.cnp or "").strip()
    if not (cnp and len(cnp) == 13 and cnp.isdigit()):
        return False

    if not (profile.faculty or "").strip():
        return False
    if not (profile.specialization or "").strip():
        return False
    if not (profile.study_level or "").strip():
        return False
    if profile.year_of_study is None or profile.year_of_study <= 0:
        return False

    return True


def _has_company_identification_data(user):
    profile = getattr(user, "company_profile", None)
    if not profile:
        return False

    full_company_name = (profile.full_company_name or "").strip()
    cui = (profile.cui or "").strip()
    address = (profile.address or "").strip()
    contact_person = (profile.contact_person or "").strip()

    if not full_company_name:
        return False
    if not (cui and cui.isdigit()):
        return False
    if not address:
        return False
    if not contact_person:
        return False

    return True


def home(request):
    q = (request.GET.get("q") or "").strip()
    offers = InternshipOffer.objects.filter(is_active=True)
    if q:
        offers = offers.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(company__company_profile__company_name__icontains=q)
        ).distinct()
    offers = offers.order_by("-created_at")
    context = {
        "offers": offers,
        "q": q,
    }
    return render(request, "main/home.html", context)


def offer_details(request, pk):
    offer = get_object_or_404(InternshipOffer, pk=pk)
    is_owner = request.user == offer.company if request.user.is_authenticated else False
    has_applied = False
    student_application = None
    has_active_internship = False
    has_complete_cv = False
    has_uploaded_cv = False
    has_applicable_cv_data = False
    has_identification_data = False
    if request.user.is_authenticated and request.user.is_student():
        student_application = Application.objects.filter(
            student=request.user, offer=offer
        ).first()
        has_applied = student_application is not None
        has_active_internship = Internship.objects.filter(
            student=request.user, is_active=True
        ).exists()
        cv = StudentCV.objects.filter(user=request.user).first()
        has_uploaded_cv = bool(cv and cv.pdf_file)
        has_complete_cv = bool(cv and has_applicable_cv(cv) and not cv.pdf_file)
        has_applicable_cv_data = has_applicable_cv(cv)
        has_identification_data = _has_student_identification_data(request.user)
    context = {
        "offer": offer,
        "is_owner": is_owner,
        "has_applied": has_applied,
        "student_application": student_application,
        "has_active_internship": has_active_internship,
        "has_complete_cv": has_complete_cv,
        "has_uploaded_cv": has_uploaded_cv,
        "has_applicable_cv": has_applicable_cv_data,
        "has_identification_data": has_identification_data,
    }
    return render(request, "main/offer_details.html", context)


@login_required
def apply_to_offer(request, offer_id):
    if not request.user.is_student():
        return _forbidden_page(request, "Doar studenții pot aplica.")

    if not _has_student_identification_data(request.user):
        messages.warning(
            request,
            "Pentru a aplica, trebuie să completezi datele de identificare.",
        )
        return redirect("identification_data")

    cv = StudentCV.objects.filter(user=request.user).first()
    if not has_applicable_cv(cv):
        messages.warning(
            request,
            "Pentru a aplica, trebuie să ai CV-ul completat sau să încarci un CV personal (PDF).",
        )
        return redirect("edit_cv")

    if Internship.objects.filter(student=request.user, is_active=True).exists():
        messages.warning(
            request,
            "Ai deja un stagiu activ. Nu poți aplica la o nouă ofertă până la finalizarea lui.",
        )
        return redirect("my_internship")

    offer = get_object_or_404(InternshipOffer, pk=offer_id)

    if request.method == "POST":
        existing_application = Application.objects.filter(
            student=request.user, offer=offer
        ).first()

        if existing_application:
            messages.warning(request, "Ai aplicat deja la această ofertă.")
            return redirect("offer_details", pk=offer_id)

        Application.objects.create(student=request.user, offer=offer, status="pending")
        messages.success(request, "Aplicația ta a fost trimisă cu succes!")
        return redirect("offer_details", pk=offer_id)

    return redirect("offer_details", pk=offer_id)


@login_required
def withdraw_application(request, offer_id):
    if not request.user.is_student():
        return _forbidden_page(request, "Doar studenții pot retrage o aplicație.")

    offer = get_object_or_404(InternshipOffer, pk=offer_id)

    if request.method == "POST":
        app = Application.objects.filter(student=request.user, offer=offer).first()
        if not app:
            messages.warning(
                request, "Nu există nicio aplicație de retras pentru această ofertă."
            )
            return redirect("offer_details", pk=offer_id)

        app.delete()
        messages.success(request, "Cererea a fost retrasă cu succes.")
        return redirect("offer_details", pk=offer_id)

    return redirect("offer_details", pk=offer_id)


@login_required
def my_applications(request):
    if not request.user.is_student():
        return _forbidden_page(request, "Doar studenții pot vizualiza aplicațiile lor.")

    applications = Application.objects.filter(student=request.user).order_by(
        "-applied_at"
    )
    context = {
        "applications": applications,
    }
    return render(request, "main/my_applications.html", context)


@login_required
def my_internship(request):
    if not request.user.is_student():
        return _forbidden_page(
            request,
            "Doar studenții pot vizualiza stagiile de practică.",
        )

    internship = (
        Internship.objects.select_related(
            "offer", "company", "company__company_profile"
        )
        .filter(student=request.user, is_active=True, offer__isnull=False)
        .order_by("-start_date")
        .first()
    )

    if not internship:
        internship = (
            Internship.objects.select_related(
                "offer", "company", "company__company_profile"
            )
            .filter(student=request.user, is_active=True)
            .order_by("-start_date")
            .first()
        )

    entries = []
    hr_contact_name = None
    hr_contact_email = None
    career_analysis = None
    is_career_running = False
    journal_weeks_total = 0
    journal_entries_count = 0
    can_add_journal_entry = False
    can_submit_journal = False
    journal_is_submitted = False
    journal_is_confirmed = False

    if internship:
        entries = internship.journal_entries.all().order_by(
            "-week_number", "-created_at"
        )
        journal_entries_count = entries.count()
        journal_weeks_total = internship.offer.duration_weeks if internship.offer else 0
        can_add_journal_entry = bool(
            journal_weeks_total
            and journal_entries_count < journal_weeks_total
            and not internship.journal_is_locked()
        )
        can_submit_journal = internship.journal_can_be_submitted()
        journal_is_submitted = bool(internship.journal_submitted_at)
        journal_is_confirmed = bool(internship.journal_confirmed_at)

        career_analysis = (
            CareerAnalysis.objects.filter(internship=internship)
            .order_by("-created_at")
            .first()
        )

        is_career_running = bool(
            cache.get(_career_analysis_lock_key(request.user.id, internship.id))
        )

        company_profile = getattr(internship.company, "company_profile", None)
        company_name = (
            getattr(company_profile, "company_name", "") if company_profile else ""
        )
        contact_person = (
            getattr(company_profile, "contact_person", "") if company_profile else ""
        )

        hr_contact_name = (
            (contact_person or "").strip()
            or (internship.company.get_full_name() or "").strip()
            or company_name
        )
        hr_contact_email = (internship.company.email or "").strip() or None

    context = {
        "internship": internship,
        "entries": entries,
        "hr_contact_name": hr_contact_name,
        "hr_contact_email": hr_contact_email,
        "career_analysis": career_analysis,
        "is_career_running": is_career_running,
        "journal_weeks_total": journal_weeks_total,
        "journal_entries_count": journal_entries_count,
        "can_add_journal_entry": can_add_journal_entry,
        "can_submit_journal": can_submit_journal,
        "journal_is_submitted": journal_is_submitted,
        "journal_is_confirmed": journal_is_confirmed,
    }
    return render(request, "main/my_internship.html", context)


def _validate_journal_entry_payload(internship, week_number_raw, content):
    if not week_number_raw or not content:
        return None, "Numărul săptămânii și conținutul sunt obligatorii."

    try:
        week_number = int(week_number_raw)
    except (TypeError, ValueError):
        return None, "Numărul săptămânii trebuie să fie un număr valid."

    if week_number < 1:
        return None, "Numărul săptămânii trebuie să fie cel puțin 1."

    if internship.offer and internship.offer.duration_weeks:
        max_weeks = internship.offer.duration_weeks
        if week_number > max_weeks:
            return (
                None,
                f"Numărul săptămânii nu poate depăși durata stagiului ({max_weeks} săptămâni).",
            )

    return week_number, None


@login_required
def create_journal_entry(request, internship_id):
    internship = get_object_or_404(Internship, pk=internship_id)

    if request.user != internship.student:
        return _forbidden_page(request, "Doar studentul poate crea intrări în jurnal.")

    if internship.journal_is_locked():
        messages.warning(
            request,
            "Jurnalul a fost deja trimis pentru semnare și nu mai poate fi modificat.",
        )
        return redirect("my_internship")

    existing_weeks = set(
        internship.journal_entries.values_list("week_number", flat=True)
    )
    next_available_week = None
    if internship.offer and internship.offer.duration_weeks:
        for week_number in range(1, internship.offer.duration_weeks + 1):
            if week_number not in existing_weeks:
                next_available_week = week_number
                break

    if request.method == "POST" and next_available_week is None:
        messages.warning(
            request, "Jurnalul este complet. Nu mai poți adăuga alte intrări."
        )
        return redirect("my_internship")

    if request.method == "POST":
        week_number_raw = request.POST.get("week_number")
        content = request.POST.get("content")

        week_number, payload_error = _validate_journal_entry_payload(
            internship, week_number_raw, content
        )
        if payload_error:
            messages.error(request, payload_error)
            return render(
                request,
                "main/create_journal_entry.html",
                {
                    "internship": internship,
                    "submitted_week": week_number_raw,
                    "submitted_content": content,
                },
            )

        existing_entry = JournalEntry.objects.filter(
            internship=internship, week_number=week_number
        ).first()

        if existing_entry:
            messages.warning(
                request, f"Există deja o intrare pentru săptămâna {week_number}."
            )
            return render(
                request,
                "main/create_journal_entry.html",
                {
                    "internship": internship,
                    "submitted_week": week_number_raw,
                    "submitted_content": content,
                },
            )

        JournalEntry.objects.create(
            internship=internship,
            week_number=int(week_number),
            content=content,
        )
        messages.success(
            request,
            f"Intrarea în jurnal pentru săptămâna {week_number} a fost adăugată cu succes!",
        )
        return redirect("my_internship")

    context = {
        "internship": internship,
        "next_available_week": next_available_week,
    }
    return render(request, "main/create_journal_entry.html", context)


@login_required
def edit_journal_entry(request, internship_id, entry_id):
    internship = get_object_or_404(Internship, pk=internship_id)

    if request.user != internship.student:
        return _forbidden_page(request, "Doar studentul poate edita intrări în jurnal.")

    if internship.journal_is_locked():
        messages.warning(
            request,
            "Jurnalul a fost deja trimis pentru semnare și nu mai poate fi modificat.",
        )
        return redirect("my_internship")

    entry = get_object_or_404(JournalEntry, pk=entry_id, internship=internship)

    if request.method == "POST":
        week_number_raw = request.POST.get("week_number")
        content = request.POST.get("content")

        week_number, payload_error = _validate_journal_entry_payload(
            internship, week_number_raw, content
        )
        if payload_error:
            messages.error(request, payload_error)
            return render(
                request,
                "main/edit_journal_entry.html",
                {
                    "internship": internship,
                    "entry": entry,
                    "submitted_week": week_number_raw,
                    "submitted_content": content,
                },
            )

        duplicate_entry = (
            JournalEntry.objects.filter(internship=internship, week_number=week_number)
            .exclude(pk=entry.pk)
            .first()
        )
        if duplicate_entry:
            messages.warning(
                request, f"Există deja o intrare pentru săptămâna {week_number}."
            )
            return render(
                request,
                "main/edit_journal_entry.html",
                {
                    "internship": internship,
                    "entry": entry,
                    "submitted_week": week_number_raw,
                    "submitted_content": content,
                },
            )

        entry.week_number = week_number
        entry.content = content
        entry.save(update_fields=["week_number", "content"])
        messages.success(request, "Intrarea din jurnal a fost actualizată cu succes!")
        return redirect("my_internship")

    context = {
        "internship": internship,
        "entry": entry,
    }
    return render(request, "main/edit_journal_entry.html", context)


@login_required
def delete_journal_entry(request, internship_id, entry_id):
    internship = get_object_or_404(Internship, pk=internship_id)

    if request.user != internship.student:
        return _forbidden_page(
            request, "Doar studentul poate șterge intrări din jurnal."
        )

    if internship.journal_is_locked():
        messages.warning(
            request,
            "Jurnalul a fost deja trimis pentru semnare și nu mai poate fi modificat.",
        )
        return redirect("my_internship")

    entry = get_object_or_404(JournalEntry, pk=entry_id, internship=internship)

    if request.method != "POST":
        return redirect("my_internship")

    entry.delete()
    messages.success(request, "Intrarea din jurnal a fost ștearsă cu succes!")
    return redirect("my_internship")


@login_required
def preview_journal_pdf(request, internship_id):
    internship = get_object_or_404(Internship, pk=internship_id)

    if request.user != internship.student:
        return _forbidden_page(
            request,
            "Doar studentul poate previzualiza jurnalul acestui stagiu.",
        )

    entries = internship.journal_entries.all().order_by("week_number", "created_at")
    if not entries.exists():
        messages.info(
            request, "Nu există încă intrări în jurnal pentru previzualizare."
        )
        return redirect("my_internship")

    context = _journal_pdf_context(internship)
    pdf_content = generate_pdf("main/pdf/journal_template.html", context)

    response = HttpResponse(pdf_content, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="Jurnal_practica_{internship.id}.pdf"'
    )
    return response


@login_required
def submit_journal_for_signature(request, internship_id):
    internship = get_object_or_404(Internship, pk=internship_id)

    if request.user != internship.student:
        return _forbidden_page(
            request,
            "Doar studentul poate trimite jurnalul pentru semnare.",
        )

    if request.method != "POST":
        return redirect("my_internship")

    if internship.journal_confirmed_at:
        messages.info(request, "Jurnalul a fost deja confirmat de HR/mentor.")
        return redirect("my_internship")

    if not internship.journal_can_be_submitted():
        messages.warning(
            request,
            "Trebuie să completezi toate intrările cerute înainte de a trimite jurnalul.",
        )
        return redirect("my_internship")

    internship.journal_submitted_at = timezone.now()
    internship.save(update_fields=["journal_submitted_at"])
    return redirect("my_internship")


@login_required
@user_passes_test(is_company)
def company_preview_journal_pdf(request, internship_id):
    internship = get_object_or_404(
        Internship, pk=internship_id, company=request.user, offer__isnull=False
    )

    if not internship.journal_submitted_at:
        return _redirect_to_application_or_company_dashboard(internship)

    if internship.journal_confirmed_at and internship.journal_pdf:
        return redirect("serve_protected_journal_pdf", internship_id=internship.id)

    entries = internship.journal_entries.all().order_by("week_number", "created_at")
    if not entries.exists():
        messages.info(
            request, "Nu există încă intrări în jurnal pentru previzualizare."
        )
        return redirect("company_candidates")

    context = _journal_pdf_context(internship)
    pdf_content = generate_pdf("main/pdf/journal_template.html", context)

    response = HttpResponse(pdf_content, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="Jurnal_practica_{internship.id}.pdf"'
    )
    return response


@login_required
@user_passes_test(is_company)
def confirm_journal(request, internship_id):
    internship = get_object_or_404(Internship, pk=internship_id, company=request.user)

    if request.method != "POST":
        return redirect("company_candidates")

    if internship.journal_confirmed_at:
        messages.info(request, "Jurnalul este deja confirmat.")
        return _redirect_to_application_or_company_dashboard(internship)

    if not internship.journal_submitted_at:
        messages.warning(
            request, "Jurnalul trebuie trimis de student înainte de confirmare."
        )
        return _redirect_to_application_or_company_dashboard(internship)

    entries = internship.journal_entries.all().order_by("week_number", "created_at")
    if not entries.exists() or not internship.journal_is_complete():
        messages.warning(request, "Jurnalul nu este complet și nu poate fi confirmat.")
        return _redirect_to_application_or_company_dashboard(internship)

    internship.journal_confirmed_at = timezone.now()
    internship.journal_confirmed_by = request.user
    pdf_content = generate_pdf(
        "main/pdf/journal_template.html", _journal_pdf_context(internship)
    )
    filename = (
        f"Jurnal_practica_{internship.student.get_full_name()}_{internship.id}.pdf"
    )
    internship.journal_pdf.save(filename, ContentFile(pdf_content), save=False)
    internship.save(
        update_fields=["journal_pdf", "journal_confirmed_at", "journal_confirmed_by"]
    )

    return _redirect_to_application_or_company_dashboard(internship)


@login_required
def serve_protected_journal_pdf(request, internship_id):
    internship = get_object_or_404(Internship, pk=internship_id)

    if not _can_access_journal_pdf(request, internship):
        return _forbidden_page(
            request,
            "Nu ai permisiunea să descarci acest jurnal.",
        )

    if not internship.journal_pdf:
        messages.info(request, "Nu există încă un PDF semnat pentru acest jurnal.")
        return redirect(
            "my_internship"
            if request.user == internship.student
            else "company_candidates"
        )

    return FileResponse(
        internship.journal_pdf.open("rb"), content_type="application/pdf"
    )


@login_required
@user_passes_test(is_company)
def company_my_offers(request):
    offers = InternshipOffer.objects.filter(company=request.user).order_by(
        "-created_at"
    )
    has_identification_data = _has_company_identification_data(request.user)
    return render(
        request,
        "main/company_my_offers.html",
        {
            "offers": offers,
            "has_identification_data": has_identification_data,
        },
    )


@login_required
@user_passes_test(is_company)
def company_journals(request):
    internships = (
        Internship.objects.filter(
            company=request.user, journal_submitted_at__isnull=False
        )
        .select_related("student", "offer")
        .order_by("-journal_submitted_at", "-journal_confirmed_at")
    )

    context = {"internships": internships}
    return render(request, "main/company_journals.html", context)


@login_required
@user_passes_test(is_company)
def create_internship_offer(request):
    if not _has_company_identification_data(request.user):
        messages.warning(request, "Te rugam să completezi datele de identificare.")
        return redirect("identification_data")
    if request.method == "POST":
        form = InternshipOfferForm(request.POST)
        if form.is_valid():
            offer = form.save(commit=False)
            offer.company = request.user
            offer.save()
            if offer.is_active:
                _notify_students_about_new_offer(request, offer)
            messages.success(request, "Oferta de stagiu a fost creată cu succes!")
            return redirect("company_my_offers")
    else:
        form = InternshipOfferForm()
    return render(request, "main/create_internship_offer.html", {"form": form})


@login_required
@user_passes_test(is_company)
def edit_internship_offer(request, pk):
    offer = get_object_or_404(InternshipOffer, pk=pk)

    if offer.company != request.user:
        return _forbidden_page(request, "Nu ai permisiunea de a edita această ofertă.")

    if request.method == "POST":
        form = InternshipOfferForm(request.POST, instance=offer)
        if form.is_valid():
            form.save()
            messages.success(request, "Oferta de stagiu a fost actualizată cu succes!")
            return redirect("company_my_offers")
    else:
        form = InternshipOfferForm(instance=offer)

    return render(
        request, "main/edit_internship_offer.html", {"form": form, "offer": offer}
    )


@login_required
@user_passes_test(is_company)
def archive_internship_offer(request, pk):
    offer = get_object_or_404(InternshipOffer, pk=pk)

    if offer.company != request.user:
        return _forbidden_page(request, "Nu ai permisiunea de a arhiva această ofertă.")

    if request.method == "POST":
        password = request.POST.get("password")
        if not password or not check_password(password, request.user.password):
            context = {
                "offer": offer,
                "password_error": "Parola introdusă este incorectă.",
            }
            return render(request, "main/archive_internship_offer.html", context)

        if offer.is_archived:
            messages.info(request, "Oferta este deja arhivata.")
            return redirect("company_my_offers")

        offer.is_active = False
        offer.is_archived = True
        offer.save(update_fields=["is_active", "is_archived"])

        offer.applications.filter(status="pending").update(
            status="withdrawn", updated_at=timezone.now()
        )

        messages.success(
            request,
            "Oferta a fost arhivata. Aplicațiile în așteptare au fost retrase automat.",
        )
        return redirect("company_my_offers")

    return render(request, "main/archive_internship_offer.html", {"offer": offer})


@login_required
@user_passes_test(is_company)
def company_candidates(request):
    my_offers = InternshipOffer.objects.filter(company=request.user)

    offers_with_candidates = []
    for offer in my_offers:
        apps = Application.objects.filter(offer=offer).select_related(
            "student__student_profile", "student__student_cv"
        )
        if apps.exists():
            offers_with_candidates.append({"offer": offer, "applications": apps})

    return render(
        request, "main/company_candidates.html", {"offer_data": offers_with_candidates}
    )


@login_required
@user_passes_test(is_company)
def update_application_status(request, application_id, status):
    if request.method != "POST":
        return _forbidden_page(request, "Această acțiune necesită o cerere POST.")

    app = get_object_or_404(Application, id=application_id, offer__company=request.user)

    if status in ["accepted", "rejected"]:
        if status == "accepted":
            if Internship.objects.filter(student=app.student, is_active=True).exists():
                messages.warning(
                    request,
                    f"Studentul {app.student.get_full_name()} are deja un stagiu activ.",
                )
                return redirect("company_candidates")

            app.status = "hr_accepted"
            app.save()

            messages.success(
                request,
                f"Studentul {app.student.get_full_name()} a fost acceptat. Așteptăm confirmarea studentului.",
            )
        else:
            app.status = "rejected"
            app.save()
            messages.info(request, "Aplicația a fost refuzată.")

    return redirect("company_candidates")


@login_required
def update_student_application_status(request, application_id, action):
    if request.method != "POST":
        return _forbidden_page(request, "Această acțiune necesită o cerere POST.")

    if not request.user.is_student():
        return _forbidden_page(
            request,
            "Doar studenții pot confirma sau refuza participarea.",
        )

    app = get_object_or_404(Application, id=application_id, student=request.user)

    if app.status != "hr_accepted":
        messages.warning(
            request,
            "Această cerere nu este în starea potrivită pentru confirmare/refuz.",
        )
        return redirect("my_applications")

    if action == "decline":
        app.status = "student_declined"
        app.save()
        messages.info(request, "Ai refuzat participarea la acest stagiu.")
        return redirect("my_applications")

    if action == "confirm":
        existing_active = Internship.objects.filter(
            student=request.user, is_active=True
        ).first()
        if existing_active:
            messages.warning(
                request,
                "Ai deja un stagiu activ. Nu poți confirma o nouă participare.",
            )
            return redirect("my_internship")

        app.status = "student_confirmed"
        app.save()

        Application.objects.filter(
            student=request.user, status__in=["pending", "hr_accepted"]
        ).exclude(id=app.id).update(status="withdrawn")

        internship = Internship.objects.create(
            student=app.student,
            company=app.offer.company,
            offer=app.offer,
            start_date=app.offer.start_date or timezone.now().date(),
            is_active=True,
        )

        context = {
            "internship": internship,
            "student": app.student,
            "company": app.offer.company.company_profile,
            "offer": app.offer,
        }

        pdf_content = generate_pdf("main/pdf/contract_template.html", context)
        filename = f"Conventie_{app.student.get_full_name()}_{app.offer.id}.pdf"
        internship.signed_contract.save(filename, ContentFile(pdf_content))

        messages.success(
            request,
            "Participarea a fost confirmată. Conventia de practică a fost generată.",
        )
        return redirect("my_internship")

    messages.warning(request, "Acțiune invalidă.")
    return redirect("my_applications")


@login_required
@user_passes_test(is_company)
def view_candidate_application(request, application_id):
    """View candidate's application with CV and accept/reject options"""
    app = get_object_or_404(Application, id=application_id, offer__company=request.user)

    try:
        cv = app.student.student_cv
    except StudentCV.DoesNotExist:
        cv = None

    internship = None
    if app.status == "student_confirmed":
        internship = (
            Internship.objects.filter(
                student=app.student,
                company=request.user,
                offer=app.offer,
            )
            .order_by("-created_at")
            .first()
        )

    context = {
        "application": app,
        "cv": cv,
        "student": app.student,
        "internship": internship,
    }
    return render(request, "main/view_candidate_application.html", context)


@login_required
def view_cv(request):
    """View student's CV in read-only mode"""
    if not request.user.is_student():
        return _forbidden_page(request, "Doar studenții pot vedea CV-uri.")

    try:
        cv = StudentCV.objects.get(user=request.user)
    except StudentCV.DoesNotExist:
        cv = None

    context = {
        "cv": cv,
    }
    return render(request, "main/view_cv.html", context)


@login_required
def edit_cv(request):
    """Edit student's CV with all sections"""
    if not request.user.is_student():
        return _forbidden_page(request, "Doar studenții pot edita CV-uri.")

    cv, created = StudentCV.objects.get_or_create(user=request.user)
    upload_error = None
    is_upload_request = request.method == "POST" and bool(
        request.POST.get("upload_pdf")
    )
    is_delete_upload_request = request.method == "POST" and bool(
        request.POST.get("delete_pdf")
    )

    if is_delete_upload_request:
        if cv.pdf_file:
            cv.pdf_file.delete(save=False)
            cv.pdf_file = None
            cv.save(update_fields=["pdf_file", "updated_at"])
            messages.success(request, "CV-ul personal a fost șters cu succes.")
        else:
            messages.info(request, "Nu există niciun CV PDF de șters.")
        return redirect("edit_cv")

    if is_upload_request:
        pdf_file = request.FILES.get("pdf_file")

        if not pdf_file:
            upload_error = "Selectează un fișier PDF înainte de încărcare."

        elif not (pdf_file.name or "").lower().endswith(".pdf"):
            upload_error = "Poți încărca doar fișiere PDF."

        else:
            original_name = os.path.splitext(pdf_file.name)[0].strip() or "cv"
            safe_base = "_".join(original_name.split())
            short_code = uuid4().hex[:8]
            unique_filename = f"{safe_base}_{short_code}.pdf"

            if cv.pdf_file:
                cv.pdf_file.delete(save=False)

            cv.pdf_file.save(unique_filename, pdf_file, save=False)
            cv.save(update_fields=["pdf_file", "updated_at"])
            messages.success(request, "CV-ul PDF a fost încărcat cu succes.")
            return redirect("edit_cv")

    education_extra = 0 if cv.education.exists() else 1
    experience_extra = 0 if cv.experience.exists() else 1
    skill_extra = 0 if cv.skills.exists() else 1

    EducationFormSet = modelformset_factory(
        CVEducation, form=CVEducationForm, extra=education_extra, can_delete=True
    )
    ExperienceFormSet = modelformset_factory(
        CVExperience, form=CVExperienceForm, extra=experience_extra, can_delete=True
    )
    SkillFormSet = modelformset_factory(
        CVSkill, form=CVSkillForm, extra=skill_extra, can_delete=True
    )

    if request.method == "POST" and not is_upload_request:
        cv_form = StudentCVForm(request.POST, request.FILES, instance=cv)
        education_formset = EducationFormSet(
            request.POST, queryset=cv.education.all(), prefix="education"
        )
        experience_formset = ExperienceFormSet(
            request.POST, queryset=cv.experience.all(), prefix="experience"
        )
        skill_formset = SkillFormSet(
            request.POST, queryset=cv.skills.all(), prefix="skill"
        )

        if (
            cv_form.is_valid()
            and education_formset.is_valid()
            and experience_formset.is_valid()
            and skill_formset.is_valid()
        ):
            cv_form.save()

            education_instances = education_formset.save(commit=False)
            for instance in education_instances:
                instance.cv = cv
                instance.save()
            education_formset.save_m2m()

            for obj in education_formset.deleted_objects:
                obj.delete()

            experience_instances = experience_formset.save(commit=False)
            for instance in experience_instances:
                instance.cv = cv
                instance.save()
            experience_formset.save_m2m()

            for obj in experience_formset.deleted_objects:
                obj.delete()

            skill_instances = skill_formset.save(commit=False)
            for instance in skill_instances:
                instance.cv = cv
                instance.save()
            skill_formset.save_m2m()

            for obj in skill_formset.deleted_objects:
                obj.delete()

            messages.success(request, "CV-ul a fost salvat cu succes!")
            return redirect("view_cv")
    else:
        cv_form = StudentCVForm(instance=cv)
        education_formset = EducationFormSet(
            queryset=cv.education.all(), prefix="education"
        )
        experience_formset = ExperienceFormSet(
            queryset=cv.experience.all(), prefix="experience"
        )
        skill_formset = SkillFormSet(queryset=cv.skills.all(), prefix="skill")

    uploaded_pdf_filename = (
        os.path.basename(cv.pdf_file.name) if cv and cv.pdf_file else None
    )

    context = {
        "cv": cv,
        "uploaded_pdf_filename": uploaded_pdf_filename,
        "upload_error": upload_error,
        "cv_form": cv_form,
        "education_formset": education_formset,
        "experience_formset": experience_formset,
        "skill_formset": skill_formset,
    }
    return render(request, "main/edit_cv.html", context)


@login_required
def smart_match_sync(request):
    if not request.user.is_student():
        return _forbidden_page(
            request,
            "Doar studenții pot genera potrivirile de compatibilitate.",
        )

    lock_key = _smart_match_lock_key(request.user.id)
    lock_acquired = cache.add(lock_key, True, timeout=600)
    if not lock_acquired:
        messages.info(
            request,
            "Analiza este deja în curs. Te rugăm să aștepți finalizarea ei.",
        )
        return redirect("smart_match")

    try:
        try:
            student_cv = request.user.student_cv
        except StudentCV.DoesNotExist:
            return _smart_match_error_redirect(request)

        if not has_applicable_cv(student_cv):
            return _smart_match_error_redirect(request)

        try:
            student_domain = request.user.student_profile.domain
        except Exception:
            return _smart_match_error_redirect(request)

        relevant_offers = InternshipOffer.objects.filter(
            is_active=True,
            company__company_profile__domain=student_domain,
        )

        if not relevant_offers.exists():
            messages.warning(
                request,
                "Nu există oferte active în domeniul tău. Încearcă din nou mai târziu.",
            )
            return redirect("smart_match")

        try:
            matches = get_smart_matches(student_cv, relevant_offers)
        except Exception:
            logger.exception("Smart matching failed for user %s", request.user.id)
            return _smart_match_error_redirect(request)

        parsed_matches = []
        if matches:
            if isinstance(matches, list):
                parsed_matches = matches
            elif isinstance(matches, dict):
                if isinstance(matches.get("results"), list):
                    parsed_matches = matches.get("results", [])
                elif isinstance(matches.get("matches"), list):
                    parsed_matches = matches.get("matches", [])

        if parsed_matches:
            CompatibilityMatch.objects.filter(student=request.user).delete()

            relevant_offers_map = {offer.id: offer for offer in relevant_offers}
            created_count = 0

            for item in parsed_matches:
                if not isinstance(item, dict):
                    continue

                offer_id_raw = item.get("offer_id")
                try:
                    offer_id = int(offer_id_raw)
                except (TypeError, ValueError):
                    continue

                offer_obj = relevant_offers_map.get(offer_id)
                if not offer_obj:
                    continue

                score_raw = item.get("score", item.get("scor", 0))
                try:
                    score = int(score_raw)
                except (TypeError, ValueError):
                    score = 0
                score = max(0, min(100, score))

                explanation = _extract_match_explanation(item, offer_obj)

                CompatibilityMatch.objects.create(
                    student=request.user,
                    offer=offer_obj,
                    score=score,
                    explanation=explanation,
                )
                created_count += 1

            if created_count:
                messages.success(
                    request,
                    "Rezultatele au fost actualizate cu succes.",
                )
            else:
                messages.warning(request, SMART_MATCH_ERROR_MESSAGE)
        else:
            messages.warning(request, SMART_MATCH_ERROR_MESSAGE)

        return redirect("smart_match")
    finally:
        cache.delete(lock_key)


@login_required
def smart_match(request):
    if not request.user.is_student():
        return _forbidden_page(
            request,
            "Doar studenții pot vizualiza rezultatele de compatibilitate.",
        )

    if request.method == "POST":
        return smart_match_sync(request)

    is_match_running = bool(cache.get(_smart_match_lock_key(request.user.id)))
    student_matches = CompatibilityMatch.objects.filter(student=request.user)
    student_cv = StudentCV.objects.filter(user=request.user).first()
    has_applicable_cv_data = has_applicable_cv(student_cv)

    matches = student_matches.select_related("offer").order_by("-score")[:10]
    last_analysis_at = (
        student_matches.order_by("-created_at")
        .values_list("created_at", flat=True)
        .first()
    )

    return render(
        request,
        "main/smart_match.html",
        {
            "matches": matches,
            "is_match_running": is_match_running,
            "last_analysis_at": last_analysis_at,
            "has_applicable_cv": has_applicable_cv_data,
        },
    )


@login_required
def analyze_career_view(request, internship_id):
    if not request.user.is_student():
        return _forbidden_page(
            request,
            "Doar studenții pot genera analize de carieră.",
        )

    internship = get_object_or_404(Internship, pk=internship_id, student=request.user)

    if request.method != "POST":
        return redirect("my_internship")

    lock_key = _career_analysis_lock_key(request.user.id, internship.id)
    lock_acquired = cache.add(lock_key, True, timeout=600)
    if not lock_acquired:
        messages.info(
            request,
            "Analiza de carieră este deja în curs. Te rugăm să aștepți finalizarea ei.",
            extra_tags="career",
        )
        return redirect("my_internship")

    user_context = (request.POST.get("user_context") or "").strip()[:100]

    student_cv = StudentCV.objects.filter(user=request.user).first()
    if not student_cv:
        messages.warning(
            request,
            "Trebuie să ai un CV completat pentru a genera analiza de carieră.",
            extra_tags="career",
        )
        return redirect("edit_cv")

    journal_entries = internship.journal_entries.all().order_by("week_number")
    if not journal_entries.exists():
        messages.warning(
            request,
            "Trebuie să ai cel puțin o intrare în jurnal pentru a genera analiza de carieră.",
            extra_tags="career",
        )
        return redirect("my_internship")

    try:
        guidance_text = get_career_guidance(student_cv, journal_entries, user_context)
    except Exception:
        logger.exception("Career analysis failed for user %s", request.user.id)
        messages.error(
            request,
            "Analiza de carieră nu a putut fi generată în acest moment.",
            extra_tags="career",
        )
        return redirect("my_internship")
    finally:
        cache.delete(lock_key)

    CareerAnalysis.objects.filter(internship=internship).delete()
    CareerAnalysis.objects.create(
        internship=internship,
        result_text=guidance_text,
        user_context=user_context,
    )

    messages.success(
        request, "Analiza de carieră a fost generată cu succes.", extra_tags="career"
    )
    return redirect("my_internship")


# =======================================================
# =======================================================
def test_contract_pdf(request):
    student = User.objects.filter(username="robert_student", role="student").first()
    company = User.objects.filter(role="company").first()

    if not student or not company:
        return HttpResponse(
            "Nu există studenți sau companii. Rulează 'python manage.py seed_data'"
        )

    offer = InternshipOffer.objects.filter(company=company).first()

    internship, _ = Internship.objects.get_or_create(
        student=student,
        company=company,
        offer=offer,
        defaults={
            "start_date": timezone.now().date(),
            "is_active": True,
        },
    )

    context = {
        "internship": internship,
        "student": student,
        "company": company.company_profile,
        "offer": offer,
    }

    pdf_content = generate_pdf("main/pdf/contract_template.html", context)
    response = HttpResponse(pdf_content, content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="Test_Conventie.pdf"'

    return response
