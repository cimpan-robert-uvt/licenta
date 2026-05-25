import random
import string

from django.shortcuts import render, redirect
from django.contrib.auth import login, update_session_auth_hash, logout
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import send_mail
from .forms import (
    SignUpForm,
    CustomAuthenticationForm,
    ProfileForm,
    StudentIdentificationForm,
    CompanyIdentificationForm,
    DeleteAccountForm,
    CustomPasswordChangeForm,
    ResetPasswordForm,
)
from .models import User, StudentProfile, CompanyProfile
from main.models import Internship


def register(request):
    if request.method == "POST":
        form = SignUpForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            full_name = user.get_full_name().strip() or user.username
            if user.email:
                send_mail(
                    "Bine ai venit pe platforma PIGSP!",
                    (
                        f"Buna, {full_name}!\n\n"
                        "Iti multumim ca te-ai inregistrat pe platforma PIGSP. "
                        "Contul tau a fost creat cu succes.\n\n"
                        "Succes,\n"
                        "Echipa PIGSP"
                    ),
                    None,
                    [user.email],
                )
            login(request, user)
            return redirect("home")
    else:
        form = SignUpForm()
    return render(request, "accounts/register.html", {"form": form})


def forgot_password(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        if not email:
            messages.error(request, "Te rugam sa introduci adresa de email.")
            return render(request, "accounts/forgot_password.html")

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            messages.error(request, "Nu exista un utilizator cu acest email.")
            return render(request, "accounts/forgot_password.html")

        code = "".join(
            random.choice(string.ascii_letters + string.digits) for _ in range(8)
        )
        email_key = user.email.lower()
        cache.set(f"reset_code_{email_key}", code, 300)
        request.session["reset_email"] = user.email

        send_mail(
            "Cod de resetare parola",
            (
                f"Buna, {user.get_full_name().strip() or user.username}!\n\n"
                "Ai solicitat resetarea parolei. Codul tau este:\n\n"
                f"{code}\n\n"
                "Codul este valabil 5 minute."
            ),
            None,
            [user.email],
        )
        messages.success(request, "Am trimis un cod de resetare pe email.")
        return redirect("reset_password")

    return render(request, "accounts/forgot_password.html")


def reset_password(request):
    email = request.session.get("reset_email")
    if not email:
        messages.error(request, "Nu exista o cerere activa de resetare.")
        return redirect("forgot_password")

    if request.method == "POST":
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["code"]
            cached_code = cache.get(f"reset_code_{email.lower()}")
            if not cached_code:
                form.add_error("code", "Codul a expirat. Solicita unul nou.")
            elif code != cached_code:
                form.add_error("code", "Codul este invalid.")
            else:
                user = User.objects.filter(email__iexact=email).first()
                if not user:
                    messages.error(request, "Utilizatorul nu a fost gasit.")
                    return redirect("forgot_password")

                user.set_password(form.cleaned_data["new_password1"])
                user.save()
                cache.delete(f"reset_code_{email.lower()}")
                request.session.pop("reset_email", None)
                messages.success(request, "Parola a fost schimbata cu succes.")
                return render(
                    request,
                    "accounts/reset_password.html",
                    {
                        "form": form,
                        "password_reset_success": True,
                    },
                )

        return render(request, "accounts/reset_password.html", {"form": form})

    form = ResetPasswordForm()
    return render(request, "accounts/reset_password.html", {"form": form})


@login_required(login_url="login")
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil actualizat cu succes!")
            return redirect("profile")
    else:
        form = ProfileForm(instance=request.user)

    return render(request, "accounts/profile.html", {"form": form})


@login_required(login_url="login")
def identification_data(request):
    if request.user.is_student():
        profile, _ = StudentProfile.objects.get_or_create(user=request.user)
        form_class = StudentIdentificationForm
        page_title = "Date de identificare student"
    elif request.user.is_company():
        profile, _ = CompanyProfile.objects.get_or_create(user=request.user)
        form_class = CompanyIdentificationForm
        page_title = "Date de identificare companie"
    else:
        messages.warning(request, "Tip de cont neacceptat pentru aceasta pagina.")
        return redirect("profile")

    if request.method == "POST":
        form = form_class(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Datele de identificare au fost salvate.")
            return redirect("identification_data")
    else:
        form = form_class(instance=profile)

    return render(
        request,
        "accounts/identification_data.html",
        {
            "form": form,
            "page_title": page_title,
        },
    )


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = CustomAuthenticationForm
    redirect_authenticated_user = True


@login_required(login_url="login")
def change_password(request):
    if request.method == "POST":
        form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            messages.success(request, "Parola a fost schimbată cu succes!")
            return redirect("profile")
    else:
        form = CustomPasswordChangeForm(user=request.user)
    return render(request, "accounts/change_password.html", {"form": form})


@login_required(login_url="login")
def delete_account(request):
    user = request.user
    company_delete_blocked = False
    student_delete_blocked = False
    delete_blocked_message = (
        "Contul nu poate fi sters momentan. Contactati administratorul."
    )
    if user.role == "company":
        company_delete_blocked = Internship.objects.filter(
            company=user, journal_confirmed_at__isnull=True
        ).exists()
    elif user.role == "student":
        student_delete_blocked = Internship.objects.filter(
            student=user, journal_confirmed_at__isnull=True
        ).exists()

    delete_blocked = company_delete_blocked or student_delete_blocked

    if request.method == "POST":
        form = DeleteAccountForm(user=request.user, data=request.POST)
        if delete_blocked:
            return render(
                request,
                "accounts/delete_account.html",
                {
                    "form": form,
                    "company_delete_blocked": company_delete_blocked,
                    "student_delete_blocked": student_delete_blocked,
                    "delete_blocked": delete_blocked,
                    "delete_blocked_message": delete_blocked_message,
                },
            )
        if form.is_valid():
            if user.role == "company":
                user.internship_offers.update(is_active=False, is_archived=True)

                try:
                    cp = user.company_profile
                    cp.company_name = f"Companie arhivată #{user.id}"
                    cp.domain = "altele"
                    cp.industry = ""
                    cp.website = ""
                    cp.address = ""
                    cp.contact_person = ""
                    cp.contact_phone = ""
                    cp.save()
                except Exception:
                    pass

                rand_suffix = "".join(
                    random.choice(string.ascii_lowercase) for _ in range(6)
                )
                user.username = f"deleted_user_{user.id}_{rand_suffix}"
                user.email = ""
                user.first_name = ""
                user.last_name = ""
                try:
                    user.phone_number = None
                except Exception:
                    pass
                user.set_unusable_password()
                user.is_active = False
                try:
                    if user.profile_picture:
                        user.profile_picture.delete(save=False)
                        user.profile_picture = None
                except Exception:
                    pass
                user.save()
            else:
                try:
                    if user.profile_picture:
                        user.profile_picture.delete(save=False)
                except Exception:
                    pass

                try:
                    cv = user.student_cv
                    if cv and cv.pdf_file:
                        cv.pdf_file.delete(save=False)
                except Exception:
                    pass

                user.delete()

            logout(request)
            messages.success(request, "Contul a fost șters cu succes!")
            return redirect("home")
    else:
        form = DeleteAccountForm()
    return render(
        request,
        "accounts/delete_account.html",
        {
            "form": form,
            "company_delete_blocked": company_delete_blocked,
            "student_delete_blocked": student_delete_blocked,
            "delete_blocked": delete_blocked,
            "delete_blocked_message": (
                delete_blocked_message if delete_blocked else ""
            ),
        },
    )
