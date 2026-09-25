import sys
import asyncio
sys.path.insert(0, '.')

from routers.agent import phase_retrieve

async def main():
    print("Testing phase_retrieve...")
    try:
        context, chunks = await phase_retrieve("write a python code for a complete calculator and try running it")
        print(f"Chunks found: {len(chunks)}")
        print(chunks)
    except Exception as e:
        print(f"ERROR: {e}")

asyncio.run(main())
