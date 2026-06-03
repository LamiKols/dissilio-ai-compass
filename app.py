import os
import json
from datetime import datetime
from statistics import mean

from flask import Flask, request, redirect, url_for, render_template_string
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# New database file for Version 2.1 to avoid old schema conflicts.
if os.environ.get("USE_DATABASE_URL") == "true":
    database_uri = os.environ.get("DATABASE_URL", "sqlite:///dissilio_v21.db")
else:
    database_uri = "sqlite:///dissilio_v21.db"

app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

APP_NAME = "Dissilio AI & Automation Diagnostic"
PAID_PRICE = "£79"
CONSULTANCY_PRICE = "£1,500"


# ----------------------------
# Database Models
# ----------------------------

class Organisation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False)
    contact_name = db.Column(db.String(120), nullable=False)
    contact_email = db.Column(db.String(180), nullable=False)
    sector = db.Column(db.String(120), nullable=False)
    size = db.Column(db.String(80), nullable=False)
    country = db.Column(db.String(80), nullable=False, default="United Kingdom")
    biggest_pressure = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assessments = db.relationship("Assessment", backref="organisation", lazy=True)


class Assessment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey("organisation.id"), nullable=False)
    status = db.Column(db.String(40), default="draft")
    tier = db.Column(db.String(40), default="free")
    responses_json = db.Column(db.Text, nullable=True)
    scores_json = db.Column(db.Text, nullable=True)
    recommendations_json = db.Column(db.Text, nullable=True)
    risks_json = db.Column(db.Text, nullable=True)
    opportunities_json = db.Column(db.Text, nullable=True)
    is_paid = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)


# ----------------------------
# Question Bank
# ----------------------------

def make_options(a, b, c, d, e):
    return [
        {"score": 0, "label": a},
        {"score": 2.5, "label": b},
        {"score": 5, "label": c},
        {"score": 7.5, "label": d},
        {"score": 10, "label": e},
    ]


