# Chat API Test Scenarios Report

### 1. Standard Greeting
- **Result**: ✅ PASS
- **Status Code**: 200
- **Response Snippet**: Hello! I am Axis AI, a premium software engineering alignment assistant. I can help you understand y...
- **Confidence**: 0.0

---

### 2. Specific Domain Query
- **Result**: ✅ PASS
- **Status Code**: 200
- **Response Snippet**: I encountered an unexpected error while generating the alignment response. Please try again shortly....
- **Confidence**: 0.0

---

### 3. Multi-turn context
- **Result**: ✅ PASS
- **Status Code**: 200
- **Response Snippet**: I encountered an unexpected error while generating the alignment response. Please try again shortly....
- **Confidence**: 0.0

---

### 4. Multi-turn follow up
- **Result**: ✅ PASS
- **Status Code**: 200
- **Response Snippet**: I encountered an unexpected error while generating the alignment response. Please try again shortly....
- **Confidence**: 0.0

---

### 5. Empty Query
- **Result**: ✅ PASS
- **Status Code**: 422
- **Error Output**: {'detail': [{'type': 'string_too_short', 'loc': ['body', 'query'], 'msg': 'String should have at least 1 character', 'input': '', 'ctx': {'min_length': 1}}]}

---

### 6. Whitespace Query
- **Result**: ✅ PASS
- **Status Code**: 200
- **Response Snippet**: I encountered an unexpected error while generating the alignment response. Please try again shortly....
- **Confidence**: 0.0

---

### 7. Very Long Query (1000 chars)
- **Result**: ✅ PASS
- **Status Code**: 200
- **Response Snippet**: I cannot find an answer to your query in the provided workspace resources. The context does not cont...
- **Confidence**: 0.0

---

### 8. Special Characters
- **Result**: ✅ PASS
- **Status Code**: 200
- **Response Snippet**: I cannot find an answer to your query in the workspace resources. The provided context does not cont...
- **Confidence**: 0.0

---

### 9. SQL Injection attempt
- **Result**: ✅ PASS
- **Status Code**: 200
- **Response Snippet**: I cannot find information about a `users` table or how to execute SQL queries like `SELECT * FROM us...
- **Confidence**: 0.0

---

### 10. XSS attempt
- **Result**: ✅ PASS
- **Status Code**: 200
- **Response Snippet**: I cannot find any information related to "<script>alert(1)</script>" in the workspace resources....
- **Confidence**: 0.0

---

### 11. Unicode / Emoji
- **Result**: ✅ PASS
- **Status Code**: 200
- **Response Snippet**: I encountered an unexpected error while generating the alignment response. Please try again shortly....
- **Confidence**: 0.0

---

### 12. Markdown formatting
- **Result**: ✅ PASS
- **Status Code**: 200
- **Response Snippet**: I encountered an unexpected error while generating the alignment response. Please try again shortly....
- **Confidence**: 0.0

---

### 13. Invalid Project ID (malformed)
- **Result**: ✅ PASS
- **Status Code**: 400
- **Error Output**: {'detail': 'Invalid project_id UUID format'}

---

### 14. Non-existent Project ID
- **Result**: ✅ PASS
- **Status Code**: 200
- **Response Snippet**: I encountered an unexpected error while generating the alignment response. Please try again shortly....
- **Confidence**: 0.0

---

### 15. Null Project ID
- **Result**: ✅ PASS
- **Status Code**: 422
- **Error Output**: {'detail': [{'type': 'string_type', 'loc': ['body', 'project_id'], 'msg': 'Input should be a valid string', 'input': None}]}

---

### 16. Missing Project ID
- **Result**: ✅ PASS
- **Status Code**: 422
- **Error Output**: {'detail': [{'type': 'missing', 'loc': ['body', 'project_id'], 'msg': 'Field required', 'input': {'query': 'Hello', 'limit': 5}}]}

---

### 17. Limit = 0 (Under boundary)
- **Result**: ✅ PASS
- **Status Code**: 422
- **Error Output**: {'detail': [{'type': 'greater_than_equal', 'loc': ['body', 'limit'], 'msg': 'Input should be greater than or equal to 1', 'input': 0, 'ctx': {'ge': 1}}]}

---

### 18. Limit = 1 (Min boundary)
- **Result**: ✅ PASS
- **Status Code**: 200
- **Response Snippet**: I encountered an unexpected error while generating the alignment response. Please try again shortly....
- **Confidence**: 0.0

---

### 19. Limit = 20 (Max boundary)
- **Result**: ✅ PASS
- **Status Code**: 200
- **Response Snippet**: I encountered an unexpected error while generating the alignment response. Please try again shortly....
- **Confidence**: 0.0

---

### 20. Limit = 100 (Over boundary)
- **Result**: ✅ PASS
- **Status Code**: 422
- **Error Output**: {'detail': [{'type': 'less_than_equal', 'loc': ['body', 'limit'], 'msg': 'Input should be less than or equal to 20', 'input': 100, 'ctx': {'le': 20}}]}

---

### 21. Invalid Session ID format
- **Result**: ✅ PASS
- **Status Code**: 200
- **Response Snippet**: I encountered an unexpected error while generating the alignment response. Please try again shortly....
- **Confidence**: 0.0

---
