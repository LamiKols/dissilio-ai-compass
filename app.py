import os
import json
from datetime import datetime
from statistics import mean

from flask import Flask, request, redirect, url_for, render_template_string
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# For Replit MVP testing, SQLite is easiest.
# If Replit has a DATABASE_URL set, we ignore it unless USE_DATABASE_URL=true.
if os.environ.get("USE_DATABASE_URL") == "true":
    database_uri = os.environ.get("DATABASE_URL", "sqlite:///dissilio_ai_compass.db")
else:
    database_uri = "sqlite:///dissilio_ai_compass.db"

app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

APP_NAME = "Dissilio AI Compass"


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
# Response Scale Labels
# ----------------------------

DEFAULT_SCORE_LABELS = {
    0: "No / Not in place",
    1: "Very limited",
    2: "Partially in place",
    3: "Mostly in place",
    4: "Fully in place",
}

SCALE_LABELS_BY_TYPE = {
    "control": {
        0: "No / Not in place",
        1: "Very limited",
        2: "Partially in place",
        3: "Mostly in place",
        4: "Fully in place",
    },
    "awareness": {
        0: "No awareness",
        1: "Low awareness",
        2: "Basic awareness",
        3: "Good awareness",
        4: "Strong awareness",
    },
    "opportunity": {
        0: "No opportunity",
        1: "Low opportunity",
        2: "Moderate opportunity",
        3: "High opportunity",
        4: "Very high opportunity",
    },
    "manual_workload": {
        0: "None",
        1: "Very few",
        2: "Some",
        3: "Many",
        4: "Extensive",
    },
    "data_quality": {
        0: "Poor / unreliable",
        1: "Limited quality",
        2: "Reasonable but inconsistent",
        3: "Mostly reliable",
        4: "Structured and reliable",
    },
    "investment": {
        0: "No appetite",
        1: "Low appetite",
        2: "Open to discussion",
        3: "Likely with a clear case",
        4: "Strong appetite",
    },
    "human_review": {
        0: "Never required",
        1: "Rarely required",
        2: "Sometimes required",
        3: "Usually required",
        4: "Always required",
    },
}


# ----------------------------
# Assessment Question Bank
# ----------------------------