QUESTIONS = [
    {
        "id": "q1_strategy_clarity",
        "section": "1. AI & Automation Strategy",
        "question": "How clearly has your organisation defined why it wants to use AI or automation?",
        "options": make_options(
            "We have not discussed AI or automation properly",
            "We are interested but have no clear reason yet",
            "We have some broad ideas but no agreed priorities",
            "We have identified priority areas where AI or automation may help",
            "We have clear objectives, owners, and expected business outcomes",
        ),
        "score_map": {"ai": "direct", "business_value": "direct", "governance": "direct", "risk": "inverse"},
        "tools": ["AI strategy canvas", "Opportunity register", "Business case template"],
    },
    {
        "id": "q2_leadership_support",
        "section": "1. AI & Automation Strategy",
        "question": "How strongly is leadership supporting AI and automation improvement?",
        "options": make_options(
            "Leadership has not engaged with AI or automation",
            "A few leaders are curious but no one owns it",
            "Leadership is supportive but not actively driving it",
            "A senior person is sponsoring early exploration",
            "Leadership actively owns, funds, and governs AI/automation activity",
        ),
        "score_map": {"business_value": "direct", "governance": "direct", "risk": "inverse"},
        "tools": ["Leadership workshop", "AI steering group", "Roadmap template"],
    },
    {
        "id": "q3_ai_vs_automation",
        "section": "1. AI & Automation Strategy",
        "question": "How clearly does your organisation distinguish between automation and AI?",
        "options": make_options(
            "We treat automation and AI as the same thing",
            "We have limited understanding of the difference",
            "Some people understand the difference, but not consistently",
            "We usually understand when automation or AI is appropriate",
            "We clearly distinguish automation, AI assistance, and AI agents",
        ),
        "score_map": {"ai": "direct", "governance": "direct", "risk": "inverse"},
        "tools": ["AI vs automation decision guide", "Staff awareness guide"],
    },
    {
        "id": "q4_idea_capture",
        "section": "1. AI & Automation Strategy",
        "question": "How are AI or automation ideas currently identified?",
        "options": make_options(
            "Ideas are not captured",
            "Ideas are raised informally but not tracked",
            "Some ideas are captured but not assessed consistently",
            "Ideas are reviewed against business need and feasibility",
            "Ideas are captured, scored, prioritised, and linked to business outcomes",
        ),
        "score_map": {"process": "direct", "business_value": "direct", "governance": "direct"},
        "tools": ["Opportunity register", "Prioritisation matrix", "ROI scoring"],
    },
    {
        "id": "q5_problem_confidence",
        "section": "1. AI & Automation Strategy",
        "question": "How confident are you that AI or automation investment would solve real business problems?",
        "options": make_options(
            "We are not confident because the problems are unclear",
            "We believe there may be value but have not validated it",
            "We can see some likely benefits",
            "We have clear problem areas where improvement is needed",
            "We have validated problems, expected benefits, and success measures",
        ),
        "score_map": {"business_value": "direct", "ai": "direct"},
        "tools": ["Problem statement workshop", "Benefits map", "Pilot business case"],
    },

    {
        "id": "q6_manual_work",
        "section": "2. Manual Work & Automation Opportunity",
        "question": "How much repetitive manual work exists in your organisation?",
        "options": make_options(
            "Very little repetitive manual work",
            "A few small admin tasks are repetitive",
            "Several recurring manual tasks exist",
            "Many recurring tasks exist across teams",
            "Manual work is a major operational burden",
        ),
        "score_map": {"automation": "direct", "business_value": "direct"},
        "tools": ["Power Automate", "Zapier", "Make", "n8n", "Airtable"],
    },
    {
        "id": "q7_copy_between_systems",
        "section": "2. Manual Work & Automation Opportunity",
        "question": "How often do staff copy information between systems, spreadsheets, emails, or documents?",
        "options": make_options(
            "Almost never",
            "Occasionally",
            "Weekly in some teams",
            "Daily in several teams",
            "Constantly across the organisation",
        ),
        "score_map": {"automation": "direct", "systems": "inverse", "risk": "direct", "business_value": "direct"},
        "tools": ["Power Automate", "Make", "Zapier", "n8n", "API integration"],
    },
    {
        "id": "q8_reporting_workload",
        "section": "2. Manual Work & Automation Opportunity",
        "question": "How much time is spent preparing routine reports?",
        "options": make_options(
            "Very little time",
            "Some time, but not a major issue",
            "Regular time is spent preparing reports",
            "Reporting is a major recurring workload",
            "Reporting consumes significant staff or management time",
        ),
        "score_map": {"automation": "direct", "business_value": "direct", "ai": "direct"},
        "tools": ["Power BI", "Looker Studio", "Tableau", "Excel automation", "AI report summariser"],
    },
    {
        "id": "q9_manual_followups",
        "section": "2. Manual Work & Automation Opportunity",
        "question": "How often are approvals, reminders, or follow-ups handled manually?",
        "options": make_options(
            "Rarely or never",
            "Occasionally",
            "Regularly in some processes",
            "Frequently across multiple teams",
            "Manual chasing and follow-up is a major issue",
        ),
        "score_map": {"automation": "direct", "process": "inverse", "business_value": "direct"},
        "tools": ["Power Automate", "Monday.com", "ClickUp", "Asana", "Airtable"],
    },
    {
        "id": "q10_repeated_questions",
        "section": "2. Manual Work & Automation Opportunity",
        "question": "How often do staff answer the same questions repeatedly?",
        "options": make_options(
            "Rarely",
            "Occasionally",
            "Frequently in some teams",
            "Frequently across several teams",
            "Repeated questions create major workload",
        ),
        "score_map": {"automation": "direct", "ai": "direct", "business_value": "direct"},
        "tools": ["Knowledge base", "SharePoint", "Notion", "Confluence", "Custom AI assistant"],
    },
    {
        "id": "q11_document_creation",
        "section": "2. Manual Work & Automation Opportunity",
        "question": "How often do staff manually create documents, letters, emails, forms, or summaries?",
        "options": make_options(
            "Rarely",
            "Occasionally",
            "Regularly in some roles",
            "Frequently across teams",
            "Document creation is a major workload",
        ),
        "score_map": {"automation": "direct", "ai": "direct", "business_value": "direct", "risk": "direct"},
        "tools": ["Microsoft Copilot", "Google Gemini", "ChatGPT Enterprise", "Template automation"],
    },
    {
        "id": "q12_decision_rules",
        "section": "2. Manual Work & Automation Opportunity",
        "question": "How clear are the rules behind routine decisions?",
        "options": make_options(
            "Decisions are unclear and inconsistent",
            "Decisions depend heavily on individual judgement",
            "Some rules exist but there are many exceptions",
            "Most routine decisions follow clear rules",
            "Decisions are highly rule-based and well documented",
        ),
        "score_map": {"automation": "direct", "process": "direct", "ai": "direct", "risk": "inverse"},
        "tools": ["Decision matrix", "Workflow rules", "Approval thresholds"],
    },

    {
        "id": "q13_process_documentation",
        "section": "3. Process Readiness",
        "question": "How well documented are your key business processes?",
        "options": make_options(
            "Not documented",
            "Mostly known by individuals",
            "Partially documented",
            "Mostly documented",
            "Fully documented and regularly reviewed",
        ),
        "score_map": {"process": "direct", "automation": "direct", "risk": "inverse"},
        "tools": ["Process maps", "SOP templates", "Workflow design"],
    },
    {
        "id": "q14_process_owners",
        "section": "3. Process Readiness",
        "question": "Are process owners clearly identified?",
        "options": make_options(
            "No clear process owners",
            "Ownership is informal",
            "Some processes have owners",
            "Most key processes have owners",
            "All key processes have clear owners and accountability",
        ),
        "score_map": {"process": "direct", "governance": "direct", "risk": "inverse"},
        "tools": ["RACI", "Process ownership model"],
    },
    {
        "id": "q15_variation",
        "section": "3. Process Readiness",
        "question": "How often do different teams complete the same task in different ways?",
        "options": make_options(
            "Almost always done differently",
            "Often done differently",
            "Some variation exists",
            "Mostly standardised",
            "Highly standardised across teams",
        ),
        "score_map": {"process": "direct", "automation": "direct", "risk": "inverse"},
        "tools": ["Process standardisation", "SOP review"],
    },
    {
        "id": "q16_handoffs",
        "section": "3. Process Readiness",
        "question": "How clear are handoffs between teams or roles?",
        "options": make_options(
            "Handoffs are unclear and often missed",
            "Handoffs depend on individuals",
            "Some handoffs are defined",
            "Most handoffs are clear",
            "Handoffs are clearly defined, tracked, and measured",
        ),
        "score_map": {"process": "direct", "automation": "direct", "risk": "inverse"},
        "tools": ["Workflow automation", "Case management", "Task tracking"],
    },
    {
        "id": "q17_exceptions",
        "section": "3. Process Readiness",
        "question": "How well are exceptions and edge cases understood?",
        "options": make_options(
            "Exceptions are not understood",
            "Exceptions are handled informally",
            "Common exceptions are known",
            "Most exceptions are documented",
            "Exceptions are documented with clear handling rules",
        ),
        "score_map": {"process": "direct", "governance": "direct", "risk": "inverse"},
        "tools": ["Exception log", "Process controls", "Escalation rules"],
    },

    {
        "id": "q18_data_reliability",
        "section": "4. Data Readiness",
        "question": "How reliable is the data used for reporting or decision-making?",
        "options": make_options(
            "Poor or unreliable",
            "Limited quality",
            "Usable but inconsistent",
            "Mostly reliable",
            "Structured, reliable, and trusted",
        ),
        "score_map": {"data": "direct", "ai": "direct", "risk": "inverse"},
        "tools": ["Data quality review", "Power BI", "Data cleanup"],
    },
    {
        "id": "q19_data_location",
        "section": "4. Data Readiness",
        "question": "Where is important business data mainly stored?",
        "options": make_options(
            "Mostly in people’s heads or informal notes",
            "Mostly in emails and scattered documents",
            "Mostly in spreadsheets",
            "Mostly in structured systems with some spreadsheets",
            "Mostly in structured systems with clear ownership",
        ),
        "score_map": {"data": "direct", "systems": "direct", "risk": "inverse"},
        "tools": ["Data catalogue", "Document management", "CRM/ERP review"],
    },
    {
        "id": "q20_data_owners",
        "section": "4. Data Readiness",
        "question": "Are data owners clearly identified?",
        "options": make_options(
            "No data owners are identified",
            "Ownership is informal",
            "Some important data has owners",
            "Most important data has owners",
            "Data ownership is clear and actively managed",
        ),
        "score_map": {"data": "direct", "governance": "direct", "risk": "inverse"},
        "tools": ["Data ownership model", "Data governance checklist"],
    },
    {
        "id": "q21_data_access",
        "section": "4. Data Readiness",
        "question": "Can staff access the data they need without workarounds?",
        "options": make_options(
            "Staff frequently cannot access needed data",
            "Staff rely heavily on workarounds",
            "Access is mixed",
            "Most staff can access what they need",
            "Access is reliable, controlled, and role-appropriate",
        ),
        "score_map": {"data": "direct", "systems": "direct", "automation": "direct", "risk": "inverse"},
        "tools": ["Role-based dashboards", "Access review", "Data portal"],
    },
    {
        "id": "q22_sensitive_data",
        "section": "4. Data Readiness",
        "question": "Is sensitive or personal data clearly identified and controlled?",
        "options": make_options(
            "We do not clearly identify sensitive or personal data",
            "We identify some sensitive data informally",
            "Some sensitive data is classified or controlled",
            "Most sensitive data is identified and controlled",
            "Sensitive data is clearly classified, controlled, and reviewed",
        ),
        "score_map": {"data": "direct", "governance": "direct", "risk": "inverse"},
        "tools": ["Data classification", "DPIA checklist", "Access control review"],
    },

    {
        "id": "q23_data_exports",
        "section": "5. Systems & Integration",
        "question": "Can your systems export data reliably?",
        "options": make_options(
            "No reliable export is available",
            "Data must be copied manually",
            "Basic exports are available",
            "Regular exports are available",
            "Reliable exports, APIs, or integrations are available",
        ),
        "score_map": {"systems": "direct", "automation": "direct", "risk": "inverse"},
        "tools": ["Power BI", "Looker Studio", "CSV automation", "API integration"],
    },
    {
        "id": "q24_system_integration",
        "section": "5. Systems & Integration",
        "question": "Do your systems integrate with each other?",
        "options": make_options(
            "Systems do not connect",
            "Systems connect only through manual workarounds",
            "Some limited integrations exist",
            "Most key systems can share data",
            "Systems are well integrated or integration-ready",
        ),
        "score_map": {"systems": "direct", "automation": "direct", "risk": "inverse"},
        "tools": ["Power Automate", "Zapier", "Make", "n8n", "Custom integration"],
    },
    {
        "id": "q25_spreadsheet_reliance",
        "section": "5. Systems & Integration",
        "question": "How much of your work relies on spreadsheets outside core systems?",
        "options": make_options(
            "Almost all important work happens in uncontrolled spreadsheets",
            "Heavy reliance on spreadsheets",
            "Moderate spreadsheet reliance",
            "Limited spreadsheet reliance",
            "Spreadsheets are controlled or not central to operations",
        ),
        "score_map": {"systems": "direct", "risk": "inverse", "automation": "inverse"},
        "tools": ["Airtable", "Power Apps", "Retool", "Internal tools", "Dashboard automation"],
    },
    {
        "id": "q26_digital_tools",
        "section": "5. Systems & Integration",
        "question": "Which digital workplace tools are actively used?",
        "options": make_options(
            "Few shared digital tools are used",
            "Email and documents only",
            "Microsoft 365 or Google Workspace is used",
            "Collaboration tools, shared storage, and task tools are used",
            "Digital workplace tools are mature and actively managed",
        ),
        "score_map": {"systems": "direct", "ai": "direct", "automation": "direct"},
        "tools": ["Microsoft 365", "Google Workspace", "Teams", "SharePoint", "Copilot Studio"],
    },

    {
        "id": "q27_ai_usage_known",
        "section": "6. Current AI Usage / Shadow AI",
        "question": "Do you know whether staff use tools such as ChatGPT, Copilot, Gemini, Claude, or similar?",
        "options": make_options(
            "We do not know",
            "We suspect some staff use them",
            "We know some usage exists",
            "Usage is known and partially guided",
            "Usage is known, approved, and monitored",
        ),
        "score_map": {"governance": "direct", "risk": "inverse", "ai": "direct"},
        "tools": ["AI usage register", "AI policy", "Copilot", "ChatGPT Enterprise"],
    },
    {
        "id": "q28_ai_use_cases",
        "section": "6. Current AI Usage / Shadow AI",
        "question": "What do staff mainly use AI tools for today?",
        "options": make_options(
            "We do not know what staff use AI for",
            "Personal experimentation only",
            "Drafting, summarising, or research",
            "Work support with some review",
            "Approved work use cases with clear review controls",
        ),
        "score_map": {"ai": "direct", "governance": "direct", "risk": "inverse"},
        "tools": ["AI usage register", "AI use case catalogue", "Staff guidance"],
    },
    {
        "id": "q29_ai_allowed",
        "section": "6. Current AI Usage / Shadow AI",
        "question": "Are staff allowed to use AI tools for work?",
        "options": make_options(
            "There is no guidance",
            "It is unclear",
            "Informally allowed in some cases",
            "Allowed with basic guidance",
            "Allowed under clear rules and approved use cases",
        ),
        "score_map": {"governance": "direct", "risk": "inverse"},
        "tools": ["AI acceptable use policy", "Approved tool list"],
    },
    {
        "id": "q30_ai_output_review",
        "section": "6. Current AI Usage / Shadow AI",
        "question": "Are AI outputs reviewed before being used externally or in important decisions?",
        "options": make_options(
            "No review is required",
            "Review depends on the individual",
            "Some outputs are reviewed",
            "Most important outputs are reviewed",
            "Review is required for external, sensitive, or decision-support outputs",
        ),
        "score_map": {"governance": "direct", "risk": "inverse"},
        "tools": ["Human review checklist", "AI quality controls"],
    },
    {
        "id": "q31_ai_error_process",
        "section": "6. Current AI Usage / Shadow AI",
        "question": "Are AI-generated errors, poor outputs, or concerns captured and corrected?",
        "options": make_options(
            "No process exists",
            "Issues are handled informally",
            "Some issues are corrected but not tracked",
            "Issues are usually reviewed and corrected",
            "Issues are tracked, reviewed, corrected, and used to improve controls",
        ),
        "score_map": {"governance": "direct", "risk": "inverse"},
        "tools": ["AI issue log", "Correction process", "Escalation route"],
    },

    {
        "id": "q32_ai_policy",
        "section": "7. Governance, Risk & Privacy",
        "question": "Do you have an AI acceptable use policy?",
        "options": make_options(
            "No policy exists",
            "Informal guidance exists",
            "Draft or partial policy exists",
            "Policy exists but needs improvement",
            "Policy exists, is communicated, and is reviewed",
        ),
        "score_map": {"governance": "direct", "risk": "inverse"},
        "tools": ["AI policy pack", "Governance checklist", "Staff guidance"],
    },
    {
        "id": "q33_prohibited_data",
        "section": "7. Governance, Risk & Privacy",
        "question": "Do staff know what information must not be entered into public AI tools?",
        "options": make_options(
            "No, this has not been explained",
            "Some staff may know informally",
            "Basic guidance has been shared",
            "Most staff understand the rules",
            "Staff are trained and rules are enforced",
        ),
        "score_map": {"governance": "direct", "risk": "inverse"},
        "tools": ["AI data handling guide", "Staff training", "Privacy checklist"],
    },
    {
        "id": "q34_tool_risk_review",
        "section": "7. Governance, Risk & Privacy",
        "question": "Are AI-related risks reviewed before new tools are adopted?",
        "options": make_options(
            "No review happens",
            "Review is informal",
            "Some risk checks happen",
            "Most new tools are reviewed",
            "AI tools are reviewed for privacy, security, value, and operational risk before adoption",
        ),
        "score_map": {"governance": "direct", "risk": "inverse"},
        "tools": ["Tool approval checklist", "DPIA checklist", "Vendor review"],
    },
    {
        "id": "q35_service_user_impact",
        "section": "7. Governance, Risk & Privacy",
        "question": "Are customers, clients, learners, patients, or service users affected by any AI-supported process?",
        "options": make_options(
            "We do not know",
            "Possibly, but not clearly assessed",
            "Yes, in low-impact ways",
            "Yes, in some important service processes",
            "Yes, in high-impact or sensitive processes",
        ),
        "score_map": {"ai": "direct", "risk": "direct"},
        "tools": ["Impact assessment", "Human oversight plan", "Transparency notice"],
    },
    {
        "id": "q36_human_control",
        "section": "7. Governance, Risk & Privacy",
        "question": "Are high-impact decisions kept under human control?",
        "options": make_options(
            "No clear human control exists",
            "Human control is informal",
            "Human review exists in some cases",
            "Most high-impact decisions are human-controlled",
            "High-impact decisions require clear human accountability and review",
        ),
        "score_map": {"governance": "direct", "risk": "inverse"},
        "tools": ["Human review framework", "Decision accountability matrix"],
    },
    {
        "id": "q37_correction_process",
        "section": "7. Governance, Risk & Privacy",
        "question": "Is there a process for correcting AI-generated errors or challenging AI-supported outputs?",
        "options": make_options(
            "No process exists",
            "Issues are handled case by case",
            "Some correction route exists",
            "Most issues can be escalated and corrected",
            "Clear correction, escalation, and accountability process exists",
        ),
        "score_map": {"governance": "direct", "risk": "inverse"},
        "tools": ["Correction process", "Appeals process", "Issue log"],
    },

    {
        "id": "q38_staff_confidence",
        "section": "8. People, Adoption & Business Value",
        "question": "How confident are staff in using AI or automation tools responsibly?",
        "options": make_options(
            "Not confident",
            "Low confidence",
            "Mixed confidence",
            "Good confidence in some teams",
            "Strong confidence supported by training and guidance",
        ),
        "score_map": {"staff": "direct", "governance": "direct", "risk": "inverse"},
        "tools": ["AI training", "Change readiness", "Staff guidance"],
    },
    {
        "id": "q39_training",
        "section": "8. People, Adoption & Business Value",
        "question": "Has any practical AI or automation training been provided?",
        "options": make_options(
            "No training has been provided",
            "Informal tips only",
            "Some basic awareness training",
            "Practical training for some teams",
            "Role-specific training with guidance and controls",
        ),
        "score_map": {"staff": "direct", "governance": "direct", "risk": "inverse"},
        "tools": ["Role-based AI training", "Prompting guide", "Safe-use training"],
    },
    {
        "id": "q40_investment_appetite",
        "section": "8. People, Adoption & Business Value",
        "question": "If a clear business case existed, how likely is leadership to invest in AI or automation?",
        "options": make_options(
            "Very unlikely",
            "Unlikely without strong pressure",
            "Open to discussion",
            "Likely if benefits are clear",
            "Very likely if value, risk, and cost are clearly presented",
        ),
        "score_map": {"business_value": "direct"},
        "tools": ["Business case", "ROI estimate", "Pilot roadmap"],
    },
]


