import asyncio

from smoke_phase2_3_7_runtime_tools import run_smoke


async def main() -> None:
    await run_smoke()
    print("Phase 2.4 runtime governance smoke passed.")


if __name__ == "__main__":
    asyncio.run(main())
