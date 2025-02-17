import logging

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.html import format_html
from social_django.models import UserSocialAuth

from sboms.models import SBOM, Component, Product, Project
from teams.models import Member, Team

from .models import User

logger = logging.getLogger(__name__)


class DashboardView(admin.AdminSite):
    site_header = "sbomify administration"
    site_title = "sbomify admin"
    index_title = "sbomify administration"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("dashboard/", self.admin_view(self.dashboard_view), name="admin_dashboard"),
        ]
        return custom_urls + urls

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        app_list = self.get_app_list(request)

        # Add dashboard link to the index
        dashboard_app = {
            "name": "Dashboard",
            "app_label": "core",
            "app_url": "/admin/dashboard/",
            "has_module_perms": True,
            "models": [{
                "name": "System Dashboard",
                "object_name": "Dashboard",
                "admin_url": "/admin/dashboard/",
                "view_only": True,
            }],
        }

        app_list.insert(0, dashboard_app)
        extra_context["app_list"] = app_list
        return super().index(request, extra_context)

    def dashboard_view(self, request):
        context = {
            **self.each_context(request),
            "title": "System Dashboard",
            "stats": {
                "users": User.objects.count(),
                "teams": Team.objects.count(),
                "products": Product.objects.count(),
                "projects": Project.objects.count(),
                "components": Component.objects.count(),
                "sboms": SBOM.objects.count(),
                "users_per_team": list(Team.objects.annotate(
                    user_count=Count("members")
                ).values("name", "user_count")),
            },
            "app_label": "core",
            "has_permission": True,
        }
        return TemplateResponse(request, "admin/dashboard.html", context)


class CustomUserAdmin(UserAdmin):
    """Custom admin for User model with Auth0 integration."""

    list_display = UserAdmin.list_display + ("email_verified_status",)
    readonly_fields = UserAdmin.readonly_fields + ("email_verified_status",)

    @admin.display(
        description="Email Verified",
        boolean=False  # We're using custom HTML output
    )
    def email_verified_status(self, obj):
        """Get email verification status from Auth0.

        Checks both Auth0 and social login providers (GitHub/Google) which
        always have verified emails.
        """
        try:
            # First check for social logins (GitHub/Google)
            social_auths = UserSocialAuth.objects.filter(user=obj)

            for auth in social_auths:
                # GitHub/Google emails are always verified
                if auth.provider in ["github", "google-oauth2"]:
                    return format_html(
                        '<img src="/static/admin/img/icon-yes.svg" alt="True"> '
                        '<span style="color: #417690;">({})</span>',
                        auth.provider
                    )

                # Check Auth0 verification
                if auth.provider == "auth0" and auth.extra_data:
                    email_verified = auth.extra_data.get("email_verified", False)
                    if email_verified:
                        return format_html(
                            '<img src="/static/admin/img/icon-yes.svg" alt="True">'
                        )
                    return format_html(
                        '<img src="/static/admin/img/icon-no.svg" alt="False"> '
                        '<span style="color: #ba2121;">unverified</span>'
                    )

            # No social auths found
            return format_html(
                '<span style="color: #666;">no social auth</span>'
            )

        except Exception as e:
            # Log the error but don't expose it in admin
            logger.error(f"Error checking email verification for user {obj.id}: {str(e)}")
            return format_html(
                '<span style="color: #666;">error checking status</span>'
            )


# Create custom admin site
admin_site = DashboardView(name="admin")

# Register all models with our custom admin site
admin_site.register(User, CustomUserAdmin)
admin_site.register(Team)
admin_site.register(Member)
admin_site.register(Product)
admin_site.register(Project)
admin_site.register(Component)
admin_site.register(SBOM)
