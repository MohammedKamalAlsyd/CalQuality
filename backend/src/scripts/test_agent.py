# python -m src.scripts.test_agent
import requests
import json

BASE_URL = "http://localhost:8000"

def print_section(title):
    print("\n" + "=" * 80)
    print(f"🧪 {title}")
    print("=" * 80)

def run_tests():
    # 1. Health Check
    print_section("1. Health Check")
    try:
        res = requests.get(f"{BASE_URL}/health")
        print(f"Status: {res.status_code}, Body: {res.json()}")
    except requests.exceptions.ConnectionError:
        print("❌ Error: FastAPI server is not running. Start it with 'python -m src.main' first.")
        return

    # 2. Test Assessment Question: Northstar Cancellation
    print_section("2. Testing Agreement Override (Assessment Example)")
    payload = {
        "message": "Can Northstar cancel ORD-1001 without a cancellation fee? Explain why.",
        "account_id": "ACCT-001"
    }
    res = requests.post(f"{BASE_URL}/chat", json=payload).json()
    print("👤 User (ACCT-001):", payload["message"])
    print("🤖 AI Response:\n", res.get("response_text"))

    # 3. Test Access Control Isolation (SECURITY CHECK)
    print_section("3. Testing Data Layer Access Control (Security Check)")
    print("Context: LumenWorks (ACCT-002) attempts to query Northstar's (ACCT-001) order.")
    payload = {
        "message": "What is the status of order ORD-1001?",
        "account_id": "ACCT-002" # LumenWorks asking for Northstar's order
    }
    res = requests.post(f"{BASE_URL}/chat", json=payload).json()
    print("👤 User (ACCT-002):", payload["message"])
    print("🤖 AI Response:\n", res.get("response_text"))
    print("✅ Note: If the AI says it cannot find the order, the security mechanism is working perfectly!")

    # 4. Test Internal Ops Access (GLOBAL VIEW)
    print_section("4. Testing Internal Ops Global View")
    print("Context: Internal agent queries the same order, should have access.")
    payload = {
        "message": "What is the status of order ORD-1001? Also, what account does it belong to?",
        "account_id": "INTERNAL_OPS" # System Admin
    }
    res = requests.post(f"{BASE_URL}/chat", json=payload).json()
    print("👤 User (INTERNAL_OPS):", payload["message"])
    print("🤖 AI Response:\n", res.get("response_text"))

    # 5. Test State-Changing Action + Human Confirmation Flow
    print_section("5. Testing Human-in-the-Loop Escalation Flow")
    payload = {
        "message": "Please escalate ticket TKT-501 due to severe system outage.",
        "account_id": "ACCT-001"
    }
    chat_res = requests.post(f"{BASE_URL}/chat", json=payload).json()
    print("👤 User (ACCT-001):", payload["message"])
    print(f"⚙️ Requires Action: {chat_res.get('requires_action')}")
    print("📦 Action Payload:", json.dumps(chat_res.get("action_payload"), indent=2))

    if chat_res.get("requires_action"):
        thread_id = chat_res.get("thread_id")
        tool_call_id = chat_res["action_payload"]["tool_call_id"]
        
        print("\n👉 Simulating User clicking 'CONFIRM' on Frontend...")
        confirm_payload = {
            "thread_id": thread_id,
            "account_id": "ACCT-001",
            "tool_call_id": tool_call_id,
            "is_confirmed": True
        }
        confirm_res = requests.post(f"{BASE_URL}/confirm_action", json=confirm_payload).json()
        print("\n🤖 Final AI Response after confirmation:\n", confirm_res.get("response_text"))

if __name__ == "__main__":
    run_tests()