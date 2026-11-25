"""Offline planner regressions, using only the Python standard library."""
import contextlib
import importlib
import io
import sys
import unittest
from unittest.mock import patch


@contextlib.contextmanager
def no_network():
    """Fail closed if import, planning or the offline CLI attempts networking."""
    targets = (
        "urllib.request.urlopen",
        "urllib.request.OpenerDirector.open",
        "socket.create_connection",
        "socket.getaddrinfo",
        "socket.socket.connect",
        "socket.socket.connect_ex",
    )
    with contextlib.ExitStack() as stack:
        mocks = [stack.enter_context(patch(target, side_effect=AssertionError(
            "Network access is forbidden in offline tests"))) for target in targets]
        yield
        for mock in mocks:
            mock.assert_not_called()


class OfflinePlanTests(unittest.TestCase):
    def test_import_is_quiet_and_offline(self):
        with no_network(), patch.object(sys, "argv", ["touchgrass.py"]):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    importlib.reload(importlib.import_module("touchgrass"))
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "")

    def test_time_and_energy_change_the_plan(self):
        with no_network():
            planner = importlib.import_module("touchgrass")
            for minutes in (10, 90):
                for mood, energy in (("tired", "low"), ("energetic", "high")):
                    with self.subTest(minutes=minutes, mood=mood):
                        text = f"{minutes} minutes and {mood}"
                        self.assertEqual(planner.extract_minutes(text), minutes)
                        self.assertEqual(planner.extract_energy(text), energy)
                        plan = planner.offline_plan(
                            planner.extract_minutes(text), planner.extract_energy(text))
                        self.assertIsInstance(plan, dict)
                        self.assertTrue(plan)
                        self.assertEqual(plan["screen_minutes_saved"], minutes)
                        self.assertIsInstance(plan["steps"], list)
                        self.assertEqual(len(plan["steps"]), 3)
                        for value in (plan["plan_title"], plan["why_it_works"], *plan["steps"]):
                            self.assertIsInstance(value, str)
                            self.assertTrue(value.strip())
                        first, second, third = plan["steps"]
                        if energy == "low":
                            self.assertEqual(plan["plan_title"], "Slow loop around the block")
                            self.assertIn("walk slowly", first)
                            self.assertIn(f"({min(minutes, 15)} min,", first)
                            self.assertIn("sit on and just watch", second)
                            self.assertIn("notice three things", third)
                            self.assertNotIn("push-ups", second)
                        else:
                            self.assertEqual(plan["plan_title"], "Out and back, the long way")
                            self.assertIn("Brisk walk or jog", first)
                            self.assertTrue(first.endswith(f"in {minutes // 2} minutes"))
                            self.assertIn("stairs, a hill sprint, or 20 push-ups", second)
                            self.assertIn("Cool down", third)
                            self.assertNotIn("sit on and just watch", second)

    def test_offline_cli_for_each_time_and_mood(self):
        with no_network():
            planner = importlib.import_module("touchgrass")
            for minutes in (10, 90):
                for mood in ("tired", "energetic"):
                    with self.subTest(minutes=minutes, mood=mood):
                        argv = ["touchgrass.py", "--offline", f"{minutes} minutes and {mood}"]
                        with patch.object(sys, "argv", argv), patch.object(sys, "stdin", io.StringIO()):
                            with patch.object(planner, "ask_model", side_effect=AssertionError(
                                    "--offline must not call the model")) as model:
                                with contextlib.redirect_stdout(io.StringIO()) as out:
                                    with contextlib.redirect_stderr(io.StringIO()) as err:
                                        planner.main()
                                model.assert_not_called()
                        self.assertEqual(err.getvalue(), "")
                        self.assertIn(f"~{minutes} minutes away from the screen", out.getvalue())
                        self.assertIn("offline heuristic", out.getvalue())
                        self.assertIn("Slow loop" if mood == "tired" else "Out and back", out.getvalue())


if __name__ == "__main__":
    unittest.main()
