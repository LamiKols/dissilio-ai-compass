import os
import json
from datetime import datetime
from statistics import mean

from flask import Flask, request, redirect, url_for, render_template_string
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Version 2.2 uses a fresh SQLite database by default to avoid older schema conflicts.
if os.environ.get("USE_DATABASE_URL") == "true":
    database_uri = os.environ.get("DATABASE_URL", "sqlite:///dissilio_v22.db")
else:
    database_uri = "sqlite:///dissilio_v22.db"

app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

APP_NAME = "Dissilio AI & Automation Diagnostic"
APP_VERSION = "2.2"
PAID_PRICE = "£79"
CONSULTANCY_PRICE = "£1,500"
ADMIN_PASS = os.environ.get("ADMIN_PASS", "dissilio-admin")


# -----------------------------------------------------------------------------
# Database Models
# -----------------------------------------------------------------------------

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
    intelligence_json = db.Column(db.Text, nullable=True)
    is_paid = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)


# -----------------------------------------------------------------------------
# Question Bank
# -----------------------------------------------------------------------------

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


def make_options(labels):
    scores = [0, 2.5, 5, 7.5, 10]
    return [{"score": score, "label": label} for score, label in zip(scores, labels)]


def q(qid, section, question, labels, score_map, theme, tool_category, examples):
    return {
        "id": qid,
        "section": section,
        "question": question,
        "options": make_options(labels),
        "score_map": score_map,
        "theme": theme,
        "tool_category": tool_category,
        "examples": examples,
    }


