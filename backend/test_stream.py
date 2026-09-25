import asyncio
import httpx
import json

async def main():
    payload = {
        "message": "write a python code for a complete calculator and try running it"
    }
    
    print("Sending request...")
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", "http://localhost:8000/api/agent/stream", json=payload) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data["type"] == "token":
                            print(data["text"], end="", flush=True)
                        elif data["type"] == "phase":
                            print(f"\n[PHASE: {data['phase']}]")
                        elif data["type"] == "done":
                            print("\n[DONE]")
                        elif data["type"] == "error":
                            print(f"\n[ERROR: {data['message']}]")
    except Exception as e:
        print(f"\n[EXCEPTION: {e}]")

asyncio.run(main())
