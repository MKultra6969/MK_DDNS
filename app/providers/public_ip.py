import aiohttp


async def get_public_ip(session: aiohttp.ClientSession) -> str:
    async with session.get("https://api.ipify.org", timeout=10) as response:
        response.raise_for_status()
        return (await response.text()).strip()