SCORE_LABELS = {
    "automation": "Automation Opportunity",
    "ai": "AI Suitability",
    "process": "Process Readiness",
    "data": "Data Readiness",
    "systems": "Systems Readiness",
    "governance": "Governance Maturity",
    "staff": "Staff Readiness",
    "business_value": "Business Value Potential",
    "risk": "Risk Exposure",
}


# ----------------------------
# Scoring Logic
# ----------------------------

def score_to_band(score):
    if score <= 20:
        return "Critical gap"
    if score <= 40:
        return "Low maturity"
    if score <= 60:
        return "Developing"
    if score <= 80:
        return "Ready to scale"
    return "Advanced"


def risk_band(score):
    if score <= 20:
        return "Low risk"
    if score <= 40:
        return "Moderate risk"
    if score <= 60:
        return "Elevated risk"
    if score <= 80:
        return "High risk"
    return "Critical risk"


def safe_avg(values):
    return round(mean(values)) if values else 0


def score_value(raw_score, mode):
    score = float(raw_score)
    if mode == "direct":
        return score * 10
    if mode == "inverse":
        return (10 - score) * 10
    return score * 10


def get_question(qid):
    return next((question for question in QUESTIONS if question["id"] == qid), None)


def get_selected_option(question, score):
    for option in question["options"]:
        if float(option["score"]) == float(score):
            return option
    return question["options"][0]


def calculate_scores(responses):
    score_buckets = {key: [] for key in SCORE_LABELS.keys()}
    section_buckets = {}

    for question in QUESTIONS:
        raw_score = float(responses.get(question["id"], 0))
        section_buckets.setdefault(question["section"], []).append(raw_score * 10)

        for score_name, mode in question["score_map"].items():
            if score_name in score_buckets:
                score_buckets[score_name].append(score_value(raw_score, mode))

    scores = {
        "section_scores": {
            section: safe_avg(values)
            for section, values in section_buckets.items()
        },
        "automation_score": safe_avg(score_buckets["automation"]),
        "ai_score": safe_avg(score_buckets["ai"]),
        "process_score": safe_avg(score_buckets["process"]),
        "data_score": safe_avg(score_buckets["data"]),
        "systems_score": safe_avg(score_buckets["systems"]),
        "governance_score": safe_avg(score_buckets["governance"]),
        "staff_score": safe_avg(score_buckets["staff"]),
        "business_value_score": safe_avg(score_buckets["business_value"]),
        "risk_score": safe_avg(score_buckets["risk"]),
    }

    readiness_inputs = [
        scores["automation_score"],
        scores["ai_score"],
        scores["process_score"],
        scores["data_score"],
        scores["systems_score"],
        scores["governance_score"],
        scores["staff_score"],
        scores["business_value_score"],
        100 - scores["risk_score"],
    ]
    scores["overall_score"] = safe_avg(readiness_inputs)

    return scores


