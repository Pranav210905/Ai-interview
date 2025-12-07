from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from io import BytesIO
from datetime import datetime

def generate_pdf_report(session_data: dict, answers_data: list) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor='#1a1a1a',
        spaceAfter=30,
        alignment=TA_CENTER
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor='#2c3e50',
        spaceAfter=12,
        spaceBefore=20
    )
    normal_style = styles['Normal']

    story = []

    story.append(Paragraph("Interview Results Report", title_style))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%B %d, %Y')}", normal_style))
    story.append(Paragraph(f"<b>Duration:</b> {session_data['duration_seconds'] // 60} minutes", normal_style))
    story.append(Spacer(1, 0.3*inch))

    story.append(Paragraph("Job Description", heading_style))
    story.append(Paragraph(session_data['job_description'][:500] + "...", normal_style))
    story.append(Spacer(1, 0.3*inch))

    for idx, answer in enumerate(answers_data, 1):
        if idx > 1:
            story.append(PageBreak())

        story.append(Paragraph(f"Question {idx}", heading_style))

        question_text = next(
            (q['text'] for q in session_data.get('questions', []) if q['id'] == answer['question_id']),
            "Question not found"
        )
        story.append(Paragraph(f"<b>Q:</b> {question_text}", normal_style))
        story.append(Spacer(1, 0.2*inch))

        story.append(Paragraph(f"<b>Your Answer:</b>", normal_style))
        story.append(Paragraph(answer.get('transcript', 'No transcript available'), normal_style))
        story.append(Spacer(1, 0.2*inch))

        if answer.get('score'):
            story.append(Paragraph(f"<b>Score:</b> {answer['score']}/10", normal_style))
            story.append(Spacer(1, 0.1*inch))

        if answer.get('feedback'):
            story.append(Paragraph(f"<b>Feedback:</b>", normal_style))
            for feedback_item in answer['feedback']:
                story.append(Paragraph(f"• {feedback_item}", normal_style))
            story.append(Spacer(1, 0.2*inch))

        if answer.get('model_answer'):
            story.append(Paragraph(f"<b>Model Answer:</b>", normal_style))
            story.append(Paragraph(answer['model_answer'], normal_style))

        story.append(Spacer(1, 0.2*inch))

    doc.build(story)

    buffer.seek(0)
    return buffer.read()
