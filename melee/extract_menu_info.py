"""Extract Menu Info gecko payload layout and parsing (crowd-control fork).

Mirrors gecko/ExtractMenuInfo/SendMenuFrame.asm. EXI transfer length is 0x4C
(command byte at 0x0 plus payload bytes 0x1–0x4B). Offline CSS CPU fields:

- 0x41–0x44: CPU level bytes (CSSData->players[i].cpu_level +0x0F)
- 0x45–0x48: CSSDoor.is_hold_cpu_slider (+0x12) at mnCharSel_803F0DFC.doors[i]

See doldecomp/melee src/melee/mn/types.h (PlayerInitData, CSSDoor).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from melee import enums

if TYPE_CHECKING:
    from melee.gamestate import GameState, PlayerState

EXI_TRANSFER_LEN = 0x4C
"""Bytes sent by SendMenuFrame (PAYLOAD_LEN 0x4B + command at 0x0)."""

# Scene halfwords (offset 0x1, big-endian u16).
SCENE_PRESS_START = 0x0000
SCENE_MAIN_MENU = 0x0001
SCENE_OFFLINE_CSS = 0x0002
SCENE_SLIPPI_ONLINE_CSS = 0x0008
SCENE_OFFLINE_SSS = 0x0102
SCENE_ONLINE_SSS = 0x0108
SCENE_IN_GAME = 0x0202
SCENE_ONLINE_IN_GAME = 0x0208
SCENE_SUDDEN_DEATH = 0x0302
SCENE_POSTGAME = 0x0402


def scene_to_menu_state(scene: int) -> enums.Menu:
    if scene == SCENE_OFFLINE_CSS:
        return enums.Menu.CHARACTER_SELECT
    if scene in (SCENE_OFFLINE_SSS, SCENE_ONLINE_SSS):
        return enums.Menu.STAGE_SELECT
    if scene == SCENE_IN_GAME:
        return enums.Menu.IN_GAME
    if scene == SCENE_SUDDEN_DEATH:
        return enums.Menu.SUDDEN_DEATH
    if scene == SCENE_POSTGAME:
        return enums.Menu.POSTGAME_SCORES
    if scene == SCENE_MAIN_MENU:
        return enums.Menu.MAIN_MENU
    if scene == SCENE_SLIPPI_ONLINE_CSS:
        return enums.Menu.SLIPPI_ONLINE_CSS
    if scene == SCENE_PRESS_START:
        return enums.Menu.PRESS_START
    return enums.Menu.UNKNOWN_MENU


def menu_state_needs_css_players(menu_state: enums.Menu) -> bool:
    return menu_state in (
        enums.Menu.CHARACTER_SELECT,
        enums.Menu.SLIPPI_ONLINE_CSS,
        enums.Menu.STAGE_SELECT,
    )


def _read_u8(event_bytes: bytes, offset: int) -> int:
    return int(np.ndarray((1,), ">B", event_bytes, offset)[0])


def _read_u16(event_bytes: bytes, offset: int) -> int:
    return int(np.ndarray((1,), ">H", event_bytes, offset)[0])


def _read_i32(event_bytes: bytes, offset: int) -> int:
    return int(np.ndarray((1,), ">i", event_bytes, offset)[0])


def _read_u32(event_bytes: bytes, offset: int) -> int:
    return int(np.ndarray((1,), ">I", event_bytes, offset)[0])


def _read_f32(event_bytes: bytes, offset: int) -> float:
    return float(np.ndarray((1,), ">f", event_bytes, offset)[0])


def _fresh_player_states() -> dict[int, PlayerState]:
    from melee.gamestate import PlayerState

    return {
        1: PlayerState(),
        2: PlayerState(),
        3: PlayerState(),
        4: PlayerState(),
    }


def apply_extract_menu_info_payload(event_bytes: bytes, gamestate: GameState) -> None:
    """Update *gamestate* from a SendMenuFrame EXI buffer."""
    scene = _read_u16(event_bytes, 0x1)
    menu_state = scene_to_menu_state(scene)
    gamestate.menu_state = menu_state

    if menu_state_needs_css_players(menu_state):
        gamestate.players = _fresh_player_states()

    if menu_state in (enums.Menu.CHARACTER_SELECT, enums.Menu.SLIPPI_ONLINE_CSS):
        _apply_css_screen_fields(event_bytes, gamestate)

    if menu_state == enums.Menu.STAGE_SELECT:
        _apply_stage_select_fields(event_bytes, gamestate, scene)

    gamestate.frame = _read_i32(event_bytes, 0x39)

    try:
        gamestate.submenu = enums.SubMenu(_read_u8(event_bytes, 0x3D))
    except (TypeError, ValueError):
        gamestate.submenu = enums.SubMenu.UNKNOWN_SUBMENU

    try:
        gamestate.menu_selection = _read_u8(event_bytes, 0x3E)
    except TypeError:
        gamestate.menu_selection = 0

    _apply_costume_fields(event_bytes, gamestate)
    _apply_online_nametag_submenu(event_bytes, gamestate)
    _apply_cpu_level_fields(event_bytes, gamestate)
    _apply_cpu_slider_fields(event_bytes, gamestate)


def _apply_css_screen_fields(event_bytes: bytes, gamestate: GameState) -> None:
    for port, (x_off, y_off) in enumerate(
        ((0x3, 0x7), (0xB, 0xF), (0x13, 0x17), (0x1B, 0x1F)),
        start=1,
    ):
        player = gamestate.players[port]
        player.controller_status = enums.ControllerStatus(_read_u8(event_bytes, 0x24 + port))
        player.cursor.x = np.float32(_read_f32(event_bytes, x_off))
        player.cursor.y = np.float32(_read_f32(event_bytes, y_off))
        try:
            character = enums.to_internal(_read_u8(event_bytes, 0x28 + port))
            player.character = character
            player.character_selected = character
        except TypeError:
            player.character = enums.Character.UNKNOWN_CHARACTER
            player.character_selected = enums.Character.UNKNOWN_CHARACTER
        try:
            player.coin_down = _read_u8(event_bytes, 0x2C + port) == 2
        except TypeError:
            player.coin_down = False

    gamestate.ready_to_start = _read_u8(event_bytes, 0x23)


def _apply_stage_select_fields(
    event_bytes: bytes,
    gamestate: GameState,
    scene: int,
) -> None:
    try:
        gamestate.stage = enums.Stage(_read_u8(event_bytes, 0x24))
    except ValueError:
        gamestate.stage = enums.Stage.NO_STAGE

    # gecko/ExtractMenuInfo fills cursors only on offline SSS (0x0102).
    if scene != SCENE_OFFLINE_SSS:
        return

    cursor_x = np.float32(_read_f32(event_bytes, 0x31))
    cursor_y = np.float32(_read_f32(event_bytes, 0x35))
    for player in gamestate.players.values():
        player.cursor.x = cursor_x
        player.cursor.y = cursor_y


def _apply_costume_fields(event_bytes: bytes, gamestate: GameState) -> None:
    try:
        if gamestate.menu_state == enums.Menu.SLIPPI_ONLINE_CSS:
            gamestate.players[1].costume = _read_u8(event_bytes, 0x3F)
    except (TypeError, KeyError):
        pass


def _apply_online_nametag_submenu(event_bytes: bytes, gamestate: GameState) -> None:
    if gamestate.menu_state != enums.Menu.SLIPPI_ONLINE_CSS:
        return
    try:
        nametag = _read_u8(event_bytes, 0x40)
        if nametag == 0x05:
            gamestate.submenu = enums.SubMenu.NAME_ENTRY_SUBMENU
        elif nametag == 0x00:
            gamestate.submenu = enums.SubMenu.ONLINE_CSS
    except TypeError:
        pass


def _apply_cpu_level_fields(event_bytes: bytes, gamestate: GameState) -> None:
    """Parse CPU level bytes at 0x41–0x44 (PlayerInitData.cpu_level via gecko)."""
    if gamestate.menu_state != enums.Menu.CHARACTER_SELECT:
        return
    try:
        for port in range(1, 5):
            cpu_level = _read_u8(event_bytes, 0x40 + port)
            if (
                gamestate.players[port].controller_status
                != enums.ControllerStatus.CONTROLLER_CPU
            ):
                cpu_level = 0
            gamestate.players[port].cpu_level = cpu_level
    except (TypeError, KeyError):
        pass


def _apply_cpu_slider_fields(event_bytes: bytes, gamestate: GameState) -> None:
    """Parse slider-held bytes at 0x45–0x48 (CSSDoor.is_hold_cpu_slider via gecko)."""
    if gamestate.menu_state != enums.Menu.CHARACTER_SELECT:
        return
    try:
        for port in range(1, 5):
            holding = _read_u8(event_bytes, 0x44 + port)
            if (
                gamestate.players[port].controller_status
                != enums.ControllerStatus.CONTROLLER_CPU
            ):
                holding = 0
            gamestate.players[port].is_holding_cpu_slider = bool(holding)
    except (TypeError, KeyError):
        pass
