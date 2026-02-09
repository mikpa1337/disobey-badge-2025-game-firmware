import asyncio
import random
import time

from bdg.msg import AppMsg, BadgeMsg, CancelActivityMsg
from bdg.msg.connection import Connection, Beacon
from bdg.widgets.meter import Meter
from gui.core.colors import GREEN, BLACK, RED, YELLOW, MAGENTA, BLUE, DARKBLUE
from gui.core.ugui import Screen, ssd
from gui.core.ugui import Widget, display
from gui.core.writer import CWriter
from gui.fonts import font10
from gui.widgets import Label
from gui.widgets.buttons import Button
from gui.widgets.region import Region
from hardware_setup import ssd

dolittle = lambda *_: None

WAITING_OTHER = 1
WAITING_PLAYER = 2
GAME_OVER = 0
NEW_ROUND = 3


@AppMsg.register
class TttStart(BadgeMsg):
    def __init__(self, iam: str, move: int, init: float, round_num: int):
        super().__init__()
        self.iam: str = iam  # Player character: "x" or "o"
        self.move: int = move
        self.init: float = init
        self.round_num: int = round_num


@AppMsg.register
class TttMove(BadgeMsg):
    def __init__(self, move: int):
        super().__init__()
        self.move: int = move


@AppMsg.register
class TttEnd(BadgeMsg):
    def __init__(self, iam_winner: bool, move: int):
        super().__init__()
        # if player does not claim win, it must be tie
        self.iam_winner: bool = iam_winner
        self.move: int = move


