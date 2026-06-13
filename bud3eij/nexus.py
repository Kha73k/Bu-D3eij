"""Nexus utilities for Bu D3eij — everyday tools, done 100% locally.

Pure, GUI-free logic (importable + testable without launching the app), in the
same lazy-import style as the other tool modules. Two tools live here:

* **Converter** — currency (ECB daily rates via the open Frankfurter endpoint,
  cached + seeded so it works offline), units (`pint`), and time zones
  (stdlib `zoneinfo` + the `tzdata` package).
* **QR Code** — build the payload for several content types and render a QR
  with `qrcode` (colours, error-correction, an optional centre logo).

None of this touches the network except `refresh_rates()` (an explicit user
action); everything else runs offline with no account and no usage limits.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from .formats import ConversionError, unique_path

# --------------------------------------------------------------------------- #
# Currency (ECB daily rates, base EUR)
# --------------------------------------------------------------------------- #
# Frankfurter is a free, key-less wrapper around the ECB reference rates. The
# `.dev/v1` host needs a User-Agent (a bare urllib request gets a 403); the data
# is base-EUR and omits EUR itself (we add it back as 1.0 when normalising).
RATES_URL = "https://api.frankfurter.dev/v1/latest"
RATES_TIMEOUT = 10                     # socket timeout (s): a stall fails, not hangs
_UA = "BuD3eij/4.2 (offline currency converter)"

_NEXUS_DIR = Path.home() / ".bud3eij" / "nexus"
RATES_CACHE = _NEXUS_DIR / "rates.json"
_SEED_REL = "assets/data/rates_seed.json"   # bundled snapshot (offline fallback)

# code -> display name (the ECB set + EUR). Used to label the dropdowns; an
# unknown code still works, it just shows without a name.
CURRENCY_NAMES = {
    "EUR": "Euro", "USD": "US Dollar", "GBP": "British Pound",
    "JPY": "Japanese Yen", "AUD": "Australian Dollar", "CAD": "Canadian Dollar",
    "CHF": "Swiss Franc", "CNY": "Chinese Yuan", "HKD": "Hong Kong Dollar",
    "NZD": "New Zealand Dollar", "SEK": "Swedish Krona", "NOK": "Norwegian Krone",
    "DKK": "Danish Krone", "PLN": "Polish Zloty", "CZK": "Czech Koruna",
    "HUF": "Hungarian Forint", "RON": "Romanian Leu", "BGN": "Bulgarian Lev",
    "ISK": "Icelandic Krona", "TRY": "Turkish Lira", "ILS": "Israeli Shekel",
    "INR": "Indian Rupee", "IDR": "Indonesian Rupiah", "KRW": "South Korean Won",
    "MYR": "Malaysian Ringgit", "PHP": "Philippine Peso", "SGD": "Singapore Dollar",
    "THB": "Thai Baht", "ZAR": "South African Rand", "BRL": "Brazilian Real",
    "MXN": "Mexican Peso",
    # USD-pegged Gulf currencies the ECB feed doesn't publish (see USD_PEGGED).
    "BHD": "Bahraini Dinar", "AED": "UAE Dirham", "SAR": "Saudi Riyal",
    "QAR": "Qatari Riyal", "OMR": "Omani Rial",
}

# Currencies pegged to the US dollar that the ECB/Frankfurter feed omits, as
# fixed units-per-USD. Derived from the live/seed USD rate at load time so they
# stay consistent across a refresh (and never need their own data source).
USD_PEGGED = {
    "BHD": 0.376,      # Bahraini Dinar  (1 BHD = 2.65957 USD)
    "OMR": 0.384497,   # Omani Rial
    "AED": 3.6725,     # UAE Dirham
    "SAR": 3.75,       # Saudi Riyal
    "QAR": 3.64,       # Qatari Riyal
}


def _resource(rel: str) -> Path:
    """Path to a bundled resource — works in dev and in a PyInstaller exe."""
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
    return Path(base) / rel


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - missing/corrupt file is fine
        return None


def _normalize_rates(rates: dict) -> dict[str, float]:
    """Coerce to {CODE: float} and guarantee the EUR base is present (1.0)."""
    out = {"EUR": 1.0}
    for code, value in rates.items():
        try:
            out[str(code).upper()] = float(value)
        except (TypeError, ValueError):
            continue
    return out


def _augment_pegged(rates: dict[str, float]) -> dict[str, float]:
    """Add the USD-pegged currencies the feed omits, derived from its USD rate.

    Rates are per-EUR, so a currency pegged at `per_usd` units-per-USD is
    `per_usd * rates['USD']` per EUR. Uses `setdefault`, so a real feed rate
    (should one ever appear) always wins over the peg.
    """
    usd = rates.get("USD")
    if usd:
        for code, per_usd in USD_PEGGED.items():
            rates.setdefault(code, per_usd * usd)
    return rates


def load_rates() -> dict:
    """Return the best available rate table without touching the network.

    Load order is **cache → bundled seed** so a brand-new, offline machine still
    converts. Returns ``{"rates": {CODE: float (base EUR)}, "date": str,
    "source": "cache" | "seed"}``. Raises if neither source exists.
    """
    cached = _read_json(RATES_CACHE)
    if cached and cached.get("rates"):
        return {"rates": _augment_pegged(_normalize_rates(cached["rates"])),
                "date": cached.get("date", "?"), "source": "cache"}
    seed = _read_json(_resource(_SEED_REL))
    if seed and seed.get("rates"):
        return {"rates": _augment_pegged(_normalize_rates(seed["rates"])),
                "date": seed.get("date", "?"), "source": "seed"}
    raise ConversionError(
        "No currency rates available — no cache and no bundled snapshot.")


def refresh_rates() -> dict:
    """Fetch today's ECB rates from Frankfurter, cache them, and return them.

    Returns the same shape as :func:`load_rates` with ``"source": "network"``.
    Raises :class:`ConversionError` on any network/parse failure — the caller
    keeps using the cached table (a refresh failure is a warning, not fatal).
    """
    import urllib.request

    req = urllib.request.Request(RATES_URL, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=RATES_TIMEOUT) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"Could not fetch live rates: {exc}") from exc
    rates = _normalize_rates(data.get("rates", {}))
    if len(rates) <= 1:
        raise ConversionError("Live rates came back empty — keeping the cached set.")
    date = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    try:
        _NEXUS_DIR.mkdir(parents=True, exist_ok=True)
        RATES_CACHE.write_text(  # cache the pure ECB set; pegs are added at load
            json.dumps({"date": date, "base": "EUR", "rates": rates}, indent=2),
            encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - caching is best-effort
        print("Could not cache rates:", exc)
    return {"rates": _augment_pegged(dict(rates)), "date": date, "source": "network"}


def convert_currency(amount: float, src: str, dst: str, rates: dict) -> float:
    """Convert `amount` from currency `src` to `dst` using base-EUR `rates`."""
    src, dst = src.upper(), dst.upper()
    if src not in rates:
        raise ConversionError(f"No rate for {src}.")
    if dst not in rates:
        raise ConversionError(f"No rate for {dst}.")
    return amount / rates[src] * rates[dst]


def currency_label(code: str) -> str:
    """Dropdown label, e.g. ``USD (US Dollar)`` (just the code if unknown)."""
    name = CURRENCY_NAMES.get(code.upper())
    return f"{code} ({name})" if name else code


# --------------------------------------------------------------------------- #
# Units (pint)
# --------------------------------------------------------------------------- #
# category -> [(display label, pint unit string)]. The labels drive the
# dropdowns; the pint strings are passed to convert_units. pint parses the
# offset temperature units correctly (degC/degF/kelvin), which is the whole
# reason we don't roll our own factor table.
UNIT_CATEGORIES: dict[str, list[tuple[str, str]]] = {
    "Length": [
        ("Millimeters", "millimeter"), ("Centimeters", "centimeter"),
        ("Meters", "meter"), ("Kilometers", "kilometer"),
        ("Inches", "inch"), ("Feet", "foot"), ("Yards", "yard"),
        ("Miles", "mile"), ("Nautical miles", "nautical_mile"),
    ],
    "Mass": [
        ("Milligrams", "milligram"), ("Grams", "gram"), ("Kilograms", "kilogram"),
        ("Metric tonnes", "metric_ton"), ("Ounces", "ounce"), ("Pounds", "pound"),
        ("Stone", "stone"),
    ],
    "Temperature": [
        ("Celsius", "degC"), ("Fahrenheit", "degF"), ("Kelvin", "kelvin"),
    ],
    "Area": [
        ("Sq. millimeters", "millimeter**2"), ("Sq. centimeters", "centimeter**2"),
        ("Sq. meters", "meter**2"), ("Hectares", "hectare"),
        ("Sq. kilometers", "kilometer**2"), ("Sq. feet", "foot**2"),
        ("Acres", "acre"), ("Sq. miles", "mile**2"),
    ],
    "Volume": [
        ("Milliliters", "milliliter"), ("Liters", "liter"),
        ("Cubic meters", "meter**3"), ("Teaspoons (US)", "teaspoon"),
        ("Tablespoons (US)", "tablespoon"), ("Cups (US)", "cup"),
        ("Fluid ounces (US)", "fluid_ounce"), ("Pints (US)", "pint"),
        ("Quarts (US)", "quart"), ("Gallons (US)", "gallon"),
    ],
    "Speed": [
        ("Meters / second", "meter/second"), ("Kilometers / hour", "kilometer/hour"),
        ("Miles / hour", "mile/hour"), ("Feet / second", "foot/second"),
        ("Knots", "knot"),
    ],
    "Digital storage": [
        ("Bits", "bit"), ("Bytes", "byte"), ("Kilobytes (1000)", "kilobyte"),
        ("Megabytes (1000)", "megabyte"), ("Gigabytes (1000)", "gigabyte"),
        ("Terabytes (1000)", "terabyte"), ("Kibibytes (1024)", "kibibyte"),
        ("Mebibytes (1024)", "mebibyte"), ("Gibibytes (1024)", "gibibyte"),
        ("Tebibytes (1024)", "tebibyte"),
    ],
    "Time": [
        ("Milliseconds", "millisecond"), ("Seconds", "second"),
        ("Minutes", "minute"), ("Hours", "hour"), ("Days", "day"),
        ("Weeks", "week"), ("Years", "year"),
    ],
    "Energy": [
        ("Joules", "joule"), ("Kilojoules", "kilojoule"), ("Calories", "calorie"),
        ("Kilocalories", "kilocalorie"), ("Watt-hours", "watt_hour"),
        ("Kilowatt-hours", "kilowatt_hour"), ("BTU", "BTU"),
        ("Electronvolts", "electron_volt"),
    ],
    "Pressure": [
        ("Pascals", "pascal"), ("Kilopascals", "kilopascal"), ("Bar", "bar"),
        ("Atmospheres", "atmosphere"), ("PSI", "psi"), ("Torr", "torr"),
        ("mmHg", "mmHg"),
    ],
    "Angle": [
        ("Degrees", "degree"), ("Radians", "radian"), ("Gradians", "gradian"),
        ("Arcminutes", "arcminute"), ("Arcseconds", "arcsecond"),
        ("Turns", "turn"),
    ],
}
DEFAULT_UNIT_CATEGORY = "Length"

_UREG = None  # lazily-created pint UnitRegistry (shared)


def _registry():
    global _UREG
    if _UREG is None:
        import pint  # lazy: parses its big unit-definition file on first use

        _UREG = pint.UnitRegistry()
    return _UREG


def convert_units(value: float, src_unit: str, dst_unit: str) -> float:
    """Convert `value` from `src_unit` to `dst_unit` (pint unit strings).

    Temperature offsets are handled correctly by pint. A mismatched pair (e.g.
    metres → grams) raises a clear :class:`ConversionError`.
    """
    ureg = _registry()
    try:
        return float(ureg.Quantity(value, src_unit).to(dst_unit).magnitude)
    except ConversionError:
        raise
    except Exception as exc:  # noqa: BLE001 - pint raises several error types
        raise ConversionError(
            f"Can't convert {src_unit} to {dst_unit}: {exc}") from exc


# --------------------------------------------------------------------------- #
# Time zones (stdlib zoneinfo + the tzdata package)
# --------------------------------------------------------------------------- #
# A small set of zones for the pinned world-clock list. The user's own zone is
# added by the GUI from the system default.
WORLD_CLOCK_ZONES = [
    "UTC", "America/Los_Angeles", "America/New_York", "Europe/London",
    "Europe/Paris", "Asia/Dubai", "Asia/Kolkata", "Asia/Tokyo",
    "Australia/Sydney",
]

# A short, sensible default list for the time-zone dropdowns — the full IANA set
# (~600 zones) is a scroll-arrow mess, so the GUI shows this until the user types
# (which filters the full `list_timezones()` instead).
COMMON_TIMEZONES = [
    "UTC",
    "America/Los_Angeles", "America/Denver", "America/Chicago",
    "America/New_York", "America/Sao_Paulo",
    "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Madrid",
    "Europe/Rome", "Europe/Istanbul", "Europe/Moscow",
    "Africa/Cairo", "Africa/Johannesburg", "Africa/Lagos",
    "Asia/Dubai", "Asia/Riyadh", "Asia/Tehran", "Asia/Karachi",
    "Asia/Kolkata", "Asia/Dhaka", "Asia/Bangkok", "Asia/Shanghai",
    "Asia/Singapore", "Asia/Hong_Kong", "Asia/Tokyo", "Asia/Seoul",
    "Australia/Perth", "Australia/Sydney", "Pacific/Auckland", "Pacific/Honolulu",
]


def list_timezones() -> list[str]:
    """Sorted list of IANA time-zone names (from the bundled tzdata)."""
    from zoneinfo import available_timezones

    return sorted(available_timezones())


def parse_datetime(text: str) -> datetime:
    """Parse the time-zone tool's free-text input into a naive datetime.

    Accepts ISO (``2026-06-13T14:30``), ``YYYY-MM-DD HH:MM[:SS]``, a bare date,
    or a bare ``HH:MM`` (assumes today). Empty or ``now`` returns the current
    local time.
    """
    text = (text or "").strip()
    if not text or text.lower() == "now":
        return datetime.now().replace(microsecond=0)
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    now = datetime.now()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%H:%M:%S", "%H:%M"):
        try:
            dt = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if fmt.startswith("%H"):  # time only -> today
            dt = dt.replace(year=now.year, month=now.month, day=now.day)
        return dt
    raise ConversionError(
        f"Couldn't read the date/time '{text}'. Try e.g. 2026-06-13 14:30.")


def convert_timezone(dt: datetime, src_tz: str, dst_tz: str) -> datetime:
    """Interpret `dt` as wall-time in `src_tz` and return it in `dst_tz`.

    The result is timezone-aware; a naive `dt` is localised to `src_tz` first.
    """
    from zoneinfo import ZoneInfo

    try:
        src, dst = ZoneInfo(src_tz), ZoneInfo(dst_tz)
    except Exception as exc:  # noqa: BLE001 - unknown zone key
        raise ConversionError(f"Unknown time zone: {exc}") from exc
    dt = dt.replace(tzinfo=src) if dt.tzinfo is None else dt.astimezone(src)
    return dt.astimezone(dst)


def tz_offset_str(dt: datetime) -> str:
    """UTC offset of an aware datetime as ``UTC+05:30`` (``UTC`` for zero)."""
    off = dt.utcoffset()
    if off is None:
        return ""
    total = int(off.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"UTC{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"


# --------------------------------------------------------------------------- #
# QR codes (qrcode)
# --------------------------------------------------------------------------- #
QR_TYPES = ["Text / URL", "Wi-Fi", "Email", "Phone", "SMS", "vCard", "Geo"]
# error-correction letter -> (rough recoverable %, blurb)
QR_EC_LEVELS = {
    "L": "~7%", "M": "~15%", "Q": "~25%", "H": "~30%",
}
WIFI_ENCRYPTIONS = ["WPA/WPA2", "WEP", "None"]


def _esc_wifi(value: str) -> str:
    """Escape the WIFI: payload special characters (\\ ; , : ")."""
    out = []
    for ch in value:
        if ch in "\\;,:\"":
            out.append("\\")
        out.append(ch)
    return "".join(out)


def build_qr_payload(kind: str, fields: dict) -> str:
    """Build the encoded string for a QR content type.

    `kind` is one of :data:`QR_TYPES`; `fields` holds the per-type inputs.
    Returns ``""`` when the essential field(s) are blank so the caller can show
    a 'nothing to encode yet' state instead of a meaningless QR.
    """
    g = lambda k: str(fields.get(k, "") or "").strip()  # noqa: E731

    if kind == "Text / URL":
        return g("text")

    if kind == "Wi-Fi":
        ssid = g("ssid")
        if not ssid:
            return ""
        enc_label = g("encryption") or "WPA/WPA2"
        t = {"WPA/WPA2": "WPA", "WEP": "WEP", "None": "nopass"}.get(enc_label, "WPA")
        parts = [f"WIFI:T:{t}", f"S:{_esc_wifi(ssid)}"]
        if t != "nopass":
            parts.append(f"P:{_esc_wifi(g('password'))}")
        if fields.get("hidden"):
            parts.append("H:true")
        return ";".join(parts) + ";;"

    if kind == "Email":
        to = g("to")
        if not to:
            return ""
        from urllib.parse import quote
        params = []
        if g("subject"):
            params.append("subject=" + quote(g("subject")))
        if g("body"):
            params.append("body=" + quote(g("body")))
        return f"mailto:{to}" + (("?" + "&".join(params)) if params else "")

    if kind == "Phone":
        num = g("number")
        return f"tel:{num}" if num else ""

    if kind == "SMS":
        num = g("number")
        if not num:
            return ""
        msg = g("message")
        return f"SMSTO:{num}:{msg}" if msg else f"SMSTO:{num}"

    if kind == "vCard":
        first, last = g("first"), g("last")
        if not (first or last or g("phone") or g("email")):
            return ""
        lines = ["BEGIN:VCARD", "VERSION:3.0",
                 f"N:{last};{first}", f"FN:{(first + ' ' + last).strip()}"]
        if g("org"):
            lines.append(f"ORG:{g('org')}")
        if g("title"):
            lines.append(f"TITLE:{g('title')}")
        if g("phone"):
            lines.append(f"TEL;TYPE=CELL:{g('phone')}")
        if g("email"):
            lines.append(f"EMAIL:{g('email')}")
        if g("url"):
            lines.append(f"URL:{g('url')}")
        lines.append("END:VCARD")
        return "\n".join(lines)

    if kind == "Geo":
        lat, lon = g("lat"), g("lon")
        return f"geo:{lat},{lon}" if (lat and lon) else ""

    return g("text")


def _ec_constant(ec: str):
    import qrcode.constants as c

    return {"L": c.ERROR_CORRECT_L, "M": c.ERROR_CORRECT_M,
            "Q": c.ERROR_CORRECT_Q, "H": c.ERROR_CORRECT_H}.get(ec, c.ERROR_CORRECT_M)


def make_qr(payload: str, *, ec: str = "M", scale: int = 10, margin: int = 4,
            fg: str = "#000000", bg: str = "#FFFFFF", logo_path=None):
    """Render `payload` to a QR as a PIL ``Image`` (RGBA), for preview or PNG save.

    `ec` is an error-correction letter (L/M/Q/H); a `logo_path` forces H so the
    centre overlay stays recoverable. `scale` is the module pixel size and
    `margin` the quiet-zone width in modules.
    """
    if not payload:
        raise ConversionError("Nothing to encode — fill in the fields first.")
    import qrcode

    if logo_path:
        ec = "H"  # a centre logo eats modules; max recovery keeps it scannable
    qr = qrcode.QRCode(error_correction=_ec_constant(ec),
                       box_size=max(1, int(scale)), border=max(0, int(margin)))
    qr.add_data(payload)
    try:
        qr.make(fit=True)
    except Exception as exc:  # noqa: BLE001 - data too large for any version
        raise ConversionError(f"That's too much data for one QR code: {exc}") from exc
    img = qr.make_image(fill_color=fg, back_color=bg).convert("RGBA")

    if logo_path:
        from PIL import Image

        try:
            logo = Image.open(logo_path).convert("RGBA")
        except Exception as exc:  # noqa: BLE001
            raise ConversionError(f"Couldn't open the logo image: {exc}") from exc
        side = max(1, img.width // 5)
        logo.thumbnail((side, side), Image.LANCZOS)
        # White rounded backing so the logo never sits on dark modules.
        pad = max(2, side // 12)
        box = Image.new("RGBA", (logo.width + 2 * pad, logo.height + 2 * pad),
                        (255, 255, 255, 255))
        box.alpha_composite(logo, (pad, pad))
        img.alpha_composite(box, ((img.width - box.width) // 2,
                                  (img.height - box.height) // 2))
    return img


def make_qr_svg(payload: str, *, ec: str = "M", scale: int = 10, margin: int = 4,
                fg: str = "#000000", bg: str = "#FFFFFF") -> str:
    """Render `payload` to a scalable SVG string (no logo — vector only)."""
    if not payload:
        raise ConversionError("Nothing to encode — fill in the fields first.")
    import io

    import qrcode
    from qrcode.image.svg import SvgPathFillImage

    qr = qrcode.QRCode(error_correction=_ec_constant(ec),
                       box_size=max(1, int(scale)), border=max(0, int(margin)))
    qr.add_data(payload)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(image_factory=SvgPathFillImage).save(buf)
    svg = buf.getvalue().decode("utf-8")
    # SvgPathFillImage emits the modules as fill="#000000" and the background
    # rect as fill="white"; recolour both.
    return svg.replace('fill="#000000"', f'fill="{fg}"').replace(
        'fill="white"', f'fill="{bg}"')


def save_qr(payload: str, out_path, *, fmt: str = "png", overwrite: bool = False,
            ec: str = "M", scale: int = 10, margin: int = 4,
            fg: str = "#000000", bg: str = "#FFFFFF", logo_path=None) -> Path:
    """Render and write a QR to `out_path` (PNG or SVG); return the saved path.

    Unless `overwrite` is set the path is de-duplicated with ``unique_path``
    (` (n)` suffix), matching the rest of the app's save contract.
    """
    out = Path(out_path)
    if not overwrite:
        out = unique_path(out)
    fmt = (fmt or out.suffix.lstrip(".") or "png").lower()
    if fmt == "svg":
        out.write_text(make_qr_svg(payload, ec=ec, scale=scale, margin=margin,
                                   fg=fg, bg=bg), encoding="utf-8")
    else:
        img = make_qr(payload, ec=ec, scale=scale, margin=margin, fg=fg, bg=bg,
                      logo_path=logo_path)
        img.save(out)
    return out
