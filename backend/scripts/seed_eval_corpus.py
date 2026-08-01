"""Seed the reproducible fixture corpus used by backend/app/evals/datasets/retrieval_golden.jsonl.

Creates (or reuses) a dedicated "Scrutinize Eval Corpus" project, ingests a small
set of synthetic documents as files/segments, embeds them, and upserts them to
Qdrant. Idempotent: existing segments/vectors for the eval project are wiped
and rebuilt each run so the corpus always matches this script's fixtures.

Usage: python backend/scripts/seed_eval_corpus.py
"""

from __future__ import annotations

import sys
from uuid import uuid4

from sqlmodel import Session, select

from app.core.config import reload_settings
from app.core.database import get_engine, init_db
from app.models.file import File, FileModality, FileStatus
from app.models.project import Project
from app.models.segment import Segment
from app.services.embedding_service import EmbeddingService
from app.services.job_orchestrator import JobOrchestrator
from app.services.text_processor import chunk_text
from app.services.vector_store import VectorSegment, VectorStore

EVAL_PROJECT_NAME = "Scrutinize Eval Corpus"

# doc_id -> (filename, body). doc_id matches expected_doc_ids in retrieval_golden.jsonl.
FIXTURE_DOCS: dict[str, tuple[str, str]] = {
    "vendor_contract": (
        "vendor_services_agreement.md",
        """# Vendor Services Agreement

This Vendor Services Agreement ("Agreement") is entered into between Acme Corp
("Client") and Northwind Supply Co. ("Vendor").

## Payment Terms
All invoices are payable in USD within 30 days of receipt. Late payments
accrue a fee of 1.5% per month on the outstanding balance.

## Term and Termination
Either party may terminate this Agreement for convenience with 60 days
written notice. Either party may terminate immediately for material breach
that remains uncured after 15 days.

## Limitation of Liability
Acme Corp's aggregate liability under this Agreement shall not exceed the
total fees paid in the preceding 12 months.

## Signatures
This Agreement is executed by an authorized representative of Acme Corp and
an authorized representative of Northwind Supply Co.
""",
    ),
    "hr_policy": (
        "employee_handbook_leave_policy.md",
        """# Employee Handbook: Leave Policy

## Annual Leave
Employees accrue 20 days of annual leave per calendar year. Accrual resets
every January 1st. Up to 5 unused days may roll over into the following year.

## Sick Leave
Full-time employees are entitled to 10 paid sick days per year, credited at
the start of employment and renewed annually.

## Parental Leave
Employees requesting parental leave must submit a written request to HR at
least 30 days before the expected leave start date, along with supporting
documentation.

## Remote Work Eligibility
Employees are eligible for remote work after completing a 90-day probationary
period, subject to manager approval.

## Disciplinary Process
Policy violations follow a progressive discipline process: verbal warning,
written warning, final written warning, and termination.
""",
    ),
    "q3_earnings": (
        "q3_earnings_summary.md",
        """# Q3 Earnings Summary

Total quarterly revenue for Q3 was $42.3 million, up 18% year over year.

## Margins
Gross margin for the quarter was 61%, an improvement of 3 points from Q2.

## Operating Expenses
Operating expenses grew 9% year over year, driven primarily by increased
headcount in sales and customer support.

## Guidance
Management issued Q4 guidance of $45-47 million in revenue, ahead of prior
analyst consensus estimates. The company beat analyst expectations for the
third consecutive quarter.

## Churn
Customer churn increased slightly in Q3, attributed to a pricing change
introduced in July that affected the smallest customer tier.
""",
    ),
    "support_faq": (
        "support_faq.md",
        """# Support FAQ

## Resetting Your Password
Go to the login page and click "Forgot password." Enter your email address
and follow the reset link sent to your inbox. Reset links expire after 1 hour.

## Cancelling a Subscription
You can cancel your subscription at any time from Account Settings > Billing.
Cancelling during a free trial takes effect immediately with no charge.

## Payment Methods
We accept Visa, Mastercard, American Express, and PayPal. Bank transfers are
available for annual enterprise plans only.

## Refund Policy
Refunds are available within 14 days of purchase for annual plans and are
not available for monthly plans after the billing date has passed.

## Exporting Your Data
Before closing your account, export your data from Account Settings > Data
Export. Exports are available in CSV or JSON format.
""",
    ),
    "sourdough_recipe": (
        "sourdough_bread_recipe.md",
        """# Sourdough Bread Recipe

## Starter Maintenance
Keep your starter at room temperature, around 21-24°C (70-75°F), and feed it
once every 24 hours with equal parts flour and water by weight.

## Hydration
This recipe uses 75% hydration: 750g water for every 1000g of flour.

## Bulk Fermentation
Let the dough undergo bulk fermentation for 4-6 hours at room temperature,
performing a series of stretch-and-folds every 30 minutes for the first 2 hours.

## Baking
Preheat the oven to 250°C (482°F) with a Dutch oven inside. Bake covered for
20 minutes, then uncovered at 230°C (446°F) for another 20-25 minutes.
""",
    ),
    "incident_runbook": (
        "incident_response_runbook.md",
        """# Incident Response Runbook

## Severity and Response Time SLAs
Critical (Sev1) incidents require acknowledgment within 5 minutes and an
initial response within 15 minutes. High (Sev2) incidents require response
within 1 hour.

## First Steps on Detecting an Outage
1. Acknowledge the page. 2. Open an incident channel. 3. Assess customer
impact. 4. Escalate to the on-call lead if impact is customer-facing.

## On-Call Rotation
The on-call rotation is assigned weekly on a round-robin basis across the
platform engineering team, managed through the on-call scheduling tool.

## Escalation
If the primary on-call engineer does not acknowledge within 15 minutes, the
page automatically escalates to the secondary on-call, then to the
engineering manager.

## Postmortems
Every Sev1 or Sev2 incident requires a postmortem within 5 business days,
covering: timeline, root cause, impact, and action items.
""",
    ),
    "drone_manual": (
        "drone_operation_manual.md",
        """# Drone Operation Manual

## Specifications
Maximum operating altitude is 120 meters (400 feet) above ground level, in
line with common aviation regulations. Maximum safe wind speed for operation
is 29 km/h (18 mph).

## Battery
Full battery charging takes approximately 90 minutes using the included
charger. Flight time per charge is approximately 30 minutes.

## Pre-Flight Safety Checklist
Before first flight: verify propellers are securely attached, calibrate the
compass away from metal objects and electronics, and confirm GPS lock.

## Compass Calibration
To calibrate the compass, enter calibration mode from the app, then rotate
the drone 360 degrees horizontally, then 360 degrees vertically, following
the on-screen prompts.
""",
    ),
    "drug_leaflet": (
        "medication_patient_leaflet.md",
        """# Patient Information Leaflet

## Dosage
The recommended adult dosage is 500mg taken orally every 6 hours as needed,
not to exceed 4 doses (2000mg) in 24 hours.

## Side Effects
Common side effects include mild nausea, dizziness, and drowsiness. Seek
immediate medical attention for signs of allergic reaction such as swelling
or difficulty breathing.

## Contraindications
Do not take this medication if pregnant or breastfeeding without consulting
a physician. Not recommended for patients with severe liver impairment.

## Interactions
Avoid alcohol while taking this medication, as it may increase drowsiness
and risk of liver toxicity.
""",
    ),
}