QUESTIONS = [
    {
        "id": "strategy_1",
        "category": "Strategy & Leadership",
        "question": "Does your organisation have clear objectives for using AI?",
        "helper": "This checks whether AI is linked to business goals rather than experimentation only.",
        "scale_type": "control",
        "score_use": "readiness",
    },
    {
        "id": "strategy_2",
        "category": "Strategy & Leadership",
        "question": "Is there a senior owner or sponsor responsible for AI adoption?",
        "helper": "Strong ownership reduces fragmented or unmanaged AI adoption.",
        "scale_type": "control",
        "score_use": "readiness",
    },
    {
        "id": "usage_1",
        "category": "Current AI Usage",
        "question": "Do you know which AI tools your staff currently use?",
        "helper": "This helps identify shadow AI and unmanaged tool usage.",
        "scale_type": "control",
        "score_use": "governance",
    },
    {
        "id": "usage_2",
        "category": "Current AI Usage",
        "question": "Are AI tools being used consistently across departments?",
        "helper": "Consistency helps standardise value, controls, and training.",
        "scale_type": "control",
        "score_use": "maturity",
    },
    {
        "id": "process_1",
        "category": "Business Processes",
        "question": "Have your key business processes been documented or mapped?",
        "helper": "AI works best when processes are understood before automation.",
        "scale_type": "control",
        "score_use": "readiness",
    },
    {
        "id": "process_2",
        "category": "Business Processes",
        "question": "How many repetitive manual tasks consume significant staff time?",
        "helper": "High manual workload often indicates strong automation potential.",
        "scale_type": "manual_workload",
        "score_use": "opportunity",
    },
    {
        "id": "data_1",
        "category": "Data Readiness",
        "question": "How would you rate the quality and reliability of your business data?",
        "helper": "Poor data quality reduces the reliability of AI outputs.",
        "scale_type": "data_quality",
        "score_use": "readiness",
    },
    {
        "id": "data_2",
        "category": "Data Readiness",
        "question": "Do you know who owns key datasets in your organisation?",
        "helper": "Data ownership is essential for governance and accountability.",
        "scale_type": "control",
        "score_use": "readiness",
    },
    {
        "id": "systems_1",
        "category": "Systems & Technology",
        "question": "Are your core systems cloud-based or integration-friendly?",
        "helper": "Integration-friendly systems make AI and automation easier to implement.",
        "scale_type": "control",
        "score_use": "readiness",
    },
    {
        "id": "systems_2",
        "category": "Systems & Technology",
        "question": "Can your existing systems export reports or data reliably?",
        "helper": "Reliable exports are often the first step toward AI-enabled reporting.",
        "scale_type": "control",
        "score_use": "readiness",
    },
    {
        "id": "governance_1",
        "category": "Governance & Compliance",
        "question": "Do you have an AI acceptable use policy?",
        "helper": "An AI policy helps staff understand safe and approved use.",
        "scale_type": "control",
        "score_use": "governance",
    },
    {
        "id": "governance_2",
        "category": "Governance & Compliance",
        "question": "Do you review AI use for privacy, security, or compliance risk?",
        "helper": "This is important where sensitive business or personal data is involved.",
        "scale_type": "control",
        "score_use": "governance",
    },
    {
        "id": "security_1",
        "category": "Security & Privacy",
        "question": "Are staff trained not to enter confidential or personal data into public AI tools?",
        "helper": "This reduces data leakage and privacy risk.",
        "scale_type": "control",
        "score_use": "governance",
    },
    {
        "id": "security_2",
        "category": "Security & Privacy",
        "question": "Do you have access controls for systems containing sensitive data?",
        "helper": "AI adoption increases the need for good access control.",
        "scale_type": "control",
        "score_use": "governance",
    },
    {
        "id": "people_1",
        "category": "Staff Capability",
        "question": "How aware are staff of how AI could support their role?",
        "helper": "Low awareness can block adoption and increase misuse.",
        "scale_type": "awareness",
        "score_use": "maturity",
    },
    {
        "id": "people_2",
        "category": "Staff Capability",
        "question": "Have staff received practical AI training or guidance?",
        "helper": "Training improves productivity and reduces uncontrolled usage.",
        "scale_type": "control",
        "score_use": "readiness",
    },
    {
        "id": "impact_1",
        "category": "Customer / Service Impact",
        "question": "How much opportunity is there for AI to improve your customer, learner, patient, or service-user experience?",
        "helper": "This checks whether AI can improve service quality, speed, or consistency.",
        "scale_type": "opportunity",
        "score_use": "value",
    },
    {
        "id": "impact_2",
        "category": "Customer / Service Impact",
        "question": "How often would AI outputs require human review before being used with customers or service users?",
        "helper": "Frequent need for human review can indicate higher impact and higher control requirements.",
        "scale_type": "human_review",
        "score_use": "risk",
    },
    {
        "id": "value_1",
        "category": "Financial Value Potential",
        "question": "How much opportunity is there for AI to save cost, reduce admin, or increase revenue?",
        "helper": "Clear value areas make the business case stronger.",
        "scale_type": "opportunity",
        "score_use": "value",
    },
    {
        "id": "value_2",
        "category": "Financial Value Potential",
        "question": "How likely is leadership to invest in AI if a clear business case is produced?",
        "helper": "Budget appetite helps determine whether to recommend a roadmap or smaller pilot.",
        "scale_type": "investment",
        "score_use": "value",
    },
]


# ----------------------------
# Scoring Logic
# ----------------------------

def normalise(value):
    return round((int(value) / 4) * 100)


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


def safe_average(values):
    return round(mean(values)) if values else 0


