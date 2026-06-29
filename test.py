#!/usr/bin/python3
import unittest

import melee

class SLPFile(unittest.TestCase):
    """
    Test cases that can be run automatically in the Github cloud environment
    In particular, there are no live dolphin tests here.
    """
    def test_read_file(self):
        """
        Load and parse SLP file
        """
        console = melee.Console(is_dolphin=False,
                                allow_old_version=False,
                                path="test_artifacts/test_game_1.slp")
        self.assertTrue(console.connect())
        framecount = 0
        while True:
            gamestate = console.step()
            framecount += 1
            if gamestate is None:
                self.assertEqual(framecount, 1039)
                break
            if gamestate.frame == -123:
                self.assertEqual(console.slp_version_tuple, (3, 6, 1))
                self.assertEqual(gamestate.players[1].character.value, 1)
                self.assertEqual(gamestate.players[2].character.value, 1)
            if gamestate.frame == 297:
                self.assertEqual(gamestate.players[1].action.value, 0)
                self.assertEqual(gamestate.players[2].action.value, 27)
                self.assertEqual(int(gamestate.players[1].percent), 17)
                self.assertEqual(gamestate.players[2].percent, 0)


    def test_read_old_file(self):
        """
        Load and parse old SLP file
        """
        console = melee.Console(is_dolphin=False,
                                allow_old_version=True,
                                path="test_artifacts/test_game_2.slp")
        self.assertTrue(console.connect())
        framecount = 0
        while True:
            gamestate = console.step()
            framecount += 1
            if gamestate is None:
                self.assertEqual(framecount, 3840)
                break
            if gamestate.frame == -123:
                self.assertEqual(console.slp_version_tuple, (2, 0, 1))
                self.assertEqual(gamestate.players[2].character.value, 3)
                self.assertEqual(gamestate.players[3].character.value, 18)
            if gamestate.frame == 301:
                self.assertEqual(gamestate.players[2].action.value, 88)
                self.assertEqual(gamestate.players[3].action.value, 56)
                self.assertEqual(int(gamestate.players[2].percent), 25)
                self.assertEqual(gamestate.players[3].percent, 0)

    def test_framedata(self):
        """
        Test that frame and stage data retreive correctly
        """
        framedata = melee.FrameData()
        self.assertTrue(framedata.is_attack(melee.Character.FALCO, melee.Action.DAIR))
        self.assertFalse(framedata.is_attack(melee.Character.FALCO, melee.Action.STANDING))

