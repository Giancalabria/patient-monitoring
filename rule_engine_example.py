from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from datetime import datetime
import logging
import zen
import json
from pydantic import BaseModel
import copy
import uuid
from models.models import User
from utils.create_access_token import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rules", tags=["rules_engine"])


class SimulationRequest(BaseModel):
    age: int
    gender: str
    marital_status: str
    income: float
    bankruptcy_status: str
    bmi: float
    cholesterol: float
    blood_pressure_systolic: int
    blood_pressure_diastolic: int
    hdl_cholesterol: float
    ldl_cholesterol: float
    triglycerides: float
    hgba1c: float
    glucose: float
    nicotine: str
    alcohol_abuse: str
    dui_3_years: int
    violations_12_months: int
    cancer: str
    cardiac_circulatory: str
    diabetes_renal_endocrine: str
    occupation_name: str
    skydiving: str
    private_pilot: str
    scuba_diving_deep: str


class SimulationResult(BaseModel):
    final_decision: str
    final_risk_class: str
    final_reason: str
    triggered_rules: List[str]
    input_data: Dict[str, Any]


class JDMRules(BaseModel):
    contentType: str = "application/vnd.gorules.decision"
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


# Default underwriting rules in JDM format
DEFAULT_UNDERWRITING_RULES = {
    "contentType": "application/vnd.gorules.decision",
    "nodes": [
        {
            "id": "input-node",
            "type": "inputNode",
            "name": "Applicant Data",
            "position": {"x": 100, "y": 100},
            "content": {
                "fields": [
                    {"field": "age", "name": "Age", "dataType": "number"},
                    {"field": "income", "name": "Annual Income", "dataType": "number"},
                    {
                        "field": "bankruptcy_status",
                        "name": "Bankruptcy Status",
                        "dataType": "text",
                    },
                    {"field": "bmi", "name": "BMI", "dataType": "number"},
                    {
                        "field": "cholesterol",
                        "name": "Total Cholesterol",
                        "dataType": "number",
                    },
                    {
                        "field": "dui_3_years",
                        "name": "DUI in 3 Years",
                        "dataType": "number",
                    },
                    {"field": "nicotine", "name": "Nicotine Use", "dataType": "text"},
                    {
                        "field": "occupation_name",
                        "name": "Occupation",
                        "dataType": "text",
                    },
                    {"field": "skydiving", "name": "Skydiving", "dataType": "text"},
                    {"field": "cancer", "name": "Cancer History", "dataType": "text"},
                ]
            },
        },
        {
            "id": "knockout-financial",
            "type": "decisionTableNode",
            "name": "Financial Knockout Rules",
            "position": {"x": 400, "y": 50},
            "content": {
                "inputs": [
                    {
                        "id": "bankruptcy_status",
                        "field": "bankruptcy_status",
                        "name": "Bankruptcy Status",
                    },
                    {"id": "income", "field": "income", "name": "Income"},
                ],
                "outputs": [
                    {
                        "id": "decision",
                        "field": "knockout_decision",
                        "name": "Decision",
                    },
                    {"id": "reason", "field": "knockout_reason", "name": "Reason"},
                ],
                "rules": [
                    {
                        "bankruptcy_status": '"Open"',
                        "income": "",
                        "decision": '"Deny"',
                        "reason": '"Open bankruptcy status"',
                    },
                    {
                        "bankruptcy_status": "",
                        "income": "< 50000",
                        "decision": '"Deny"',
                        "reason": '"Income below minimum threshold"',
                    },
                ],
                "hitPolicy": "first",
            },
        },
        {
            "id": "knockout-driving",
            "type": "decisionTableNode",
            "name": "Driving History Knockout",
            "position": {"x": 400, "y": 200},
            "content": {
                "inputs": [
                    {
                        "id": "dui_3_years",
                        "field": "dui_3_years",
                        "name": "DUI in 3 Years",
                    }
                ],
                "outputs": [
                    {"id": "decision", "field": "driving_decision", "name": "Decision"},
                    {"id": "reason", "field": "driving_reason", "name": "Reason"},
                ],
                "rules": [
                    {
                        "dui_3_years": "> 0",
                        "decision": '"Deny"',
                        "reason": '"DUI in past 3 years"',
                    }
                ],
                "hitPolicy": "first",
            },
        },
        {
            "id": "knockout-activities",
            "type": "decisionTableNode",
            "name": "High Risk Activities",
            "position": {"x": 400, "y": 350},
            "content": {
                "inputs": [
                    {"id": "skydiving", "field": "skydiving", "name": "Skydiving"}
                ],
                "outputs": [
                    {
                        "id": "decision",
                        "field": "activity_decision",
                        "name": "Decision",
                    },
                    {"id": "reason", "field": "activity_reason", "name": "Reason"},
                ],
                "rules": [
                    {
                        "skydiving": '"Y"',
                        "decision": '"Deny"',
                        "reason": '"Skydiving activity"',
                    }
                ],
                "hitPolicy": "first",
            },
        },
        {
            "id": "knockout-medical",
            "type": "decisionTableNode",
            "name": "Medical Knockout Rules",
            "position": {"x": 400, "y": 500},
            "content": {
                "inputs": [{"id": "cancer", "field": "cancer", "name": "Cancer"}],
                "outputs": [
                    {"id": "decision", "field": "medical_decision", "name": "Decision"},
                    {"id": "reason", "field": "medical_reason", "name": "Reason"},
                ],
                "rules": [
                    {
                        "cancer": '"Y"',
                        "decision": '"Deny"',
                        "reason": '"Cancer history (excluding basal/squamous cell)"',
                    }
                ],
                "hitPolicy": "first",
            },
        },
        {
            "id": "risk-scoring",
            "type": "decisionTableNode",
            "name": "Risk Scoring Rules",
            "position": {"x": 700, "y": 200},
            "content": {
                "inputs": [
                    {"id": "age", "field": "age", "name": "Age"},
                    {"id": "bmi", "field": "bmi", "name": "BMI"},
                    {
                        "id": "cholesterol",
                        "field": "cholesterol",
                        "name": "Cholesterol",
                    },
                    {"id": "nicotine", "field": "nicotine", "name": "Nicotine"},
                    {
                        "id": "occupation_name",
                        "field": "occupation_name",
                        "name": "Occupation",
                    },
                ],
                "outputs": [
                    {"id": "risk_class", "field": "risk_class", "name": "Risk Class"},
                    {"id": "reason", "field": "risk_reason", "name": "Reason"},
                ],
                "rules": [
                    {
                        "age": "18..30",
                        "bmi": "18.5..25",
                        "cholesterol": "<= 200",
                        "nicotine": '"N"',
                        "occupation_name": '"Teacher"',
                        "risk_class": '"Accept/Preferred"',
                        "reason": '"Low risk profile"',
                    },
                    {
                        "age": "31..50",
                        "bmi": "18.5..30",
                        "cholesterol": "201..240",
                        "nicotine": '"N"',
                        "occupation_name": '"Software Developer"',
                        "risk_class": '"Accept/Standard"',
                        "reason": '"Standard risk profile"',
                    },
                    {
                        "age": "51..65",
                        "bmi": "25..35",
                        "cholesterol": "> 240",
                        "nicotine": '"Y"',
                        "occupation_name": '"Construction Worker"',
                        "risk_class": '"Accept/Substandard"',
                        "reason": '"Higher risk factors present"',
                    },
                ],
                "hitPolicy": "first",
            },
        },
        {
            "id": "final-decision",
            "type": "functionNode",
            "name": "Final Decision Logic",
            "position": {"x": 1000, "y": 300},
            "content": {
                "inputs": [
                    {
                        "id": "knockout_decision",
                        "field": "knockout_decision",
                        "name": "Knockout Decision",
                    },
                    {
                        "id": "driving_decision",
                        "field": "driving_decision",
                        "name": "Driving Decision",
                    },
                    {
                        "id": "activity_decision",
                        "field": "activity_decision",
                        "name": "Activity Decision",
                    },
                    {
                        "id": "medical_decision",
                        "field": "medical_decision",
                        "name": "Medical Decision",
                    },
                    {"id": "risk_class", "field": "risk_class", "name": "Risk Class"},
                ],
                "outputs": [
                    {
                        "id": "final_decision",
                        "field": "final_decision",
                        "name": "Final Decision",
                    },
                    {
                        "id": "final_reason",
                        "field": "final_reason",
                        "name": "Final Reason",
                    },
                ],
                "expression": """
                if (knockout_decision === "Deny" || driving_decision === "Deny" ||
                    activity_decision === "Deny" || medical_decision === "Deny") {
                    return {
                        final_decision: "Deny",
                        final_reason: knockout_reason || driving_reason || activity_reason || medical_reason
                    };
                } else {
                    return {
                        final_decision: risk_class || "Review Required",
                        final_reason: risk_reason || "Manual review required"
                    };
                }
                """,
            },
        },
        {
            "id": "output-node",
            "type": "outputNode",
            "name": "Decision Output",
            "position": {"x": 1300, "y": 300},
            "content": {
                "fields": [
                    {"field": "final_decision", "name": "Final Decision"},
                    {"field": "final_reason", "name": "Decision Reason"},
                    {"field": "risk_class", "name": "Risk Classification"},
                ]
            },
        },
    ],
    "edges": [
        {"id": "edge-1", "source": "input-node", "target": "knockout-financial"},
        {"id": "edge-2", "source": "input-node", "target": "knockout-driving"},
        {"id": "edge-3", "source": "input-node", "target": "knockout-activities"},
        {"id": "edge-4", "source": "input-node", "target": "knockout-medical"},
        {"id": "edge-5", "source": "input-node", "target": "risk-scoring"},
        {"id": "edge-6", "source": "knockout-financial", "target": "final-decision"},
        {"id": "edge-7", "source": "knockout-driving", "target": "final-decision"},
        {"id": "edge-8", "source": "knockout-activities", "target": "final-decision"},
        {"id": "edge-9", "source": "knockout-medical", "target": "final-decision"},
        {"id": "edge-10", "source": "risk-scoring", "target": "final-decision"},
        {"id": "edge-11", "source": "final-decision", "target": "output-node"},
    ],
}


