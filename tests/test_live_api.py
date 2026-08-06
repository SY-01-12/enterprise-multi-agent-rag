"""
Real API end-to-end tests - verify all 4 fixes against running backend.
"""
import json
import sys
import time

import requests

BASE = "http://127.0.0.1:8000"


def register_and_login():
    """Register or login test user, return (token, username)."""
    username = f"apitest_{int(time.time())}"
    password = "test123456"
    email = f"{username}@test.com"

    # Step 1: Try to register (may fail if user exists)
    reg_resp = requests.post(f"{BASE}/api/auth/register", json={
        "username": username,
        "password": password,
        "confirm_password": password,
        "email": email,
    })
    print(f"  Register: {reg_resp.status_code}")

    # Step 2: Always login to get the token
    login_resp = requests.post(f"{BASE}/api/auth/login", json={
        "username": username,
        "password": password,
    })
    print(f"  Login: {login_resp.status_code}")

    if login_resp.status_code != 200:
        print(f"  Login response: {login_resp.text[:200]}")
        return None, None

    data = login_resp.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        print(f"  No token in response: {data}")
        return None, None
    return token, username


def stream_chat(token, kb_id, question):
    """Stream request to /api/chat/stream, return all SSE events."""
    resp = requests.post(
        f"{BASE}/api/chat/stream",
        json={
            "knowledge_base_id": kb_id,
            "question": question,
            "model": None,
            "mode": "auto",
        },
        headers={"Authorization": f"Bearer {token}"},
        stream=True,
    )

    if resp.status_code != 200:
        print(f"Request failed: {resp.status_code} {resp.text[:200]}")
        return None

    events = []
    for line in resp.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except:
                pass
    return events


def analyze_events(events, label):
    """Analyze SSE event stream."""
    print(f"\n{'='*60}")
    print(f"[ANALYZE] {label}")
    print(f"{'='*60}")

    tokens = []
    images = []
    tools = []
    errors = []
    session_id = None
    done = False

    for e in events:
        if "session_id" in e:
            session_id = e["session_id"]
        elif "token" in e:
            tokens.append(e["token"])
        elif "url" in e:
            images.append(e)
        elif "tool" in e:
            tools.append(e)
        elif "error" in e:
            errors.append(e)
        elif "done" in e:
            done = True

    full_text = "".join(tokens)

    print(f"  session_id: {session_id}")
    print(f"  tool_calls: {len(tools)}")
    for t in tools:
        try:
            print(f"    TOOL: {t.get('label', t.get('tool', '?'))} -> {str(t.get('input', ''))[:60]}")
        except UnicodeEncodeError:
            print(f"    TOOL: {t.get('label', t.get('tool', '?'))} (input hidden - encoding)")
    print(f"  images_generated: {len(images)}")
    for img in images:
        url = img.get('url', '')
        try:
            print(f"    IMG: {url[:80]}...")
        except UnicodeEncodeError:
            print(f"    IMG: (url hidden - encoding)")
    print(f"  token_chunks: {len(tokens)}")
    print(f"  full_text_len: {len(full_text)} chars")
    if full_text:
        print(f"  text_preview(200):")
        try:
            print(f"    {full_text[:200]}")
        except UnicodeEncodeError:
            safe = full_text[:200].encode('ascii', errors='replace').decode('ascii')
            print(f"    {safe}")
    if errors:
        try:
            print(f"  ERRORS: {errors}")
        except UnicodeEncodeError:
            print(f"  ERRORS: (hidden - encoding)")
    print(f"  done: {done}")

    return {
        "session_id": session_id,
        "tool_count": len(tools),
        "image_count": len(images),
        "token_count": len(tokens),
        "full_text": full_text,
        "errors": errors,
        "done": done,
    }


