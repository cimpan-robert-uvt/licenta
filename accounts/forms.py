import re
from django import forms
from django.contrib.auth.forms import (
    UserCreationForm,
    AuthenticationForm,
    PasswordChangeForm,
)
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from .models import (
    User,
    StudentProfile,
    CompanyProfile,
    StudentCV,
    CVEducation,
    CVExperience,
    CVSkill,
    DOMAIN_CHOICES,
)


class DateInputISO(forms.DateInput):
    """Custom DateInput widget that always renders dates in ISO format (YYYY-MM-DD)
    regardless of locale settings. Required for HTML5 input type='date'."""

    input_type = "date"

    def format_value(self, value):
        """Render date value in ISO format (YYYY-MM-DD) for HTML5 input type='date'"""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return value.strftime("%Y-%m-%d")


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Nume utilizator", widget=forms.TextInput(attrs={"autofocus": True})
    )
    password = forms.CharField(
        label="Parolă",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    error_messages = {
        "invalid_login": "Numele de utilizator sau parola sunt incorecte.",
        "inactive": "Acest cont este inactiv.",
    }


class SignUpForm(UserCreationForm):
    ROLE_CHOICES = [
        ("student", "Student"),
        ("company", "Companie"),
    ]
    role = forms.ChoiceField(
        choices=ROLE_CHOICES, widget=forms.RadioSelect, label="Sunt"
    )

    company_name = forms.CharField(
        required=False,
        label="Nume companie",
        help_text="Obligatoriu dacă selectați Companie",
    )

    domain = forms.ChoiceField(
        choices=DOMAIN_CHOICES,
        required=True,
        label="Domeniu",
    )

    phone_number = forms.CharField(
        required=True,
        label="Număr telefon",
        max_length=15,
        validators=[
            RegexValidator(
                regex=r"^\+?[0-9]{10,}$",
                message="Numărul de telefon trebuie să conțină cel puțin 10 cifre și opțional un '+' la început.",
            )
        ],
    )

    profile_picture = forms.ImageField(required=False, label="Fotografie profil")

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "birth_date",
            "password1",
            "password2",
            "role",
            "domain",
            "company_name",
            "profile_picture",
        )
        labels = {
            "username": "Nume utilizator",
            "email": "Email",
            "first_name": "Prenume",
            "last_name": "Nume",
            "birth_date": "Data nașterii",
        }
        help_texts = {
            "username": "30 de caractere sau mai puțin. Doar litere, cifre și @/./+/-/_ .",
        }
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["domain"].choices = [("", "---")] + list(DOMAIN_CHOICES)
        self.fields["domain"].initial = ""
        self.fields["email"].required = True
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["birth_date"].required = True
        self.fields["password1"].label = "Parolă"
        self.fields[
            "password1"
        ].help_text = "Parola trebuie să conțină minim 8 caractere, o literă mică, o literă mare, o cifră și un caracter special."
        self.fields["password2"].label = "Confirmă parola"
        self.fields[
            "password2"
        ].help_text = "Introduceți din nou parola pentru verificare."

        self.error_messages["password_mismatch"] = "Cele două parole nu se potrivesc."

        for field in self.fields.values():
            field.error_messages["required"] = "Acest câmp este obligatoriu."
        self.fields["email"].error_messages["invalid"] = (
            "Introduceți o adresă de email validă."
        )

    def clean_domain(self):
        domain = self.cleaned_data.get("domain")
        if not domain:
            raise ValidationError("Selectează un domeniu.")
        return domain

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        company_name = cleaned_data.get("company_name")

        if role == "company" and not company_name:
            self.add_error(
                "company_name",
                "Numele companiei este obligatoriu pentru conturile de companie.",
            )

        password1 = self.cleaned_data.get("password1")
        if password1:
            if len(password1) < 8:
                self.add_error(
                    "password1", "Parola trebuie să conțină cel puțin 8 caractere."
                )
            elif not any(char.isupper() for char in password1):
                self.add_error(
                    "password1",
                    "Parola trebuie să conțină cel puțin o literă mare.",
                )
            elif not any(char.islower() for char in password1):
                self.add_error(
                    "password1",
                    "Parola trebuie să conțină cel puțin o literă mică.",
                )
            elif not any(char.isdigit() for char in password1):
                self.add_error(
                    "password1", "Parola trebuie să conțină cel puțin o cifră."
                )
            elif not re.search(r"[^a-zA-Z0-9]", password1):
                self.add_error(
                    "password1",
                    "Parola trebuie să conțină cel puțin un caracter special (ex: @, #, !, etc.).",
                )

        return cleaned_data

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if email:
            if not re.match(r"^.+@.+\..+$", email):
                raise ValidationError("Introduceți o adresă de email validă.")
            if User.objects.filter(email__iexact=email).exists():
                raise ValidationError("Există deja un cont cu această adresă de email.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data.get("role")

        if commit:
            user.save()
            if user.role == "student":
                StudentProfile.objects.create(
                    user=user,
                    domain=self.cleaned_data.get("domain"),
                )
            elif user.role == "company":
                CompanyProfile.objects.create(
                    user=user,
                    company_name=self.cleaned_data.get("company_name"),
                    domain=self.cleaned_data.get("domain"),
                )
        return user


class ProfileForm(forms.ModelForm):
    phone_number = forms.CharField(
        required=True,
        label="Număr telefon",
        max_length=15,
        validators=[
            RegexValidator(
                regex=r"^\+?[0-9]{10,}$",
                message="Numărul de telefon trebuie să conțină cel puțin 10 cifre și opțional un '+' la început.",
            )
        ],
    )

    company_name = forms.CharField(
        required=True,
        label="Nume companie",
    )

    domain = forms.ChoiceField(
        choices=DOMAIN_CHOICES,
        required=True,
        label="Domeniu",
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "birth_date",
            "profile_picture",
        )
        labels = {
            "username": "Nume utilizator",
            "email": "Email",
            "first_name": "Prenume",
            "last_name": "Nume",
            "profile_picture": "Fotografie profil",
            "birth_date": "Data nașterii",
        }
        help_texts = {
            "username": "30 de caractere sau mai puțin. Doar litere, cifre și @/./+/-/_ .",
        }
        widgets = {
            "profile_picture": forms.ClearableFileInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "birth_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["birth_date"].required = True

        if self.instance.pk and self.instance.role == "student":
            self.fields["company_name"].required = False
        else:
            self.fields["company_name"].required = True

        if self.instance.pk and hasattr(self.instance, "company_profile"):
            self.fields[
                "company_name"
            ].initial = self.instance.company_profile.company_name

        if (
            self.instance.pk
            and self.instance.role == "student"
            and hasattr(self.instance, "student_profile")
        ):
            self.fields["domain"].initial = self.instance.student_profile.domain
        elif (
            self.instance.pk
            and self.instance.role == "company"
            and hasattr(self.instance, "company_profile")
        ):
            self.fields["domain"].initial = self.instance.company_profile.domain

        for field in self.fields.values():
            field.error_messages["required"] = "Acest câmp este obligatoriu."
        self.fields["email"].error_messages["invalid"] = (
            "Introduceți o adresă de email validă."
        )

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if User.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Acest nume de utilizator este deja folosit.")
        return username

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if email:
            if not re.match(r"^.+@.+\..+$", email):
                raise ValidationError("Introduceți o adresă de email validă.")
            if (
                User.objects.filter(email__iexact=email)
                .exclude(pk=self.instance.pk)
                .exists()
            ):
                raise ValidationError("Există deja un cont cu această adresă de email.")
        return email

    def save(self, commit=True):
        user = super().save(commit=commit)

        if user.role == "company":
            company_name = self.cleaned_data.get("company_name")
            domain = self.cleaned_data.get("domain")
            if hasattr(user, "company_profile"):
                user.company_profile.company_name = company_name
                user.company_profile.domain = domain
                user.company_profile.save()
            else:
                CompanyProfile.objects.create(
                    user=user,
                    company_name=company_name,
                    domain=domain,
                )
        elif user.role == "student":
            domain = self.cleaned_data.get("domain")
            if hasattr(user, "student_profile"):
                user.student_profile.domain = domain
                user.student_profile.save()
            else:
                StudentProfile.objects.create(user=user, domain=domain)

        return user


class StudentCVForm(forms.ModelForm):
    class Meta:
        model = StudentCV
        fields = ["phone", "email", "linkedin", "city", "resume", "pdf_file"]
        widgets = {
            "phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Numărul tău de telefon",
                }
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "Adresa ta de email"}
            ),
            "linkedin": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://linkedin.com/in/...",
                }
            ),
            "city": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Orașul în care locuiești",
                }
            ),
            "resume": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Scrie un scurt rezumat despre tine (competențe principale, obiective profesionale, etc.)",
                    "maxlength": "500",
                }
            ),
            "pdf_file": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": ".pdf,application/pdf",
                }
            ),
        }
        labels = {
            "phone": "Telefon *",
            "email": "Email *",
            "linkedin": "Profil LinkedIn",
            "city": "Oraș",
            "resume": "Rezumat *",
            "pdf_file": "CV personal (PDF)",
        }

    def clean_pdf_file(self):
        pdf_file = self.cleaned_data.get("pdf_file")
        if not pdf_file:
            return pdf_file

        filename = (pdf_file.name or "").lower()
        if not filename.endswith(".pdf"):
            raise ValidationError("Poți încărca doar fișiere PDF.")

        return pdf_file


