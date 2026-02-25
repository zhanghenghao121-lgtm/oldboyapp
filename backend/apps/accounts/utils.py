import base64
import io
import random
import re
import string
from PIL import Image, ImageDraw, ImageFont


PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$")


def valid_com_email(email: str) -> bool:
    return email.lower().endswith(".com")


def valid_password(password: str) -> bool:
    return bool(PASSWORD_PATTERN.match(password))


def gen_numeric_code(length: int = 6) -> str:
    return "".join(random.choice(string.digits) for _ in range(length))


def gen_captcha_text(length: int = 4) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def captcha_base64(text: str) -> str:
    img = Image.new("RGB", (120, 40), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("Arial.ttf", 24)
    except Exception:
        font = ImageFont.load_default()
    draw.text((15, 8), text, fill=(20, 40, 70), font=font)
    for _ in range(5):
        x1, y1 = random.randint(0, 120), random.randint(0, 40)
        x2, y2 = random.randint(0, 120), random.randint(0, 40)
        draw.line((x1, y1, x2, y2), fill=(180, 180, 180), width=1)
    stream = io.BytesIO()
    img.save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("utf-8")