def question_interpretation(question, selected_score):
    low = selected_score <= 2.5
    medium = selected_score == 5
    high = selected_score >= 7.5

    section = question["section"]

    if "Manual Work" in section:
        if high:
            meaning = "This response suggests a strong practical opportunity to reduce manual effort and improve consistency."
            automation = "Automation is likely to be relevant. Start with repeatable tasks, approvals, reporting, reminders, or handoffs."
            ai = "AI may add value if the work involves documents, emails, summarisation, classification, or knowledge retrieval."
            risk = "The main risks are errors, delay, duplication, staff workload, and uncontrolled workarounds."
            strategy = "Create an automation opportunity register and select one high-volume, low-risk pilot."
        elif medium:
            meaning = "This response suggests a moderate opportunity that should be validated before investment."
            automation = "A small automation pilot may be useful if the process is repetitive and rule-based."
            ai = "AI may help in targeted areas, but not every problem requires AI."
            risk = "The main risk is overbuilding before the problem is properly sized."
            strategy = "Confirm frequency, time spent, process owner, and expected benefit before choosing tools."
        else:
            meaning = "This response suggests limited immediate automation pressure."
            automation = "Automation may not be the first priority unless specific pain points are identified."
            ai = "AI should be used only where there is a clear use case."
            risk = "The main risk is investing in tools without a strong operational need."
            strategy = "Focus first on identifying clearer business problems and quick wins."
    elif "Process" in section:
        if high:
            meaning = "This response suggests the organisation has a reasonable process foundation for automation."
            automation = "Automation is more feasible when owners, handoffs, rules, and exceptions are understood."
            ai = "AI can support process insight, summaries, and knowledge work, but should follow process clarity."
            risk = "Risk is lower, but change management and exception handling still matter."
            strategy = "Select a process with clear ownership and measurable benefit for the first pilot."
        elif medium:
            meaning = "This response suggests partial process readiness."
            automation = "Some automation may be possible, but process mapping is needed first."
            ai = "AI may help document and analyse processes, but cannot replace ownership and controls."
            risk = "Unclear processes can lead to failed automation and user resistance."
            strategy = "Map the process, confirm owners, define exceptions, and then design the solution."
        else:
            meaning = "This response suggests weak process readiness."
            automation = "Automation should not be rushed because the underlying workflow may not be stable."
            ai = "AI may create confusion if used before the process is understood."
            risk = "High risk of automating a broken or inconsistent process."
            strategy = "Start with process discovery and standardisation before implementation."
    elif "Data" in section:
        if high:
            meaning = "This response suggests a stronger data foundation."
            automation = "Data-led automation, reporting, and dashboards may be feasible."
            ai = "AI can be considered for analysis, summarisation, and knowledge retrieval using approved data sources."
            risk = "Risk is lower where data is controlled, owned, and reliable."
            strategy = "Identify priority datasets that can support reporting automation or AI use cases."
        elif medium:
            meaning = "This response suggests data is usable but needs improvement."
            automation = "Automation may work for controlled datasets but may fail where data is inconsistent."
            ai = "AI outputs may be unreliable if the input data is incomplete or poorly structured."
            risk = "Data quality and ownership issues could reduce trust in outputs."
            strategy = "Clean priority data and assign data owners before advanced AI adoption."
        else:
            meaning = "This response suggests weak data readiness."
            automation = "Automation may simply move poor data faster unless cleanup happens first."
            ai = "AI should not be used for important analysis or decision support until data quality improves."
            risk = "High risk of inaccurate outputs, privacy issues, and poor decision-making."
            strategy = "Start with data ownership, classification, cleanup, and access controls."
    elif "Systems" in section:
        if high:
            meaning = "This response suggests the technology environment may support practical automation."
            automation = "Workflow automation, integration, and reporting automation may be feasible."
            ai = "AI can be layered onto existing systems where data and permissions are controlled."
            risk = "Risk is lower if systems are actively managed and access is controlled."
            strategy = "Start with the tools already in use before introducing new platforms."
        elif medium:
            meaning = "This response suggests mixed system readiness."
            automation = "Some automation may be possible, but integration gaps may remain."
            ai = "AI may be useful in isolated use cases, but data movement and access need review."
            risk = "Workarounds and spreadsheets may create operational risk."
            strategy = "Review system handoffs and identify one integration or reporting improvement."
        else:
            meaning = "This response suggests weak technical readiness."
            automation = "Automation may require basic data capture, exports, or workflow setup first."
            ai = "AI should not be the first step if the system foundations are weak."
            risk = "Disconnected systems increase duplication, errors, and manual workload."
            strategy = "Prioritise simple digital foundations before AI-led transformation."
    elif "AI Usage" in section or "Governance" in section:
        if high:
            meaning = "This response suggests stronger visibility and control over AI use."
            automation = "Automation can be scaled more safely when governance is clear."
            ai = "AI use cases can be formalised and expanded where appropriate controls exist."
            risk = "Risk is lower but still requires monitoring, review, and issue handling."
            strategy = "Move from informal guidance to a controlled AI use-case register and review process."
        elif medium:
            meaning = "This response suggests partial governance maturity."
            automation = "Automation can proceed in low-risk areas, but ownership and controls should be strengthened."
            ai = "AI use should be limited to approved, reviewed, low-risk use cases."
            risk = "Risk exists around shadow AI, data handling, accuracy, and accountability."
            strategy = "Create clear AI usage rules, human review guidance, and an approved tool list."
        else:
            meaning = "This response suggests weak AI governance or limited visibility."
            automation = "Automation should focus on low-risk internal processes first."
            ai = "AI adoption should not be scaled until basic safe-use controls are in place."
            risk = "High risk of shadow AI, confidential data exposure, poor outputs, and weak accountability."
            strategy = "Introduce an AI acceptable use policy, staff guidance, and tool approval checklist."
    else:
        if high:
            meaning = "This response suggests stronger readiness and adoption potential."
            automation = "Automation may be adopted successfully if linked to clear business outcomes."
            ai = "AI use cases can be explored with appropriate training and governance."
            risk = "Risk is manageable if controls, training, and human review are maintained."
            strategy = "Build a business case for one practical AI or automation pilot."
        elif medium:
            meaning = "This response suggests moderate readiness."
            automation = "Small pilots may be suitable where the process is clear and benefits are measurable."
            ai = "AI should be introduced gradually with practical guidance."
            risk = "Risk exists if staff are not trained or leadership appetite is unclear."
            strategy = "Use a low-cost pilot to prove value and build confidence."
        else:
            meaning = "This response suggests low readiness or adoption appetite."
            automation = "Automation should start with small internal improvements only."
            ai = "AI should be introduced through awareness, training, and low-risk examples."
            risk = "Low confidence and weak training can lead to poor adoption or misuse."
            strategy = "Begin with awareness, training, and a simple foundation review."

    return {
        "meaning": meaning,
        "automation": automation,
        "ai": ai,
        "risk": risk,
        "strategy": strategy,
    }


def generate_question_diagnostics(responses):
    diagnostics = []

    for question in QUESTIONS:
        selected_score = float(responses.get(question["id"], 0))
        selected_option = get_selected_option(question, selected_score)
        interpretation = question_interpretation(question, selected_score)

        diagnostics.append({
            "section": question["section"],
            "question": question["question"],
            "answer": selected_option["label"],
            "score": selected_score,
            "meaning": interpretation["meaning"],
            "automation": interpretation["automation"],
            "ai": interpretation["ai"],
            "risk": interpretation["risk"],
            "strategy": interpretation["strategy"],
            "tools": question["tools"],
        })

    return diagnostics


def generate_recommendations(scores):
    recommendations = []

    if scores["automation_score"] >= 65:
        recommendations.append({
            "title": "Prioritise automation opportunity discovery",
            "priority": "High",
            "text": "There appears to be strong potential to reduce manual work. Build an opportunity register and select one low-risk, high-volume process for a pilot."
        })

    if scores["ai_score"] >= 60:
        recommendations.append({
            "title": "Explore AI-assisted work carefully",
            "priority": "Medium",
            "text": "AI may support drafting, summarising, knowledge retrieval, reporting commentary, and classification where controls and review are in place."
        })

    if scores["governance_score"] < 50 or scores["risk_score"] > 60:
        recommendations.append({
            "title": "Strengthen governance before scaling",
            "priority": "High",
            "text": "Introduce an AI acceptable use policy, approved tool list, sensitive-data rules, and human review guidance before wider AI adoption."
        })

    if scores["process_score"] < 50:
        recommendations.append({
            "title": "Map processes before automation",
            "priority": "High",
            "text": "Process clarity is not yet strong enough for reliable automation. Map owners, handoffs, rules, exceptions, and success measures first."
        })

    if scores["data_score"] < 50:
        recommendations.append({
            "title": "Improve data readiness",
            "priority": "High",
            "text": "Data quality, ownership, access, or classification may limit the success of AI and automation. Start with key datasets."
        })

    if scores["business_value_score"] >= 60:
        recommendations.append({
            "title": "Create a business case for a first pilot",
            "priority": "Medium",
            "text": "There appears to be enough value potential to justify a small pilot with clear success measures and cost/benefit assumptions."
        })

    if not recommendations:
        recommendations.append({
            "title": "Start with a foundation review",
            "priority": "Medium",
            "text": "Clarify objectives, current processes, data quality, AI usage, and practical first steps before investing in tools."
        })

    return recommendations[:6]