class TTTbox(Widget):
    def __init__(
        self,
        writer,
        row,
        col,
        *,
        height=30,
        fillcolor=None,
        fgcolor=None,
        bgcolor=None,
        bdcolor=False,
        callback=dolittle,
        adj_cb=None,
        args=[],
        value="",
        active=True,
    ):
        super().__init__(
            writer, row, col, height, height, fgcolor, bgcolor, bdcolor, value, active
        )
        super()._set_callbacks(callback, args)
        self.fillcolor = fillcolor
        self.adj_cb = adj_cb
        self.has_border = False

    def show(self):
        if super().show():
            x = self.col
            y = self.row
            pad = 4
            ht = self.height
            x1 = x + ht - 1
            y1 = y + ht - 1
            # if self._value:
            #    if self.fillcolor is not None:
            #        display.fill_rect(x, y, ht, ht, self.fillcolor)
            # else:
            #
            # if self.has_focus():
            #    display.fill_rect(x, y, ht, ht, self.bgcolor)

            display.rect(x, y, ht, ht, MAGENTA if self.has_focus() else self.fgcolor)
            if self.fillcolor is None:
                if self._value == "x":
                    display.line(x, y, x1, y1, self.fgcolor)
                    display.line(x, y1, x1, y, self.fgcolor)
                elif self._value == "o":
                    radius = (self.height // 2) - pad
                    display.circle(
                        x + radius + pad, y + radius + pad, radius, self.fgcolor
                    )
                else:
                    pass

    def do_sel(self):  # Select was pushed
        self.callback(self)  # callback is place_cb

    def do_adj(self, button, value):
        print(f"adj: {value=}, {button=}")
        self.adj_cb(self, value)


class TicTacToe(Screen):
    sync_update = True

    def __init__(self, conn: Connection):
        super().__init__()
        self.rd_msg = None
        self.turn_timer = None
        self.wri = CWriter(ssd, font10, GREEN, BLACK, verbose=False)

        self.round = 0
        self.max_round = 5
        self.wins = 0
        self.opponent_wins = 0
        # Number of wins required to win the match (best of N)
        self.needed_wins = (self.max_round // 2) + 1

        self._init = 0
        self.ui_state = GAME_OVER
        self._first_move = True

        self.cb_disable = False
        pad = 40
        boxw = 30

        x_step = boxw + 5
        y_step = boxw + 5

        self.leds = []
        self.mov_mat = [
            [6, 7, 8, 0, 1, 2, 3, 4, 5],  # move up #0
            [3, 4, 5, 6, 7, 8, 0, 1, 2],  # move down #1
        ]
        row = col = pad
        for y in range(3):
            for x in range(3):
                self.leds.append(
                    TTTbox(
                        self.wri,
                        row,
                        col,
                        fgcolor=GREEN,
                        bdcolor=False,
                        callback=self.place_cb,
                        adj_cb=self.adj_cb,
                        value="",
                        height=boxw,
                    )
                )
                col += x_step
            row += y_step
            col = pad

        self.b_start = Button(
            self.wri, 145, 260, text="Start", callback=self.start_cb, args=("Yes",)
        )

        self.d_tmr2 = Meter(
            self.wri,
            40,
            10,
            divisions=5,
            ptcolor=DARKBLUE,
            bgcolor=MAGENTA,
            height=100,
            width=15,
            label=30,
            style=Meter.BAR,
            # legends=("0.0", "1.0", "5.0"),
            legends=None,
        )

        reg = Region(self.d_tmr2, 0.0, 0.2, RED, dolittle)

        self.d_tmr2.regions
        self.g_state = TTTGame()
        self.g_state._act = False

        self.l_player = Label(self.wri, 12, 40, 110)
        self.l_info = Label(self.wri, 75, 150, 320 - 150)
        self.l_score = Label(self.wri, 12, 150, 320 - 150, justify=1)

        self.set_player_label("??")
        self.conn: Connection = conn
        self.cancelled = False

        self.update_board(self.g_state.to_dict())

    def on_open(self):
        # TODO: README This is the only way to add workers to app!!
        # if reg_task() is called in init task will not be restarted when coming
        # back from dialog of dropdown
        Beacon.suspend(True)
        if not self.rd_msg or self.rd_msg.done():
            self.rd_msg = self.reg_task(self.read_messages(), True)

    def on_hide(self):
        # TODO: how to disallow back when in competitive mode?
        self.cancel_turn_timer()
        
        if self.conn and not self.conn.closed:
            # Send cancellation message if leaving early (not already cancelled by other badge)
            if not self.cancelled:
                try:
                    msg = CancelActivityMsg()
                    self.conn.send_app_msg(msg, sync=False)
                    print("TicTacToe: Sent cancel to other badge")
                except Exception as e:
                    print(f"TicTacToe: Failed to send cancel: {e}")
            
            # Also send TttEnd to handle older versions gracefully
            try:
                self.conn.send_app_msg(TttEnd(False, -1), sync=False)
            except Exception as e:
                print(f"Failed to send TttEnd: {e}")
            
            asyncio.create_task(self.conn.terminate(send_out=True))

        Beacon.suspend(False)

    async def _conn_error(self):
        # opponent did not reply in time
        self.set_info_label("Connection error!")
        self.ui_state = GAME_OVER
        self.g_state._act = False
        self.update_board(self.g_state.to_dict(), upd_btn=True)

    async def _player_empty_move(self):
        # player did  not make a move in time
        self.ui_state = WAITING_OTHER
        self.set_info_label("Failed to move!", err=True)

        if self._first_move:
            self._first_move = False
            self._init = random.random()
            self.conn.send_app_msg(
                TttStart(self.g_state.cp, -1, self._init, self.round), sync=False
            )

        self.conn.send_app_msg(TttMove(-1))  # we did not send it time
        self.start_turn_timer(
            9000, self._conn_error()  # wait for opponent or execute error func
        )

    async def read_messages(self):
        # This function is a msg reader and part of the UI game logic
        # * read_messages - modifies state with opponents moves
        # * place_cb - modifies state with players moves
        if not self.conn or not self.conn.active:
            print("read_messages() stopped, conn closed")
            return

        async for msg in self.conn.get_msg_aiter():
            print(f"ttt -> {msg}")
            
            # Handle cancellation from other badge
            if msg.msg_type == "CancelActivityMsg":
                print("TicTacToe: Received cancel from other badge")
                self.cancelled = True
                self.cancel_turn_timer()
                self.ui_state = GAME_OVER
                self.set_info_label("Game cancelled by opponent", err=True)
                await asyncio.sleep(1.5)
                Screen.back()
                return
            
            if msg.msg_type == "TttStart":

                if msg.init < self._init:
                    # we won the initiative
                    continue

                # game started but user lost the initiative
                # Users start the game same time, but first to send Start gets first move
                self.cancel_turn_timer()

                self.g_state = TTTGame()
                self.g_state.cp = "x" if msg.iam == "o" else "o"
                self._first_move = False
                self.round = msg.round_num
                # add other players move in
                if msg.move != -1:
                    self.g_state.add_move(msg.move // 3, msg.move % 3)
                    self.set_info_label("Initiative lost, move!", err=True)
                else:
                    self.set_info_label("Got initiative, move!")

                self.ui_state = WAITING_PLAYER
                self.update_board(self.g_state.to_dict(), upd_btn=True)
                self.start_turn_timer(5000, fail_coro=self._player_empty_move())

            elif self.ui_state is WAITING_PLAYER:
                print(f"Error: Received {msg.msg_type} while waiting Player!!!")
                continue

            if msg.msg_type == "TttMove":
                self.cancel_turn_timer()
                self.ui_state = WAITING_PLAYER
                self.set_info_label("Your turn.")
                # modify game state, opponent did not claim win
                if msg.move != -1:
                    self.g_state.add_move(msg.move // 3, msg.move % 3)
                # update board to reflect changes
                self.update_board(self.g_state.to_dict(), upd_btn=False)
                # for making, it harder suffle the cursor position
                self.move_to(self.leds[random.choice(self.mov_mat[0])])
                # start turn timer and trigger _player_empty_move if time runs out
                self.start_turn_timer(timeout=5000, fail_coro=self._player_empty_move())

            elif msg.msg_type == "TttEnd":
                # Opponent claims victory or declares a draw
                self.cancel_turn_timer()
                self.ui_state = GAME_OVER
                # modify game state, opponent did not claim win
                self.g_state.add_move(msg.move // 3, msg.move % 3)
                self.update_board(self.g_state.to_dict(), upd_btn=True)
                # Update opponent wins counter if they claimed a valid win
                if msg.iam_winner and self.g_state.is_winner(self.g_state.other_p()):
                    self.opponent_wins += 1
                    # opponent claimed victory and our game state said the same
                    self.set_info_label(
                        f"Game lost to {self.g_state.other_p().upper()}", err=True
                    )

                elif not msg.iam_winner and self.g_state.is_draw():
                    # game is draw
                    self.set_info_label(f"Draw with {self.g_state.other_p()}")

                else:
                    self.set_info_label(f"{self.g_state.other_p()} is a cheater!")

                # If match reached end conditions (best-of or max rounds), decide match winner
                if (
                    self.wins >= self.needed_wins
                    or self.opponent_wins >= self.needed_wins
                    or self.round >= self.max_round
                ):
                    self._check_match_over()

            elif msg.msg_type == "Ttt_State":
                pass

    def place_cb(self, led):
        # This function places user token and part of the UI game logic
        # * read_messages() - modifies state with opponents moves
        # * place_cb() - modifies state with players moves
        #   place own token to a place, update game state and send move to other player

        if self.cb_disable or self.ui_state is not WAITING_PLAYER:
            # user should not be able to add tokens while waiting other player
            return

        self.cancel_turn_timer()

        move = self.leds.index(led)
        ended = False
        try:
            ended = self.g_state.make_move(move // 3, move % 3)
        except Exception as e:
            move = -1  # empty move, player chose occupied place

        if ended:
            winner = self.g_state.champ == self.g_state.cp  # if false, its a draw
            # Update local wins counter
            if winner:
                self.wins += 1

            # Notify opponent about round end
            try:
                self.conn.send_app_msg(TttEnd(winner, move), sync=False)
            except Exception as e:
                print(f"Failed to send TttEnd: {e}")

            self.set_info_label("You Won!!" if winner else "It's A DRAW!")
            self.ui_state = GAME_OVER

            # If match reached end conditions (best-of or max rounds), decide match winner
            if self.wins >= self.needed_wins or self.round >= self.max_round:
                self._check_match_over()
        else:
            if self._first_move:
                self._first_move = False
                self._init = random.random()
                self.conn.send_app_msg(
                    TttStart(self.g_state.cp, move, self._init, self.round), sync=False
                )
            else:
                self.conn.send_app_msg(TttMove(move), sync=False)

            self.set_info_label("Opponent turn.", err=True)
            self.ui_state = WAITING_OTHER
            self.start_turn_timer(9000, fail_coro=self._conn_error())

        self.update_board(self.g_state.to_dict(), upd_btn=ended)

    def start_cb(self, *args):
        print(f"start_cb: {args}")
        # Prevent starting new rounds when match is over (best-of) or max rounds reached
        if self.wins >= self.needed_wins or self.opponent_wins >= self.needed_wins or self.round >= self.max_round:
            self.set_info_label("Match finished", err=True)
            try:
                self.b_start.greyed_out(True)
            except Exception:
                pass
            return

        self._first_move = True
        self.round += 1
        self.g_state = TTTGame()
        self.update_board(self.g_state.to_dict(), upd_btn=True)
        self.ui_state = WAITING_PLAYER
        self.set_info_label("Game started.")
        self.move_to(self.leds[random.choice(self.mov_mat[0])])
        self.start_turn_timer(5000, self._player_empty_move())

    def update_board(self, state: dict, upd_btn: bool = True):
        # updates the board and the button visibility based on the game state
        self.cb_disable = True
        # making sure that during deactivation we dont get any false selects

        for i, led in enumerate(self.leds):
            led.value(state["board"][i // 3][i % 3])

        if upd_btn:
            self.set_scoreboard()
            active = self.g_state.is_act()
            self.set_player_label(state["cp"] if active else "??")
            # Disable start if game is active or match is finished (best-of) or max rounds reached
            match_over = self.wins >= self.needed_wins or self.opponent_wins >= self.needed_wins
            self.b_start.greyed_out(active or match_over or (self.round >= self.max_round))
            for led in self.leds:
                led.greyed_out(not active)

            if not active:
                self.move_to(self.b_start)

        self.cb_disable = False

    async def turn_timer_task(self, pl, timeout=5000, fail_coro=None):
        # Run animation on the dial screen and if timeout reached creates task from fail_coro
        elapsed_ms = 0

        self.d_tmr2.bgcolor = RED if self.ui_state is WAITING_OTHER else GREEN

        start = time.ticks_ms()
        self.d_tmr2.text(f"{timeout / 1000:.1f}")
        while elapsed_ms < timeout:
            elapsed_ms = min(timeout, time.ticks_diff(time.ticks_ms(), start))
            self.d_tmr2.value(max(0, min(1, (timeout - elapsed_ms) / timeout)))
            await asyncio.sleep(0.11)

        # time r elapsed, wanted thing did not happen in time
        if fail_coro:
            # turn timer can be cancelled, now we are overtime, so cancel
            # won't affect fail_coro
            asyncio.create_task(fail_coro)

    def adj_cb(self, *args):
        # move selection up and down, normally this cb action is for tuning values+/-
        if self.cb_disable:
            return

        i = self.leds.index(args[0])
        if args[1] > 0:
            dest = self.mov_mat[0][i]
        else:
            dest = self.mov_mat[1][i]
        print(f"move={i}, to={dest}")
        self.move_to(self.leds[dest])

    def set_player_label(self, player):
        text = f"You are: {player.upper()}"
        fg = {
            "x": YELLOW,
            "o": MAGENTA,
            "??": RED,
        }.get(player, GREEN)
        self.l_player.value(text=text, fgcolor=fg)

    def set_info_label(self, info_text: str, err=False):
        self.l_info.value(text=info_text, fgcolor=MAGENTA if err else GREEN)

    def set_scoreboard(self):
        self.l_score.value(
            text=f"Round:{self.round}/{self.max_round} W:{self.wins}", fgcolor=BLUE
        )

    def start_turn_timer(self, timeout, fail_coro=None):
        # making sure there is only one timer at the time
        if self.turn_timer and not self.turn_timer.done():
            self.turn_timer.cancel()

        timeout
        self.turn_timer = asyncio.create_task(
            self.turn_timer_task(
                self.g_state.cp, timeout - ((self.round - 1) * 500), fail_coro
            )
        )

    def cancel_turn_timer(self):
        print("turn timer cancelled")
        if self.turn_timer and not self.turn_timer.done():
            self.turn_timer.cancel()

    def _check_match_over(self):
        """Decide and display match result based on accumulated wins."""
        if self.wins > self.opponent_wins:
            self.set_info_label("Match Over: You won!", err=False)
        elif self.wins < self.opponent_wins:
            self.set_info_label("Match Over: You lost!", err=True)
        else:
            self.set_info_label("Match Over: Draw", err=False)
        try:
            self.b_start.greyed_out(True)
        except Exception:
            pass


class TTTGException(Exception):
    pass


class TTTGame:
    def __init__(self, state=None):

        print(f"TTTGame: {state=}")
        if state:
            self.board = state["board"]
            self.cp = state["cp"]
            self._act = (
                self.is_draw() or state["act"]
            )  # game might end because rage quit
            self.champ = state["champ"]
        else:
            self.board = [["" for _ in range(3)] for _ in range(3)]
            self.cp = "x"
            self._act = True
            self.champ = None

    def is_winner(self, player):
        for row in self.board:
            if all(s == player for s in row):
                return True

        for col in range(3):
            if all(self.board[row][col] == player for row in range(3)):
                return True

        if all(self.board[i][i] == player for i in range(3)) or all(
            self.board[i][2 - i] == player for i in range(3)
        ):
            return True

        return False

    def is_draw(self):
        return all(self.board[row][col] != "" for row in range(3) for col in range(3))

    def set_cp(self, player):
        if player == "x":
            self.cp = "x"
        else:
            self.cp = "o"

    def other_p(self):
        return "x" if self.cp == "o" else "o"

    def add_move(self, row, col):
        ### add move from other player
        iam = self.cp
        self.cp = "x" if self.cp == "o" else "o"
        try:
            self.make_move(row, col)
        except Exception:
            pass
        finally:
            self.cp = iam

    def make_move(self, row, col):
        if not self._act:
            raise Exception("Game has ended")
        print(f"make move {row=} {col=} with {self.cp}")
        if self.board[row][col] != "":
            raise Exception(
                f"Invalid move: {row=} {col=} already taken by {self.board[row][col]}"
            )

        self.board[row][col] = self.cp
        if self.is_winner(self.cp):
            print(f"Player {self.cp} wins!")
            self._act = False
            self.champ = self.cp
            return True
        if self.is_draw():
            self._act = False
            print("It's a draw!")
            return True

        return False

    def to_dict(self):
        return {"board": self.board, "cp": self.cp, "act": self._act}

    @classmethod
    def from_dict(cls, state):
        return cls(state)

    def is_act(self):
        if self.is_draw():
            self._act = False
        return self._act


def badge_game_config():
    """
    Configuration for TicTacToe game registration.

    Returns:
        dict: Game configuration with con_id, title, screen_class, etc.
    """
    return {
        "con_id": 1,
        "title": "TicTacToe",
        "screen_class": TicTacToe,
        "screen_args": (),  # Connection passed separately by framework
        "multiplayer": True,
        "description": "Classic TicTacToe game between two badges",
    }