def debug_rules_structure(rules):
    """Debug function to print the structure of each node in the rules"""
    for i, node in enumerate(rules.get("nodes", [])):
        node_type = node.get("type", "unknown")
        node_id = node.get("id", "unknown")
        node_name = node.get("name", "missing-name")  # This could be the issue

        logger.info(f"Node {i}: id={node_id}, type={node_type}, name={node_name}")

        # For decision tables, check the content structure
        if node_type == "decisionTableNode" and "content" in node:
            content = node["content"]
            inputs = content.get("inputs", [])
            outputs = content.get("outputs", [])
            rules = content.get("rules", [])

            logger.info(
                f"  Decision table structure: {len(inputs)} inputs, {len(outputs)} outputs, {len(rules)} rules"
            )

            # Check each rule for completeness
            for j, rule in enumerate(rules):
                logger.info(f"  Rule {j}: keys={list(rule.keys())}")


# for production, this would be in database (s3, dynamodb, etc)
current_rules = DEFAULT_UNDERWRITING_RULES.copy()

debug_rules_structure(current_rules)


zen_engine = zen.ZenEngine()


def find_problematic_node(rules_data):

    try:

        rules_json = json.dumps(rules_data)

        error_position = 1493
        context_range = 200
        start = max(0, error_position - context_range)
        end = min(len(rules_json), error_position + context_range)
        context = rules_json[start:end]

        for i, node in enumerate(rules_data.get("nodes", [])):
            node_json = json.dumps(node)
            if context in node_json:
                return i, node

        return None, None
    except Exception as e:
        logger.error(f"Error finding problematic node: {e}")
        return None, None