def generate_risks(scores):
    risks = []

    if scores["risk_score"] > 60:
        risks.append({
            "risk": "High AI and automation risk exposure",
            "cause": "Weak controls, unclear AI use, sensitive data exposure, or high-impact use cases may be present.",
            "severity": "High",
            "mitigation": "Introduce AI usage rules, tool approval, human review, data restrictions, and an issue escalation process."
        })

    if scores["governance_score"] < 50:
        risks.append({
            "risk": "Weak governance and accountability",
            "cause": "AI or automation activity may not have clear ownership, policy, or review controls.",
            "severity": "High",
            "mitigation": "Assign ownership, create an AI acceptable use policy, and define review responsibilities."
        })

    if scores["data_score"] < 50:
        risks.append({
            "risk": "Poor data quality affecting outputs",
            "cause": "Data may be unreliable, scattered, poorly owned, or difficult to access.",
            "severity": "Medium",
            "mitigation": "Identify key datasets, assign owners, clean priority data, and define access rules."
        })

    if scores["process_score"] < 50:
        risks.append({
            "risk": "Automation failure due to unclear processes",
            "cause": "Processes, handoffs, rules, or exceptions may not be sufficiently understood.",
            "severity": "Medium",
            "mitigation": "Map processes before automation and define rules, owners, handoffs, and exceptions."
        })

    if not risks:
        risks.append({
            "risk": "Scaling without monitoring",
            "cause": "Even mature organisations need monitoring as AI and automation use expands.",
            "severity": "Medium",
            "mitigation": "Track use cases, issues, performance, user feedback, and risk controls."
        })

    return risks


def generate_opportunities(scores):
    opportunities = []

    if scores["automation_score"] >= 60:
        opportunities.append({
            "area": "Workflow automation",
            "problem": "Repetitive manual work, approvals, reminders, handoffs, or follow-ups may be consuming staff time.",
            "automation": "Automate task routing, reminders, approvals, escalations, and status updates.",
            "ai": "Use AI only where the workflow involves drafting, summarising, classifying, or interpreting text.",
            "tools": "Power Automate, Zapier, Make, n8n, Airtable, Monday.com, ClickUp",
            "mvp": "Build one low-risk workflow automation pilot for a high-volume process."
        })

    if scores["business_value_score"] >= 55:
        opportunities.append({
            "area": "Reporting automation",
            "problem": "Routine reporting may be taking too much time or relying on manual preparation.",
            "automation": "Automate data extraction, dashboards, report packs, and scheduled updates.",
            "ai": "Use AI to generate commentary, executive summaries, trend explanations, and exception notes.",
            "tools": "Power BI, Looker Studio, Tableau, Excel automation, AI reporting assistant",
            "mvp": "Automate one recurring management report and add an AI-generated summary."
        })

    if scores["ai_score"] >= 60:
        opportunities.append({
            "area": "AI knowledge or document assistant",
            "problem": "Staff may spend time searching for information, answering repeated questions, or drafting documents.",
            "automation": "Centralise approved documents, FAQs, policies, templates, and guidance.",
            "ai": "Use AI to answer questions from approved sources, draft content, summarise documents, or classify information.",
            "tools": "Microsoft Copilot Studio, ChatGPT Enterprise, SharePoint, Notion AI, custom RAG assistant",
            "mvp": "Create a controlled assistant using approved internal documents."
        })

    if scores["systems_score"] < 50 and scores["automation_score"] >= 50:
        opportunities.append({
            "area": "System handoff and integration review",
            "problem": "Disconnected systems may be causing copy-paste work, duplication, and inconsistent reporting.",
            "automation": "Use integrations, form capture, or middleware-style workflows to reduce manual data movement.",
            "ai": "Use AI for extraction or classification only after reliable data movement is established.",
            "tools": "Power Automate, Make, Zapier, n8n, API integration, lightweight internal tool",
            "mvp": "Automate one data handoff between a form, spreadsheet, email, or system."
        })

    if not opportunities:
        opportunities.append({
            "area": "AI and automation foundation",
            "problem": "The organisation may not yet have enough clarity, process maturity, or data readiness to implement confidently.",
            "automation": "Start by mapping processes and identifying repeatable tasks.",
            "ai": "Use AI only for low-risk internal support until governance improves.",
            "tools": "Process maps, AI policy template, opportunity register, staff guidance",
            "mvp": "Create an AI and automation foundation pack before selecting tools."
        })

    return opportunities[:5]


def recommend_consultancy(scores):
    if scores["automation_score"] >= 65 and scores["process_score"] < 55:
        return {
            "name": "Process & Automation Discovery Audit",
            "price": CONSULTANCY_PRICE,
            "duration": "3 days",
            "reason": "There is strong automation potential, but process clarity needs to be validated before solution design.",
            "deliverables": "Process review, automation opportunity register, prioritised roadmap, and first MVP recommendation."
        }

    if scores["risk_score"] > 60 or scores["governance_score"] < 50:
        return {
            "name": "AI Governance & Safe Adoption Audit",
            "price": CONSULTANCY_PRICE,
            "duration": "3 days",
            "reason": "AI use or AI risk exposure appears to need stronger controls before scaling.",
            "deliverables": "AI usage review, acceptable-use guidance, risk register, governance checklist, and safe adoption roadmap."
        }

    if scores["business_value_score"] >= 60:
        return {
            "name": "AI & Automation Opportunity Audit",
            "price": CONSULTANCY_PRICE,
            "duration": "3 days",
            "reason": "The organisation appears to have enough value potential to justify a structured opportunity and business-case review.",
            "deliverables": "Opportunity register, 30/60/90-day roadmap, business case outline, and first solution design brief."
        }

    return {
        "name": "AI & Automation Foundation Review",
        "price": CONSULTANCY_PRICE,
        "duration": "3 days",
        "reason": "The organisation would benefit from clarifying objectives, risks, processes, and practical first steps.",
        "deliverables": "Readiness review, gap summary, practical action plan, and prioritised next-step recommendations."
    }


# ----------------------------
# Styling
# ----------------------------

BASE_CSS = """
<style>
:root {
  --bg: #f8f7f3;
  --panel: #ffffff;
  --panel-soft: #f1efe8;
  --text: #101828;
  --muted: #667085;
  --line: #e5e7eb;
  --navy: #111827;
  --gold: #bfa46f;
  --gold-dark: #9a8151;
  --green: #027a48;
  --red: #b42318;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
}
a { color: inherit; text-decoration: none; }
.container { max-width: 1180px; margin: 0 auto; padding: 28px 22px; }
.nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 42px;
}
.logo {
  font-weight: 850;
  letter-spacing: -0.04em;
  font-size: 22px;
  color: var(--navy);
}
.logo span { color: var(--gold-dark); }
.navlinks {
  display: flex;
  gap: 18px;
  color: var(--muted);
  font-size: 14px;
  align-items: center;
  flex-wrap: wrap;
}
.navlinks a:hover { color: var(--navy); }
.hero {
  display: grid;
  grid-template-columns: 1.05fr 0.95fr;
  gap: 48px;
  align-items: center;
  padding: 34px 0 56px;
}
.badge {
  display: inline-flex;
  border: 1px solid #d7c49a;
  background: #fffaf0;
  color: #8a6a24;
  padding: 8px 13px;
  border-radius: 999px;
  font-size: 13px;
  margin-bottom: 20px;
  font-weight: 650;
}
h1 {
  font-size: 58px;
  line-height: 1.02;
  letter-spacing: -0.06em;
  margin: 0 0 20px;
  color: var(--navy);
}
h2 {
  font-size: 32px;
  line-height: 1.15;
  letter-spacing: -0.04em;
  margin: 0 0 16px;
  color: var(--navy);
}
h3 { margin: 0 0 10px; color: var(--navy); }
p { color: var(--muted); line-height: 1.65; }
.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 24px;
  padding: 26px;
  box-shadow: 0 14px 40px rgba(16, 24, 40, 0.06);
}
.soft {
  background: var(--panel-soft);
  border: 1px solid #e7e0cf;
}
.grid { display: grid; gap: 20px; }
.grid-4 { grid-template-columns: repeat(4, 1fr); }
.grid-3 { grid-template-columns: repeat(3, 1fr); }
.grid-2 { grid-template-columns: repeat(2, 1fr); }
.btn {
  display: inline-block;
  background: var(--navy);
  color: #fff;
  padding: 13px 18px;
  border-radius: 12px;
  font-weight: 750;
  border: 0;
  cursor: pointer;
}
.btn.gold {
  background: var(--gold);
  color: #111827;
}
.btn.secondary {
  background: transparent;
  color: var(--navy);
  border: 1px solid var(--line);
}
.form-row { margin-bottom: 16px; }
label { display: block; margin-bottom: 8px; color: var(--navy); font-weight: 700; }
input, select, textarea {
  width: 100%;
  padding: 13px 14px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--text);
}
.help { font-size: 13px; color: var(--muted); margin-top: 5px; }
.section-title {
  margin-top: 32px;
  padding: 14px 16px;
  background: #fffaf0;
  border: 1px solid #ead7a3;
  border-radius: 16px;
  color: #8a6a24;
  font-weight: 850;
}
.question {
  border-bottom: 1px solid var(--line);
  padding: 22px 0;
}
.scale {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
  margin-top: 12px;
}
.scale label {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 11px;
  font-size: 12px;
  color: var(--muted);
  cursor: pointer;
  background: #fff;
  min-height: 74px;
}
.scale label:hover {
  border-color: var(--gold);
  background: #fffaf0;
}
.scale input {
  width: auto;
  margin-right: 6px;
}
.score {
  font-size: 42px;
  font-weight: 900;
  letter-spacing: -0.06em;
  color: var(--navy);
}
.muted { color: var(--muted); }
.kpi {
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 18px;
  background: #fff;
}
.bar {
  height: 10px;
  border-radius: 999px;
  background: #eaecf0;
  overflow: hidden;
}
.fill {
  height: 100%;
  background: linear-gradient(90deg, var(--gold), var(--navy));
}
.table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 12px;
  font-size: 14px;
}
.table th, .table td {
  border-bottom: 1px solid var(--line);
  padding: 12px;
  text-align: left;
  vertical-align: top;
}
.table th {
  color: var(--navy);
  font-size: 13px;
  background: #f9fafb;
}
.notice {
  padding: 15px 17px;
  border-radius: 14px;
  background: #fffaf0;
  border: 1px solid #ead7a3;
  color: #8a6a24;
  margin-bottom: 18px;
  font-weight: 650;
}
.price {
  font-size: 38px;
  font-weight: 900;
  letter-spacing: -0.04em;
  color: var(--navy);
}
.footer {
  margin-top: 56px;
  color: var(--muted);
  font-size: 13px;
  border-top: 1px solid var(--line);
  padding-top: 22px;
}
@media (max-width: 960px) {
  .hero, .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; }
  h1 { font-size: 40px; }
  .scale { grid-template-columns: 1fr; }
}
</style>
"""


