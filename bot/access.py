"""Контроль доступа: пропускаем апдейты только от whitelist Telegram id."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from .config import WHITELIST


def is_allowed(user_id: int | None) -> bool:
    return user_id is not None and user_id in WHITELIST


class WhitelistMiddleware(BaseMiddleware):
    """Outer-middleware: молча игнорирует чужих, кратко отвечая «нет доступа»."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        user_id = user.id if user else None

        if is_allowed(user_id):
            return await handler(event, data)

        # Вежливый отказ для сообщений/коллбеков; остальные апдейты просто игнорируем.
        inner = event.event if isinstance(event, Update) else event
        if isinstance(inner, Message):
            await inner.answer("⛔ Нет доступа. Этот бот личный.")
        elif isinstance(inner, CallbackQuery):
            await inner.answer("⛔ Нет доступа", show_alert=True)
        return None
