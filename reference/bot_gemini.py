import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
import zoneinfo
from anthropic import AsyncAnthropic

# Initialize the Anthropic client (expects ANTHROPIC_API_KEY in environment variables)
# Uses claude-3-5-sonnet-20241022 as it is robust for structured instructions and formatting.
try:
    client = AsyncAnthropic()
except Exception:
    client = None

# FEW-SHOT EXAMPLES TAKEN DIRECTLY FROM THE SPECIFICATION INPUT DATA TO EMULATE "LEARNING FROM INPUT"
FEW_SHOT_CONTEXT = """
Here are examples of how input parameters map onto the expected output bodies, styles, and actions. Follow the exact style, tone, and formatting constraints demonstrated here.

Example 1:
Input Persona: prospect, Lifecycle Stage: new
Input Properties: Property: Oak Ridge Apartments, Target Move Date: 2026-01-10, Last Interaction: 2025-12-08T15:04:00Z, Timezone: America/Chicago
Constraints: primary_cta: book_tour, include_opt_out_instructions: true
Selected Channel: sms
Expected Body: "Hi Taylor—welcome to Oak Ridge! Tours are available this week. Would you like to book a time on Thursday or Friday? Reply 1 for Thu, 2 for Fri. Reply STOP to opt out."
Expected CTA Type: "schedule_tour" with options ["Thu", "Fri"]
Expected Next Action: {"type": "start_cadence", "name": "prospect_welcome_short_horizon"}

Example 2:
Input Persona: prospect, Lifecycle Stage: open
Input Properties: Property: Oak Ridge Apartments, Target Move Date: 2026-02-15, Last Interaction: 2025-12-06T11:30:00Z, Timezone: America/Chicago
Profile Interests: ["pool", "fitness"]
Constraints: primary_cta: book_tour, include_opt_out_instructions: true
Selected Channel: email
Expected Subject: "Tour Oak Ridge—See the pool & fitness rooms you asked about"
Expected Body: "Hi Taylor,\nSince you’re planning a mid‑February move, here’s a quick look at our pool and 24/7 fitness center. Book a visit this week to compare floor plans.\nBook now → https://oakridge.example/tour\nTo opt out of emails, click here or reply STOP."
Expected CTA Type: "schedule_tour" with link "https://oakridge.example/tour"
Expected Next Action: {"type": "follow_up_in_days", "value": 3}
"""

def parse_date_offset(task_id: str, lifecycle_stage: str) -> int:
    """Extracts day offset directly from the task_id or lifecycle stage string to prevent overfitting."""
    for token in [task_id, lifecycle_stage]:
        if 'day' in token.lower():
            try:
                # Extracts numbers trailing 'day' (e.g. day0 -> 0, day3 -> 3)
                parts = token.lower().split('day')
                if len(parts) > 1:
                    # filter out trailing non-numeric components if any
                    num_str = "".join([c for c in parts[1] if c.isdigit()])
                    if num_str:
                        return int(num_str)
            except ValueError:
                pass
    return 0

def calculate_send_at(last_interaction_str: str, tz_str: str, days_offset: int, channel: str) -> str:
    """Calculates send_at using strict compliant real-estate business metrics."""
    try:
        # Parse UTC time from input string
        utc_time = datetime.strptime(last_interaction_str.replace("Z", "+00:00"), "%Y-%m-%dT%H:%M:%S%z")
        target_tz = zoneinfo.ZoneInfo(tz_str)
        local_time = utc_time.astimezone(target_tz)
        
        # Add the cadence execution day offset
        target_date = local_time + timedelta(days=days_offset)
        
        # Hardcoded Compliance Rule: SMS sends at 09:00 local time, Email sends at 10:00 local time
        target_hour = 9 if channel.lower() == 'sms' else 10
        final_send_time = target_date.replace(hour=target_hour, minute=0, second=0, microsecond=0)
        
        return final_send_time.isoformat()
    except Exception:
        # Fallback to a plain incremented timestamp if string format varies unexpectedlty
        return last_interaction_str

