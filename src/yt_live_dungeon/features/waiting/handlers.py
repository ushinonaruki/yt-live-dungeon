from yt_live_dungeon.features.commands.dispatch import HandlerRegistry
from yt_live_dungeon.features.commands.parse import Login, Logout, Ready
from yt_live_dungeon.features.waiting.login import handle_login
from yt_live_dungeon.features.waiting.logout import handle_logout
from yt_live_dungeon.features.waiting.ready import handle_ready


def build_waiting_handlers() -> HandlerRegistry:
    """A fresh handler mapping per call -- never a shared module-global
    registry, so concurrent requests can never see each other's
    handlers.

    Only @login/@logout/@ready are meaningful during WAITING
    (obsidian/.../進行/参加受付.md section 4); every other command has no
    handler here and falls through dispatch()'s NOT_IMPLEMENTED default,
    same as any command CAMP's own handler registry doesn't recognize.
    """
    return {
        Login: handle_login,
        Logout: handle_logout,
        Ready: handle_ready,
    }