class CVEducationForm(forms.ModelForm):
    class Meta:
        model = CVEducation
        fields = ["school_name", "start_date", "end_date", "details"]
        widgets = {
            "school_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                }
            ),
            "start_date": DateInputISO(attrs={"class": "form-control"}),
            "end_date": DateInputISO(attrs={"class": "form-control"}),
            "details": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                }
            ),
        }
        labels = {
            "school_name": "Școala/Facultatea",
            "start_date": "Data de început",
            "end_date": "Data de sfârşit",
            "details": "Detalii",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["school_name"].required = False
        self.fields["start_date"].required = False
        self.fields["start_date"].input_formats = ["%Y-%m-%d"]
        self.fields["end_date"].required = False
        self.fields["end_date"].input_formats = ["%Y-%m-%d"]
        self.fields["details"].required = False


class CVExperienceForm(forms.ModelForm):
    class Meta:
        model = CVExperience
        fields = ["institution_name", "start_date", "end_date", "details"]
        widgets = {
            "institution_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                }
            ),
            "start_date": DateInputISO(attrs={"class": "form-control"}),
            "end_date": DateInputISO(attrs={"class": "form-control"}),
            "details": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                }
            ),
        }
        labels = {
            "institution_name": "Instituție/Companie",
            "start_date": "Data de început",
            "end_date": "Data de sfârşit",
            "details": "Detalii",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["institution_name"].required = False
        self.fields["start_date"].required = False
        self.fields["start_date"].input_formats = ["%Y-%m-%d"]
        self.fields["end_date"].required = False
        self.fields["end_date"].input_formats = ["%Y-%m-%d"]
        self.fields["details"].required = False


class CVSkillForm(forms.ModelForm):
    class Meta:
        model = CVSkill
        fields = ["skill_type", "skill_name"]
        widgets = {
            "skill_type": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
            "skill_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "De exemplu: Python, Comunicare, etc.",
                }
            ),
        }
        labels = {
            "skill_type": "Tip Abilitate",
            "skill_name": "Abilitate",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["skill_type"].required = False
        self.fields["skill_name"].required = False


class DeleteAccountForm(forms.Form):
    password = forms.CharField(
        label="PAROLA",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if self.user and not self.user.check_password(password):
            raise ValidationError("Parola este incorectă.")
        return password


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Parola veche"
        self.fields["new_password1"].label = "Parolă nouă"
        self.fields[
            "new_password1"
        ].help_text = "Parola trebuie să conțină minim 8 caractere, o literă mică, o literă mare, o cifră și un caracter special."
        self.fields["new_password2"].label = "Confirmă parola nouă"
        self.fields[
            "new_password2"
        ].help_text = "Introduceți din nou parola pentru verificare."

        self.error_messages["password_mismatch"] = "Cele două parole nu se potrivesc."

        for field in self.fields.values():
            field.error_messages["required"] = "Acest câmp este obligatoriu."

    def clean_new_password1(self):
        password = super().clean_new_password1()
        if password:
            if len(password) < 8:
                raise ValidationError(
                    "Parola trebuie să conțină cel puțin 8 caractere."
                )
            elif not any(char.isupper() for char in password):
                raise ValidationError(
                    "Parola trebuie să conțină cel puțin o literă mare."
                )
            elif not any(char.islower() for char in password):
                raise ValidationError(
                    "Parola trebuie să conțină cel puțin o literă mică."
                )
            elif not any(char.isdigit() for char in password):
                raise ValidationError("Parola trebuie să conțină cel puțin o cifră.")
            elif not re.search(r"[^a-zA-Z0-9]", password):
                raise ValidationError(
                    "Parola trebuie să conțină cel puțin un caracter special (ex: @, #, !, etc.)."
                )
        return password