def ensure_valid_decision_tables(rules_data):

    if not isinstance(rules_data, dict):
        return rules_data

    if "nodes" not in rules_data:
        return rules_data

    for node in rules_data["nodes"]:
        if node.get("type") == "decisionTableNode":

            if "content" not in node:
                node["content"] = {
                    "inputs": [],
                    "outputs": [],
                    "rules": [],
                    "hitPolicy": "first",
                }

            content = node["content"]
            if "inputs" not in content:
                content["inputs"] = []
            if "outputs" not in content:
                content["outputs"] = []
            if "rules" not in content:
                content["rules"] = []
            if "hitPolicy" not in content:
                content["hitPolicy"] = "first"

            for input_item in content.get("inputs", []):
                if "id" not in input_item:
                    input_item["id"] = f"input-{uuid.uuid4().hex[:8]}"
                if "field" not in input_item:
                    input_item["field"] = input_item["id"]

            for output_item in content.get("outputs", []):
                if "id" not in output_item:
                    output_item["id"] = f"output-{uuid.uuid4().hex[:8]}"
                if "field" not in output_item:
                    output_item["field"] = output_item["id"]

        elif node.get("type") == "functionNode":

            if "content" not in node:
                node["content"] = {"inputs": [], "outputs": [], "expression": ""}

            content = node["content"]
            if "inputs" not in content:
                content["inputs"] = []
            if "outputs" not in content:
                content["outputs"] = []
            if "expression" not in content:
                content["expression"] = ""

    return rules_data