QUESTIONS = [
    q(
        "q1_strategy_clarity",
        "1. AI & Automation Strategy",
        "How clearly has your organisation defined why it wants to use AI or automation?",
        [
            "We have not discussed AI or automation properly",
            "We are interested but have no clear reason yet",
            "We have some broad ideas but no agreed priorities",
            "We have identified priority areas where AI or automation may help",
            "We have clear objectives, owners, and expected business outcomes",
        ],
        {"ai": "direct", "business_value": "direct", "governance": "direct", "risk": "inverse"},
        "strategy",
        "Strategy and prioritisation",
        "AI strategy canvas, opportunity register, business case template",
    ),
    q(
        "q2_leadership_support",
        "1. AI & Automation Strategy",
        "How strongly is leadership supporting AI and automation improvement?",
        [
            "Leadership has not engaged with AI or automation",
            "A few leaders are curious but no one owns it",
            "Leadership is supportive but not actively driving it",
            "A senior person is sponsoring early exploration",
            "Leadership actively owns, funds, and governs AI/automation activity",
        ],
        {"business_value": "direct", "governance": "direct", "risk": "inverse"},
        "leadership",
        "Leadership and operating model",
        "Leadership workshop, AI steering group, roadmap template",
    ),
    q(
        "q3_ai_vs_automation",
        "1. AI & Automation Strategy",
        "How clearly does your organisation distinguish between automation and AI?",
        [
            "We treat automation and AI as the same thing",
            "We have limited understanding of the difference",
            "Some people understand the difference, but not consistently",
            "We usually understand when automation or AI is appropriate",
            "We clearly distinguish automation, AI assistance, and AI agents",
        ],
        {"ai": "direct", "governance": "direct", "risk": "inverse"},
        "ai_vs_automation",
        "AI and automation education",
        "AI vs automation decision guide, staff awareness guide",
    ),
    q(
        "q4_idea_capture",
        "1. AI & Automation Strategy",
        "How are AI or automation ideas currently identified?",
        [
            "Ideas are not captured",
            "Ideas are raised informally but not tracked",
            "Some ideas are captured but not assessed consistently",
            "Ideas are reviewed against business need and feasibility",
            "Ideas are captured, scored, prioritised, and linked to business outcomes",
        ],
        {"process": "direct", "business_value": "direct", "governance": "direct"},
        "opportunity_management",
        "Opportunity management",
        "Opportunity register, prioritisation matrix, ROI scoring",
    ),
    q(
        "q5_problem_confidence",
        "1. AI & Automation Strategy",
        "How confident are you that AI or automation investment would solve real business problems?",
        [
            "We are not confident because the problems are unclear",
            "We believe there may be value but have not validated it",
            "We can see some likely benefits",
            "We have clear problem areas where improvement is needed",
            "We have validated problems, expected benefits, and success measures",
        ],
        {"business_value": "direct", "ai": "direct"},
        "problem_validation",
        "Problem validation",
        "Problem statement workshop, benefits map, pilot business case",
    ),
    q(
        "q6_manual_work",
        "2. Manual Work & Automation Opportunity",
        "How much repetitive manual work exists in your organisation?",
        [
            "Very little repetitive manual work",
            "A few small admin tasks are repetitive",
            "Several recurring manual tasks exist",
            "Many recurring tasks exist across teams",
            "Manual work is a major operational burden",
        ],
        {"automation": "direct", "business_value": "direct"},
        "manual_work",
        "Workflow automation",
        "Power Automate, Zapier, Make, n8n, Airtable",
    ),
    q(
        "q7_copy_between_systems",
        "2. Manual Work & Automation Opportunity",
        "How often do staff copy information between systems, spreadsheets, emails, or documents?",
        [
            "Almost never",
            "Occasionally",
            "Weekly in some teams",
            "Daily in several teams",
            "Constantly across the organisation",
        ],
        {"automation": "direct", "systems": "inverse", "risk": "direct", "business_value": "direct"},
        "data_movement",
        "Integration and data movement automation",
        "Power Automate, Make, Zapier, n8n, API integration",
    ),
    q(
        "q8_reporting_workload",
        "2. Manual Work & Automation Opportunity",
        "How much time is spent preparing routine reports?",
        [
            "Very little time",
            "Some time, but not a major issue",
            "Regular time is spent preparing reports",
            "Reporting is a major recurring workload",
            "Reporting consumes significant staff or management time",
        ],
        {"automation": "direct", "business_value": "direct", "ai": "direct"},
        "reporting",
        "Reporting automation",
        "Power BI, Looker Studio, Tableau, Excel automation, AI report summariser",
    ),
    q(
        "q9_manual_followups",
        "2. Manual Work & Automation Opportunity",
        "How often are approvals, reminders, or follow-ups handled manually?",
        [
            "Rarely or never",
            "Occasionally",
            "Regularly in some processes",
            "Frequently across multiple teams",
            "Manual chasing and follow-up is a major issue",
        ],
        {"automation": "direct", "process": "inverse", "business_value": "direct"},
        "followups",
        "Workflow and approval automation",
        "Power Automate, Monday.com, ClickUp, Asana, Airtable",
    ),
    q(
        "q10_repeated_questions",
        "2. Manual Work & Automation Opportunity",
        "How often do staff answer the same questions repeatedly?",
        [
            "Rarely",
            "Occasionally",
            "Frequently in some teams",
            "Frequently across several teams",
            "Repeated questions create major workload",
        ],
        {"automation": "direct", "ai": "direct", "business_value": "direct"},
        "knowledge_queries",
        "Knowledge base and AI assistant",
        "SharePoint, Notion, Confluence, Copilot Studio, custom AI assistant",
    ),
    q(
        "q11_document_creation",
        "2. Manual Work & Automation Opportunity",
        "How often do staff manually create documents, letters, emails, forms, or summaries?",
        [
            "Rarely",
            "Occasionally",
            "Regularly in some roles",
            "Frequently across teams",
            "Document creation is a major workload",
        ],
        {"automation": "direct", "ai": "direct", "business_value": "direct", "risk": "direct"},
        "document_creation",
        "Document automation and AI drafting",
        "Microsoft Copilot, Google Gemini, ChatGPT Enterprise, template automation",
    ),
    q(
        "q12_decision_rules",
        "2. Manual Work & Automation Opportunity",
        "How clear are the rules behind routine decisions?",
        [
            "Decisions are unclear and inconsistent",
            "Decisions depend heavily on individual judgement",
            "Some rules exist but there are many exceptions",
            "Most routine decisions follow clear rules",
            "Decisions are highly rule-based and well documented",
        ],
        {"automation": "direct", "process": "direct", "ai": "direct", "risk": "inverse"},
        "decision_rules",
        "Rules and decision workflow automation",
        "Decision matrix, workflow rules, approval thresholds",
    ),
    q(
        "q13_process_documentation",
        "3. Process Readiness",
        "How well documented are your key business processes?",
        [
            "Not documented",
            "Mostly known by individuals",
            "Partially documented",
            "Mostly documented",
            "Fully documented and regularly reviewed",
        ],
        {"process": "direct", "automation": "direct", "risk": "inverse"},
        "process_documentation",
        "Process mapping and SOPs",
        "Process maps, SOP templates, workflow design",
    ),
    q(
        "q14_process_owners",
        "3. Process Readiness",
        "Are process owners clearly identified?",
        [
            "No clear process owners",
            "Ownership is informal",
            "Some processes have owners",
            "Most key processes have owners",
            "All key processes have clear owners and accountability",
        ],
        {"process": "direct", "governance": "direct", "risk": "inverse"},
        "process_ownership",
        "Ownership and accountability",
        "RACI, process ownership model, service ownership model",
    ),
    q(
        "q15_variation",
        "3. Process Readiness",
        "How often do different teams complete the same task in different ways?",
        [
            "Almost always done differently",
            "Often done differently",
            "Some variation exists",
            "Mostly standardised",
            "Highly standardised across teams",
        ],
        {"process": "direct", "automation": "direct", "risk": "inverse"},
        "process_variation",
        "Process standardisation",
        "Process standardisation, SOP review, operating model review",
    ),
    q(
        "q16_handoffs",
        "3. Process Readiness",
        "How clear are handoffs between teams or roles?",
        [
            "Handoffs are unclear and often missed",
            "Handoffs depend on individuals",
            "Some handoffs are defined",
            "Most handoffs are clear",
            "Handoffs are clearly defined, tracked, and measured",
        ],
        {"process": "direct", "automation": "direct", "risk": "inverse"},
        "handoffs",
        "Case management and task tracking",
        "Workflow automation, case management, task tracking",
    ),
    q(
        "q17_exceptions",
        "3. Process Readiness",
        "How well are exceptions and edge cases understood?",
        [
            "Exceptions are not understood",
            "Exceptions are handled informally",
            "Common exceptions are known",
            "Most exceptions are documented",
            "Exceptions are documented with clear handling rules",
        ],
        {"process": "direct", "governance": "direct", "risk": "inverse"},
        "exceptions",
        "Exception handling and escalation",
        "Exception log, process controls, escalation rules",
    ),
    q(
        "q18_data_reliability",
        "4. Data Readiness",
        "How reliable is the data used for reporting or decision-making?",
        [
            "Poor or unreliable",
            "Limited quality",
            "Usable but inconsistent",
            "Mostly reliable",
            "Structured, reliable, and trusted",
        ],
        {"data": "direct", "ai": "direct", "risk": "inverse"},
        "data_quality",
        "Data quality and reporting readiness",
        "Data quality review, Power BI, data cleanup",
    ),
    q(
        "q19_data_location",
        "4. Data Readiness",
        "Where is important business data mainly stored?",
        [
            "Mostly in people’s heads or informal notes",
            "Mostly in emails and scattered documents",
            "Mostly in spreadsheets",
            "Mostly in structured systems with some spreadsheets",
            "Mostly in structured systems with clear ownership",
        ],
        {"data": "direct", "systems": "direct", "risk": "inverse"},
        "data_location",
        "Data structure and knowledge management",
        "Data catalogue, document management, CRM/ERP review",
    ),
    q(
        "q20_data_owners",
        "4. Data Readiness",
        "Are data owners clearly identified?",
        [
            "No data owners are identified",
            "Ownership is informal",
            "Some important data has owners",
            "Most important data has owners",
            "Data ownership is clear and actively managed",
        ],
        {"data": "direct", "governance": "direct", "risk": "inverse"},
        "data_ownership",
        "Data governance",
        "Data ownership model, data governance checklist",
    ),
    q(
        "q21_data_access",
        "4. Data Readiness",
        "Can staff access the data they need without workarounds?",
        [
            "Staff frequently cannot access needed data",
            "Staff rely heavily on workarounds",
            "Access is mixed",
            "Most staff can access what they need",
            "Access is reliable, controlled, and role-appropriate",
        ],
        {"data": "direct", "systems": "direct", "automation": "direct", "risk": "inverse"},
        "data_access",
        "Role-based access and dashboards",
        "Role-based dashboards, access review, data portal",
    ),
    q(
        "q22_sensitive_data",
        "4. Data Readiness",
        "Is sensitive or personal data clearly identified and controlled?",
        [
            "We do not clearly identify sensitive or personal data",
            "We identify some sensitive data informally",
            "Some sensitive data is classified or controlled",
            "Most sensitive data is identified and controlled",
            "Sensitive data is clearly classified, controlled, and reviewed",
        ],
        {"data": "direct", "governance": "direct", "risk": "inverse"},
        "sensitive_data",
        "Data classification and privacy controls",
        "Data classification, DPIA checklist, access control review",
    ),
    q(
        "q23_data_exports",
        "5. Systems & Integration",
        "Can your systems export data reliably?",
        [
            "No reliable export is available",
            "Data must be copied manually",
            "Basic exports are available",
            "Regular exports are available",
            "Reliable exports, APIs, or integrations are available",
        ],
        {"systems": "direct", "automation": "direct", "risk": "inverse"},
        "data_exports",
        "Reporting and integration foundations",
        "Power BI, Looker Studio, CSV automation, API integration",
    ),
    q(
        "q24_system_integration",
        "5. Systems & Integration",
        "Do your systems integrate with each other?",
        [
            "Systems do not connect",
            "Systems connect only through manual workarounds",
            "Some limited integrations exist",
            "Most key systems can share data",
            "Systems are well integrated or integration-ready",
        ],
        {"systems": "direct", "automation": "direct", "risk": "inverse"},
        "integration",
        "Integration and workflow orchestration",
        "Power Automate, Zapier, Make, n8n, custom integration",
    ),
    q(
        "q25_spreadsheet_reliance",
        "5. Systems & Integration",
        "How much of your work relies on spreadsheets outside core systems?",
        [
            "Almost all important work happens in uncontrolled spreadsheets",
            "Heavy reliance on spreadsheets",
            "Moderate spreadsheet reliance",
            "Limited spreadsheet reliance",
            "Spreadsheets are controlled or not central to operations",
        ],
        {"systems": "direct", "risk": "inverse", "automation": "inverse"},
        "spreadsheet_reliance",
        "Internal tools and controlled data capture",
        "Airtable, Power Apps, Retool, internal tools, dashboard automation",
    ),
    q(
        "q26_digital_tools",
        "5. Systems & Integration",
        "Which digital workplace tools are actively used?",
        [
            "Few shared digital tools are used",
            "Email and documents only",
            "Microsoft 365 or Google Workspace is used",
            "Collaboration tools, shared storage, and task tools are used",
            "Digital workplace tools are mature and actively managed",
        ],
        {"systems": "direct", "ai": "direct", "automation": "direct"},
        "digital_tools",
        "Digital workplace automation",
        "Microsoft 365, Google Workspace, Teams, SharePoint, Copilot Studio",
    ),
    q(
        "q27_ai_usage_known",
        "6. Current AI Usage / Shadow AI",
        "Do you know whether staff use tools such as ChatGPT, Copilot, Gemini, Claude, or similar?",
        [
            "We do not know",
            "We suspect some staff use them",
            "We know some usage exists",
            "Usage is known and partially guided",
            "Usage is known, approved, and monitored",
        ],
        {"governance": "direct", "risk": "inverse", "ai": "direct"},
        "shadow_ai",
        "AI usage visibility and control",
        "AI usage register, AI policy, Copilot, ChatGPT Enterprise",
    ),
    q(
        "q28_ai_use_cases",
        "6. Current AI Usage / Shadow AI",
        "What do staff mainly use AI tools for today?",
        [
            "We do not know what staff use AI for",
            "Personal experimentation only",
            "Drafting, summarising, or research",
            "Work support with some review",
            "Approved work use cases with clear review controls",
        ],
        {"ai": "direct", "governance": "direct", "risk": "inverse"},
        "ai_use_cases",
        "AI use-case catalogue",
        "AI usage register, AI use case catalogue, staff guidance",
    ),
    q(
        "q29_ai_allowed",
        "6. Current AI Usage / Shadow AI",
        "Are staff allowed to use AI tools for work?",
        [
            "There is no guidance",
            "It is unclear",
            "Informally allowed in some cases",
            "Allowed with basic guidance",
            "Allowed under clear rules and approved use cases",
        ],
        {"governance": "direct", "risk": "inverse"},
        "ai_permissions",
        "AI acceptable use policy",
        "AI acceptable use policy, approved tool list",
    ),
    q(
        "q30_ai_output_review",
        "6. Current AI Usage / Shadow AI",
        "Are AI outputs reviewed before being used externally or in important decisions?",
        [
            "No review is required",
            "Review depends on the individual",
            "Some outputs are reviewed",
            "Most important outputs are reviewed",
            "Review is required for external, sensitive, or decision-support outputs",
        ],
        {"governance": "direct", "risk": "inverse"},
        "human_review",
        "Human review and quality control",
        "Human review checklist, AI quality controls",
    ),
    q(
        "q31_ai_error_process",
        "6. Current AI Usage / Shadow AI",
        "Are AI-generated errors, poor outputs, or concerns captured and corrected?",
        [
            "No process exists",
            "Issues are handled informally",
            "Some issues are corrected but not tracked",
            "Issues are usually reviewed and corrected",
            "Issues are tracked, reviewed, corrected, and used to improve controls",
        ],
        {"governance": "direct", "risk": "inverse"},
        "ai_errors",
        "AI issue management",
        "AI issue log, correction process, escalation route",
    ),
    q(
        "q32_ai_policy",
        "7. Governance, Risk & Privacy",
        "Do you have an AI acceptable use policy?",
        [
            "No policy exists",
            "Informal guidance exists",
            "Draft or partial policy exists",
            "Policy exists but needs improvement",
            "Policy exists, is communicated, and is reviewed",
        ],
        {"governance": "direct", "risk": "inverse"},
        "ai_policy",
        "AI policy and governance pack",
        "AI policy pack, governance checklist, staff guidance",
    ),
    q(
        "q33_prohibited_data",
        "7. Governance, Risk & Privacy",
        "Do staff know what information must not be entered into public AI tools?",
        [
            "No, this has not been explained",
            "Some staff may know informally",
            "Basic guidance has been shared",
            "Most staff understand the rules",
            "Staff are trained and rules are enforced",
        ],
        {"governance": "direct", "risk": "inverse"},
        "prohibited_data",
        "AI data handling guidance",
        "AI data handling guide, staff training, privacy checklist",
    ),
    q(
        "q34_tool_risk_review",
        "7. Governance, Risk & Privacy",
        "Are AI-related risks reviewed before new tools are adopted?",
        [
            "No review happens",
            "Review is informal",
            "Some risk checks happen",
            "Most new tools are reviewed",
            "AI tools are reviewed for privacy, security, value, and operational risk before adoption",
        ],
        {"governance": "direct", "risk": "inverse"},
        "tool_review",
        "Tool approval and vendor review",
        "Tool approval checklist, DPIA checklist, vendor review",
    ),
    q(
        "q35_service_user_impact",
        "7. Governance, Risk & Privacy",
        "Are customers, clients, learners, patients, or service users affected by any AI-supported process?",
        [
            "We do not know",
            "Possibly, but not clearly assessed",
            "Yes, in low-impact ways",
            "Yes, in some important service processes",
            "Yes, in high-impact or sensitive processes",
        ],
        {"ai": "direct", "risk": "direct"},
        "service_impact",
        "Impact assessment and oversight",
        "Impact assessment, human oversight plan, transparency notice",
    ),
    q(
        "q36_human_control",
        "7. Governance, Risk & Privacy",
        "Are high-impact decisions kept under human control?",
        [
            "No clear human control exists",
            "Human control is informal",
            "Human review exists in some cases",
            "Most high-impact decisions are human-controlled",
            "High-impact decisions require clear human accountability and review",
        ],
        {"governance": "direct", "risk": "inverse"},
        "human_control",
        "Human oversight and accountability",
        "Human review framework, decision accountability matrix",
    ),
    q(
        "q37_correction_process",
        "7. Governance, Risk & Privacy",
        "Is there a process for correcting AI-generated errors or challenging AI-supported outputs?",
        [
            "No process exists",
            "Issues are handled case by case",
            "Some correction route exists",
            "Most issues can be escalated and corrected",
            "Clear correction, escalation, and accountability process exists",
        ],
        {"governance": "direct", "risk": "inverse"},
        "correction_process",
        "Correction and escalation process",
        "Correction process, appeals process, issue log",
    ),
    q(
        "q38_staff_confidence",
        "8. People, Adoption & Business Value",
        "How confident are staff in using AI or automation tools responsibly?",
        [
            "Not confident",
            "Low confidence",
            "Mixed confidence",
            "Good confidence in some teams",
            "Strong confidence supported by training and guidance",
        ],
        {"staff": "direct", "governance": "direct", "risk": "inverse"},
        "staff_confidence",
        "Training and change readiness",
        "AI training, change readiness, staff guidance",
    ),
    q(
        "q39_training",
        "8. People, Adoption & Business Value",
        "Has any practical AI or automation training been provided?",
        [
            "No training has been provided",
            "Informal tips only",
            "Some basic awareness training",
            "Practical training for some teams",
            "Role-specific training with guidance and controls",
        ],
        {"staff": "direct", "governance": "direct", "risk": "inverse"},
        "training",
        "Role-based AI and automation training",
        "Role-based AI training, prompting guide, safe-use training",
    ),
    q(
        "q40_investment_appetite",
        "8. People, Adoption & Business Value",
        "If a clear business case existed, how likely is leadership to invest in AI or automation?",
        [
            "Very unlikely",
            "Unlikely without strong pressure",
            "Open to discussion",
            "Likely if benefits are clear",
            "Very likely if value, risk, and cost are clearly presented",
        ],
        {"business_value": "direct"},
        "investment",
        "Business case and pilot roadmap",
        "Business case, ROI estimate, pilot roadmap",
    ),
]