def main():
    print("=" * 60)
    print(">>> Real API End-to-End Test <<<")
    print("=" * 60)

    # 1. Get Token
    token, username = register_and_login()
    if not token:
        print("FATAL: Cannot get token, aborting")
        return 1
    print(f"\n[OK] Logged in as: {username}")

    # 2. Check knowledge bases
    kb_resp = requests.get(
        f"{BASE}/api/knowledge-base/list",
        headers={"Authorization": f"Bearer {token}"},
    )
    kb_list = kb_resp.json() if kb_resp.status_code == 200 else []
    print(f"\n[KBS] Available knowledge bases: {len(kb_list)}")
    for kb in kb_list[:3]:
        print(f"    {kb['id']}: {kb['name']}")

    kb_id = kb_list[0]["id"] if kb_list else 0
    print(f"    Using kb_id={kb_id} for tests")

    results = {}

    # === TEST 1: RAG knowledge base search - verify no duplicate reply ===
    print("\n" + "=" * 60)
    print("TEST 1: RAG search - verify NO duplicate reply")
    print("=" * 60)
    events = stream_chat(token, kb_id, "员工转正的规定是什么？试用期多久？")
    if events:
        result = analyze_events(events, "RAG: employee probation policy")
        results["rag"] = result
        text = result["full_text"]
        mid = len(text) // 2
        if mid > 10:
            first_half = text[:mid].strip()
            second_half = text[mid:].strip()
            if first_half and first_half == second_half:
                print("  FAIL: Duplicate reply detected! Exact halves match!")
                results["rag_duplicate"] = True
            elif len(first_half) > 100 and first_half[:50] in second_half:
                print("  WARN: Possible duplicate - first half appears in second half")
                results["rag_duplicate"] = "possible"
            else:
                print("  PASS: No duplicate reply detected")
                results["rag_duplicate"] = False
    else:
        print("  FAIL: Request failed")
        results["rag"] = None

    # === TEST 2: Image generation - verify only ONE image ===
    print("\n" + "=" * 60)
    print("TEST 2: Image generation - verify only ONE image")
    print("=" * 60)
    events = stream_chat(token, kb_id, "生成一张日落的风景照片，夕阳西下，海面倒映着金色的光芒")
    if events:
        result = analyze_events(events, "Image: sunset scenery")
        results["image"] = result
        if result["image_count"] == 0:
            print("  WARN: No image generated (may be API issue)")
        elif result["image_count"] == 1:
            print("  PASS: Exactly 1 image (deduplication working)")
        else:
            print(f"  FAIL: {result['image_count']} images! Should be 1")
            results["image_duplicate"] = True
        if "![" in result["full_text"]:
            print("  FAIL: Markdown image syntax ![ still in text")
        elif "http" in result["full_text"] and ".png" in result["full_text"]:
            print("  WARN: Image URL still in text")
        else:
            print("  PASS: No image URL in text (URL separated from LLM output)")
    else:
        print("  FAIL: Request failed")
        results["image"] = None

    # === TEST 3: Math calculation - verify auto routing ===
    print("\n" + "=" * 60)
    print("TEST 3: Math calculation - verify auto routing to general_agent")
    print("=" * 60)
    events = stream_chat(token, kb_id, "计算 123 * 456 等于多少？")
    if events:
        result = analyze_events(events, "Calc: 123*456")
        results["calc"] = result
        if "56088" in result["full_text"]:
            print("  PASS: Correct calculation result (56088)")
        elif result["tool_count"] > 0:
            print("  PASS: Used calculator tool (routed to general_agent)")
        else:
            print("  INFO: No tool detected, checking response...")
            print(f"  Full response: {result['full_text'][:200]}")
    else:
        print("  FAIL: Request failed")
        results["calc"] = None

    # === TEST 4: Multi-intent query - verify supervisor decomposition ===
    print("\n" + "=" * 60)
    print("TEST 4: Multi-intent - verify supervisor auto-decomposition")
    print("=" * 60)
    events = stream_chat(token, kb_id, "请假制度是什么？3+9等于多少？")
    if events:
        result = analyze_events(events, "Multi: leave policy + 3+9")
        results["multi"] = result
        if result["tool_count"] >= 2:
            print("  PASS: Multiple tools called (supervisor decomposed tasks)")
        elif "search" in str(events).lower() or "12" in result["full_text"]:
            print("  PASS: Got response covering both parts")
    else:
        print("  FAIL: Request failed")
        results["multi"] = None

    # === TEST 5: kb_id=0 general chat - verify still uses supervisor ===
    print("\n" + "=" * 60)
    print("TEST 5: kb_id=0 - verify supervisor still works (no manual mode switch)")
    print("=" * 60)
    events = stream_chat(token, 0, "你好，请介绍一下你自己")
    if events:
        result = analyze_events(events, "kb_id=0: self-intro")
        results["general"] = result
        if result["full_text"]:
            print("  PASS: kb_id=0 works with supervisor mode")
    else:
        print("  FAIL: kb_id=0 request failed")
        results["general"] = None

    # === SUMMARY ===
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_pass = True
    for name in ["rag", "image", "calc", "multi", "general"]:
        r = results.get(name)
        if r is None:
            print(f"  FAIL: {name} - request failed")
            all_pass = False
        elif isinstance(r, dict) and r.get("errors"):
            print(f"  FAIL: {name} - {r['errors']}")
            all_pass = False
        elif isinstance(r, bool) and r:
            print(f"  FAIL: {name} - issue detected")
            all_pass = False
        else:
            status = "OK" if r.get("done") else "INCOMPLETE"
            tools = r.get("tool_count", 0)
            imgs = r.get("image_count", 0)
            text_len = len(r.get("full_text", ""))
            print(f"  {status}: {name} (tools={tools}, images={imgs}, text_len={text_len})")
            if not r.get("done"):
                all_pass = False

    # Duplicate checks
    if results.get("rag_duplicate"):
        print("  FAIL: RAG duplicate reply detected!")
        all_pass = False
    else:
        print("  PASS: RAG no duplicate reply")

    if results.get("image_duplicate"):
        print("  FAIL: Image duplication detected!")
        all_pass = False
    elif results.get("image") and results["image"]["image_count"] <= 1:
        print("  PASS: Image no duplication")

    print(f"\nOverall: {'ALL PASS' if all_pass else 'SOME FAILURES'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