def calculate_scores(responses):
    category_values = {}

    readiness_values = []
    maturity_values = []
    governance_values = []
    data_values = []
    opportunity_values = []
    value_values = []
    risk_exposure_values = []

    for q in QUESTIONS:
        raw_value = int(responses.get(q["id"], 0))
        normalised = normalise(raw_value)
        category_values.setdefault(q["category"], []).append(normalised)

        score_use = q.get("score_use", "readiness")

        if score_use == "readiness":
            readiness_values.append(normalised)

        if score_use == "maturity":
            maturity_values.append(normalised)

        if score_use == "governance":
            governance_values.append(normalised)

        if q["category"] == "Data Readiness":
            data_values.append(normalised)

        if score_use == "opportunity":
            opportunity_values.append(normalised)

        if score_use == "value":
            value_values.append(normalised)

        # Risk logic:
        # Weak controls increase risk.
        # Higher human-review requirement increases risk.
        if score_use == "governance":
            risk_exposure_values.append(100 - normalised)

        if score_use == "risk":
            risk_exposure_values.append(normalised)

        if q["id"] == "usage_1":
            risk_exposure_values.append(100 - normalised)

    category_scores = {
        category: safe_average(values)
        for category, values in category_values.items()
    }

    ai_readiness_score = safe_average(readiness_values + governance_values + maturity_values)
    ai_maturity_score = safe_average(maturity_values + governance_values)
    data_readiness_score = safe_average(data_values)
    governance_maturity_score = safe_average(governance_values)
    automation_opportunity_score = safe_average(opportunity_values)
    business_value_potential_score = safe_average(value_values + opportunity_values)
    ai_risk_score = safe_average(risk_exposure_values)

    return {
        "category_scores": category_scores,
        "ai_readiness_score": ai_readiness_score,
        "ai_maturity_score": ai_maturity_score,
        "ai_risk_score": ai_risk_score,
        "data_readiness_score": data_readiness_score,
        "governance_maturity_score": governance_maturity_score,
        "automation_opportunity_score": automation_opportunity_score,
        "business_value_potential_score": business_value_potential_score,
    }


def generate_recommendations(scores):
    recs = []

    if scores["ai_readiness_score"] < 50:
        recs.append({
            "title": "Create an AI adoption baseline",
            "priority": "High",
            "text": "Define business objectives, owners, priority use cases, and minimum governance controls before investing heavily in AI tools."
        })
    else:
        recs.append({
            "title": "Move from exploration to controlled pilots",
            "priority": "Medium",
            "text": "Your organisation has enough baseline readiness to identify two or three controlled AI pilots with clear success measures."
        })

    if scores["ai_risk_score"] > 60:
        recs.append({
            "title": "Reduce AI governance and privacy exposure",
            "priority": "High",
            "text": "Introduce an AI acceptable use policy, staff guidance, tool approval process, and controls for confidential data."
        })

    if scores["automation_opportunity_score"] >= 50:
        recs.append({
            "title": "Prioritise automation opportunities",
            "priority": "High",
            "text": "Map repetitive administrative processes and select one low-risk, high-frequency workflow for an AI automation pilot."
        })
    else:
        recs.append({
            "title": "Improve process clarity before automation",
            "priority": "Medium",
            "text": "The assessment suggests there may not yet be enough process clarity or automation demand to start building immediately."
        })

    if scores["data_readiness_score"] < 50:
        recs.append({
            "title": "Improve data readiness",
            "priority": "High",
            "text": "Identify key data owners, clean critical data sources, and define rules for data access before using AI for reporting or decision support."
        })

    if scores["business_value_potential_score"] >= 60:
        recs.append({
            "title": "Build an AI business case",
            "priority": "Medium",
            "text": "There is enough value potential to create a business case covering savings, productivity gains, implementation cost, and risk controls."
        })

    return recs


def generate_risks(scores):
    risks = []

    if scores["ai_risk_score"] > 60:
        risks.append({
            "title": "Unmanaged AI usage",
            "severity": "High",
            "likelihood": "Medium",
            "mitigation": "Create an AI usage register, acceptable use policy, and approved tool list."
        })

    if scores["governance_maturity_score"] < 50:
        risks.append({
            "title": "Weak AI governance controls",
            "severity": "High",
            "likelihood": "Medium",
            "mitigation": "Assign AI ownership, define review steps, and introduce a governance checklist."
        })

    if scores["data_readiness_score"] < 50:
        risks.append({
            "title": "Poor data quality affecting AI outputs",
            "severity": "Medium",
            "likelihood": "High",
            "mitigation": "Clean priority datasets and define data owners before AI implementation."
        })

    if not risks:
        risks.append({
            "title": "Scaling AI without continuous monitoring",
            "severity": "Medium",
            "likelihood": "Medium",
            "mitigation": "Track AI use cases, performance, user feedback, and risk controls as adoption increases."
        })

    return risks


