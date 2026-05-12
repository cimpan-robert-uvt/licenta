from django import forms
from django.utils import timezone
from .models import InternshipOffer


class InternshipOfferForm(forms.ModelForm):
    class Meta:
        model = InternshipOffer
        fields = [
            "title",
            "description",
            "requirements",
            "location",
            "duration_weeks",
            "start_date",
            "is_active",
        ]
        labels = {
            "title": "Titlu ofertă",
            "description": "Descriere",
            "requirements": "Cerințe",
            "location": "Locație",
            "duration_weeks": "Durata (săptămâni)",
            "start_date": "Data începerii",
            "is_active": "Ofertă activă",
        }
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "requirements": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "location": forms.TextInput(attrs={"class": "form-control"}),
            "duration_weeks": forms.NumberInput(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_start_date(self):
        start_date = self.cleaned_data.get("start_date")
        today = timezone.localdate()

        if not start_date:
            return start_date

        if not self.instance.pk and start_date < today:
            raise forms.ValidationError(
                "Data începerii stagiului nu poate fi în trecut."
            )

        if (
            self.instance.pk
            and start_date < today
            and self.instance.start_date != start_date
        ):
            raise forms.ValidationError(
                "Data începerii stagiului nu poate fi în trecut."
            )

        return start_date

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = True
        self.fields["description"].required = True
        self.fields["requirements"].required = True
        self.fields["location"].required = True
        self.fields["duration_weeks"].required = True
        self.fields["start_date"].required = True

    def clean_duration_weeks(self):
        duration = self.cleaned_data.get("duration_weeks")

        if self.instance and self.instance.pk:
            has_internships = self.instance.internships.exists()
            if has_internships and duration != self.instance.duration_weeks:
                raise forms.ValidationError(
                    "Durata nu poate fi modificată deoarece există deja stagii asociate acestei oferte."
                )

        return duration