def main() -> int:
    settings = reload_settings()
    init_db()
    engine = get_engine()
    vector_store = VectorStore(settings)
    embedding_service = EmbeddingService(settings)

    with Session(engine) as session:
        project = session.exec(
            select(Project).where(Project.name == EVAL_PROJECT_NAME)
        ).first()
        if project is None:
            project = Project(
                name=EVAL_PROJECT_NAME,
                api_key=f"scrutinize_sk_eval_{uuid4().hex}",
                client_key=f"scrutinize_pk_eval_{uuid4().hex}",
            )
            session.add(project)
            session.commit()
            session.refresh(project)
            print(f"Created eval project {project.id}")
        else:
            print(f"Reusing eval project {project.id}")

        existing_files = session.exec(
            select(File).where(File.project_id == project.id)
        ).all()
        for file_record in existing_files:
            vector_store.delete_by_file_id(file_record.id)
            for segment in session.exec(
                select(Segment).where(Segment.file_id == file_record.id)
            ).all():
                session.delete(segment)
            session.delete(file_record)
        session.commit()
        if existing_files:
            print(f"Cleared {len(existing_files)} existing eval file(s)")

        orchestrator = JobOrchestrator(session)

        for doc_id, (filename, body) in FIXTURE_DOCS.items():
            file_record = orchestrator.create_file(
                filename=filename,
                modality=FileModality.TEXT,
                storage_path=f"eval-fixture://{doc_id}",
                size_bytes=len(body.encode("utf-8")),
                project_id=project.id,
            )

            chunks = chunk_text(
                body,
                chunk_size=settings.text_chunk_size,
                overlap=settings.text_chunk_overlap,
            )
            vectors = embedding_service.embed_texts(chunks)

            vector_segments: list[VectorSegment] = []
            for chunk, vector in zip(chunks, vectors, strict=True):
                segment_id = uuid4()
                orchestrator.create_segment(
                    file_id=file_record.id,
                    modality=FileModality.TEXT,
                    content=chunk,
                    segment_id=segment_id,
                    project_id=project.id,
                )
                vector_segments.append(
                    VectorSegment(
                        id=segment_id,
                        vector=vector,
                        file_id=file_record.id,
                        project_id=project.id,
                        modality=FileModality.TEXT.value,
                        content=chunk,
                        source_path=file_record.storage_path,
                        title=file_record.filename,
                    )
                )

            vector_store.upsert_segments(vector_segments)
            orchestrator.mark_file_status(file_record.id, FileStatus.INDEXED)
            print(f"Seeded {doc_id}: {len(vector_segments)} segment(s)")

        print(f"\nEval project id (for tests/evals config): {project.id}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
