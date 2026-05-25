import logging
from io import BytesIO

from django.template.loader import render_to_string
from xhtml2pdf import pisa

logger = logging.getLogger(__name__)


def generate_pdf(template_name, context):
    """
    Renders a Django template to a PDF using xhtml2pdf.
    """
    html_string = render_to_string(template_name, context or {})
    buffer = BytesIO()
    pdf_status = pisa.CreatePDF(
        src=html_string,
        dest=buffer,
        encoding="UTF-8",
    )

    if pdf_status.err:
        logger.error(
            "Error generating PDF for template %s: %s", template_name, pdf_status.log
        )
        raise ValueError(
            "Could not generate PDF. Check logs for details from xhtml2pdf."
        )

    pdf_content = buffer.getvalue()
    buffer.close()
    return pdf_content
