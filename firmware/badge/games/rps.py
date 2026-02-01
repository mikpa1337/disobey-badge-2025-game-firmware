import asyncio
from bdg.config import Config
from bdg.msg import AppMsg, BadgeMsg
from bdg.msg.connection import Connection, Beacon

from gui.core.ugui import Screen, ssd
from gui.widgets import Label, RadioButtons
from gui.core.writer import CWriter
from gui.fonts import font10
import gui.fonts.arial10 as arial10
from gui.core.colors import *

# -----------------------------
# Multiplayer Message Types
# -----------------------------

@AppMsg.register
class RpsMove(BadgeMsg):
    def __init__(self, weapon=None):
        super().__init__()
        self.weapon = weapon


@AppMsg.register
class MatchOver(BadgeMsg):
    def __init__(self, winner=None):
        super().__init__()
        self.winner = winner


@AppMsg.register
class Nickname(BadgeMsg):
    def __init__(self, nick=None):
        super().__init__()
        self.nick = nick


# -----------------------------
# Game Logic
# -----------------------------

class RpsGame:
    def __init__(self):
        self.win_descriptions = {
            ("rock", "scissors"): "Rock smashed scissors",
            ("rock", "lizard"): "Rock crushed lizard",
            ("scissors", "paper"): "Scissors cut paper",
            ("scissors", "lizard"): "Scissors decapitated lizard",
            ("paper", "rock"): "Paper covered rock",
            ("paper", "spock"): "Paper disproved Spock",
            ("lizard", "spock"): "Lizard poisoned Spock",
            ("lizard", "paper"): "Lizard eats paper",
            ("spock", "scissors"): "Spock smashed scissors",
            ("spock", "rock"): "Spock vaporized rock",
        }
        self.round_count = 0
        self.scores = {"player": 0, "opponent": 0}
        self.last_result = ""
        self.last_winner = None
        self.consecutive_winner = None

    def determine_winner(self, player, opponent):
        if player == opponent:
            return "Tie", "tie"
        if (player, opponent) in self.win_descriptions:
            return self.win_descriptions[(player, opponent)], "player"
        return self.win_descriptions[(opponent, player)], "opponent"

    def resolve_round(self, player_weapon, opponent_weapon):
        result, winner = self.determine_winner(player_weapon, opponent_weapon)

        # Only count non-tie rounds
        if winner != "tie":
            self.round_count += 1
            self.scores[winner] += 1

            if winner == self.last_winner:
                self.consecutive_winner = winner
            else:
                self.consecutive_winner = None
        else:
            self.consecutive_winner = None

        self.last_result = result
        self.last_winner = winner
        return result, winner


    def determine_final_winner(self):
        if self.scores["player"] > self.scores["opponent"]:
            return "player"
        if self.scores["opponent"] > self.scores["player"]:
            return "opponent"
        return "tie"


# -----------------------------
# Main Game Screen
# -----------------------------