@router.get("/")
async def get_underwriting_rules(current_user: User = Depends(get_current_user)):
    """Get current underwriting rules in JDM format"""
    try:
        return {"rules": current_rules}
    except Exception as e:
        logger.error(f"Error retrieving rules: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve rules")


@router.post("/")
async def update_underwriting_rules(
    rules: JDMRules, current_user: User = Depends(get_current_user)
):
    try:
        global current_rules

        rules_dict = rules
        if hasattr(rules, "dict"):
            rules_dict = rules.dict()

        sanitized_rules = sanitize_rules_for_zen(rules_dict)

        current_rules = sanitized_rules

        logger.info(f"Rules updated by user {current_user.username}")

        try:
            rules_json = json.dumps(sanitized_rules)
            zen_engine.create_decision(rules_json)
            logger.info("Rules validated successfully with Zen Engine")
        except Exception as zen_error:
            logger.error(f"Invalid rules format: {str(zen_error)}")
            raise HTTPException(
                status_code=400, detail=f"Invalid rules format: {str(zen_error)}"
            )

        return {"message": "Rules updated successfully", "rules": current_rules}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating rules: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update rules: {str(e)}")


def sanitize_rules_for_zen(rules_data: Dict[str, Any]) -> Dict[str, Any]:
    fixed_rules = copy.deepcopy(rules_data)

    # Ensure contentType is set properly
    fixed_rules["contentType"] = "application/vnd.gorules.decision"

    for i, node in enumerate(fixed_rules.get("nodes", [])):

        if "id" not in node:
            node["id"] = f"node-{i}"

        if "type" not in node:
            node["type"] = "decisionTableNode"

        if "name" not in node or not node["name"]:
            node["name"] = f"Node {i+1}"

        if "position" not in node:
            node["position"] = {"x": i * 200, "y": 100}

        if "content" not in node:
            if node["type"] == "inputNode":
                node["content"] = {"fields": []}
            elif node["type"] == "outputNode":
                node["content"] = {"fields": []}
            elif node["type"] == "decisionTableNode":
                node["content"] = {
                    "inputs": [],
                    "outputs": [],
                    "rules": [],
                    "hitPolicy": "first",
                }
            elif node["type"] == "functionNode":
                node["content"] = {"inputs": [], "outputs": [], "expression": ""}

    for i, edge in enumerate(fixed_rules.get("edges", [])):
        if "id" not in edge:
            edge["id"] = f"edge-{i}"
        if "source" not in edge:

            edge["source"] = "placeholder-source"
        if "target" not in edge:
            edge["target"] = "placeholder-target"

    return fixed_rules


