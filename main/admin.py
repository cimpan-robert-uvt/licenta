from django.contrib import admin
from .models import InternshipOffer, Application, Internship, JournalEntry


@admin.register(InternshipOffer)
class InternshipOfferAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "company",
        "location",
        "is_active",
        "is_archived",
        "created_at",
    )
    list_filter = ("is_active", "is_archived", "created_at", "start_date")
    search_fields = ("title", "description", "company__username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("student", "offer", "status", "applied_at")
    list_filter = ("status", "applied_at")
    search_fields = ("student__username", "offer__title")
    readonly_fields = ("applied_at", "updated_at")
    actions = ["accept_applications", "reject_applications"]

    def accept_applications(self, request, queryset):
        for app in queryset.filter(status="pending"):
            app.accept()
        self.message_user(request, "Aplicațiile selectate au fost acceptate.")

    accept_applications.short_description = "Acceptă aplicațiile selectate"

    def reject_applications(self, request, queryset):
        for app in queryset.filter(status="pending"):
            app.reject()
        self.message_user(request, "Aplicațiile selectate au fost respinse.")

    reject_applications.short_description = "Respinge aplicațiile selectate"


@admin.register(Internship)
class InternshipAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "company",
        "start_date",
        "is_active",
        "journal_submitted_at",
        "journal_confirmed_at",
    )
    list_filter = ("is_active", "start_date", "journal_submitted_at", "journal_confirmed_at")
    search_fields = ("student__username", "company__username")
    readonly_fields = ("created_at", "get_current_week")

    def get_current_week(self, obj):
        return obj.get_current_week() or "Inactiv"

    get_current_week.short_description = "Săptămâna curentă"


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("internship", "week_number", "created_at")
    list_filter = ("created_at", "week_number")
    search_fields = ("internship__student__username", "content")
    readonly_fields = ("created_at",)