def generate_opportunities(scores):
    opportunities = []

    if scores["automation_opportunity_score"] >= 50:
        opportunities.append({
            "title": "AI workflow automation pilot",
            "area": "Operations / Administration",
            "value": "Reduce manual effort and improve consistency",
            "complexity": "Medium",
            "mvp": "Build a small AI assistant that processes repetitive requests, drafts outputs, or summarises records."
        })

    if scores["business_value_potential_score"] >= 50:
        opportunities.append({
            "title": "AI reporting assistant",
            "area": "Management / Reporting",
            "value": "Improve visibility and reduce time spent producing manual reports",
            "complexity": "Low to Medium",
            "mvp": "Connect structured inputs to a dashboard and AI-generated executive summaries."
        })

    if scores["data_readiness_score"] >= 50:
        opportunities.append({
            "title": "AI knowledge base assistant",
            "area": "Internal Support",
            "value": "Help staff find policies, procedures, templates, and guidance faster",
            "complexity": "Medium",
            "mvp": "Create a controlled document-based assistant using approved internal content."
        })

    if not opportunities:
        opportunities.append({
            "title": "AI readiness foundation project",
            "area": "Strategy / Governance",
            "value": "Prepare the organisation for safe and practical AI adoption",
            "complexity": "Low",
            "mvp": "Create AI policy, staff guidance, process inventory, and first-use-case shortlist."
        })

    return opportunities


# ----------------------------
# UI Styling
# ----------------------------