# -----------------------------------------------------------------------------
# Scoring and Intelligence Engine
# -----------------------------------------------------------------------------

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
    buckets = {key: [] for key in SCORE_LABELS.keys()}
    section_buckets = {}

    for question in QUESTIONS:
        raw_score = float(responses.get(question["id"], 0))
        section_buckets.setdefault(question["section"], []).append(raw_score * 10)

        for score_name, mode in question["score_map"].items():
            if score_name in buckets:
                buckets[score_name].append(score_value(raw_score, mode))

    scores = {
        "section_scores": {section: safe_avg(values) for section, values in section_buckets.items()},
        "automation_score": safe_avg(buckets["automation"]),
        "ai_score": safe_avg(buckets["ai"]),
        "process_score": safe_avg(buckets["process"]),
        "data_score": safe_avg(buckets["data"]),
        "systems_score": safe_avg(buckets["systems"]),
        "governance_score": safe_avg(buckets["governance"]),
        "staff_score": safe_avg(buckets["staff"]),
        "business_value_score": safe_avg(buckets["business_value"]),
        "risk_score": safe_avg(buckets["risk"]),
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


def sector_context(sector):
    sector = (sector or "").lower()
    if "care" in sector or "health" in sector:
        return {
            "risk_focus": "service-user data, safeguarding, care quality, confidentiality, and human oversight",
            "language": "For care or health-related organisations, AI should be introduced carefully where personal data or service-user impact is involved.",
        }
    if "education" in sector or "training" in sector:
        return {
            "risk_focus": "learner data, safeguarding, transparency, staff guidance, and human review",
            "language": "For education and training providers, AI use should be controlled where learner data, safeguarding, or assessment support may be involved.",
        }
    if "charity" in sector or "community" in sector:
        return {
            "risk_focus": "limited capacity, volunteer data, funding evidence, safeguarding, and low-cost implementation",
            "language": "For charities and community organisations, the priority is usually practical value, simple governance, and low-cost automation.",
        }
    if "finance" in sector or "regulated" in sector:
        return {
            "risk_focus": "client confidentiality, audit trails, accuracy, regulatory expectations, and human accountability",
            "language": "For regulated organisations, AI and automation should be supported by stronger controls, audit trails, and review responsibilities.",
        }
    if "professional" in sector:
        return {
            "risk_focus": "client confidentiality, quality assurance, knowledge management, document drafting, and review controls",
            "language": "For professional services firms, AI can add value in knowledge work and document-heavy processes, but outputs must be quality-reviewed.",
        }
    return {
        "risk_focus": "privacy, operational risk, staff adoption, data quality, and business value",
        "language": "For SMEs and general organisations, the priority is usually reducing manual work, improving reporting, and introducing safe AI usage rules.",
    }


def answer_band(score):
    score = float(score)
    if score <= 2.5:
        return "low"
    if score == 5:
        return "medium"
    return "high"


def per_answer_interpretation(question, selected_score, sector_note):
    band = answer_band(selected_score)
    theme = question["theme"]

    theme_map = {
        "manual_work": {
            "low": ["Manual workload does not appear to be the main constraint.", "Avoid forcing automation where there is no recurring pain.", "AI should only be explored where there is a specific language or knowledge task.", "The main risk is spending money on unnecessary tools.", "Look for clearer pain points before launching an automation project."],
            "medium": ["There is a moderate level of recurring work that may justify targeted improvement.", "A small workflow or task automation pilot may be suitable.", "AI may help if the manual work includes drafting, classification, summarisation, or searching.", "The risk is overbuilding before the workload is properly measured.", "Measure frequency, time spent, owner, and error rate before choosing a tool."],
            "high": ["Manual work appears to be a major operational constraint.", "This is a strong signal for automation discovery, especially around repeatable tasks, approvals, reminders, and reporting.", "AI may add value where manual work involves text, emails, documents, or knowledge retrieval.", "The risk is ongoing delay, errors, staff overload, and inconsistent service.", "Create an automation opportunity register and select one high-volume, low-risk pilot."],
        },
        "reporting": {
            "low": ["Routine reporting does not appear to be a major burden.", "Reporting automation may not be the first priority.", "AI-generated report commentary is unlikely to be high value unless reporting needs increase.", "The risk is low, provided reports remain accurate and timely.", "Monitor reporting effort but prioritise stronger pain points first."],
            "medium": ["Reporting effort is present and may be worth improving.", "Standard templates, scheduled exports, or dashboard improvements may help.", "AI could support summaries if reports require narrative explanation.", "The risk is inconsistent reporting or hidden manual effort.", "Identify one recurring report and test whether it can be automated."],
            "high": ["Reporting is likely consuming meaningful staff or management time.", "Automated dashboards, scheduled report packs, and standardised data flows are strong candidates.", "AI can add value by creating executive summaries, trend commentary, and exception notes.", "The risk is decision-making based on late, inconsistent, or manually assembled data.", "Prioritise a reporting automation pilot and define the source data, audience, frequency, and success measure."],
        },
        "knowledge_queries": {
            "low": ["Repeated questions do not appear to be a major workload.", "A knowledge assistant may not be the first priority.", "AI should only be used if there is a clear searchable knowledge need.", "The main risk is building a knowledge tool with limited demand.", "Prioritise other automation opportunities first."],
            "medium": ["Repeated questions exist in some areas and may justify a knowledge base.", "Self-service FAQs or structured guidance may reduce interruptions.", "AI may help users find answers from approved documents.", "The risk is inconsistent answers if content is not controlled.", "Start by centralising approved answers before adding AI."],
            "high": ["Repeated questions are creating avoidable workload.", "A knowledge base, enquiry assistant, or staff helpdesk workflow may be valuable.", "AI is highly relevant if users need natural-language answers from approved content.", "The risk is inaccurate answers if AI is connected to uncontrolled or outdated information.", "Create a controlled knowledge base and test an AI assistant using approved content only."],
        },
        "document_creation": {
            "low": ["Manual document creation is not a major workload.", "Template automation may not be urgent.", "AI drafting should be limited to specific low-risk cases.", "The main risk is introducing AI where review effort outweighs benefit.", "Focus on other areas unless document demand grows."],
            "medium": ["Some document creation effort exists and may justify templates.", "Templates, standard forms, and reusable wording may reduce workload.", "AI can help draft first versions, summaries, or variations.", "The risk is using AI-generated text externally without review.", "Start with internal templates and require human review for external documents."],
            "high": ["Document creation appears to be a significant workload.", "Document automation and template workflows are strong candidates.", "AI can help with drafting, summarising, rewriting, classification, and form generation.", "The risk is inaccurate or inappropriate content if outputs are not reviewed.", "Prioritise a controlled drafting workflow with templates, approved prompts, and human review."],
        },
        "shadow_ai": {
            "low": ["There is limited visibility of current AI use.", "Automation may be safer to begin with than AI expansion.", "AI should not be scaled until usage is understood.", "The risk is shadow AI, confidential data exposure, and inconsistent output quality.", "Create an AI usage inventory and ask teams where AI is already being used."],
            "medium": ["Some AI usage is known but may not yet be fully controlled.", "Automation opportunities may exist in the areas where staff already use AI informally.", "AI use cases should be reviewed and converted into approved use cases.", "The risk is partial control and inconsistent human review.", "Document current use cases, tools, data types, and review requirements."],
            "high": ["AI usage appears to be visible and partly controlled.", "This creates a better foundation for scaling safe AI-enabled workflows.", "AI use cases can be formalised where value and controls are clear.", "The risk is lower but ongoing monitoring is still required.", "Move toward an approved AI use-case register with owners, risks, and success measures."],
        },
        "default": {
            "low": ["This answer suggests a low level of maturity or readiness in this area.", "Automation should be approached carefully until the underlying issue is clearer.", "AI should not be scaled without stronger foundations.", "The risk is acting too quickly without the right controls or evidence.", "Start with clarification, ownership, and a small controlled improvement step."],
            "medium": ["This answer suggests partial maturity or a developing capability.", "A focused pilot may be possible if the process, owner, and benefit are clear.", "AI may be useful in a targeted way, but should be reviewed carefully.", "The risk is inconsistency if the approach is not standardised.", "Validate the use case, define controls, and start with a low-risk pilot."],
            "high": ["This answer suggests stronger maturity or readiness in this area.", "Automation may be feasible where it is linked to clear outcomes.", "AI can be explored where data, process, and review controls are sufficient.", "Risk is more manageable, but monitoring and accountability remain important.", "Move toward controlled pilots, clear ownership, and measurable outcomes."],
        },
    }

    row = theme_map.get(theme, theme_map["default"]).get(band, theme_map["default"][band])
    meaning, automation, ai, risk, strategy = row

    if theme in ["sensitive_data", "service_impact", "human_control", "prohibited_data"]:
        risk = f"{risk} Sector-specific focus: {sector_note['risk_focus']}."

    return {
        "meaning": meaning,
        "automation": automation,
        "ai": ai,
        "risk": risk,
        "strategy": strategy,
    }


def generate_question_diagnostics(responses, sector):
    sector_note = sector_context(sector)
    diagnostics = []

    for question in QUESTIONS:
        selected_score = float(responses.get(question["id"], 0))
        selected = get_selected_option(question, selected_score)
        interpretation = per_answer_interpretation(question, selected_score, sector_note)
        evidence = "Strong" if selected_score in [0, 10] else "Moderate" if selected_score in [2.5, 7.5] else "Indicative"

        diagnostics.append({
            "section": question["section"],
            "question": question["question"],
            "answer": selected["label"],
            "score": selected_score,
            "evidence": evidence,
            "meaning": interpretation["meaning"],
            "automation": interpretation["automation"],
            "ai": interpretation["ai"],
            "risk": interpretation["risk"],
            "strategy": interpretation["strategy"],
            "tool_category": question["tool_category"],
            "examples": question["examples"],
        })

    return diagnostics


def detect_patterns(scores, responses):
    patterns = []

    def add(title, evidence, diagnosis, action):
        patterns.append({
            "title": title,
            "evidence": evidence,
            "diagnosis": diagnosis,
            "action": action,
        })

    if scores["automation_score"] >= 65 and scores["process_score"] < 55:
        add(
            "High automation opportunity but weak process readiness",
            "Strong",
            "The organisation appears to have meaningful automation potential, but process clarity may not yet be strong enough for reliable implementation.",
            "Prioritise process mapping before tool selection. Document owners, handoffs, rules, exceptions, and success measures.",
        )

    if scores["ai_score"] >= 60 and scores["risk_score"] >= 60:
        add(
            "AI suitability exists, but risk exposure is high",
            "Strong",
            "AI may create value, but current risk conditions suggest governance, human review, and data controls should come first.",
            "Introduce an AI acceptable use policy, approved tool list, prohibited data guidance, and human review rules before scaling AI use.",
        )

    if float(responses.get("q8_reporting_workload", 0)) >= 7.5 and scores["data_score"] >= 55:
        add(
            "Reporting automation is a strong first candidate",
            "Strong",
            "Reporting workload is high and data readiness appears sufficient to consider an early reporting automation pilot.",
            "Define one recurring report, confirm the source data, automate the report pack, and consider AI-generated commentary.",
        )

    if float(responses.get("q10_repeated_questions", 0)) >= 7.5 and scores["data_score"] >= 50:
        add(
            "Knowledge assistant may be suitable",
            "Moderate",
            "Repeated questions and reasonable data/document readiness suggest a controlled knowledge base or AI assistant may reduce workload.",
            "Centralise approved content first, then test an AI assistant that answers only from controlled sources.",
        )

    if float(responses.get("q27_ai_usage_known", 0)) <= 2.5 and float(responses.get("q32_ai_policy", 0)) <= 2.5:
        add(
            "Shadow AI governance gap",
            "Strong",
            "AI tools may already be used without visibility or policy controls.",
            "Create an AI usage register, acceptable use policy, approved tool list, and prohibited data guidance.",
        )

    if float(responses.get("q25_spreadsheet_reliance", 0)) <= 2.5 and float(responses.get("q6_manual_work", 0)) >= 7.5:
        add(
            "Spreadsheet-heavy manual operation",
            "Strong",
            "Important work may be happening in uncontrolled spreadsheets while manual workload is high.",
            "Review critical spreadsheets and consider controlled workflow apps, dashboards, or lightweight internal tools before AI.",
        )

    if not patterns:
        add(
            "No dominant pattern detected",
            "Indicative",
            "The responses do not show one overwhelming priority. A balanced foundation review may be the right next step.",
            "Clarify objectives, identify top manual processes, review current AI use, and select one low-risk improvement area.",
        )

    return patterns


def detect_contradictions(responses):
    flags = []

    def add(title, evidence, why_it_matters, action):
        flags.append({"title": title, "evidence": evidence, "why": why_it_matters, "action": action})

    if float(responses.get("q27_ai_usage_known", 0)) >= 5 and float(responses.get("q32_ai_policy", 0)) <= 2.5:
        add(
            "AI is being used but policy controls are weak",
            "Strong",
            "Staff may be using AI without clear boundaries on data, review, or accountability.",
            "Create an AI acceptable use policy and approved tool guidance immediately.",
        )

    if float(responses.get("q18_data_reliability", 0)) <= 2.5 and float(responses.get("q5_problem_confidence", 0)) >= 7.5:
        add(
            "Strong AI ambition but weak data reliability",
            "Moderate",
            "The organisation may be ready to act, but poor data may reduce the quality of AI or reporting outputs.",
            "Prioritise data cleanup and ownership before AI decision support or analytics automation.",
        )

    if float(responses.get("q13_process_documentation", 0)) <= 2.5 and float(responses.get("q6_manual_work", 0)) >= 7.5:
        add(
            "High manual workload but weak process documentation",
            "Strong",
            "There may be strong automation demand, but undocumented processes can lead to failed automation.",
            "Map the priority process before implementing workflow automation.",
        )

    if float(responses.get("q22_sensitive_data", 0)) <= 2.5 and float(responses.get("q35_service_user_impact", 0)) >= 7.5:
        add(
            "Sensitive service impact without strong data controls",
            "Strong",
            "AI-supported processes may affect people while sensitive data controls are weak.",
            "Pause high-impact AI use until data classification, human review, and escalation controls are defined.",
        )

    return flags


def evidence_strength_for_recommendation(score, related_scores):
    if score >= 70 and all(item >= 50 for item in related_scores):
        return "Strong"
    if score >= 55:
        return "Moderate"
    return "Indicative"


def generate_recommendations(scores):
    recommendations = []

    def add(title, priority, evidence, text):
        recommendations.append({"title": title, "priority": priority, "evidence": evidence, "text": text})

    if scores["automation_score"] >= 60:
        add(
            "Prioritise automation opportunity discovery",
            "High",
            evidence_strength_for_recommendation(scores["automation_score"], [scores["process_score"], scores["systems_score"]]),
            "There is enough automation signal to justify an opportunity review. Identify repetitive, high-volume, low-risk processes and convert them into a prioritised automation register.",
        )

    if scores["ai_score"] >= 60:
        add(
            "Explore AI-assisted work with controls",
            "Medium",
            evidence_strength_for_recommendation(scores["ai_score"], [scores["governance_score"], 100 - scores["risk_score"]]),
            "AI may be useful for drafting, summarising, knowledge search, classification, reporting commentary, or document support, but should be introduced with human review and data controls.",
        )

    if scores["governance_score"] < 50 or scores["risk_score"] > 60:
        add(
            "Strengthen AI governance before scaling",
            "High",
            "Strong" if scores["risk_score"] > 60 else "Moderate",
            "Introduce an AI acceptable use policy, approved tool list, prohibited data guidance, human review rules, and a simple issue escalation process.",
        )

    if scores["process_score"] < 50:
        add(
            "Map processes before automating",
            "High",
            "Strong",
            "Process clarity is not yet strong enough for reliable automation. Map owners, handoffs, rules, exceptions, and success measures before selecting tools.",
        )

    if scores["data_score"] < 50:
        add(
            "Improve data readiness",
            "High",
            "Strong",
            "Data quality, ownership, access, or classification may limit the success of AI and automation. Start with key datasets and sensitive data controls.",
        )

    if scores["business_value_score"] >= 60:
        add(
            "Create a business case for a first pilot",
            "Medium",
            evidence_strength_for_recommendation(scores["business_value_score"], [scores["automation_score"], scores["process_score"]]),
            "There appears to be enough value potential to justify a first pilot with time-saving, cost, quality, risk, and service improvement assumptions.",
        )

    if not recommendations:
        add(
            "Start with a foundation review",
            "Medium",
            "Indicative",
            "Clarify objectives, map the most painful processes, review current AI use, and identify one low-risk improvement area before buying tools.",
        )

    return recommendations[:7]


def generate_risk_controls(scores, responses, sector):
    sector_note = sector_context(sector)
    risks = []

    def add(risk, severity, control, evidence):
        risks.append({"risk": risk, "severity": severity, "control": control, "evidence": evidence})

    if scores["risk_score"] > 60:
        add(
            "High AI and automation risk exposure",
            "High",
            "Introduce AI usage rules, tool approval, human review, prohibited data guidance, and issue escalation.",
            "Strong",
        )

    if scores["governance_score"] < 50:
        add(
            "Weak governance and accountability",
            "High",
            "Assign AI/automation ownership, create an acceptable-use policy, and define approval and review responsibilities.",
            "Strong",
        )

    if scores["data_score"] < 50:
        add(
            "Poor data quality or weak data ownership",
            "Medium",
            "Identify key datasets, assign owners, clean priority data, and document access rules.",
            "Strong",
        )

    if float(responses.get("q22_sensitive_data", 0)) <= 5:
        add(
            "Sensitive or personal data may not be sufficiently controlled",
            "High",
            f"Classify sensitive data and define what must not be used in public AI tools. Sector focus: {sector_note['risk_focus']}.",
            "Moderate",
        )

    if float(responses.get("q30_ai_output_review", 0)) <= 5:
        add(
            "AI outputs may be used without sufficient human review",
            "High",
            "Define which AI outputs require review before external use or decision support.",
            "Moderate",
        )

    if scores["process_score"] < 50:
        add(
            "Automation failure due to unclear processes",
            "Medium",
            "Map processes, handoffs, rules, and exceptions before implementing automation.",
            "Strong",
        )

    if not risks:
        add(
            "Scaling without monitoring",
            "Medium",
            "Track AI use cases, issues, performance, feedback, and risk controls as adoption increases.",
            "Indicative",
        )

    return risks


def generate_automation_matrix(scores, responses):
    rows = []

    def add(area, suitability, evidence, why, tools, mvp):
        rows.append({"area": area, "suitability": suitability, "evidence": evidence, "why": why, "tools": tools, "mvp": mvp})

    if float(responses.get("q6_manual_work", 0)) >= 7.5 or float(responses.get("q9_manual_followups", 0)) >= 7.5:
        add(
            "Workflow automation",
            "High" if scores["process_score"] >= 50 else "Medium - prepare first",
            "Strong",
            "Manual work, approvals, reminders, or follow-ups appear to create operational friction.",
            "Power Automate, Make, Zapier, n8n, Airtable, Monday.com",
            "Automate one high-volume approval, reminder, task routing, or follow-up process.",
        )

    if float(responses.get("q8_reporting_workload", 0)) >= 5:
        add(
            "Reporting automation",
            "High" if scores["data_score"] >= 50 else "Medium - data cleanup needed",
            "Strong" if float(responses.get("q8_reporting_workload", 0)) >= 7.5 else "Moderate",
            "Routine reporting appears to consume recurring effort.",
            "Power BI, Looker Studio, Tableau, Excel automation",
            "Automate one recurring management report and define standard data sources.",
        )

    if float(responses.get("q7_copy_between_systems", 0)) >= 5 or scores["systems_score"] < 50:
        add(
            "Data handoff automation",
            "Medium",
            "Moderate",
            "Copying information between systems or weak integration may be creating duplication and errors.",
            "Power Automate, Make, Zapier, n8n, API integration",
            "Automate one data handoff between a form, spreadsheet, email, or system.",
        )

    if float(responses.get("q25_spreadsheet_reliance", 0)) <= 5:
        add(
            "Spreadsheet replacement or control",
            "Medium",
            "Moderate",
            "Spreadsheet reliance may indicate uncontrolled operational processes.",
            "Airtable, Power Apps, Retool, internal tools, dashboards",
            "Convert one critical spreadsheet process into a controlled workflow or dashboard.",
        )

    if not rows:
        add(
            "Foundation automation discovery",
            "Low to medium",
            "Indicative",
            "No single automation opportunity dominates the results yet.",
            "Process maps, opportunity register, workflow review",
            "Map the top 3 manual processes and score them before selecting a tool.",
        )

    return rows


def generate_ai_suitability_matrix(scores, responses):
    rows = []

    def add(use_case, suitability, evidence, reason, controls):
        rows.append({"use_case": use_case, "suitability": suitability, "evidence": evidence, "reason": reason, "controls": controls})

    governance_ok = scores["governance_score"] >= 50 and scores["risk_score"] <= 60

    if float(responses.get("q11_document_creation", 0)) >= 5:
        add(
            "AI drafting assistant",
            "High" if governance_ok else "Medium - governance needed",
            "Strong" if float(responses.get("q11_document_creation", 0)) >= 7.5 else "Moderate",
            "Document, email, summary, or form creation appears to consume staff time.",
            "Use approved prompts, templates, and human review before external use.",
        )

    if float(responses.get("q10_repeated_questions", 0)) >= 5:
        add(
            "AI knowledge assistant",
            "High" if scores["data_score"] >= 50 and governance_ok else "Medium - content/control work needed",
            "Strong" if float(responses.get("q10_repeated_questions", 0)) >= 7.5 else "Moderate",
            "Repeated questions suggest value from controlled knowledge retrieval.",
            "Use only approved documents and keep source ownership clear.",
        )

    if float(responses.get("q8_reporting_workload", 0)) >= 5:
        add(
            "AI reporting commentary",
            "High" if scores["data_score"] >= 60 else "Medium - data quality needed",
            "Moderate",
            "Reporting workload suggests AI may help explain trends and summarise key changes.",
            "Keep data sources transparent and require management review of commentary.",
        )

    if float(responses.get("q35_service_user_impact", 0)) >= 7.5:
        add(
            "AI-supported service-user process",
            "Low until validated",
            "Strong",
            "AI may affect customers, learners, patients, clients, or service users.",
            "Require impact assessment, human oversight, escalation, and transparency before implementation.",
        )

    if not rows:
        add(
            "Low-risk internal AI support",
            "Medium",
            "Indicative",
            "No dominant AI use case is strongly indicated yet.",
            "Start with training, safe-use rules, and low-risk internal drafting or summarisation examples.",
        )

    return rows


def implementation_readiness(scores):
    if scores["risk_score"] > 70 or scores["governance_score"] < 35:
        return {
            "rating": "Not ready to scale",
            "reason": "Risk exposure or governance gaps are too high for broad AI or automation rollout.",
            "next_step": "Introduce basic governance, data controls, and human review rules before scaling.",
        }
    if scores["automation_score"] >= 65 and scores["process_score"] < 55:
        return {
            "rating": "Prepare first",
            "reason": "Automation opportunity exists, but process readiness must be improved before implementation.",
            "next_step": "Run a process and automation discovery audit before selecting tools.",
        }
    if scores["automation_score"] >= 60 and scores["process_score"] >= 55 and scores["risk_score"] <= 60:
        return {
            "rating": "Ready to pilot",
            "reason": "The diagnostic indicates a reasonable balance between opportunity and readiness.",
            "next_step": "Select one low-risk pilot with measurable success criteria.",
        }
    return {
        "rating": "Consultancy validation recommended",
        "reason": "There is some potential, but the best first step requires further validation.",
        "next_step": "Validate the findings with stakeholders and review process, data, and tool constraints.",
    }


def first_mvp_recommendation(scores, responses):
    if float(responses.get("q8_reporting_workload", 0)) >= 7.5 and scores["data_score"] >= 50:
        return {
            "name": "Reporting Automation MVP",
            "why": "Reporting workload is high and data readiness appears sufficient for a practical first pilot.",
            "scope": "Automate one recurring report, connect reliable data sources, and add a simple executive summary.",
        }
    if float(responses.get("q9_manual_followups", 0)) >= 7.5 or float(responses.get("q6_manual_work", 0)) >= 7.5:
        return {
            "name": "Workflow Automation MVP",
            "why": "Manual work, reminders, approvals, or handoffs appear to create meaningful operational burden.",
            "scope": "Automate one task routing, approval, reminder, or escalation process with clear ownership and status visibility.",
        }
    if float(responses.get("q10_repeated_questions", 0)) >= 7.5 and scores["data_score"] >= 50:
        return {
            "name": "AI Knowledge Assistant MVP",
            "why": "Repeated questions suggest a self-service knowledge assistant could reduce interruption and improve consistency.",
            "scope": "Create a controlled assistant that answers from approved documents, FAQs, policies, or templates.",
        }
    if scores["governance_score"] < 45 or scores["risk_score"] > 65:
        return {
            "name": "AI Governance Foundation Pack",
            "why": "Risk and governance gaps should be addressed before AI is scaled.",
            "scope": "Create AI acceptable use guidance, approved tool list, prohibited data rules, and human review checklist.",
        }
    return {
        "name": "AI & Automation Foundation Review",
        "why": "No single MVP dominates yet, so the organisation should validate the strongest opportunity before build.",
        "scope": "Map top processes, identify current AI use, review data readiness, and define one prioritised pilot.",
    }


def tailored_roadmap(scores, responses):
    readiness = implementation_readiness(scores)
    mvp = first_mvp_recommendation(scores, responses)

    if readiness["rating"] == "Not ready to scale":
        return [
            {"period": "Days 1-30", "focus": "Governance foundations", "actions": "Create AI acceptable use policy, approved tool list, prohibited data guidance, and human review rules."},
            {"period": "Days 31-60", "focus": "Risk and data controls", "actions": "Classify sensitive data, assign owners, document AI use cases, and define escalation routes."},
            {"period": "Days 61-90", "focus": "Low-risk pilot selection", "actions": "Select one internal low-risk automation or AI support use case and define success measures."},
        ]
    if mvp["name"] == "Reporting Automation MVP":
        return [
            {"period": "Days 1-30", "focus": "Report selection and data validation", "actions": "Select one recurring report, confirm owner, source data, audience, and reporting frequency."},
            {"period": "Days 31-60", "focus": "Dashboard/report automation", "actions": "Build a simple automated report or dashboard and reduce manual preparation effort."},
            {"period": "Days 61-90", "focus": "AI summary and adoption", "actions": "Add reviewed AI-generated commentary and train users on interpretation and review controls."},
        ]
    if mvp["name"] == "Workflow Automation MVP":
        return [
            {"period": "Days 1-30", "focus": "Process mapping", "actions": "Map the selected workflow, owners, handoffs, rules, exceptions, and approval points."},
            {"period": "Days 31-60", "focus": "Automation build", "actions": "Build a small workflow automation covering task routing, reminders, approval, or escalation."},
            {"period": "Days 61-90", "focus": "Pilot and measurement", "actions": "Run the pilot, measure time saved, capture issues, and improve the workflow."},
        ]
    return [
        {"period": "Days 1-30", "focus": "Diagnostic validation", "actions": "Validate findings with stakeholders and confirm top operational pain points."},
        {"period": "Days 31-60", "focus": "Opportunity and risk review", "actions": "Create an opportunity register, risk-to-control map, and shortlist of suitable tool categories."},
        {"period": "Days 61-90", "focus": "First pilot design", "actions": f"Define the scope, measures, and controls for: {mvp['name']}."},
    ]


def recommend_consultancy(scores):
    readiness = implementation_readiness(scores)

    if scores["automation_score"] >= 65 and scores["process_score"] < 55:
        return {
            "name": "Process & Automation Discovery Audit",
            "price": CONSULTANCY_PRICE,
            "duration": "3 days",
            "reason": "There is strong automation potential, but process clarity needs to be validated before solution design.",
            "deliverables": "Process review, automation opportunity register, prioritised roadmap, and first MVP recommendation.",
        }
    if scores["risk_score"] > 60 or scores["governance_score"] < 50:
        return {
            "name": "AI Governance & Safe Adoption Audit",
            "price": CONSULTANCY_PRICE,
            "duration": "3 days",
            "reason": "AI use or AI risk exposure appears to need stronger controls before scaling.",
            "deliverables": "AI usage review, acceptable-use guidance, risk register, governance checklist, and safe adoption roadmap.",
        }
    if readiness["rating"] == "Ready to pilot":
        return {
            "name": "AI & Automation Opportunity Audit",
            "price": CONSULTANCY_PRICE,
            "duration": "3 days",
            "reason": "The organisation appears ready to validate and shape a practical first pilot.",
            "deliverables": "Opportunity register, 30/60/90-day roadmap, business case outline, and first solution design brief.",
        }
    return {
        "name": "AI & Automation Foundation Review",
        "price": CONSULTANCY_PRICE,
        "duration": "3 days",
        "reason": "The organisation would benefit from clarifying objectives, risks, processes, and practical first steps.",
        "deliverables": "Readiness review, gap summary, practical action plan, and prioritised next-step recommendations.",
    }


def diagnostic_confidence(responses, patterns, contradictions):
    answered = len([v for v in responses.values() if v is not None])
    strong_patterns = len([p for p in patterns if p["evidence"] == "Strong"])
    contradictions_count = len(contradictions)

    if answered >= 38 and strong_patterns >= 2 and contradictions_count == 0:
        return {"rating": "High", "reason": "Most questions were answered and the diagnostic pattern is consistent."}
    if answered >= 35 and contradictions_count <= 2:
        return {"rating": "Medium", "reason": "The diagnostic is useful, but stakeholder validation would improve confidence."}
    return {"rating": "Low", "reason": "The result should be validated through discussion because the evidence base is limited or inconsistent."}


def build_intelligence(organisation, responses, scores):
    diagnostics = generate_question_diagnostics(responses, organisation.sector)
    patterns = detect_patterns(scores, responses)
    contradictions = detect_contradictions(responses)
    recommendations = generate_recommendations(scores)
    risk_controls = generate_risk_controls(scores, responses, organisation.sector)
    automation_matrix = generate_automation_matrix(scores, responses)
    ai_matrix = generate_ai_suitability_matrix(scores, responses)
    readiness = implementation_readiness(scores)
    mvp = first_mvp_recommendation(scores, responses)
    roadmap = tailored_roadmap(scores, responses)
    consultancy = recommend_consultancy(scores)
    confidence = diagnostic_confidence(responses, patterns, contradictions)
    sector_note = sector_context(organisation.sector)

    return {
        "diagnostics": diagnostics,
        "patterns": patterns,
        "contradictions": contradictions,
        "recommendations": recommendations,
        "risk_controls": risk_controls,
        "automation_matrix": automation_matrix,
        "ai_matrix": ai_matrix,
        "implementation_readiness": readiness,
        "first_mvp": mvp,
        "roadmap": roadmap,
        "consultancy": consultancy,
        "confidence": confidence,
        "sector_note": sector_note,
    }


# -----------------------------------------------------------------------------
# UI Styling
# -----------------------------------------------------------------------------

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
body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); }
a { color: inherit; text-decoration: none; }
.container { max-width: 1180px; margin: 0 auto; padding: 28px 22px; }
.nav { display: flex; justify-content: space-between; align-items: center; margin-bottom: 42px; gap: 18px; }
.logo { font-weight: 850; letter-spacing: -0.04em; font-size: 22px; color: var(--navy); }
.logo span { color: var(--gold-dark); }
.navlinks { display: flex; gap: 18px; color: var(--muted); font-size: 14px; align-items: center; flex-wrap: wrap; }
.navlinks a:hover { color: var(--navy); }
.hero { display: grid; grid-template-columns: 1.05fr 0.95fr; gap: 48px; align-items: center; padding: 34px 0 56px; }
.badge { display: inline-flex; border: 1px solid #d7c49a; background: #fffaf0; color: #8a6a24; padding: 8px 13px; border-radius: 999px; font-size: 13px; margin-bottom: 20px; font-weight: 650; }
h1 { font-size: 58px; line-height: 1.02; letter-spacing: -0.06em; margin: 0 0 20px; color: var(--navy); }
h2 { font-size: 32px; line-height: 1.15; letter-spacing: -0.04em; margin: 0 0 16px; color: var(--navy); }
h3 { margin: 0 0 10px; color: var(--navy); }
p { color: var(--muted); line-height: 1.65; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 24px; padding: 26px; box-shadow: 0 14px 40px rgba(16, 24, 40, 0.06); }
.soft { background: var(--panel-soft); border: 1px solid #e7e0cf; }
.grid { display: grid; gap: 20px; }
.grid-4 { grid-template-columns: repeat(4, 1fr); }
.grid-3 { grid-template-columns: repeat(3, 1fr); }
.grid-2 { grid-template-columns: repeat(2, 1fr); }
.btn { display: inline-block; background: var(--navy); color: #fff; padding: 13px 18px; border-radius: 12px; font-weight: 750; border: 0; cursor: pointer; }
.btn.gold { background: var(--gold); color: #111827; }
.btn.secondary { background: transparent; color: var(--navy); border: 1px solid var(--line); }
.form-row { margin-bottom: 16px; }
label { display: block; margin-bottom: 8px; color: var(--navy); font-weight: 700; }
input, select, textarea { width: 100%; padding: 13px 14px; border-radius: 12px; border: 1px solid var(--line); background: #fff; color: var(--text); }
.help { font-size: 13px; color: var(--muted); margin-top: 5px; }
.section-title { margin-top: 32px; padding: 14px 16px; background: #fffaf0; border: 1px solid #ead7a3; border-radius: 16px; color: #8a6a24; font-weight: 850; }
.question { border-bottom: 1px solid var(--line); padding: 22px 0; }
.scale { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-top: 12px; }
.scale label { border: 1px solid var(--line); border-radius: 12px; padding: 11px; font-size: 12px; color: var(--muted); cursor: pointer; background: #fff; min-height: 74px; }
.scale label:hover { border-color: var(--gold); background: #fffaf0; }
.scale input { width: auto; margin-right: 6px; }
.score { font-size: 42px; font-weight: 900; letter-spacing: -0.06em; color: var(--navy); }
.muted { color: var(--muted); }
.kpi { border: 1px solid var(--line); border-radius: 18px; padding: 18px; background: #fff; }
.bar { height: 10px; border-radius: 999px; background: #eaecf0; overflow: hidden; }
.fill { height: 100%; background: linear-gradient(90deg, var(--gold), var(--navy)); }
.table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 14px; }
.table th, .table td { border-bottom: 1px solid var(--line); padding: 12px; text-align: left; vertical-align: top; }
.table th { color: var(--navy); font-size: 13px; background: #f9fafb; }
.notice { padding: 15px 17px; border-radius: 14px; background: #fffaf0; border: 1px solid #ead7a3; color: #8a6a24; margin-bottom: 18px; font-weight: 650; }
.price { font-size: 38px; font-weight: 900; letter-spacing: -0.04em; color: var(--navy); }
.tag { display: inline-block; padding: 5px 9px; border-radius: 999px; background: #f2f4f7; color: var(--muted); font-size: 12px; font-weight: 700; }
.tag.high { background: #fef3f2; color: var(--red); }
.tag.good { background: #ecfdf3; color: var(--green); }
.footer { margin-top: 56px; color: var(--muted); font-size: 13px; border-top: 1px solid var(--line); padding-top: 22px; }
@media print { .nav, .footer, .no-print { display: none !important; } body { background: #fff; } .card { box-shadow: none; break-inside: avoid; } .container { max-width: 100%; } }
@media (max-width: 960px) { .hero, .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; } h1 { font-size: 40px; } .scale { grid-template-columns: 1fr; } }
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
      Dissilio AI & Automation Diagnostic v{APP_VERSION}. Outputs are advisory and should be reviewed before legal, compliance, procurement, or investment decisions.
    </div>
  </div>
</body>
</html>
""")


def score_card(title, score, band=None):
    band = band or score_to_band(score)
    return f"""
    <div class="card">
      <h3>{title}</h3>
      <div class="score">{score}</div>
      <p>{band}</p>
      <div class="bar"><div class="fill" style="width:{score}%"></div></div>
    </div>
    """


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------

@app.route("/")
def home():
    body = f"""
    <section class="hero">
      <div>
        <div class="badge">Commercial-grade diagnostic report • v{APP_VERSION}</div>
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
        <h2>Version 2.2 report intelligence</h2>
        <div class="grid grid-2">
          <div class="kpi">Per-answer interpretation</div>
          <div class="kpi">Pattern detection</div>
          <div class="kpi">Contradiction flags</div>
          <div class="kpi">Evidence strength</div>
          <div class="kpi">Implementation readiness</div>
          <div class="kpi">AI suitability matrix</div>
          <div class="kpi">Risk-to-control mapping</div>
          <div class="kpi">First MVP recommendation</div>
        </div>
      </div>
    </section>

    <section class="grid grid-3">
      <div class="card"><h3>Reduce manual work</h3><p>Identify repetitive admin, reporting, approvals, reminders, handoffs, and follow-ups suitable for automation.</p></div>
      <div class="card"><h3>Use AI where it fits</h3><p>Understand where AI can support drafting, summarising, knowledge search, classification, and insight.</p></div>
      <div class="card"><h3>Manage risk early</h3><p>Identify gaps around shadow AI, privacy, human review, AI policy, and governance controls.</p></div>
    </section>

    <section style="margin-top:30px;" class="card">
      <h2>Simple offer structure</h2>
      <table class="table">
        <tr><th>Offer</th><th>Price</th><th>What you get</th></tr>
        <tr><td>Free Snapshot</td><td>£0</td><td>Headline scores, top gaps, top opportunities, and basic AI vs automation guidance.</td></tr>
        <tr><td>Paid Diagnostic Report</td><td>{PAID_PRICE}</td><td>Commercial-grade diagnostic report with matrices, risk controls, contradictions, roadmap, and first MVP recommendation.</td></tr>
        <tr><td>3-Day Consultancy Audit</td><td>{CONSULTANCY_PRICE}</td><td>Human-reviewed roadmap, prioritised opportunity register, stakeholder review, and first MVP scope.</td></tr>
      </table>
    </section>
    """
    return page("Home", body)


@app.route("/how-it-works")
def how_it_works():
    body = f"""
    <div class="card">
      <h1>How it works</h1>
      <p>The diagnostic separates automation opportunities from AI use cases, then assesses whether the organisation is ready to act safely and practically.</p>
    </div>
    <section style="margin-top:24px;" class="grid grid-3">
      <div class="card"><h3>1. Complete the diagnostic</h3><p>Answer 40 practical questions about manual work, process, systems, data, AI usage, governance, people, and value.</p></div>
      <div class="card"><h3>2. Receive a free snapshot</h3><p>See headline scores, top findings, and whether automation, AI, governance, process, or data should come first.</p></div>
      <div class="card"><h3>3. Unlock the {PAID_PRICE} report</h3><p>Get a commercial-grade diagnostic with per-answer interpretation, matrices, contradictions, risk controls, roadmap, and MVP recommendation.</p></div>
      <div class="card"><h3>4. Review tool categories</h3><p>The report shows possible tool categories and examples, but final selection is reserved for consultancy.</p></div>
      <div class="card"><h3>5. Book the audit</h3><p>The {CONSULTANCY_PRICE} audit validates findings and turns them into a practical roadmap and solution design direction.</p></div>
      <div class="card"><h3>6. Build the solution</h3><p>Dissilio can then design and build a practical automation or AI MVP based on the strongest opportunity.</p></div>
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
        <p>A human-reviewed audit for organisations that want to validate their diagnostic results, prioritise realistic opportunities, manage risk, and define the first practical MVP.</p>
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
      <div class="card"><h3>What is included</h3><p>Review of diagnostic results, stakeholder session, process/opportunity validation, AI risk review, prioritised roadmap, and first MVP recommendation.</p></div>
      <div class="card"><h3>What it produces</h3><p>A validated opportunity register, 30/60/90-day roadmap, recommended first project, and build proposal where appropriate.</p></div>
      <div class="card"><h3>What it does not do</h3><p>It does not claim formal legal, regulatory, ISO, or AI assurance certification. It is a practical advisory audit.</p></div>
      <div class="card"><h3>Why it matters</h3><p>Most organisations do not need “AI everywhere.” They need the right mix of process improvement, automation, data readiness, governance, and targeted AI.</p></div>
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
          <div class="form-row"><label>Organisation name</label><input name="name" required placeholder="Example: Horizon Care Services"></div>
          <div class="form-row"><label>Contact name</label><input name="contact_name" required placeholder="Your name"></div>
          <div class="form-row"><label>Contact email</label><input name="contact_email" type="email" required placeholder="name@example.com"></div>
          <div class="form-row"><label>Sector</label><select name="sector" required><option>SME / General Business</option><option>Charity / Community Organisation</option><option>Education / Training Provider</option><option>Healthcare / Care Provider</option><option>Professional Services</option><option>Local Authority / Public Sector</option><option>Finance / Regulated Business</option><option>Other</option></select></div>
          <div class="form-row"><label>Organisation size</label><select name="size" required><option>1–10 staff</option><option>11–50 staff</option><option>51–250 staff</option><option>251–1000 staff</option><option>1000+ staff</option></select></div>
          <div class="form-row"><label>Country</label><input name="country" value="United Kingdom" required></div>
        </div>
        <div class="form-row"><label>Biggest operational pressure right now</label><textarea name="biggest_pressure" rows="3" placeholder="Example: manual reporting, admin workload, repeated enquiries, compliance documentation, slow approvals..."></textarea></div>
        <button class="btn gold" type="submit">Continue to Diagnostic</button>
      </form>
    </div>
    """
    return page("Start", body)


@app.route("/assessment/<int:assessment_id>", methods=["GET", "POST"])
def assessment(assessment_id):
    assessment_record = Assessment.query.get_or_404(assessment_id)

    if request.method == "POST":
        responses = {question["id"]: float(request.form.get(question["id"], 0)) for question in QUESTIONS}
        scores = calculate_scores(responses)
        intelligence = build_intelligence(assessment_record.organisation, responses, scores)

        assessment_record.responses_json = json.dumps(responses)
        assessment_record.scores_json = json.dumps(scores)
        assessment_record.recommendations_json = json.dumps(intelligence["recommendations"])
        assessment_record.risks_json = json.dumps(intelligence["risk_controls"])
        assessment_record.opportunities_json = json.dumps(intelligence["automation_matrix"])
        assessment_record.intelligence_json = json.dumps(intelligence)
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
      <p>Organisation: <strong>{assessment_record.organisation.name}</strong><br>Choose the answer that best reflects the current situation. There are no right or wrong answers.</p>
      <form method="post">
        {question_html}
        <div style="margin-top:24px;"><button class="btn gold" type="submit">Generate Free Snapshot</button></div>
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
    intelligence = json.loads(assessment_record.intelligence_json or "{}")
    recs = intelligence.get("recommendations", [])
    opportunities = intelligence.get("automation_matrix", [])
    readiness = intelligence.get("implementation_readiness", {})
    mvp = intelligence.get("first_mvp", {})
    confidence = intelligence.get("confidence", {})

    rec_html = "".join([f"<div class='kpi'><strong>{r['title']}</strong><br><span class='muted'>Priority: {r['priority']} • Evidence: {r['evidence']}</span><p>{r['text']}</p></div>" for r in recs[:3]])
    opp_html = "".join([f"<div class='kpi'><strong>{o['area']}</strong><br><span class='muted'>Suitability: {o['suitability']} • Evidence: {o['evidence']}</span><p>{o['why']}</p></div>" for o in opportunities[:3]])

    body = f"""
    <div class="notice">Free snapshot generated. Unlock the {PAID_PRICE} paid report for the full commercial-grade diagnostic, matrices, risk controls, contradictions, roadmap, and first MVP recommendation.</div>
    <section class="grid grid-4">
      {score_card('Overall', scores['overall_score'])}
      {score_card('Automation', scores['automation_score'])}
      {score_card('AI Suitability', scores['ai_score'])}
      {score_card('Risk Exposure', scores['risk_score'], risk_band(scores['risk_score']))}
    </section>
    <section style="margin-top:24px;" class="grid grid-2">
      <div class="card"><h2>Implementation readiness</h2><h3>{readiness.get('rating', 'N/A')}</h3><p>{readiness.get('reason', '')}</p><p><strong>Next step:</strong> {readiness.get('next_step', '')}</p></div>
      <div class="card"><h2>First suggested MVP</h2><h3>{mvp.get('name', 'N/A')}</h3><p>{mvp.get('why', '')}</p><p><strong>Scope:</strong> {mvp.get('scope', '')}</p></div>
    </section>
    <section style="margin-top:24px;" class="card"><h2>Diagnostic confidence</h2><h3>{confidence.get('rating', 'N/A')}</h3><p>{confidence.get('reason', '')}</p></section>
    <section style="margin-top:24px;" class="grid grid-2"><div class="card"><h2>Top recommendations</h2><div class="grid">{rec_html}</div></div><div class="card"><h2>Top opportunity areas</h2><div class="grid">{opp_html}</div></div></section>
    <section style="margin-top:24px;" class="card no-print"><h2>Unlock the paid diagnostic report — {PAID_PRICE}</h2><p>The paid report includes the full score dashboard, pattern detection, contradiction flags, automation matrix, AI suitability matrix, risk-to-control map, tailored roadmap, question-by-question interpretation, and consultancy pathway.</p><a class="btn gold" href="/unlock/{assessment_record.id}">Simulate {PAID_PRICE} Report Unlock</a> <a class="btn secondary" href="/report/{assessment_record.id}">View Report</a></section>
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
        <div class="card"><h1>Paid report locked</h1><p>The full diagnostic report is available after payment. This MVP uses a simulated unlock.</p><a class="btn gold" href="/unlock/{assessment_record.id}">Simulate {PAID_PRICE} Unlock</a> <a class="btn secondary" href="/results/{assessment_record.id}">Back to Free Snapshot</a></div>
        """
        return page("Report Locked", body)

    scores = json.loads(assessment_record.scores_json)
    intelligence = json.loads(assessment_record.intelligence_json or "{}")

    score_rows = "".join([
        f"<tr><td>Overall Diagnostic Score</td><td>{scores['overall_score']}/100</td><td>{score_to_band(scores['overall_score'])}</td></tr>",
        f"<tr><td>Automation Opportunity</td><td>{scores['automation_score']}/100</td><td>{score_to_band(scores['automation_score'])}</td></tr>",
        f"<tr><td>AI Suitability</td><td>{scores['ai_score']}/100</td><td>{score_to_band(scores['ai_score'])}</td></tr>",
        f"<tr><td>Process Readiness</td><td>{scores['process_score']}/100</td><td>{score_to_band(scores['process_score'])}</td></tr>",
        f"<tr><td>Data Readiness</td><td>{scores['data_score']}/100</td><td>{score_to_band(scores['data_score'])}</td></tr>",
        f"<tr><td>Systems Readiness</td><td>{scores['systems_score']}/100</td><td>{score_to_band(scores['systems_score'])}</td></tr>",
        f"<tr><td>Governance Maturity</td><td>{scores['governance_score']}/100</td><td>{score_to_band(scores['governance_score'])}</td></tr>",
        f"<tr><td>Staff Readiness</td><td>{scores['staff_score']}/100</td><td>{score_to_band(scores['staff_score'])}</td></tr>",
        f"<tr><td>Business Value Potential</td><td>{scores['business_value_score']}/100</td><td>{score_to_band(scores['business_value_score'])}</td></tr>",
        f"<tr><td>Risk Exposure</td><td>{scores['risk_score']}/100</td><td>{risk_band(scores['risk_score'])}</td></tr>",
    ])

    patterns_rows = "".join([f"<tr><td>{p['title']}</td><td>{p['evidence']}</td><td>{p['diagnosis']}</td><td>{p['action']}</td></tr>" for p in intelligence.get("patterns", [])])
    contradiction_rows = "".join([f"<tr><td>{c['title']}</td><td>{c['evidence']}</td><td>{c['why']}</td><td>{c['action']}</td></tr>" for c in intelligence.get("contradictions", [])]) or "<tr><td colspan='4'>No major contradictions detected in the response pattern.</td></tr>"
    rec_rows = "".join([f"<tr><td>{r['title']}</td><td>{r['priority']}</td><td>{r['evidence']}</td><td>{r['text']}</td></tr>" for r in intelligence.get("recommendations", [])])
    risk_rows = "".join([f"<tr><td>{r['risk']}</td><td>{r['severity']}</td><td>{r['evidence']}</td><td>{r['control']}</td></tr>" for r in intelligence.get("risk_controls", [])])
    auto_rows = "".join([f"<tr><td>{o['area']}</td><td>{o['suitability']}</td><td>{o['evidence']}</td><td>{o['why']}</td><td>{o['tools']}</td><td>{o['mvp']}</td></tr>" for o in intelligence.get("automation_matrix", [])])
    ai_rows = "".join([f"<tr><td>{a['use_case']}</td><td>{a['suitability']}</td><td>{a['evidence']}</td><td>{a['reason']}</td><td>{a['controls']}</td></tr>" for a in intelligence.get("ai_matrix", [])])
    roadmap_rows = "".join([f"<tr><td>{r['period']}</td><td>{r['focus']}</td><td>{r['actions']}</td></tr>" for r in intelligence.get("roadmap", [])])
    diag_rows = "".join([f"<tr><td><strong>{d['section']}</strong><br>{d['question']}</td><td>{d['answer']}</td><td>{d['evidence']}</td><td>{d['meaning']}</td><td>{d['automation']}</td><td>{d['ai']}</td><td>{d['risk']}</td><td>{d['strategy']}<br><br><span class='muted'><strong>Tool category:</strong> {d['tool_category']}<br><strong>Examples:</strong> {d['examples']}</span></td></tr>" for d in intelligence.get("diagnostics", [])])

    readiness = intelligence.get("implementation_readiness", {})
    mvp = intelligence.get("first_mvp", {})
    consultancy = intelligence.get("consultancy", {})
    confidence = intelligence.get("confidence", {})
    sector_note = intelligence.get("sector_note", {})

    body = f"""
    <div class="card"><h1>Commercial-Grade AI & Automation Diagnostic Report</h1><p>Organisation: <strong>{assessment_record.organisation.name}</strong><br>Sector: {assessment_record.organisation.sector}<br>Size: {assessment_record.organisation.size}<br>Completed: {assessment_record.completed_at.strftime('%d %b %Y') if assessment_record.completed_at else 'N/A'}</p><button class="btn secondary no-print" onclick="window.print()">Print / Save as PDF</button></div>
    <section style="margin-top:24px;" class="card"><h2>Executive Summary</h2><p>The organisation achieved an overall diagnostic score of <strong>{scores['overall_score']}/100</strong>. Automation opportunity is <strong>{scores['automation_score']}/100</strong>, AI suitability is <strong>{scores['ai_score']}/100</strong>, and risk exposure is <strong>{scores['risk_score']}/100</strong>.</p><p>{sector_note.get('language', '')}</p><p><strong>Implementation readiness:</strong> {readiness.get('rating', 'N/A')} — {readiness.get('reason', '')}</p><p><strong>First recommended MVP:</strong> {mvp.get('name', 'N/A')} — {mvp.get('why', '')}</p><p><strong>Diagnostic confidence:</strong> {confidence.get('rating', 'N/A')} — {confidence.get('reason', '')}</p></section>
    <section style="margin-top:24px;" class="card"><h2>Score Dashboard</h2><table class="table"><tr><th>Score</th><th>Result</th><th>Band</th></tr>{score_rows}</table></section>
    <section style="margin-top:24px;" class="card"><h2>Detected Patterns</h2><table class="table"><tr><th>Pattern</th><th>Evidence</th><th>Diagnosis</th><th>Recommended Action</th></tr>{patterns_rows}</table></section>
    <section style="margin-top:24px;" class="card"><h2>Contradiction / Mismatch Flags</h2><table class="table"><tr><th>Flag</th><th>Evidence</th><th>Why it matters</th><th>Recommended Action</th></tr>{contradiction_rows}</table></section>
    <section style="margin-top:24px;" class="card"><h2>Recommended Actions</h2><table class="table"><tr><th>Recommendation</th><th>Priority</th><th>Evidence</th><th>Details</th></tr>{rec_rows}</table></section>
    <section style="margin-top:24px;" class="card"><h2>Automation Opportunity Matrix</h2><table class="table"><tr><th>Area</th><th>Suitability</th><th>Evidence</th><th>Why</th><th>Tool Category / Examples</th><th>Suggested MVP</th></tr>{auto_rows}</table><p class="muted">Tool examples are illustrative categories only. Final tool selection should be handled through consultancy after reviewing systems, data sensitivity, budget, permissions, and integrations.</p></section>
    <section style="margin-top:24px;" class="card"><h2>AI Suitability Matrix</h2><table class="table"><tr><th>Use Case</th><th>Suitability</th><th>Evidence</th><th>Reason</th><th>Controls Required</th></tr>{ai_rows}</table></section>
    <section style="margin-top:24px;" class="card"><h2>Risk-to-Control Map</h2><table class="table"><tr><th>Risk</th><th>Severity</th><th>Evidence</th><th>Recommended Control</th></tr>{risk_rows}</table></section>
    <section style="margin-top:24px;" class="card"><h2>Tailored 30/60/90-Day Roadmap</h2><table class="table"><tr><th>Period</th><th>Focus</th><th>Actions</th></tr>{roadmap_rows}</table></section>
    <section style="margin-top:24px;" class="card"><h2>Question-by-Question Diagnostic</h2><table class="table"><tr><th>Question</th><th>Selected Answer</th><th>Evidence</th><th>What this means</th><th>Automation implication</th><th>AI implication</th><th>Risk implication</th><th>Recommended strategy</th></tr>{diag_rows}</table></section>
    <section style="margin-top:24px;" class="card"><h2>Recommended Consultancy Pathway</h2><div class="kpi"><h3>{consultancy.get('name', 'AI & Automation Opportunity Audit')} — {consultancy.get('price', CONSULTANCY_PRICE)}</h3><p><strong>Duration:</strong> {consultancy.get('duration', '3 days')}</p><p><strong>Why this is recommended:</strong> {consultancy.get('reason', '')}</p><p><strong>Deliverables:</strong> {consultancy.get('deliverables', '')}</p></div></section>
    """
    return page("Paid Report", body)


@app.route("/admin")
def admin():
    admin_pass = request.args.get("pass")
    if admin_pass != ADMIN_PASS:
        body = """
        <div class="card"><h1>Admin Access</h1><p>Append <code>?pass=dissilio-admin</code> to the URL for MVP admin access.</p><p>In production, replace this with secure authentication and role-based access control.</p></div>
        """
        return page("Admin", body)

    assessments = Assessment.query.order_by(Assessment.created_at.desc()).all()
    rows = ""
    for item in assessments:
        score = "N/A"
        risk = "N/A"
        readiness = "N/A"
        if item.scores_json:
            parsed = json.loads(item.scores_json)
            score = parsed.get("overall_score", "N/A")
            risk = parsed.get("risk_score", "N/A")
        if item.intelligence_json:
            intel = json.loads(item.intelligence_json)
            readiness = intel.get("implementation_readiness", {}).get("rating", "N/A")
        rows += f"""
        <tr><td>{item.id}</td><td>{item.organisation.name}</td><td>{item.organisation.sector}</td><td>{item.organisation.contact_email}</td><td>{item.status}</td><td>{item.tier}</td><td>{'Yes' if item.is_paid else 'No'}</td><td>{score}</td><td>{risk}</td><td>{readiness}</td><td><a href="/results/{item.id}">Snapshot</a> | <a href="/report/{item.id}">Report</a></td></tr>
        """

    body = f"""
    <div class="card"><h1>Admin Pipeline</h1><p>Review diagnostics, paid status, scores, readiness, and potential consultancy leads.</p><table class="table"><tr><th>ID</th><th>Organisation</th><th>Sector</th><th>Email</th><th>Status</th><th>Tier</th><th>Paid</th><th>Overall</th><th>Risk</th><th>Readiness</th><th>Actions</th></tr>{rows}</table></div>
    """
    return page("Admin", body)


@app.errorhandler(404)
def not_found(e):
    return page("Not Found", "<div class='card'><h1>Page not found</h1><a class='btn' href='/'>Go Home</a></div>"), 404


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
