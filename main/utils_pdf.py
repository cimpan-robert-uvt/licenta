import os
from django.conf import settings
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from io import BytesIO


def fetch_resources(uri, rel):
    """
    Convert HTML URIs to absolute system paths so xhtml2pdf can access
    local resources (like CSS and images).
    """
    if uri.startswith("data:"):
        return uri

    if uri.startswith("//"):
        uri = "https:" + uri

    if uri.startswith("http://") or uri.startswith("https://"):
        return uri

    uri = uri.split("?")[0].split("#")[0]

    path = ""
    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(str(settings.MEDIA_ROOT), uri[len(settings.MEDIA_URL) :])
    elif uri.startswith(settings.STATIC_URL):
        relative_uri = uri[len(settings.STATIC_URL) :]
        path = os.path.join(str(settings.STATIC_ROOT), relative_uri)

        if not os.path.exists(path):
            for d in getattr(settings, "STATICFILES_DIRS", []):
                alt_path = os.path.join(str(d), relative_uri)
                if os.path.exists(alt_path):
                    path = alt_path
                    break

    if path:
        return path.replace("\\", "/")

    return uri


def generate_pdf(template_name, context):
    """
    Renders a Django template to PDF and returns the file object using xhtml2pdf.
    """
    html_string = render_to_string(template_name, context)
    buffer = BytesIO()

    pisa.CreatePDF(
        html_string, dest=buffer, encoding="UTF-8", link_callback=fetch_resources
    )

    pdf = buffer.getvalue()
    buffer.close()
    return pdf
