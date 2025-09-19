"""
ユーティリティ関数
"""

import os
import yaml
import sys
from datetime import datetime
from typing import Dict, Any
from loguru import logger


def setup_logging(log_level: str = "INFO", log_file: str = None):
    """
    ログ設定

    Args:
        log_level: ログレベル
        log_file: ログファイルパス（Noneの場合は自動生成）
    """
    # 既存のログハンドラーをクリア
    logger.remove()

    # コンソール出力設定
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )

    # ファイル出力設定
    if log_file is None:
        log_dir = "data/logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"screener_{datetime.now().strftime('%Y%m%d')}.log")

    logger.add(
        log_file,
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="1 day",
        retention="7 days",
        encoding="utf-8"
    )

    logger.info(f"Logging initialized. Level: {log_level}, File: {log_file}")


def load_config(config_path: str) -> Dict[str, Any]:
    """
    設定ファイル読み込み

    Args:
        config_path: 設定ファイルパス

    Returns:
        Dict: 設定辞書

    Raises:
        FileNotFoundError: 設定ファイルが見つからない
        yaml.YAMLError: YAML解析エラー
    """
    try:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        logger.info(f"Configuration loaded from {config_path}")
        return config

    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file {config_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        raise


def format_currency(amount: float, currency: str = "¥") -> str:
    """
    通貨フォーマット

    Args:
        amount: 金額
        currency: 通貨記号

    Returns:
        str: フォーマットされた通貨文字列
    """
    if amount == 0:
        return "0"

    # 億円単位
    if amount >= 100000000:
        return f"{amount / 100000000:.1f}億"
    # 万円単位
    elif amount >= 10000:
        return f"{amount / 10000:.1f}万"
    # 千円単位
    elif amount >= 1000:
        return f"{amount / 1000:.1f}千"
    else:
        return f"{amount:,.0f}"


def format_percentage(value: float, decimal_places: int = 1) -> str:
    """
    パーセンテージフォーマット

    Args:
        value: 値（小数）
        decimal_places: 小数点以下桁数

    Returns:
        str: フォーマットされたパーセンテージ
    """
    percentage = value * 100
    if percentage > 0:
        return f"+{percentage:.{decimal_places}f}%"
    else:
        return f"{percentage:.{decimal_places}f}%"


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    安全な除算（ゼロ除算回避）

    Args:
        numerator: 分子
        denominator: 分母
        default: 分母が0の場合のデフォルト値

    Returns:
        float: 除算結果
    """
    if denominator == 0:
        return default
    return numerator / denominator


def validate_symbol(symbol: str) -> bool:
    """
    銘柄コードの妥当性チェック

    Args:
        symbol: 銘柄コード

    Returns:
        bool: 妥当かどうか
    """
    if not symbol:
        return False

    # 基本的な形式チェック（例: "7203.T"）
    if '.' in symbol:
        code, market = symbol.split('.')
        # 4桁の数字コード + ".T"の形式
        if len(code) == 4 and code.isdigit() and market == 'T':
            return True

    return False


def get_market_status() -> str:
    """
    市場状態取得

    Returns:
        str: 市場状態（"pre_market", "open", "after_hours", "closed"）
    """
    now = datetime.now()
    weekday = now.weekday()  # 0=月曜日, 6=日曜日

    # 土日は休場
    if weekday >= 5:
        return "closed"

    hour = now.hour
    minute = now.minute
    time_minutes = hour * 60 + minute

    # 市場時間（JST）
    pre_market_start = 8 * 60  # 08:00
    market_open = 9 * 60       # 09:00
    market_close = 15 * 60     # 15:00
    after_hours_end = 16 * 60  # 16:00

    if time_minutes < pre_market_start:
        return "closed"
    elif time_minutes < market_open:
        return "pre_market"
    elif time_minutes < market_close:
        return "open"
    elif time_minutes < after_hours_end:
        return "after_hours"
    else:
        return "closed"


def is_trading_day() -> bool:
    """
    取引日かどうかチェック

    Returns:
        bool: 取引日かどうか
    """
    now = datetime.now()
    weekday = now.weekday()

    # 土日は非取引日
    if weekday >= 5:
        return False

    # 祝日チェック（簡易版 - 実際の実装では祝日カレンダーを使用）
    # 年末年始
    if (now.month == 12 and now.day >= 30) or (now.month == 1 and now.day <= 3):
        return False

    return True


def clean_text(text: str) -> str:
    """
    テキストクリーニング

    Args:
        text: 元のテキスト

    Returns:
        str: クリーニング済みテキスト
    """
    if not text:
        return ""

    # 改行・タブを空白に置換
    text = text.replace('\n', ' ').replace('\t', ' ')

    # 連続する空白を単一の空白に
    import re
    text = re.sub(r'\s+', ' ', text)

    # 前後の空白を削除
    text = text.strip()

    return text


def calculate_risk_reward_ratio(
    entry_price: float,
    stop_loss: float,
    take_profit: float
) -> float:
    """
    リスクリワード比率計算

    Args:
        entry_price: エントリー価格
        stop_loss: ストップロス価格
        take_profit: 利確価格

    Returns:
        float: リスクリワード比率
    """
    if entry_price <= 0 or stop_loss <= 0 or take_profit <= 0:
        return 0.0

    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)

    return safe_divide(reward, risk, 0.0)


def get_file_size_mb(filepath: str) -> float:
    """
    ファイルサイズ取得（MB）

    Args:
        filepath: ファイルパス

    Returns:
        float: ファイルサイズ（MB）
    """
    if not os.path.exists(filepath):
        return 0.0

    size_bytes = os.path.getsize(filepath)
    return size_bytes / (1024 * 1024)


def ensure_directory(filepath: str):
    """
    ディレクトリ存在確認・作成

    Args:
        filepath: ファイルパス
    """
    directory = os.path.dirname(filepath)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        logger.debug(f"Created directory: {directory}")


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """
    文字列切り詰め

    Args:
        text: 元の文字列
        max_length: 最大長
        suffix: 切り詰め時の接尾辞

    Returns:
        str: 切り詰め済み文字列
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix