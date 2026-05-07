from django.contrib import admin
from .models import User, StudentProfile, CompanyProfile


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "first_name", "last_name", "role")
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Informații personale", {"fields": ("first_name", "last_name", "email")}),
        ("Rol", {"fields": ("role",)}),
        (
            "Permisiuni",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Date importante", {"fields": ("last_login", "date_joined")}),
    )


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "faculty", "specialization", "year_of_study")
    list_filter = ("faculty", "year_of_study")
    search_fields = ("user__username", "user__email", "faculty")


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ("company_name", "user", "industry", "contact_person")
    list_filter = ("industry", "created_at")
    search_fields = ("company_name", "user__username", "website")
