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

class MenuEventPayloadTests(unittest.TestCase):
    def _console(self):
        return melee.Console(is_dolphin=False, allow_old_version=True)

    def test_offline_css_clears_cpu_level_for_human_ports(self) -> None:
        console = self._console()
        payload = bytearray(0x50)
        payload[0x1:0x3] = (0x0002).to_bytes(2, byteorder="big")
        payload[0x25] = 0  # port 1 human
        payload[0x41] = 9

        gamestate = melee.GameState()
        console._Console__handle_slippstream_menu_event(bytes(payload), gamestate)

        self.assertEqual(gamestate.menu_state, melee.Menu.CHARACTER_SELECT)
        self.assertEqual(gamestate.players[1].cpu_level, 0)

    def test_offline_css_reads_cpu_level_for_cpu_ports(self) -> None:
        console = self._console()
        payload = bytearray(0x50)
        payload[0x1:0x3] = (0x0002).to_bytes(2, byteorder="big")
        payload[0x25] = 1  # port 1 CPU
        payload[0x41] = 9

        gamestate = melee.GameState()
        console._Console__handle_slippstream_menu_event(bytes(payload), gamestate)

        self.assertEqual(gamestate.players[1].cpu_level, 9)

    def test_offline_css_clears_cpu_slider_flag_for_human_ports(self) -> None:
        console = self._console()
        payload = bytearray(0x50)
        payload[0x1:0x3] = (0x0002).to_bytes(2, byteorder="big")
        payload[0x25] = 0  # port 1 human
        payload[0x45] = 1  # garbage slider-held byte

        gamestate = melee.GameState()
        console._Console__handle_slippstream_menu_event(bytes(payload), gamestate)

        self.assertEqual(gamestate.menu_state, melee.Menu.CHARACTER_SELECT)
        self.assertFalse(gamestate.players[1].is_holding_cpu_slider)

    def test_offline_css_reads_cpu_slider_held(self) -> None:
        console = self._console()
        payload = bytearray(0x50)
        payload[0x1:0x3] = (0x0002).to_bytes(2, byteorder="big")
        payload[0x25] = 1  # port 1 CPU
        payload[0x45] = 1

        gamestate = melee.GameState()
        console._Console__handle_slippstream_menu_event(bytes(payload), gamestate)

        self.assertTrue(gamestate.players[1].is_holding_cpu_slider)

    def test_offline_sss_reads_stage_cursors(self) -> None:
        import struct

        console = self._console()
        payload = bytearray(0x50)
        payload[0x1:0x3] = (0x0102).to_bytes(2, byteorder="big")
        struct.pack_into(">f", payload, 0x31, 1.5)
        struct.pack_into(">f", payload, 0x35, 2.5)

        gamestate = melee.GameState()
        console._Console__handle_slippstream_menu_event(bytes(payload), gamestate)

        self.assertEqual(gamestate.menu_state, melee.Menu.STAGE_SELECT)
        self.assertAlmostEqual(float(gamestate.players[1].cursor.x), 1.5)
        self.assertAlmostEqual(float(gamestate.players[1].cursor.y), 2.5)

    def test_online_sss_does_not_apply_stage_cursors(self) -> None:
        import struct

        console = self._console()
        payload = bytearray(0x50)
        payload[0x1:0x3] = (0x0108).to_bytes(2, byteorder="big")
        struct.pack_into(">f", payload, 0x31, 9.0)
        struct.pack_into(">f", payload, 0x35, 8.0)

        gamestate = melee.GameState()
        console._Console__handle_slippstream_menu_event(bytes(payload), gamestate)

        self.assertEqual(gamestate.menu_state, melee.Menu.STAGE_SELECT)
        self.assertAlmostEqual(float(gamestate.players[1].cursor.x), 0.0)
        self.assertAlmostEqual(float(gamestate.players[1].cursor.y), 0.0)


class MenuEventPauseTests(unittest.TestCase):
    def _console(self):
        return melee.Console(is_dolphin=False, allow_old_version=True)

    def _send(self, payload, gamestate=None):
        console = self._console()
        gamestate = gamestate or melee.GameState()
        console._Console__handle_slippstream_menu_event(bytes(payload), gamestate)
        return gamestate

    def test_match_pause_payload_parsed(self) -> None:
        payload = bytearray(0x60)
        payload[0x1:0x3] = (0x0202).to_bytes(2, byteorder="big")
        payload[0x4C] = 1  # pause slot port index 1 -> port 2
        payload[0x4D] = 0xFF  # pauser -1 as s8
        payload[0x4E] = 10
        payload[0x4F] = 3
        payload[0x50] = 1
        payload[0x51] = 0
        payload[0x52] = 0

        gamestate = self._send(payload)

        self.assertFalse(gamestate.match_pause.is_paused)
        self.assertIsNone(gamestate.match_pause.pause_port)
        self.assertEqual(gamestate.match_pause.raw_pause_slot, 1)
        self.assertEqual(gamestate.match_pause.pauser_port_index, -1)
        self.assertEqual(gamestate.match_pause.pause_timer_frames, 10)
        self.assertEqual(gamestate.match_pause.pause_cooldown_frames, 3)
        self.assertTrue(gamestate.match_pause.hud_enabled)
        self.assertFalse(gamestate.match_pause.match_over)
        self.assertFalse(gamestate.match_pause.match_end_pending)

    def test_match_pause_unpaused_cooldown(self) -> None:
        payload = bytearray(0x60)
        payload[0x1:0x3] = (0x0202).to_bytes(2, byteorder="big")
        payload[0x4C] = 0
        payload[0x4F] = 6
        payload[0x50] = 1

        gamestate = self._send(payload)

        self.assertFalse(gamestate.match_pause.is_paused)
        self.assertIsNone(gamestate.match_pause.pause_port)
        self.assertEqual(gamestate.match_pause.pause_cooldown_frames, 6)

    def test_pause_open_event_marks_paused(self) -> None:
        payload = bytearray(0x60)
        payload[0x1:0x3] = (0x0202).to_bytes(2, byteorder="big")
        payload[0x4C] = 1  # port index 1 -> port 2
        payload[0x53] = 1  # pause-open discriminator

        gamestate = self._send(payload)

        self.assertTrue(gamestate.match_pause.is_paused)
        self.assertEqual(gamestate.match_pause.pause_port, 2)
        self.assertTrue(gamestate.match_pause.pause_open_event)
        self.assertFalse(gamestate.match_pause.pause_close_event)
        # Pause open/close payloads short-circuit before CSS/costume/cpu parsing.
        self.assertEqual(gamestate.players, {})

    def test_pause_close_event_clears_paused(self) -> None:
        gamestate = melee.GameState()

        open_payload = bytearray(0x60)
        open_payload[0x1:0x3] = (0x0202).to_bytes(2, byteorder="big")
        open_payload[0x4C] = 0
        open_payload[0x53] = 1  # pause-open
        self._send(open_payload, gamestate)
        self.assertTrue(gamestate.match_pause.is_paused)

        close_payload = bytearray(0x60)
        close_payload[0x1:0x3] = (0x0202).to_bytes(2, byteorder="big")
        close_payload[0x4C] = 0
        close_payload[0x53] = 2  # pause-close
        self._send(close_payload, gamestate)

        self.assertFalse(gamestate.match_pause.is_paused)
        self.assertFalse(gamestate.match_pause.pause_open_event)
        self.assertTrue(gamestate.match_pause.pause_close_event)

if __name__ == '__main__':
    unittest.main()
