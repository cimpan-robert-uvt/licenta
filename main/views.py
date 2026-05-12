import logging
import os
from uuid import uuid4

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth.hashers import check_password
from django.core.files.base import ContentFile
from django.core.cache import cache
from django.forms import modelformset_factory
from django.utils import timezone
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
from accounts.models import StudentCV, CVEducation, CVExperience, CVSkill
from accounts.forms import StudentCVForm, CVEducationForm, CVExperienceForm, CVSkillForm


logger = logging.getLogger(__name__)

SMART_MATCH_ERROR_MESSAGE = "Nu au fost primite rezultate valide pentru actualizare. Rezultatele existente au fost păstrate."


def is_company(user):
    return user.is_authenticated and user.role == "company"


def _smart_match_lock_key(user_id):
    return f"smart_match_running_{user_id}"


def _career_analysis_lock_key(user_id, internship_id):
    return f"career_analysis_running_{user_id}_{internship_id}"


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


def home(request):
    offers = InternshipOffer.objects.filter(is_active=True).order_by("-created_at")
    context = {
        "offers": offers,
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
    context = {
        "offer": offer,
        "is_owner": is_owner,
        "has_applied": has_applied,
        "student_application": student_application,
        "has_active_internship": has_active_internship,
        "has_complete_cv": has_complete_cv,
        "has_uploaded_cv": has_uploaded_cv,
        "has_applicable_cv": has_applicable_cv_data,
    }
    return render(request, "main/offer_details.html", context)


@login_required
def apply_to_offer(request, offer_id):
    if not request.user.is_student():
        return _forbidden_page(request, "Doar studenții pot aplica.")

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

    if internship:
        entries = internship.journal_entries.all().order_by(
            "-week_number", "-created_at"
        )

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
    }
    return render(request, "main/create_journal_entry.html", context)


@login_required
def edit_journal_entry(request, internship_id, entry_id):
    internship = get_object_or_404(Internship, pk=internship_id)

    if request.user != internship.student:
        return _forbidden_page(request, "Doar studentul poate edita intrări în jurnal.")

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

    context = {
        "internship": internship,
        "student": internship.student,
        "company": internship.company,
        "entries": entries,
    }
    pdf_content = generate_pdf("main/pdf/journal_template.html", context)

    response = HttpResponse(pdf_content, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="Jurnal_practica_{internship.id}.pdf"'
    )
    return response


@login_required
@user_passes_test(is_company)
def company_my_offers(request):
    offers = InternshipOffer.objects.filter(company=request.user).order_by(
        "-created_at"
    )
    return render(request, "main/company_my_offers.html", {"offers": offers})


@login_required
@user_passes_test(is_company)
def create_internship_offer(request):
    if request.method == "POST":
        form = InternshipOfferForm(request.POST)
        if form.is_valid():
            offer = form.save(commit=False)
            offer.company = request.user
            offer.save()
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
def delete_internship_offer(request, pk):
    offer = get_object_or_404(InternshipOffer, pk=pk)

    if offer.company != request.user:
        return _forbidden_page(request, "Nu ai permisiunea de a șterge această ofertă.")

    if request.method == "POST":
        password = request.POST.get("password")
        if not password or not check_password(password, request.user.password):
            context = {
                "offer": offer,
                "password_error": "Parola introdusă este incorectă.",
            }
            return render(request, "main/delete_internship_offer.html", context)

        offer.delete()
        messages.success(request, "Oferta de stagiu a fost ștearsă cu succes!")
        return redirect("company_my_offers")

    return render(request, "main/delete_internship_offer.html", {"offer": offer})


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
        filename = f"Contract_{app.student.get_full_name()}_{app.offer.id}.pdf"
        internship.signed_contract.save(filename, ContentFile(pdf_content))

        messages.success(
            request,
            "Participarea a fost confirmată. Contractul de practică a fost generat.",
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
                start_date=app.offer.start_date,
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
            return _smart_match_error_redirect(request)

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
                    "Rezultatele de smart matching au fost actualizate cu succes.",
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