def page(title, body):
    return render_template_string(f"""
<!doctype html>
<html>
<head>
  <title>{title} | {APP_NAME}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {BASE_CSS}
</head>
<body>
  <div class="container">
    <div class="nav">
      <a class="logo" href="/"><span>Dissilio</span> Diagnostic</a>
      <div class="navlinks">
        <a href="/">Home</a>
        <a href="/how-it-works">How it works</a>
        <a href="/consultancy">Consultancy</a>
        <a href="/start" class="btn secondary">Start Free Snapshot</a>
      </div>
    </div>
    {body}
    <div class="footer">
      Dissilio AI & Automation Diagnostic MVP. Outputs are advisory and should be reviewed before legal, compliance, procurement, or investment decisions.
    </div>
  </div>
</body>
</html>
""")


# ----------------------------
# Routes
# ----------------------------

@app.route("/")
def home():
    body = f"""
    <section class="hero">
      <div>
        <div class="badge">AI readiness • automation opportunity • risk diagnostic</div>
        <h1>Discover where your organisation can automate work and use AI safely.</h1>
        <p>
          A practical diagnostic for organisations that want to reduce manual admin, improve reporting,
          identify AI opportunities, and understand what risks need managing before investing in tools or consultants.
        </p>
        <div style="display:flex; gap:12px; margin-top:26px; flex-wrap:wrap;">
          <a class="btn gold" href="/start">Start Free Snapshot</a>
          <a class="btn secondary" href="/how-it-works">See How It Works</a>
        </div>
      </div>
      <div class="card soft">
        <h2>Your diagnostic covers</h2>
        <div class="grid grid-2">
          <div class="kpi">Automation opportunity</div>
          <div class="kpi">AI suitability</div>
          <div class="kpi">Process readiness</div>
          <div class="kpi">Data readiness</div>
          <div class="kpi">Systems readiness</div>
          <div class="kpi">Governance maturity</div>
          <div class="kpi">Risk exposure</div>
          <div class="kpi">Business value potential</div>
        </div>
      </div>
    </section>

    <section class="grid grid-3">
      <div class="card">
        <h3>Reduce manual work</h3>
        <p>Identify repetitive admin, reporting, approvals, reminders, handoffs, and follow-ups that may be suitable for automation.</p>
      </div>
      <div class="card">
        <h3>Use AI where it fits</h3>
        <p>Understand where AI can support drafting, summarising, knowledge search, classification, reporting commentary, and insight.</p>
      </div>
      <div class="card">
        <h3>Manage risk early</h3>
        <p>Identify gaps around shadow AI, data privacy, human review, staff guidance, AI policy, and governance controls.</p>
      </div>
    </section>

    <section style="margin-top:30px;" class="card">
      <h2>Simple offer structure</h2>
      <table class="table">
        <tr><th>Offer</th><th>Price</th><th>Best for</th><th>What you get</th></tr>
        <tr><td>Free Snapshot</td><td>£0</td><td>Initial check</td><td>Headline scores, top gaps, top opportunities, and basic AI vs automation guidance.</td></tr>
        <tr><td>Paid Diagnostic Report</td><td>{PAID_PRICE}</td><td>Downloadable mini-consulting report</td><td>Full score dashboard, question-by-question analysis, opportunity register, tool categories, risks, and 30-day action plan.</td></tr>
        <tr><td>3-Day Consultancy Audit</td><td>{CONSULTANCY_PRICE}</td><td>Human-reviewed roadmap</td><td>Validated findings, stakeholder session, prioritised roadmap, first MVP recommendation, and build proposal where appropriate.</td></tr>
      </table>
    </section>
    """
    return page("Home", body)


@app.route("/how-it-works")
def how_it_works():
    body = f"""
    <div class="card">
      <h1>How it works</h1>
      <p>
        The diagnostic helps organisations move from vague AI interest to practical, prioritised action.
        It separates simple automation opportunities from AI use cases and highlights the risks that need managing.
      </p>
    </div>

    <section style="margin-top:24px;" class="grid grid-3">
      <div class="card">
        <h3>1. Complete the diagnostic</h3>
        <p>Answer 40 practical questions about manual work, processes, systems, data, AI usage, governance, people, and value.</p>
      </div>
      <div class="card">
        <h3>2. Receive your free snapshot</h3>
        <p>Get headline scores, top findings, and initial guidance on whether automation, AI, governance, or data should come first.</p>
      </div>
      <div class="card">
        <h3>3. Unlock the paid report</h3>
        <p>The {PAID_PRICE} report gives the full diagnostic, question-by-question interpretation, opportunity register, and 30-day action plan.</p>
      </div>
      <div class="card">
        <h3>4. Review tool categories</h3>
        <p>The report suggests tool categories and examples, but final tool selection is reserved for consultancy after deeper review.</p>
      </div>
      <div class="card">
        <h3>5. Book the audit</h3>
        <p>The {CONSULTANCY_PRICE} audit validates the findings and turns them into a practical roadmap and first MVP recommendation.</p>
      </div>
      <div class="card">
        <h3>6. Build the solution</h3>
        <p>Dissilio can then design and build a practical AI or automation MVP based on the highest-value opportunity.</p>
      </div>
    </section>
    """
    return page("How it works", body)


@app.route("/consultancy")
def consultancy():
    body = f"""
    <section class="hero">
      <div>
        <div class="badge">Premium consultancy pathway</div>
        <h1>3-Day AI & Automation Opportunity Audit.</h1>
        <p>
          A human-reviewed audit for organisations that want to validate their diagnostic results,
          prioritise realistic opportunities, manage risk, and define the first practical MVP.
        </p>
        <div style="display:flex; gap:12px; margin-top:24px; flex-wrap:wrap;">
          <a class="btn gold" href="/start">Start with Free Snapshot</a>
          <a class="btn secondary" href="/">Back Home</a>
        </div>
      </div>
      <div class="card soft">
        <h2>Audit price</h2>
        <div class="price">{CONSULTANCY_PRICE}</div>
        <p>Based on a 3-day engagement at £500/day.</p>
        <p><strong>Best for:</strong> SMEs, care providers, training providers, charities, professional services firms, and operational teams.</p>
      </div>
    </section>

    <section class="grid grid-2">
      <div class="card">
        <h3>What is included</h3>
        <p>Review of diagnostic results, stakeholder session, process/opportunity validation, AI risk review, prioritised roadmap, and first MVP recommendation.</p>
      </div>
      <div class="card">
        <h3>What it produces</h3>
        <p>A validated opportunity register, 30/60/90-day roadmap, recommended first project, and build proposal where appropriate.</p>
      </div>
      <div class="card">
        <h3>What it does not do</h3>
        <p>It does not claim formal legal, regulatory, or ISO certification. It is a practical advisory audit to help organisations make better AI and automation decisions.</p>
      </div>
      <div class="card">
        <h3>Why it matters</h3>
        <p>Most organisations do not need “AI everywhere.” They need the right mix of process improvement, automation, governance, data readiness, and targeted AI use cases.</p>
      </div>
    </section>
    """
    return page("Consultancy", body)