BASE_CSS = """
<style>
:root {
  --bg: #0b1020;
  --card: #111936;
  --muted: #94a3b8;
  --text: #f8fafc;
  --line: rgba(255,255,255,0.12);
  --accent: #bfa46f;
  --accent2: #38bdf8;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: radial-gradient(circle at top left, #1e293b, #0b1020 45%, #050816 100%);
  color: var(--text);
}
a { color: inherit; text-decoration: none; }
.container { max-width: 1120px; margin: 0 auto; padding: 32px 20px; }
.nav { display: flex; justify-content: space-between; align-items: center; margin-bottom: 42px; }
.logo { font-weight: 800; letter-spacing: -0.04em; font-size: 22px; }
.logo span { color: var(--accent); }
.navlinks { display: flex; gap: 16px; color: var(--muted); font-size: 14px; }
.hero { display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 32px; align-items: center; padding: 32px 0 48px; }
.badge { display: inline-flex; border: 1px solid var(--line); padding: 8px 12px; border-radius: 999px; color: var(--accent); font-size: 13px; margin-bottom: 18px; }
h1 { font-size: 56px; line-height: 1.02; letter-spacing: -0.06em; margin: 0 0 18px; }
h2 { font-size: 32px; letter-spacing: -0.04em; margin: 0 0 16px; }
h3 { margin: 0 0 10px; }
p { color: var(--muted); line-height: 1.65; }
.card {
  background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.035));
  border: 1px solid var(--line);
  border-radius: 24px;
  padding: 24px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.28);
}
.grid { display: grid; gap: 20px; }
.grid-3 { grid-template-columns: repeat(3, 1fr); }
.grid-2 { grid-template-columns: repeat(2, 1fr); }
.btn {
  display: inline-block;
  background: var(--accent);
  color: #111;
  padding: 13px 18px;
  border-radius: 12px;
  font-weight: 700;
  border: 0;
  cursor: pointer;
}
.btn.secondary {
  background: transparent;
  color: var(--text);
  border: 1px solid var(--line);
}
.form-row { margin-bottom: 16px; }
label { display: block; margin-bottom: 8px; color: #e2e8f0; font-weight: 650; }
input, select {
  width: 100%;
  padding: 13px 14px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.06);
  color: var(--text);
}
option { color: #111; }
.help { font-size: 13px; color: var(--muted); margin-top: 5px; }
.question {
  border-bottom: 1px solid var(--line);
  padding: 20px 0;
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
  padding: 10px;
  font-size: 12px;
  color: var(--muted);
  cursor: pointer;
}
.scale input { width: auto; margin-right: 6px; }
.score {
  font-size: 46px;
  font-weight: 900;
  letter-spacing: -0.06em;
}
.muted { color: var(--muted); }
.kpi {
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 18px;
  background: rgba(255,255,255,0.04);
}
.bar {
  height: 10px;
  border-radius: 999px;
  background: rgba(255,255,255,0.10);
  overflow: hidden;
}
.fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--accent2));
}
.table { width: 100%; border-collapse: collapse; margin-top: 12px; }
.table th, .table td { border-bottom: 1px solid var(--line); padding: 12px; text-align: left; vertical-align: top; }
.table th { color: #e2e8f0; font-size: 13px; }
.notice {
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(191,164,111,0.12);
  border: 1px solid rgba(191,164,111,0.30);
  color: #fde68a;
  margin-bottom: 18px;
}
.footer { margin-top: 48px; color: var(--muted); font-size: 13px; border-top: 1px solid var(--line); padding-top: 22px; }
@media (max-width: 820px) {
  .hero, .grid-2, .grid-3 { grid-template-columns: 1fr; }
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
      <a class="logo" href="/"><span>Dissilio</span> AI Compass</a>
      <div class="navlinks">
        <a href="/">Home</a>
        <a href="/start">Start Assessment</a>
        <a href="/admin">Admin</a>
      </div>
    </div>
    {body}
    <div class="footer">
      Dissilio AI Compass MVP. Outputs are advisory and should be reviewed before making legal, compliance, or investment decisions.
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
    body = """
    <section class="hero">
      <div>
        <div class="badge">AI readiness • risk • opportunity discovery</div>
        <h1>Find out if your organisation is ready for AI.</h1>
        <p>
          Complete a practical AI readiness assessment and discover your maturity score,
          governance gaps, automation opportunities, and next best actions.
        </p>
        <p>
          Built as a product-led consultancy engine for organisations that want to adopt AI safely,
          practically, and commercially.
        </p>
        <div style="display:flex; gap:12px; margin-top:24px; flex-wrap:wrap;">
          <a class="btn" href="/start">Start Free Assessment</a>
          <a class="btn secondary" href="#pricing">View Tiers</a>
        </div>
      </div>
      <div class="card">
        <h2>What you receive</h2>
        <div class="grid">
          <div class="kpi"><strong>AI Readiness Score</strong><br><span class="muted">Understand your current maturity.</span></div>
          <div class="kpi"><strong>Risk & Governance Gaps</strong><br><span class="muted">Identify where controls are missing.</span></div>
          <div class="kpi"><strong>Opportunity Map</strong><br><span class="muted">Spot practical AI and automation use cases.</span></div>
          <div class="kpi"><strong>Roadmap Pathway</strong><br><span class="muted">Know what to do next.</span></div>
        </div>
      </div>
    </section>

    <section class="grid grid-3">
      <div class="card">
        <h3>1. Assess</h3>
        <p>Answer guided questions covering strategy, data, systems, governance, security, people, and business value.</p>
      </div>
      <div class="card">
        <h3>2. Score</h3>
        <p>Receive readiness, maturity, risk, data, governance, automation, and business value scores.</p>
      </div>
      <div class="card">
        <h3>3. Act</h3>
        <p>Unlock reports, roadmaps, consultancy recommendations, and solution design opportunities.</p>
      </div>
    </section>

    <section id="pricing" style="margin-top:30px;" class="card">
      <h2>Commercial tiers</h2>
      <table class="table">
        <tr><th>Tier</th><th>Price</th><th>Best for</th><th>Output</th></tr>
        <tr><td>Free Readiness Check</td><td>£0</td><td>Lead generation</td><td>Score + basic recommendations</td></tr>
        <tr><td>Starter AI Audit Report</td><td>£149</td><td>SMEs</td><td>Detailed report</td></tr>
        <tr><td>Professional Organisation Audit</td><td>£750+</td><td>Growing organisations</td><td>Risk register + opportunity register</td></tr>
        <tr><td>AI Roadmap / Consultancy</td><td>£2,500+</td><td>Build-ready clients</td><td>Roadmap, business case, solution brief</td></tr>
      </table>
    </section>
    """
    return page("Home", body)


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
        )
        db.session.add(org)
        db.session.commit()

        assessment_record = Assessment(organisation_id=org.id, status="in_progress")
        db.session.add(assessment_record)
        db.session.commit()

        return redirect(url_for("assessment", assessment_id=assessment_record.id))

    body = """
    <div class="card">
      <h1>Start your free AI readiness assessment</h1>
      <p>Capture basic organisation details before completing the guided assessment.</p>
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
        <button class="btn" type="submit">Continue to Assessment</button>
      </form>
    </div>
    """
    return page("Start Assessment", body)


@app.route("/assessment/<int:assessment_id>", methods=["GET", "POST"])
def assessment(assessment_id):
    assessment_record = Assessment.query.get_or_404(assessment_id)

    if request.method == "POST":
        responses = {}
        for q in QUESTIONS:
            responses[q["id"]] = int(request.form.get(q["id"], 0))

        scores = calculate_scores(responses)
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

    question_html = ""

    for q in QUESTIONS:
        scale_type = q.get("scale_type", "control")
        scale_labels = SCALE_LABELS_BY_TYPE.get(scale_type, DEFAULT_SCORE_LABELS)

        options = ""
        for value, label in scale_labels.items():
            checked = "checked" if value == 2 else ""
            options += f"""
            <label>
              <input type="radio" name="{q['id']}" value="{value}" {checked}>
              {value} — {label}
            </label>
            """

        question_html += f"""
        <div class="question">
          <label>{q['question']}</label>
          <div class="help">{q['helper']}</div>
          <div class="scale">{options}</div>
        </div>
        """

    body = f"""
    <div class="card">
      <h1>AI Readiness Assessment</h1>
      <p>
        Organisation: <strong>{assessment_record.organisation.name}</strong><br>
        Answer each question using the options provided.
      </p>
      <form method="post">
        {question_html}
        <div style="margin-top:24px;">
          <button class="btn" type="submit">Generate Results</button>
        </div>
      </form>
    </div>
    """
    return page("Assessment", body)


@app.route("/results/<int:assessment_id>")
def results(assessment_id):
    assessment_record = Assessment.query.get_or_404(assessment_id)

    if not assessment_record.scores_json:
        return redirect(url_for("assessment", assessment_id=assessment_record.id))

    scores = json.loads(assessment_record.scores_json)
    recs = json.loads(assessment_record.recommendations_json or "[]")
    risks = json.loads(assessment_record.risks_json or "[]")
    opportunities = json.loads(assessment_record.opportunities_json or "[]")

    category_rows = ""
    for category, score in scores["category_scores"].items():
        category_rows += f"""
        <tr>
          <td>{category}</td>
          <td>{score}/100</td>
          <td>{score_to_band(score)}</td>
          <td><div class="bar"><div class="fill" style="width:{score}%"></div></div></td>
        </tr>
        """

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

    body = f"""
    <div class="notice">
      Free result generated. Unlock the full report to view the risk register, opportunity register, and consultancy-ready recommendations.
    </div>

    <section class="grid grid-3">
      <div class="card">
        <h3>AI Readiness</h3>
        <div class="score">{scores['ai_readiness_score']}</div>
        <p>{score_to_band(scores['ai_readiness_score'])}</p>
      </div>
      <div class="card">
        <h3>AI Risk Exposure</h3>
        <div class="score">{scores['ai_risk_score']}</div>
        <p>{risk_band(scores['ai_risk_score'])}</p>
      </div>
      <div class="card">
        <h3>Automation Opportunity</h3>
        <div class="score">{scores['automation_opportunity_score']}</div>
        <p>{score_to_band(scores['automation_opportunity_score'])}</p>
      </div>
    </section>

    <section style="margin-top:24px;" class="card">
      <h2>Category scores</h2>
      <p class="muted">These scores show the organisation's current strength or opportunity level in each area.</p>
      <table class="table">
        <tr><th>Category</th><th>Score</th><th>Band</th><th>Progress</th></tr>
        {category_rows}
      </table>
    </section>

    <section style="margin-top:24px;" class="card">
      <h2>Top recommendations</h2>
      <div class="grid grid-3">{rec_html}</div>
    </section>

    <section style="margin-top:24px;" class="grid grid-2">
      <div class="card">
        <h2>Locked: Risk Register</h2>
        <p>{len(risks)} risks identified. Unlock the full report to view severity, likelihood, and mitigation actions.</p>
      </div>
      <div class="card">
        <h2>Locked: Opportunity Register</h2>
        <p>{len(opportunities)} opportunities identified. Unlock to view use cases, value areas, and MVP build ideas.</p>
      </div>
    </section>

    <section style="margin-top:24px;" class="card">
      <h2>Unlock full report</h2>
      <p>This MVP uses a simulated payment unlock. In production, connect this button to Stripe Checkout.</p>
      <a class="btn" href="/unlock/{assessment_record.id}">Simulate £149 Report Unlock</a>
      <a class="btn secondary" href="/report/{assessment_record.id}">View Report</a>
    </section>
    """
    return page("Results", body)


@app.route("/unlock/<int:assessment_id>")
def unlock(assessment_id):
    assessment_record = Assessment.query.get_or_404(assessment_id)
    assessment_record.is_paid = True
    assessment_record.tier = "starter"
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
          <h1>Full report locked</h1>
          <p>The full AI readiness report is available after payment. This MVP uses a simulated payment unlock.</p>
          <a class="btn" href="/unlock/{assessment_record.id}">Simulate Unlock</a>
          <a class="btn secondary" href="/results/{assessment_record.id}">Back to Results</a>
        </div>
        """
        return page("Report Locked", body)

    scores = json.loads(assessment_record.scores_json)
    recs = json.loads(assessment_record.recommendations_json or "[]")
    risks = json.loads(assessment_record.risks_json or "[]")
    opportunities = json.loads(assessment_record.opportunities_json or "[]")

    risk_rows = ""
    for risk in risks:
        risk_rows += f"""
        <tr>
          <td>{risk['title']}</td>
          <td>{risk['severity']}</td>
          <td>{risk['likelihood']}</td>
          <td>{risk['mitigation']}</td>
        </tr>
        """

    opp_rows = ""
    for opp in opportunities:
        opp_rows += f"""
        <tr>
          <td>{opp['title']}</td>
          <td>{opp['area']}</td>
          <td>{opp['value']}</td>
          <td>{opp['complexity']}</td>
          <td>{opp['mvp']}</td>
        </tr>
        """

    rec_rows = ""
    for rec in recs:
        rec_rows += f"""
        <tr>
          <td>{rec['title']}</td>
          <td>{rec['priority']}</td>
          <td>{rec['text']}</td>
        </tr>
        """

    body = f"""
    <div class="card">
      <h1>AI Readiness Report</h1>
      <p>
        Organisation: <strong>{assessment_record.organisation.name}</strong><br>
        Sector: {assessment_record.organisation.sector}<br>
        Completed: {assessment_record.completed_at.strftime('%d %b %Y') if assessment_record.completed_at else 'N/A'}
      </p>
      <button class="btn secondary" onclick="window.print()">Print / Save as PDF</button>
    </div>

    <section style="margin-top:24px;" class="grid grid-3">
      <div class="card"><h3>AI Readiness</h3><div class="score">{scores['ai_readiness_score']}</div><p>{score_to_band(scores['ai_readiness_score'])}</p></div>
      <div class="card"><h3>AI Maturity</h3><div class="score">{scores['ai_maturity_score']}</div><p>{score_to_band(scores['ai_maturity_score'])}</p></div>
      <div class="card"><h3>Risk Exposure</h3><div class="score">{scores['ai_risk_score']}</div><p>{risk_band(scores['ai_risk_score'])}</p></div>
      <div class="card"><h3>Data Readiness</h3><div class="score">{scores['data_readiness_score']}</div><p>{score_to_band(scores['data_readiness_score'])}</p></div>
      <div class="card"><h3>Governance</h3><div class="score">{scores['governance_maturity_score']}</div><p>{score_to_band(scores['governance_maturity_score'])}</p></div>
      <div class="card"><h3>Business Value</h3><div class="score">{scores['business_value_potential_score']}</div><p>{score_to_band(scores['business_value_potential_score'])}</p></div>
    </section>

    <section style="margin-top:24px;" class="card">
      <h2>Executive Summary</h2>
      <p>
        {assessment_record.organisation.name} has achieved an AI readiness score of
        <strong>{scores['ai_readiness_score']}/100</strong>, placing the organisation in the
        <strong>{score_to_band(scores['ai_readiness_score'])}</strong> band.
      </p>
      <p>
        The current risk exposure is assessed as <strong>{risk_band(scores['ai_risk_score'])}</strong>.
        The recommended next step is to address governance, data readiness, and high-value automation opportunities
        before scaling AI adoption.
      </p>
    </section>

    <section style="margin-top:24px;" class="card">
      <h2>Risk Register</h2>
      <table class="table">
        <tr><th>Risk</th><th>Severity</th><th>Likelihood</th><th>Mitigation</th></tr>
        {risk_rows}
      </table>
    </section>

    <section style="margin-top:24px;" class="card">
      <h2>Opportunity Register</h2>
      <table class="table">
        <tr><th>Opportunity</th><th>Area</th><th>Value</th><th>Complexity</th><th>MVP Build Idea</th></tr>
        {opp_rows}
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
      <h2>Suggested Dissilio Consultancy Offer</h2>
      <p>Based on this result, the recommended next commercial offer is:</p>
      <div class="kpi">
        <strong>AI Audit Review Call + AI Opportunity Discovery Workshop</strong>
        <p>
          Suggested price range: £500–£3,000 depending on organisation size.
          The workshop should validate the assessment, prioritise use cases, and convert the best opportunity into a solution design brief.
        </p>
      </div>
    </section>
    """
    return page("Full Report", body)


