import random
import re
import string


PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$")
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,20}$")


def valid_com_email(email: str) -> bool:
    return email.lower().endswith(".com")


def valid_password(password: str) -> bool:
    return bool(PASSWORD_PATTERN.match(password))

def valid_username(username: str) -> bool:
    return bool(USERNAME_PATTERN.match(username))


def gen_numeric_code(length: int = 6) -> str:
    return "".join(random.choice(string.digits) for _ in range(length))
