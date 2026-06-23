"""
run_demo.py

Starts the demo target app and fires a chaos session against it.
Run from the project root:
    python run_demo.py

What it does:
1. Starts demo_target/demo_app.py on port 8001
2. Waits for it to be ready
3. POSTs a chaos session to the backend (port 8000) targeting port 8001
4. Prints the session ID so you can open the frontend and watch live
"""

import asyncio
import subprocess
import sys
import httpx
import time


BACKEND_URL = "http://localhost:8000"
TARGET_URL  = "http://localhost:8001"


async def wait_for_service(url: str, name: str, timeout: int = 30):
    print(f"  Waiting for {name}...", end="", flush=True)
    start = time.time()
    async with httpx.AsyncClient() as client:
        while time.time() - start < timeout:
            try:
                r = await client.get(f"{url}/health", timeout=2.0)
                if r.status_code == 200:
                    print(" ready!")
                    return True
            except Exception:
                pass
            await asyncio.sleep(1)
            print(".", end="", flush=True)
    print(f" TIMEOUT after {timeout}s")
    return False


async def start_chaos_session(github_repo: str = None) -> str:
    payload = {
        "target_url": TARGET_URL,
        "target_name": "Knowbite API (Demo)",
    }
    if github_repo:
        payload["github_repo"] = github_repo

    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BACKEND_URL}/api/sessions", json=payload, timeout=10.0)
        r.raise_for_status()
        data = r.json()
        return data["session_id"]


async def poll_session(session_id: str):
    print(f"\n  Session ID: {session_id}")
    print(f"  Live dashboard: http://localhost:3000/sessions/{session_id}")
    print(f"  API progress:   {BACKEND_URL}/api/sessions/{session_id}")
    print("\n  Polling progress...")

    async with httpx.AsyncClient() as client:
        last_status = None
        while True:
            await asyncio.sleep(3)
            try:
                r = await client.get(
                    f"{BACKEND_URL}/api/sessions/{session_id}", timeout=5.0
                )
                data = r.json()
                status = data.get("status")
                if status != last_status:
                    print(f"  -> {status.upper()}: "
                          f"endpoints={data.get('endpoints_found', 0)} | "
                          f"failures={data.get('failures_injected', 0)} | "
                          f"unhandled={data.get('unhandled_count', 0)} | "
                          f"fixes={data.get('fixes_generated', 0)}")
                    last_status = status

                if status in ("complete", "failed"):
                    if status == "complete":
                        prs = data.get("pull_requests", [])
                        print(f"\n  ✅ Complete!")
                        print(f"     Risk score: check report")
                        print(f"     PRs opened: {len(prs)}")
                        for pr in prs:
                            print(f"     → {pr['pr_url']}")
                    else:
                        print(f"\n  ❌ Session failed")
                    break
            except Exception as e:
                print(f"  Poll error: {e}")


async def main():
    github_repo = sys.argv[1] if len(sys.argv) > 1 else None

    print("\n=== Chaos Agent Demo ===\n")

    # Check backend is running
    print("1. Checking backend...")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{BACKEND_URL}/health", timeout=3.0)
            data = r.json()
            print(f"   Backend ready. GitHub integration: {data.get('github_integration')}")
    except Exception:
        print(f"   ❌ Backend not running. Start it first:")
        print(f"      uvicorn backend.main:app --reload --port 8000")
        sys.exit(1)

    # Start demo target
    print("\n2. Starting demo target app on port 8001...")
    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath("demo_target")
    target_proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "demo_target.demo_app:app",
            "--port", "8001",
            "--log-level", "warning",
        ],
        cwd=".",
        env=env,
    )

    ready = await wait_for_service(TARGET_URL, "demo target")
    if not ready:
        target_proc.terminate()
        sys.exit(1)

    # Fire chaos session
    print(f"\n3. Starting chaos session{f' with GitHub repo: {github_repo}' if github_repo else ''}...")
    try:
        session_id = await start_chaos_session(github_repo)
        await poll_session(session_id)
    finally:
        print("\n4. Stopping demo target...")
        target_proc.terminate()
        target_proc.wait()
        print("   Done.")


if __name__ == "__main__":
    asyncio.run(main())