@app.route("/start", methods=["GET", "POST"])
def start():
    if request.method == "POST":
        org = Organisation(
            name=request.form["name"],
            contact_name=request.form["contact_name"],
            contact_email=request.form["contact_email"],
            sector=request.form["sector"],
            size=request.form["size"],
            country=request.form["country"],
            biggest_pressure=request.form.get("biggest_pressure", ""),
        )
        db.session.add(org)
        db.session.commit()

        assessment_record = Assessment(organisation_id=org.id, status="in_progress")
        db.session.add(assessment_record)
        db.session.commit()

        return redirect(url_for("assessment", assessment_id=assessment_record.id))

    body = """
    <div class="card">
      <h1>Start your free AI & automation snapshot</h1>
      <p>Capture basic organisation details before completing the diagnostic.</p>
      <form method="post">
        <div class="grid grid-2">
          <div class="form-row">
            <label>Organisation name</label>
            <input name="name" required placeholder="Example: Horizon Care Services">
          </div>
          <div class="form-row">
            <label>Contact name</label>
            <input name="contact_name" required placeholder="Your name">
          </div>
          <div class="form-row">
            <label>Contact email</label>
            <input name="contact_email" type="email" required placeholder="name@example.com">
          </div>
          <div class="form-row">
            <label>Sector</label>
            <select name="sector" required>
              <option>SME / General Business</option>
              <option>Charity / Community Organisation</option>
              <option>Education / Training Provider</option>
              <option>Healthcare / Care Provider</option>
              <option>Professional Services</option>
              <option>Local Authority / Public Sector</option>
              <option>Finance / Regulated Business</option>
              <option>Other</option>
            </select>
          </div>
          <div class="form-row">
            <label>Organisation size</label>
            <select name="size" required>
              <option>1–10 staff</option>
              <option>11–50 staff</option>
              <option>51–250 staff</option>
              <option>251–1000 staff</option>
              <option>1000+ staff</option>
            </select>
          </div>
          <div class="form-row">
            <label>Country</label>
            <input name="country" value="United Kingdom" required>
          </div>
        </div>
        <div class="form-row">
          <label>Biggest operational pressure right now</label>
          <textarea name="biggest_pressure" rows="3" placeholder="Example: manual reporting, admin workload, repeated enquiries, compliance documentation, slow approvals..."></textarea>
        </div>
        <button class="btn gold" type="submit">Continue to Diagnostic</button>
      </form>
    </div>
    """
    return page("Start", body)


@app.route("/assessment/<int:assessment_id>", methods=["GET", "POST"])
def assessment(assessment_id):
    assessment_record = Assessment.query.get_or_404(assessment_id)

    if request.method == "POST":
        responses = {}
        for question in QUESTIONS:
            responses[question["id"]] = float(request.form.get(question["id"], 0))

        scores = calculate_scores(responses)
        diagnostics = generate_question_diagnostics(responses)
        recommendations = generate_recommendations(scores)
        risks = generate_risks(scores)
        opportunities = generate_opportunities(scores)

        assessment_record.responses_json = json.dumps(responses)
        assessment_record.scores_json = json.dumps(scores)
        assessment_record.recommendations_json = json.dumps(recommendations)
        assessment_record.risks_json = json.dumps(risks)
        assessment_record.opportunities_json = json.dumps(opportunities)
        assessment_record.status = "completed"
        assessment_record.completed_at = datetime.utcnow()
        db.session.commit()

        return redirect(url_for("results", assessment_id=assessment_record.id))

    current_section = None
    question_html = ""

    for index, question in enumerate(QUESTIONS, start=1):
        if question["section"] != current_section:
            current_section = question["section"]
            question_html += f"<div class='section-title'>{current_section}</div>"

        options_html = ""
        for option in question["options"]:
            checked = "checked" if option["score"] == 5 else ""
            options_html += f"""
            <label>
              <input type="radio" name="{question['id']}" value="{option['score']}" {checked}>
              {option['label']}
            </label>
            """

        question_html += f"""
        <div class="question">
          <label>{index}. {question['question']}</label>
          <div class="scale">{options_html}</div>
        </div>
        """

    body = f"""
    <div class="card">
      <h1>AI & Automation Diagnostic</h1>
      <p>
        Organisation: <strong>{assessment_record.organisation.name}</strong><br>
        Choose the answer that best reflects the current situation. There are no right or wrong answers.
      </p>
      <form method="post">
        {question_html}
        <div style="margin-top:24px;">
          <button class="btn gold" type="submit">Generate Free Snapshot</button>
        </div>
      </form>
    </div>
    """
    return page("Diagnostic", body)


@app.route("/results/<int:assessment_id>")
def results(assessment_id):
    assessment_record = Assessment.query.get_or_404(assessment_id)

    if not assessment_record.scores_json:
        return redirect(url_for("assessment", assessment_id=assessment_record.id))

    scores = json.loads(assessment_record.scores_json)
    recs = json.loads(assessment_record.recommendations_json or "[]")
    opportunities = json.loads(assessment_record.opportunities_json or "[]")

    rec_html = "".join([
        f"""
        <div class="kpi">
          <strong>{r['title']}</strong><br>
          <span class="muted">Priority: {r['priority']}</span>
          <p>{r['text']}</p>
        </div>
        """
        for r in recs[:3]
    ])

    opp_html = "".join([
        f"""
        <div class="kpi">
          <strong>{o['area']}</strong>
          <p>{o['problem']}</p>
        </div>
        """
        for o in opportunities[:3]
    ])

    body = f"""
    <div class="notice">
      Free snapshot generated. Unlock the {PAID_PRICE} paid report for the full question-by-question diagnostic, automation opportunity register, AI suitability map, tool categories, risk summary, and 30-day action plan.
    </div>

    <section class="grid grid-4">
      <div class="card"><h3>Overall</h3><div class="score">{scores['overall_score']}</div><p>{score_to_band(scores['overall_score'])}</p></div>
      <div class="card"><h3>Automation</h3><div class="score">{scores['automation_score']}</div><p>{score_to_band(scores['automation_score'])}</p></div>
      <div class="card"><h3>AI Suitability</h3><div class="score">{scores['ai_score']}</div><p>{score_to_band(scores['ai_score'])}</p></div>
      <div class="card"><h3>Risk Exposure</h3><div class="score">{scores['risk_score']}</div><p>{risk_band(scores['risk_score'])}</p></div>
    </section>

    <section style="margin-top:24px;" class="card">
      <h2>AI vs Automation Guidance</h2>
      <p><strong>Automation</strong> is best for repeatable, rules-based tasks such as approvals, reminders, reporting workflows, handoffs, and data movement.</p>
      <p><strong>AI</strong> is best where work involves language, knowledge, drafting, summarising, classification, search, extraction, or insight generation.</p>
      <p><strong>AI agents</strong> can complete multi-step tasks, but require stronger governance, testing, access control, and human oversight.</p>
    </section>

    <section style="margin-top:24px;" class="grid grid-2">
      <div class="card">
        <h2>Top recommendations</h2>
        <div class="grid">{rec_html}</div>
      </div>
      <div class="card">
        <h2>Top opportunity areas</h2>
        <div class="grid">{opp_html}</div>
      </div>
    </section>

    <section style="margin-top:24px;" class="card">
      <h2>Unlock the paid diagnostic report — {PAID_PRICE}</h2>
      <p>The paid report includes the full score dashboard, question-by-question breakdown, automation opportunity register, AI suitability map, tool categories, risk summary, and 30-day action plan.</p>
      <a class="btn gold" href="/unlock/{assessment_record.id}">Simulate {PAID_PRICE} Report Unlock</a>
      <a class="btn secondary" href="/report/{assessment_record.id}">View Report</a>
    </section>
    """
    return page("Free Snapshot", body)


@app.route("/unlock/<int:assessment_id>")
def unlock(assessment_id):
    assessment_record = Assessment.query.get_or_404(assessment_id)
    assessment_record.is_paid = True
    assessment_record.tier = "paid_report"
    db.session.commit()
    return redirect(url_for("report", assessment_id=assessment_record.id))


