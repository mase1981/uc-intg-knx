"""Module entry point for the KNX Hub integration."""

import asyncio

from uc_intg_knx import main

if __name__ == "__main__":
    asyncio.run(main())
