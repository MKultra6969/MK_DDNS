DB_PATH = "data/ddns.db"
LEGACY_DB_PATHS = (
    "OldDB/ddns.db",
    "ddns.db",
)

PROVIDER_1984 = "1984hosting"
PROVIDER_CLOUDFLARE = "cloudflare"

PROVIDER_LABELS = {
    PROVIDER_1984: "1984Hosting",
    PROVIDER_CLOUDFLARE: "Cloudflare",
}


def provider_label(provider: str) -> str:
    return PROVIDER_LABELS.get(provider, provider)


def _secret_key(provider: str) -> str:
    return f"provider:{provider}:secret"