@app.route("/report/<int:assessment_id>")
def report(assessment_id):
    assessment_record = Assessment.query.get_or_404(assessment_id)

    if not assessment_record.scores_json:
        return redirect(url_for("assessment", assessment_id=assessment_record.id))

    if not assessment_record.is_paid:
        body = f"""
        <div class="card">
          <h1>Paid report locked</h1>
          <p>The full diagnostic report is available after payment. This MVP uses a simulated unlock.</p>
          <a class="btn gold" href="/unlock/{assessment_record.id}">Simulate {PAID_PRICE} Unlock</a>
          <a class="btn secondary" href="/results/{assessment_record.id}">Back to Free Snapshot</a>
        </div>
        """
        return page("Report Locked", body)

    scores = json.loads(assessment_record.scores_json)
    responses = json.loads(assessment_record.responses_json or "{}")
    diagnostics = generate_question_diagnostics(responses)
    recs = json.loads(assessment_record.recommendations_json or "[]")
    risks = json.loads(assessment_record.risks_json or "[]")
    opportunities = json.loads(assessment_record.opportunities_json or "[]")
    consultancy = recommend_consultancy(scores)

    score_rows = f"""
    <tr><td>Overall Diagnostic Score</td><td>{scores['overall_score']}/100</td><td>{score_to_band(scores['overall_score'])}</td></tr>
    <tr><td>Automation Opportunity</td><td>{scores['automation_score']}/100</td><td>{score_to_band(scores['automation_score'])}</td></tr>
    <tr><td>AI Suitability</td><td>{scores['ai_score']}/100</td><td>{score_to_band(scores['ai_score'])}</td></tr>
    <tr><td>Process Readiness</td><td>{scores['process_score']}/100</td><td>{score_to_band(scores['process_score'])}</td></tr>
    <tr><td>Data Readiness</td><td>{scores['data_score']}/100</td><td>{score_to_band(scores['data_score'])}</td></tr>
    <tr><td>Systems Readiness</td><td>{scores['systems_score']}/100</td><td>{score_to_band(scores['systems_score'])}</td></tr>
    <tr><td>Governance Maturity</td><td>{scores['governance_score']}/100</td><td>{score_to_band(scores['governance_score'])}</td></tr>
    <tr><td>Staff Readiness</td><td>{scores['staff_score']}/100</td><td>{score_to_band(scores['staff_score'])}</td></tr>
    <tr><td>Business Value Potential</td><td>{scores['business_value_score']}/100</td><td>{score_to_band(scores['business_value_score'])}</td></tr>
    <tr><td>Risk Exposure</td><td>{scores['risk_score']}/100</td><td>{risk_band(scores['risk_score'])}</td></tr>
    """

    rec_rows = "".join([
        f"<tr><td>{r['title']}</td><td>{r['priority']}</td><td>{r['text']}</td></tr>"
        for r in recs
    ])

    risk_rows = "".join([
        f"<tr><td>{r['risk']}</td><td>{r['cause']}</td><td>{r['severity']}</td><td>{r['mitigation']}</td></tr>"
        for r in risks
    ])

    opp_rows = "".join([
        f"""
        <tr>
          <td>{o['area']}</td>
          <td>{o['problem']}</td>
          <td>{o['automation']}</td>
          <td>{o['ai']}</td>
          <td>{o['tools']}</td>
          <td>{o['mvp']}</td>
        </tr>
        """
        for o in opportunities
    ])

    diagnostic_rows = ""
    for d in diagnostics:
        tool_text = ", ".join(d["tools"]) if d["tools"] else "No specific tool category recommended at this stage"
        diagnostic_rows += f"""
        <tr>
          <td><strong>{d['section']}</strong><br>{d['question']}</td>
          <td>{d['answer']}</td>
          <td>{d['meaning']}</td>
          <td>{d['automation']}</td>
          <td>{d['ai']}</td>
          <td>{d['risk']}</td>
          <td>{d['strategy']}<br><br><span class="muted"><strong>Tool category/examples:</strong> {tool_text}</span></td>
        </tr>
        """

    body = f"""
    <div class="card">
      <h1>Paid AI & Automation Diagnostic Report</h1>
      <p>
        Organisation: <strong>{assessment_record.organisation.name}</strong><br>
        Sector: {assessment_record.organisation.sector}<br>
        Size: {assessment_record.organisation.size}<br>
        Completed: {assessment_record.completed_at.strftime('%d %b %Y') if assessment_record.completed_at else 'N/A'}
      </p>
      <button class="btn secondary" onclick="window.print()">Print / Save as PDF</button>
    </div>

    <section style="margin-top:24px;" class="card">
      <h2>Executive Summary</h2>
      <p>
        The organisation achieved an overall diagnostic score of <strong>{scores['overall_score']}/100</strong>,
        with automation opportunity at <strong>{scores['automation_score']}/100</strong>,
        AI suitability at <strong>{scores['ai_score']}/100</strong>,
        and risk exposure at <strong>{scores['risk_score']}/100</strong>.
      </p>
      <p>
        The recommended next step is to focus on the highest-value practical improvement area while ensuring
        that process clarity, data quality, human review, and AI governance are strong enough to support safe adoption.
      </p>
    </section>

    <section style="margin-top:24px;" class="card">
      <h2>Score Dashboard</h2>
      <table class="table">
        <tr><th>Score</th><th>Result</th><th>Band</th></tr>
        {score_rows}
      </table>
    </section>

    <section style="margin-top:24px;" class="card">
      <h2>Recommended Actions</h2>
      <table class="table">
        <tr><th>Recommendation</th><th>Priority</th><th>Details</th></tr>
        {rec_rows}
      </table>
    </section>

    <section style="margin-top:24px;" class="card">
      <h2>Automation Opportunity Register</h2>
      <table class="table">
        <tr>
          <th>Area</th>
          <th>Problem</th>
          <th>Automation Fit</th>
          <th>AI Fit</th>
          <th>Tool Category / Examples</th>
          <th>Suggested MVP</th>
        </tr>
        {opp_rows}
      </table>
      <p class="muted">
        Tool examples are illustrative categories only. Final tool selection should be handled through consultancy after reviewing systems, data sensitivity, budget, integrations, permissions, and operating model.
      </p>
    </section>

    <section style="margin-top:24px;" class="card">
      <h2>Risk Summary</h2>
      <table class="table">
        <tr><th>Risk</th><th>Cause</th><th>Severity</th><th>Recommended Mitigation</th></tr>
        {risk_rows}
      </table>
    </section>

    <section style="margin-top:24px;" class="card">
      <h2>30-Day Action Plan</h2>
      <table class="table">
        <tr><th>Week</th><th>Action</th></tr>
        <tr><td>Week 1</td><td>Confirm AI and automation objectives, identify current AI tools in use, and assign an owner.</td></tr>
        <tr><td>Week 2</td><td>Map the top 3 manual processes and identify pain points, handoffs, rules, and exceptions.</td></tr>
        <tr><td>Week 3</td><td>Create an opportunity register and score opportunities by value, feasibility, risk, and data readiness.</td></tr>
        <tr><td>Week 4</td><td>Select one low-risk pilot, define success measures, agree human review controls, and prepare a simple business case.</td></tr>
      </table>
    </section>

    <section style="margin-top:24px;" class="card">
      <h2>Question-by-Question Diagnostic</h2>
      <p class="muted">
        This section explains what each answer means, where automation may help, where AI may help, what risks exist, and what strategy is recommended.
      </p>
      <table class="table">
        <tr>
          <th>Question</th>
          <th>Selected Answer</th>
          <th>What This Means</th>
          <th>Automation Implication</th>
          <th>AI Implication</th>
          <th>Risk Implication</th>
          <th>Recommended Strategy</th>
        </tr>
        {diagnostic_rows}
      </table>
    </section>

    <section style="margin-top:24px;" class="card">
      <h2>Recommended Consultancy Pathway</h2>
      <div class="kpi">
        <h3>{consultancy['name']} — {consultancy['price']}</h3>
        <p><strong>Duration:</strong> {consultancy['duration']}</p>
        <p><strong>Why this is recommended:</strong> {consultancy['reason']}</p>
        <p><strong>Deliverables:</strong> {consultancy['deliverables']}</p>
      </div>
    </section>
    """
    return page("Paid Report", body)


@app.route("/admin")
def admin():
    admin_pass = request.args.get("pass")
    required = os.environ.get("ADMIN_PASS", "dissilio-admin")

    if admin_pass != required:
        body = """
        <div class="card">
          <h1>Admin Access</h1>
          <p>Append <code>?pass=dissilio-admin</code> to the URL for MVP admin access.</p>
          <p>In production, replace this with secure authentication and role-based access control.</p>
        </div>
        """
        return page("Admin", body)

    assessments = Assessment.query.order_by(Assessment.created_at.desc()).all()

    rows = ""
    for item in assessments:
        score = "N/A"
        risk = "N/A"

        if item.scores_json:
            parsed = json.loads(item.scores_json)
            score = parsed.get("overall_score", "N/A")
            risk = parsed.get("risk_score", "N/A")

        rows += f"""
        <tr>
          <td>{item.id}</td>
          <td>{item.organisation.name}</td>
          <td>{item.organisation.sector}</td>
          <td>{item.organisation.contact_email}</td>
          <td>{item.status}</td>
          <td>{item.tier}</td>
          <td>{'Yes' if item.is_paid else 'No'}</td>
          <td>{score}</td>
          <td>{risk}</td>
          <td>
            <a href="/results/{item.id}">Snapshot</a> |
            <a href="/report/{item.id}">Report</a>
          </td>
        </tr>
        """

    body = f"""
    <div class="card">
      <h1>Admin Pipeline</h1>
      <p>Review completed diagnostics, paid status, scores, and potential consultancy leads.</p>
      <table class="table">
        <tr>
          <th>ID</th>
          <th>Organisation</th>
          <th>Sector</th>
          <th>Email</th>
          <th>Status</th>
          <th>Tier</th>
          <th>Paid</th>
          <th>Overall</th>
          <th>Risk</th>
          <th>Actions</th>
        </tr>
        {rows}
      </table>
    </div>
    """
    return page("Admin", body)


@app.errorhandler(404)
def not_found(e):
    return page(
        "Not Found",
        "<div class='card'><h1>Page not found</h1><a class='btn' href='/'>Go Home</a></div>"
    ), 404


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
