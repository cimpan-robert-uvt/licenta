import random
import string

from django.shortcuts import render, redirect
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import send_mail
from .forms import (
    SignUpForm,
    CustomAuthenticationForm,
    ProfileForm,
    DeleteAccountForm,
    CustomPasswordChangeForm,
    ResetPasswordForm,
)
from .models import User


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
    if request.method == "POST":
        form = DeleteAccountForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = request.user
            user.delete()
            messages.success(request, "Contul a fost șters cu succes!")
            return redirect("home")
    else:
        form = DeleteAccountForm()
    return render(request, "accounts/delete_account.html", {"form": form})
