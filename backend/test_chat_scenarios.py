import asyncio
import httpx
import uuid
import json

API_URL = "http://localhost:8000/api/chat/query"
VALID_PROJECT_ID = "48ab989b-d7c9-4fc5-a880-96a4e2c4f280"
SESSION_ID = str(uuid.uuid4())

# Define test scenarios
test_cases = [
    # Normal Scenarios
    {"name": "1. Standard Greeting", "payload": {"query": "Hello", "project_id": VALID_PROJECT_ID, "limit": 5}},
    {"name": "2. Specific Domain Query", "payload": {"query": "Tell me about the graph schemas", "project_id": VALID_PROJECT_ID, "limit": 5}},
    {"name": "3. Multi-turn context", "payload": {"query": "What language are they written in?", "project_id": VALID_PROJECT_ID, "session_id": SESSION_ID, "limit": 5}},
    {"name": "4. Multi-turn follow up", "payload": {"query": "Can you summarize that last point?", "project_id": VALID_PROJECT_ID, "session_id": SESSION_ID, "limit": 5}},
    
    # Edge Cases: Queries
    {"name": "5. Empty Query", "payload": {"query": "", "project_id": VALID_PROJECT_ID, "limit": 5}, "expect_error": True},
    {"name": "6. Whitespace Query", "payload": {"query": "   ", "project_id": VALID_PROJECT_ID, "limit": 5}},
    {"name": "7. Very Long Query (1000 chars)", "payload": {"query": "A" * 1000, "project_id": VALID_PROJECT_ID, "limit": 5}},
    {"name": "8. Special Characters", "payload": {"query": "!@#$%^&*()_+{}|:\"<>?", "project_id": VALID_PROJECT_ID, "limit": 5}},
    {"name": "9. SQL Injection attempt", "payload": {"query": "SELECT * FROM users;", "project_id": VALID_PROJECT_ID, "limit": 5}},
    {"name": "10. XSS attempt", "payload": {"query": "<script>alert(1)</script>", "project_id": VALID_PROJECT_ID, "limit": 5}},
    {"name": "11. Unicode / Emoji", "payload": {"query": "tell me about 🚀 and 🐛", "project_id": VALID_PROJECT_ID, "limit": 5}},
    {"name": "12. Markdown formatting", "payload": {"query": "**Bold** and *italic* and `code`", "project_id": VALID_PROJECT_ID, "limit": 5}},
    
    # Edge Cases: Project IDs
    {"name": "13. Invalid Project ID (malformed)", "payload": {"query": "Hello", "project_id": "not-a-uuid", "limit": 5}, "expect_error": True},
    {"name": "14. Non-existent Project ID", "payload": {"query": "Hello", "project_id": str(uuid.uuid4()), "limit": 5}},
    {"name": "15. Null Project ID", "payload": {"query": "Hello", "project_id": None, "limit": 5}, "expect_error": True},
    {"name": "16. Missing Project ID", "payload": {"query": "Hello", "limit": 5}, "expect_error": True},

    # Edge Cases: Limits
    {"name": "17. Limit = 0 (Under boundary)", "payload": {"query": "Hello", "project_id": VALID_PROJECT_ID, "limit": 0}, "expect_error": True},
    {"name": "18. Limit = 1 (Min boundary)", "payload": {"query": "Hello", "project_id": VALID_PROJECT_ID, "limit": 1}},
    {"name": "19. Limit = 20 (Max boundary)", "payload": {"query": "Hello", "project_id": VALID_PROJECT_ID, "limit": 20}},
    {"name": "20. Limit = 100 (Over boundary)", "payload": {"query": "Hello", "project_id": VALID_PROJECT_ID, "limit": 100}, "expect_error": True},
    
    # Edge Cases: Session ID
    {"name": "21. Invalid Session ID format", "payload": {"query": "Hello", "project_id": VALID_PROJECT_ID, "session_id": "bad-session-id", "limit": 5}},
]

async def run_tests():
    report = ["# Chat API Test Scenarios Report\n"]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for idx, test in enumerate(test_cases):
            name = test["name"]
            payload = test["payload"]
            expect_error = test.get("expect_error", False)
            
            print(f"Running Test {idx+1}/{len(test_cases)}: {name}...")
            
            try:
                response = await client.post(API_URL, json=payload)
                status = response.status_code
                data = response.json() if status < 500 else response.text
                
                if (status >= 400 and expect_error) or (status == 200 and not expect_error):
                    result = "✅ PASS"
                else:
                    result = f"❌ FAIL (Unexpected status {status})"
                
                report.append(f"### {name}")
                report.append(f"- **Result**: {result}")
                report.append(f"- **Status Code**: {status}")
                if status == 200:
                    answer = data.get('answer', '')
                    report.append(f"- **Response Snippet**: {answer[:100]}...")
                    report.append(f"- **Confidence**: {data.get('confidence_score')}")
                else:
                    report.append(f"- **Error Output**: {data}")
                report.append("\n---\n")
                
            except Exception as e:
                result = "❌ FAIL (Exception)"
                report.append(f"### {name}")
                report.append(f"- **Result**: {result}")
                report.append(f"- **Error**: {str(e)}")
                report.append("\n---\n")

    with open("chat_test_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print("Testing complete. Report saved to chat_test_report.md")

if __name__ == "__main__":
    asyncio.run(run_tests())