class RpsScreen(Screen):
    def __init__(self, conn: Connection):
        super().__init__()
        self.conn = conn
        self.ready_for_input = True
        self.opponent_nick = None
        self.my_weapon = None
        self.their_weapon = None
        self.round_resolved = False

        self.game = RpsGame()

        # -----------------
        # GUI setup
        # -----------------
        self.wri = CWriter(ssd, font10, GREEN, BLACK, verbose=False)
        self.wribut = CWriter(ssd, arial10, GREEN, BLACK, verbose=False)

        self.round_label = Label(
            self.wri, 170 // 3 - 30, 2, 316,
            bdcolor=False, justify=1, fgcolor=D_GREEN
        )
        self.round_label.value("Best of three rounds")

        self.info = Label(
            self.wri, 170 // 3 - 5, 2, 316,
            bdcolor=False, justify=1, fgcolor=D_PINK
        )
        self.info.value("Make your choice.")

        table = [
            {"text": "rock", "args": ["rock"]},
            {"text": "paper", "args": ["paper"]},
            {"text": "scissors", "args": ["scissors"]},
            {"text": "lizard", "args": ["lizard"]},
            {"text": "spock", "args": ["spock"]},
        ]

        col = 1
        self.rb = RadioButtons(DARKGREEN, self.play_round)
        for t in table:
            self.rb.add_button(
                self.wribut,
                80,
                col,
                textcolor=WHITE,
                fgcolor=GREEN,
                height=40,
                width=55,
                **t,
            )
            col += 65

        self.score_label = Label(
            self.wri, 170 // 3 + 80, 2, 316,
            bdcolor=False, justify=1, fgcolor=D_GREEN
        )
        self.update_score()

    # -----------------------------
    # Lifecycle / Connection
    # -----------------------------

    def on_open(self):
        Beacon.suspend(True)

        if self.conn and not hasattr(self.conn, "_rps_reader_started"):
            self.conn._rps_reader_started = True
            asyncio.create_task(self.read_messages())

        my_nick = Config.config["espnow"]["nick"]
        try:
            self.conn.send_app_msg(Nickname(my_nick), sync=False)
        except Exception as e:
            print("Failed to send nickname:", e)

    def on_hide(self):
        Beacon.suspend(False)

    async def read_messages(self):
        while not self.conn or not self.conn.active:
            await asyncio.sleep(0.1)

        async for msg in self.conn.get_msg_aiter():
            print("RPS RECEIVED:", msg.msg_type, msg.__dict__)

            if msg.msg_type == "RpsMove":
                self.handle_opponent_move(msg.weapon)
            elif msg.msg_type == "MatchOver":
                self.display_final_winner_remote(msg.winner)
            elif msg.msg_type == "Nickname":
                self.opponent_nick = msg.nick or "Opponent"
            elif msg.msg_type == "ConTerm":
                from bdg.screens.scan_screen import ScannerScreen
                Screen.change(ScannerScreen, mode=Screen.REPLACE)
                return

    # -----------------------------
    # UI Helpers
    # -----------------------------

    def update_score(self):
        self.score_label.value(
            f"You: {self.game.scores['player']} / "
            f"Opponent: {self.game.scores['opponent']}"
        )

    def set_waiting_text(self):
        last = f"{self.game.last_result}. " if self.game.last_result else ""
        if self.my_weapon and not self.their_weapon:
            self.info.value(f"You chose {self.my_weapon}. Waiting for opponent.")
        elif self.their_weapon and not self.my_weapon:
            self.info.value("Opponent has chosen. Pick already.")
        else:
            self.info.value(f"{last}- pick again.")

    def reset_round_state(self):
        self.my_weapon = None
        self.their_weapon = None
        self.round_resolved = False
        self.ready_for_input = True
        self.set_waiting_text()

    # -----------------------------
    # Player Input
    # -----------------------------

    def play_round(self, button, player_weapon):
        if not self.ready_for_input or self.round_resolved or self.my_weapon is not None:
            return

        self.ready_for_input = False
        self.my_weapon = player_weapon

        try:
            self.conn.send_app_msg(RpsMove(player_weapon), sync=False)
        except Exception as e:
            print("Failed to send RpsMove:", e)

        if self.their_weapon and not self.round_resolved:
            self.resolve_round()
        else:
            self.set_waiting_text()

    # -----------------------------
    # Opponent Move
    # -----------------------------

    def handle_opponent_move(self, weapon):
        self.their_weapon = weapon

        if self.my_weapon and not self.round_resolved:
            self.resolve_round()
        else:
            self.set_waiting_text()

    # -----------------------------
    # Round Resolution
    # -----------------------------

    def resolve_round(self):
        if not self.my_weapon or not self.their_weapon:
            return

        result, winner = self.game.resolve_round(
            self.my_weapon, self.their_weapon
        )
        self.apply_result(result, winner)

    def apply_result(self, result, winner):
        self.round_resolved = True

        if winner == "tie":
            text = f"You: {self.my_weapon}, Opponent: {self.their_weapon}. {result}! Tie!"
        elif winner == "player":
            text = f"You: {self.my_weapon}, Opponent: {self.their_weapon}. {result}! You win!"
        else:
            text = f"You: {self.my_weapon}, Opponent: {self.their_weapon}. {result}! You lose!"

        self.info.value(text)
        self.round_label.value(f"Round {self.game.round_count}")
        self.update_score()

        # Only reset for non-tie rounds if game not finished
        if winner != "tie":
            if self.game.scores["player"] >= 2 or self.game.scores["opponent"] >= 2:
                side = self.game.determine_final_winner()
                if side == "player":
                    final_winner = Config.config["espnow"]["nick"]
                elif side == "opponent":
                    final_winner = self.opponent_nick or "Opponent"
                else:
                    final_winner = "tie"

                try:
                    self.conn.send_app_msg(MatchOver(final_winner), sync=False)
                except Exception as e:
                    print("Failed to send MatchOver:", e)

                self.display_final_winner(final_winner)
            else:
                self.reset_round_state()
        else:
            # Tie: allow players to pick again
            self.my_weapon = None
            self.their_weapon = None
            self.round_resolved = False
            self.ready_for_input = True
            self.set_waiting_text()


    # -----------------------------
    # Final Winner Screens
    # -----------------------------

    def display_final_winner(self, final_winner):
        from .winner_screen import WinScr

        side = self.game.determine_final_winner()

        if side == "player":
            message2 = "You won!"
        elif side == "opponent":
            message2 = "You lost!"
        else:
            message2 = "It was a tie!"

        Screen.change(
            WinScr,
            mode=Screen.REPLACE,
            kwargs={
                "winner": final_winner,
                "message1": self.game.last_result,
                "message2": message2,
                "conn": self.conn,
                "return_screen": RpsScreen,
            },
        )

    def display_final_winner_remote(self, winner):
        from .winner_screen import WinScr

        my_nick = Config.config["espnow"]["nick"]

        if winner == "tie":
            message2 = "It was a tie!"
        elif winner == my_nick:
            message2 = "You won!"
        else:
            message2 = "You lost!"

        Screen.change(
            WinScr,
            mode=Screen.REPLACE,
            kwargs={
                "winner": winner,
                "message1": self.game.last_result,
                "message2": message2,
                "conn": self.conn,
                "return_screen": RpsScreen,
            },
        )


# -----------------------------
# Game Registration
# -----------------------------

def badge_game_config():
    return {
        "con_id": 4,
        "title": "RPSLS(Dev)",
        "screen_class": RpsScreen,
        "screen_args": (),
        "multiplayer": True,
        "description": "Rock Paper Scissors Lizard Spock",
    }