@app.route("/admin")
def admin():
    admin_pass = request.args.get("pass")
    required = os.environ.get("ADMIN_PASS", "dissilio-admin")

    if admin_pass != required:
        body = """
        <div class="card">
          <h1>Admin Access</h1>
          <p>Append <code>?pass=dissilio-admin</code> to the URL for MVP admin access.</p>
          <p>In production, replace this with proper authentication and role-based access control.</p>
        </div>
        """
        return page("Admin", body)

    assessments = Assessment.query.order_by(Assessment.created_at.desc()).all()

    rows = ""
    for item in assessments:
        score = "N/A"
        band = "N/A"

        if item.scores_json:
            parsed_scores = json.loads(item.scores_json)
            score = parsed_scores.get("ai_readiness_score", "N/A")
            band = score_to_band(score) if isinstance(score, int) else "N/A"

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
          <td>{band}</td>
          <td>
            <a href="/results/{item.id}">Results</a> |
            <a href="/report/{item.id}">Report</a>
          </td>
        </tr>
        """

    body = f"""
    <div class="card">
      <h1>Admin Pipeline</h1>
      <p>Review completed assessments, paid status, readiness scores, and potential consultancy leads.</p>
      <table class="table">
        <tr>
          <th>ID</th>
          <th>Organisation</th>
          <th>Sector</th>
          <th>Email</th>
          <th>Status</th>
          <th>Tier</th>
          <th>Paid</th>
          <th>Score</th>
          <th>Band</th>
          <th>Actions</th>
        </tr>
        {rows}
      </table>
    </div>
    """
    return page("Admin Pipeline", body)


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
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
