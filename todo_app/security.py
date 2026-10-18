"""密码哈希与令牌哈希。"""

import hashlib
import hmac
import re

from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(password):
    """使用 Werkzeug 的安全哈希（默认 scrypt，自带随机 salt）。"""
    return generate_password_hash(password)


def legacy_hash_password(password):
    """旧版无盐 SHA-256，仅用于校验历史密码并在登录后自动升级。"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(stored_hash, password):
    """
    校验密码。
    返回 (是否匹配, 是否需要升级哈希)。
    """
    if not stored_hash:
        return False, False

    try:
        if check_password_hash(stored_hash, password):
            return True, False
    except (ValueError, TypeError):
        # 历史 SHA-256 哈希不是 Werkzeug 格式，会在这里失败
        pass

    if isinstance(stored_hash, str) and re.fullmatch(r"[0-9a-f]{64}", stored_hash):
        if hmac.compare_digest(stored_hash, legacy_hash_password(password)):
            return True, True

    return False, False


def hash_reset_token(token):
    """令牌只以哈希形式落库，数据库泄露时无法直接使用。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