@router.post("/simulate", response_model=SimulationResult)
async def simulate_underwriting_decision(
    request: SimulationRequest, current_user: User = Depends(get_current_user)
):
    """Simulate underwriting decision using current rules and Zen Engine"""
    try:
        # Convert request to dict for processing
        applicant_data = request.dict()
        logger.info("Running simulation with applicant data")

        # Fix function node format in the rules
        fixed_rules = fix_function_node_format(copy.deepcopy(current_rules))

        # Convert rules to JSON
        try:
            rules_json = json.dumps(fixed_rules)
            logger.info("Rules successfully converted to JSON")
        except Exception as json_error:
            logger.error(f"Error serializing rules to JSON: {str(json_error)}")
            raise HTTPException(
                status_code=500, detail=f"Invalid rules format: {str(json_error)}"
            )

        # Create a decision using Zen Engine
        try:
            logger.info("Creating decision with Zen Engine...")
            decision = zen_engine.create_decision(rules_json)
            logger.info("Decision created successfully")
        except Exception as zen_error:
            logger.error(f"Error creating decision: {str(zen_error)}")

            # Log function node content for debugging
            for node in fixed_rules.get("nodes", []):
                if node.get("type") == "functionNode":
                    logger.error(
                        f"Function node content: {json.dumps(node.get('content', {}))}"
                    )

            raise HTTPException(
                status_code=400, detail=f"Invalid rules format: {str(zen_error)}"
            )

        # Execute the rules with applicant data
        try:
            logger.info("Evaluating decision with applicant data...")
            engine_result = decision.evaluate(applicant_data)
            logger.info(f"Zen engine result keys: {list(engine_result.keys())}")
        except Exception as eval_error:
            logger.error(f"Error evaluating decision: {str(eval_error)}")
            raise HTTPException(
                status_code=400, detail=f"Error evaluating decision: {str(eval_error)}"
            )

        # Extract the results
        final_decision = engine_result.get("final_decision", "Review Required")
        final_risk_class = engine_result.get("risk_class", "Standard")
        final_reason = engine_result.get("final_reason", "Standard underwriting review")

        # Determine which rules were triggered
        triggered_rules = []
        if engine_result.get("knockout_decision") == "Deny":
            triggered_rules.append("Financial Knockout Rules")
        if engine_result.get("driving_decision") == "Deny":
            triggered_rules.append("Driving History Knockout")
        if engine_result.get("activity_decision") == "Deny":
            triggered_rules.append("High Risk Activities")
        if engine_result.get("medical_decision") == "Deny":
            triggered_rules.append("Medical Knockout Rules")
        if engine_result.get("risk_class"):
            triggered_rules.append("Risk Scoring Rules")

        return SimulationResult(
            final_decision=final_decision,
            final_risk_class=final_risk_class,
            final_reason=final_reason,
            triggered_rules=triggered_rules,
            input_data=applicant_data,
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in simulation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")


@router.get("/export")
async def export_rules(current_user: User = Depends(get_current_user)):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"underwriting_rules_{timestamp}.json"

        return {
            "filename": filename,
            "content": current_rules,
            "exported_at": datetime.now().isoformat(),
            "exported_by": current_user.username,
        }
    except Exception as e:
        logger.error(f"Error exporting rules: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to export rules")


@router.post("/import")
async def import_rules(
    rules_data: Dict[str, Any], current_user: User = Depends(get_current_user)
):
    """Import rules from JSON data"""
    try:
        # Validate the imported rules structure
        if not validate_rules_structure(rules_data):
            raise HTTPException(status_code=400, detail="Invalid rules structure")

        # Validate with Zen Engine
        try:
            rules_json = json.dumps(rules_data)
            zen_engine.create_decision(rules_json)
            logger.info("Imported rules validated successfully with Zen Engine")
        except Exception as zen_error:
            logger.error(f"Invalid imported rules format: {str(zen_error)}")
            raise HTTPException(
                status_code=400, detail=f"Invalid rules format: {str(zen_error)}"
            )

        global current_rules
        current_rules = rules_data

        logger.info(f"Rules imported by user {current_user.username}")

        return {"message": "Rules imported successfully", "rules": current_rules}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error importing rules: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to import rules: {str(e)}")


def validate_rules_structure(rules_data: Dict[str, Any]) -> bool:
    """Validate that the rules data has the correct JDM structure"""
    try:
        required_fields = ["contentType", "nodes", "edges"]
        return all(field in rules_data for field in required_fields)
    except Exception:
        return False


# Add to rules_engine.py - function to fix function node content
def fix_function_node_format(rules_data):
    """Fix function node content structure to match Zen Engine requirements"""
    if not isinstance(rules_data, dict) or "nodes" not in rules_data:
        return rules_data

    for node in rules_data.get("nodes", []):
        if node.get("type") == "functionNode" and "content" in node:
            content = node["content"]

            # Keep inputs and outputs
            inputs = content.get("inputs", [])
            outputs = content.get("outputs", [])

            # Get function body from expression or code
            function_body = ""
            if "expression" in content:
                function_body = content["expression"]
            elif "code" in content:
                function_body = content["code"]

            # Create the correct structure for Zen Engine
            node["content"] = {
                "inputs": inputs,
                "outputs": outputs,
                "functionBody": function_body,
            }

            logger.info(
                f"Fixed function node {node.get('id')} to use 'functionBody' structure"
            )

    return rules_data


@router.post("/validate")
async def validate_rules(
    rules: JDMRules, current_user: User = Depends(get_current_user)
):
    """Validate underwriting rules using Zen Engine"""
    try:
        # Convert to dict if needed
        rules_dict = rules
        if hasattr(rules, "dict"):
            rules_dict = rules.dict()

        # Check for function nodes and fix if needed
        for node in rules_dict.get("nodes", []):
            if node.get("type") == "functionNode":
                content = node.get("content", {})

                # Check for required fields
                if "inputs" not in content or "outputs" not in content:
                    return {
                        "valid": False,
                        "message": f"Function node '{node.get('name', node.get('id'))}' is missing inputs or outputs",
                    }

                # Check function body
                has_function_body = False
                for field in ["functionBody", "expression", "code"]:
                    if field in content:
                        has_function_body = True
                        break

                if not has_function_body:
                    return {
                        "valid": False,
                        "message": f"Function node '{node.get('name', node.get('id'))}' is missing function body",
                    }

        # Fix function nodes format
        fixed_rules = fix_function_node_format(copy.deepcopy(rules_dict))

        # Try to create a decision to validate with Zen Engine
        try:
            rules_json = json.dumps(fixed_rules)
            zen_engine.create_decision(rules_json)
            return {
                "valid": True,
                "message": "Rules validated successfully with Zen Engine",
            }
        except Exception as zen_error:
            logger.error(f"Rules validation failed: {str(zen_error)}")
            return {
                "valid": False,
                "message": f"Invalid rules format: {str(zen_error)}",
            }
    except Exception as e:
        logger.error(f"Error validating rules: {str(e)}")
        return {"valid": False, "message": f"Error validating rules: {str(e)}"}


@router.post("/evaluate-expression")
async def evaluate_expression(
    data: dict, current_user: User = Depends(get_current_user)
):
    """Evaluate a ZEN expression"""
    try:
        expression = data.get("expression")
        context = data.get("context", {})

        if not expression:
            raise HTTPException(status_code=400, detail="Expression is required")

        result = zen.evaluate_expression(expression, context)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error evaluating expression: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to evaluate expression: {str(e)}"
        )
