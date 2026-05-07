from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import (
    SignUpForm,
    CustomAuthenticationForm,
    ProfileForm,
    DeleteAccountForm,
    CustomPasswordChangeForm,
)
from django.contrib.auth import update_session_auth_hash


def register(request):
    if request.method == "POST":
        form = SignUpForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
    else:
        form = SignUpForm()
    return render(request, "accounts/register.html", {"form": form})


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