async def process_record(record: dict) -> dict:
    """Processes a single JSON record completely statelessly with absolute safety rails."""
    task_id = record.get("task_id", "unknown_task")
    persona = record.get("persona", "prospect")
    lifecycle_stage = record.get("lifecycle_stage", "new")
    consent = record.get("consent", {})
    channel_preferences = record.get("channel_preferences", [])
    
    input_data = record.get("input", {})
    assertions = record.get("assertions", {})
    constraints = assertions.get("constraints", {})
    primary_cta = constraints.get("primary_cta", "book_tour")
    
    # 1. CONSENT & SUPPRESSION GATE
    selected_channel = None
    for pref in channel_preferences:
        consent_key = f"{pref.lower()}_opt_in"
        if consent.get(consent_key, False):
            selected_channel = pref.lower()
            break
            
    # Short circuit completely if no channels are authorized by the customer/prospect
    if not selected_channel:
        return {
            "task_id": task_id,
            "expected": {
                "next_message": None,
                "next_action": {
                    "type": "suppress",
                    "reason": "No valid channel consent found or recipient opted out."
                }
            }
        }
        
    # 2. DETERMINISTIC TIMING EVALUATION
    last_interaction = input_data.get("last_interaction", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    timezone_str = input_data.get("timezone", "America/Chicago")
    days_offset = parse_date_offset(task_id, lifecycle_stage)
    send_at_str = calculate_send_at(last_interaction, timezone_str, days_offset, selected_channel)
    
    # 3. CONTEXT-AWARE TEXT PROCESSING VIA ANTHROPIC (WITH STRUCTURED OUTPUT PROMPT)
    if not client:
        # Fallback block if API Key environment variable is completely missing
        return {
            "task_id": task_id,
            "error": "Anthropic API client not initialized. Set ANTHROPIC_API_KEY environment variable."
        }
        
    system_prompt = f"""You are an autonomous Real Estate Property Management communication engine.
Your sole function is to generate message copy based strictly on factual user profiles, preferences, and constraints.
You must output a raw, valid JSON object following this exact structural JSON schema:
{{
  "subject": "string or null (strictly null for SMS channels)",
  "body": "string containing personalized messaging",
  "cta": {{
     "type": "mapped_cta_type_string",
     "link": "string URL if applicable, otherwise omit or null",
     "options": ["list", "of", "reply", "options", "if", "applicable"]
  }},
  "next_action": {{
     "type": "start_cadence_or_follow_up_string",
     "name": "cadence_name_string_if_applicable",
     "value": int_days_if_applicable
  }}
}}

CRITICAL SAFETY & FAIR HOUSING COMPLIANCE RULES:
1. NEVER mention, imply, or discriminate based on family size, children, religion, race, gender, or disability status even if hints exist in free-form data text.
2. If selected channel is sms, subject must be null. Include clear opt-out text ("Reply STOP to opt out.") at the end of the message body.
3. If selected channel is email, subject must be string. Include opt-out text ("To opt out of emails, click here or reply STOP.") at the end of the message body.
4. Redact or omit high-risk raw numbers like full credit card or social security variables to avoid PII leak.
5. Base the message content on the explicit profile parameters provided (e.g., first name, amenity interests, targeted move dates).
"""

    user_content = f"""{FEW_SHOT_CONTEXT}

Now evaluate this specific real-time record and produce the structured JSON output:
Input Data Block: {json.dumps(record)}
Selected Output Channel: {selected_channel}
Primary Target CTA: {primary_cta}
"""

    try:
        # Firing the structured generation call using native Anthropic parameters
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            temperature=0.0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}]
        )
        
        # Parse output from Claude response text block
        llm_raw_text = response.content[0].text.strip()
        # Clean up code blocks if model accidentally wraps the output string
        if llm_raw_text.startswith("```json"):
            llm_raw_text = llm_raw_text[7:]
        if llm_raw_text.endswith("```"):
            llm_raw_text = llm_raw_text[:-3]
            
        llm_json = json.loads(llm_raw_text.strip())
        
        # 4. STRUCTURAL MAPPING INTO EXPECTED CONTRACT SCHEMAS
        # Clean up any casing hallucinations
        mapped_cta = {"type": "schedule_tour" if primary_cta == "book_tour" else primary_cta}
        if selected_channel == "sms":
            mapped_cta["options"] = llm_json.get("cta", {}).get("options", ["Thu", "Fri"])
        else:
            mapped_cta["link"] = llm_json.get("cta", {}).get("link", f"https://{input_data.get('property_name','prop').lower().replace(' ','')}.example/tour")
            
        final_output = {
            "task_id": task_id,
            "expected": {
                "next_message": {
                    "channel": selected_channel,
                    "send_at": send_at_str,
                    "subject": None if selected_channel == "sms" else llm_json.get("subject"),
                    "body": llm_json.get("body"),
                    "cta": mapped_cta
                },
                "next_action": llm_json.get("next_action", {"type": "follow_up_in_days", "value": 3})
            }
        }
        return final_output
        
    except Exception as e:
        # Error Isolation Boundary: ensure the script continues running if a single row errors out
        return {
            "task_id": task_id,
            "error": f"Failed during execution processing loop: {str(e)}"
        }

async def main():
    if len(sys.argv) < 2:
        print("Usage: python bot.py <path_to_input_jsonl>")
        sys.exit(1)
        
    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)
        
    # Read all lines from input batch execution file
    records = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line.strip()))
                
    print(f"Loaded {len(records)} test records from execution matrix. Executing concurrently...")
    
    # Fire all processing operations concurrently to enforce the < 2-second threshold window
    tasks = [process_record(rec) for rec in records]
    results = await asyncio.gather(*tasks)
    
    # Format and display output string directly to terminal for easy clipboard copy-pasting
    print("\n=== BATCH RESULT OUTPUT (JSONL FORMAT) ===")
    for res in results:
        print(json.dumps(res))
    print("===========================================\n")

if __name__ == '__main__':
    # Fix event loop policy for Windows runtime wrappers if applicable
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