class MenuEventCostumeTests(unittest.TestCase):
    def test_offline_css_reads_port_one_costume(self) -> None:
        console = melee.Console(is_dolphin=False, allow_old_version=True)
        payload = bytearray(0x50)
        payload[0x1:0x3] = (0x0002).to_bytes(2, byteorder="big")
        payload[0x3F] = 4

        gamestate = melee.GameState()
        console._Console__handle_slippstream_menu_event(bytes(payload), gamestate)

        self.assertEqual(gamestate.menu_state, melee.Menu.CHARACTER_SELECT)
        self.assertEqual(gamestate.menu_scene, 0x0002)
        self.assertEqual(gamestate.players[1].costume, 4)
        self.assertEqual(gamestate.players[2].costume, 0)

    def test_postgame_scene_maps_to_postgame_scores(self) -> None:
        console = melee.Console(is_dolphin=False, allow_old_version=True)
        payload = bytearray(0x50)
        payload[0x1:0x3] = (0x0402).to_bytes(2, byteorder="big")

        gamestate = melee.GameState()
        console._Console__handle_slippstream_menu_event(bytes(payload), gamestate)

        self.assertEqual(gamestate.menu_state, melee.Menu.POSTGAME_SCORES)
        self.assertEqual(gamestate.menu_scene, 0x0402)

    def test_online_css_ignores_extended_costume_payload(self) -> None:
        console = melee.Console(is_dolphin=False, allow_old_version=True)
        payload = bytearray(0x50)
        payload[0x1:0x3] = (0x0008).to_bytes(2, byteorder="big")
        payload[0x3F] = 3
        payload[0x49] = 9
        payload[0x4A] = 9
        payload[0x4B] = 9
        gamestate = melee.GameState(
            players={
                1: melee.PlayerState(costume=0),
                2: melee.PlayerState(costume=7),
                3: melee.PlayerState(costume=8),
                4: melee.PlayerState(costume=9),
            }
        )

        console._Console__handle_slippstream_menu_event(bytes(payload), gamestate)

        self.assertEqual(gamestate.menu_state, melee.Menu.SLIPPI_ONLINE_CSS)
        self.assertEqual(gamestate.players[1].costume, 3)
        self.assertEqual(gamestate.players[2].costume, 0)
        self.assertEqual(gamestate.players[3].costume, 0)
        self.assertEqual(gamestate.players[4].costume, 0)

    def test_online_css_assigns_port_one_costume_only(self) -> None:
        console = melee.Console(is_dolphin=False, allow_old_version=True)
        payload = bytearray(0x50)
        payload[0x1:0x3] = (0x0008).to_bytes(2, byteorder="big")
        payload[0x3F] = 3
        gamestate = melee.GameState(
            players={
                1: melee.PlayerState(costume=0),
                2: melee.PlayerState(costume=7),
                3: melee.PlayerState(costume=8),
                4: melee.PlayerState(costume=9),
            }
        )

        console._Console__handle_slippstream_menu_event(bytes(payload), gamestate)

        self.assertEqual(gamestate.menu_state, melee.Menu.SLIPPI_ONLINE_CSS)
        self.assertEqual(gamestate.players[1].costume, 3)
        self.assertEqual(gamestate.players[2].costume, 0)

    def test_extended_payload_reads_per_port_costumes(self) -> None:
        console = melee.Console(is_dolphin=False, allow_old_version=True)
        payload = bytearray(0x50)
        payload[0x1:0x3] = (0x0002).to_bytes(2, byteorder="big")
        payload[0x3F] = 1
        payload[0x49] = 2
        payload[0x4A] = 3
        payload[0x4B] = 4

        gamestate = melee.GameState()
        console._Console__handle_slippstream_menu_event(bytes(payload), gamestate)

        self.assertEqual(gamestate.players[1].costume, 1)
        self.assertEqual(gamestate.players[2].costume, 2)
        self.assertEqual(gamestate.players[3].costume, 3)
        self.assertEqual(gamestate.players[4].costume, 4)

    def test_offline_css_clears_cpu_slider_flag_for_human_ports(self) -> None:
        console = melee.Console(is_dolphin=False, allow_old_version=True)
        payload = bytearray(0x50)
        payload[0x1:0x3] = (0x0002).to_bytes(2, byteorder="big")
        payload[0x25] = 0  # port 1 human
        payload[0x45] = 1  # garbage slider-held byte

        gamestate = melee.GameState()
        console._Console__handle_slippstream_menu_event(bytes(payload), gamestate)

        self.assertEqual(gamestate.menu_state, melee.Menu.CHARACTER_SELECT)
        self.assertEqual(gamestate.players[1].is_holding_cpu_slider, 0)

    def test_match_pause_payload_parsed(self) -> None:
        console = melee.Console(is_dolphin=False, allow_old_version=True)
        payload = bytearray(0x60)
        payload[0x1:0x3] = (0x0202).to_bytes(2, byteorder="big")
        payload[0x4C] = 1  # pause slot port index 1 -> port 2
        payload[0x4D] = 0xFF  # pauser -1 as s8
        payload[0x4E] = 10
        payload[0x4F] = 3
        payload[0x50] = 1
        payload[0x51] = 0
        payload[0x52] = 0

        gamestate = melee.GameState()
        console._Console__handle_slippstream_menu_event(bytes(payload), gamestate)

        self.assertTrue(gamestate.match_pause.is_paused)
        self.assertEqual(gamestate.match_pause.pause_port, 2)
        self.assertEqual(gamestate.match_pause.pauser_port_index, -1)
        self.assertEqual(gamestate.match_pause.pause_timer_frames, 10)
        self.assertEqual(gamestate.match_pause.pause_cooldown_frames, 3)
        self.assertTrue(gamestate.match_pause.hud_enabled)
        self.assertFalse(gamestate.match_pause.match_over)
        self.assertFalse(gamestate.match_pause.match_end_pending)

    def test_match_pause_inactive_slot(self) -> None:
        console = melee.Console(is_dolphin=False, allow_old_version=True)
        payload = bytearray(0x60)
        payload[0x1:0x3] = (0x0202).to_bytes(2, byteorder="big")
        payload[0x4C] = 99

        gamestate = melee.GameState()
        console._Console__handle_slippstream_menu_event(bytes(payload), gamestate)

        self.assertFalse(gamestate.match_pause.is_paused)
        self.assertIsNone(gamestate.match_pause.pause_port)

if __name__ == '__main__':
    unittest.main()
