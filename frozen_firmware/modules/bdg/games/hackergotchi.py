import asyncio
import time
from machine import Pin
from neopixel import NeoPixel

from gui.core.ugui import Screen, ssd
from gui.widgets import Label, Button
from gui.core.writer import CWriter
from gui.fonts import arial35, font10
from gui.core.colors import WHITE, BLACK, D_GREEN, D_PINK
import json 
import os 



# ---------------------------------------------------------
# LED HELPER (turning leds off when leaving the game)
# ---------------------------------------------------------

LED_BRIGHTNESS = 0.2 # TODO: doesn't dim anything :(

def dim_color(color):
    return tuple(int(c * LED_BRIGHTNESS) for c in color)

def turn_off_leds(np, led_power):
    # Safely clear NeoPixels
    if np:
        try:
            for i in range(len(np)):
                np[i] = (0, 0, 0)
            np.write()
        except Exception:
            pass  # silently ignore if np is unavailable or already off

    # Safely turn off LED power
    if led_power:
        try:
            led_power.value(0)
        except Exception:
            pass  

# ---------------------------------------------------------
# CAREER LOGIC
# ---------------------------------------------------------

def determine_career(stats):
    Wis = stats["Wis"]
    Tech = stats["Tech"]
    Cha = stats["Cha"]
    Str = stats["Str"] # SECRET stat 1 
    Burden = stats["Burden"] # SECRET stat 2 (multiplayer version >> dirty tricks?)

    if Burden >= 12:
        return "Chaotic Hacker"
    if Cha >= 9 and Burden >= 6:
        return "Micromanager CEO"
    if Str >= 5 and Burden >= 8:
        return "Policy Tyrant"
    if Tech >= 8 and Burden >= 8:
        return "Rogue Hacker"
    if Tech >= 10 and Str >= 3 and Cha <= 5:
        return "Zero-Day Collector"
    if Tech >= 9 and Str >= 4:
        return "Sys Admin"
    if Tech >= 9 and Str >= 2:
        return "White Hat Hacker"
    if Wis >= 9 and Cha <= 2:
        return "Digital Hermit"
    if Wis >= 11 and Str >= 1 and Cha <= 3:
        return "DFIR Analyst"
    if Cha >= 8:
        return "Keynote Speaker"
    if Wis > 9:
        return "CISO"
    if Wis > 6:
        return "Consultant"
    if Tech > 6:
        return "SOC Analyst"
    return "Happy person"



# ---------------------------------------------------------
# INTRO SCREEN
# ---------------------------------------------------------

class TamaIntroScreen(Screen):
    HACKERGOTCHI_FILE = "hackergotchi.json"

    def __init__(self):
        super().__init__()

        self.wri = CWriter(ssd, font10, WHITE, BLACK, verbose=False)

        Label(
            self.wri, 10, 2, 316,
            justify=Label.CENTRE, fgcolor=D_GREEN
        ).value("[ H A C K E R G O T C H I ]")

        if self.has_saved_hackergotchi():
            self.draw_existing_hackergotchi()
        else:
            self.draw_new_intro()

    # ---------- FILE HELPERS ----------
    def has_saved_hackergotchi(self):
        try:
            return self.HACKERGOTCHI_FILE in os.listdir()
        except Exception:
            return False

    def load_saved_hackergotchi(self):
        with open(self.HACKERGOTCHI_FILE, "r") as f:
            data = json.load(f)

        stats = data.get("stats", {})
        led_state = data.get("led_state", [(0, 0, 0)] * 10)

        return stats, led_state


    # ---------- NEW PLAYER ----------
    def draw_new_intro(self):
        Label(
            self.wri, 40, 2, 316,
            justify=Label.CENTRE, fgcolor=D_PINK
        ).value("Are you ready to commit?")

        y = 85
        for line in (
            "Hatching a Hackergotchi is hard work",
            "and takes at least one hour.",
        ):
            Label(
                self.wri, y, 2, 316,
                justify=Label.CENTRE, fgcolor=D_GREEN
            ).value(line)
            y += 18

        Button(
            self.wri, 150, 30, width=120, height=26,
            text="Yikes, nope",
            fgcolor=D_GREEN, textcolor=D_GREEN,
            callback=lambda *_: self.exit_game()
        )

        Button(
            self.wri, 150, 170, width=120, height=26,
            text="Bring it on",
            fgcolor=D_GREEN, textcolor=D_GREEN,
            callback=lambda *_: self.start_new_game()
        )

    # ---------- EXISTING HACKERGOTCHI ----------
    def draw_existing_hackergotchi(self):
        Label(
            self.wri, 40, 2, 316,
            justify=Label.CENTRE, fgcolor=D_PINK
        ).value("You already have a Hackergotchi.")

        Label(
            self.wri, 65, 2, 316,
            justify=Label.CENTRE, fgcolor=D_GREEN
        ).value("Would you like to see it")

        Label(
            self.wri, 85, 2, 316,
            justify=Label.CENTRE, fgcolor=D_GREEN
        ).value("or create a new one?")

        Button(
            self.wri, 150, 20, width=140, height=26,
            text="Old Hackergotchi ",
            fgcolor=D_GREEN, textcolor=D_GREEN,
            callback=lambda *_: self.show_existing()
        )

        Button(
            self.wri, 150, 180, width=140, height=26,
            text="Create new",
            fgcolor=D_GREEN, textcolor=D_GREEN,
            callback=lambda *_: self.start_new_game()
        )

    # ---------- ACTIONS ----------
    def show_existing(self):
        stats, led_state = self.load_saved_hackergotchi()

        Screen.change(
            TamaCareerScreen,
            args=(stats, led_state),
            mode=Screen.REPLACE
        )

    def start_new_game(self):
        Screen.change(TamaGameScreen, mode=Screen.REPLACE)

    def exit_game(self):
        from bdg.screens.solo_games_screen import SoloGamesScreen
        Screen.change(SoloGamesScreen, mode=Screen.REPLACE)

# ---------------------------------------------------------
# GAME SCREEN
# ---------------------------------------------------------

class TamaGameScreen(Screen):

    TOTAL_STAGES = 10

    QUESTIONS = [

        {
            "q": "Look! Hackergothci eggs!\nWhich color do you pick?",
            "a": [
                {"text": "Sun Orange", "stats": {"Tech": 0, "Wis": 0, "Cha": 1, "Str": 0, "Burden": 0}},
                {"text": "Terminal Green", "stats": {"Tech": 1, "Wis": 0, "Cha": 0, "Str": 0, "Burden": 0}},
                {"text": "Magic Purple", "stats": {"Tech": 0, "Wis": 1, "Cha": 0, "Str": 0, "Burden": 0}},
            ],
        },
        {
            "q": "Your hackergothi egg is a baby. \nTheir first toy is a...",
            "a": [
                {"text": "screwdriver", "stats": {"Tech": 2, "Wis": 0, "Cha": 0, "Str": 0, "Burden": 0}},
                {"text": "picture book", "stats": {"Tech": 0, "Wis": 2, "Cha": 0, "Str": 0, "Burden": 0}},
                {"text": "microphone", "stats": {"Tech": 0, "Wis": 0, "Cha": 2, "Str": 0, "Burden": 0}},
            ],
        },
        {
            "q": "Time for their first computer! \nWhich OS do you get them?",
            "a": [
                {"text": "Windows", "stats": {"Tech": 1, "Wis": 1, "Cha": 1, "Str": 0, "Burden": 0}},
                {"text": "Linux terminal", "stats": {"Tech": 2, "Wis": 1, "Cha": 0, "Str": 2, "Burden": 1}},
                {"text": "iOS", "stats": {"Tech": 0, "Wis": 1, "Cha": 2, "Str": 0, "Burden": 0}},
            ],
        },
        {
            "q": "Next they will need a hobby.\nWhat will it be?",
            "a": [
                {"text": "No hobbies", "stats": {"Tech": 0, "Wis": 0, "Cha": 0, "Str": 0, "Burden": 2}},
                {"text": "Sports", "stats": {"Tech": 0, "Wis": 0, "Cha": 1, "Str": 1, "Burden": 0}},
                {"text": "Acting", "stats": {"Tech": 0, "Wis": 0, "Cha": 2, "Str": 0, "Burden": 0}},
            ],
        },
        {
            "q": "They want a full Linux OS.\nWhich distro do you recommend?",
            "a": [
                {"text": "Kali", "stats": {"Tech": 1, "Wis": 1, "Cha": 0, "Str": 0, "Burden": 1}},
                {"text": "Arch", "stats": {"Tech": 2, "Wis": 0, "Cha": 0, "Str": 1, "Burden": 2}},
                {"text": "Red Hat", "stats": {"Tech": 1, "Wis": 1, "Cha": 0, "Str": 0, "Burden": 0}},
            ],
        },
        {
            "q": "In school you recommend \nthey concentrate on...",
            "a": [
                {"text": "history", "stats": {"Tech": 0, "Wis": 2, "Cha": 0, "Str": 0, "Burden": 0}},
                {"text": "crafts", "stats": {"Tech": 1, "Wis": 0, "Cha": 1, "Str": 0, "Burden": 0}},
                {"text": "math", "stats": {"Tech": 2, "Wis": 0, "Cha": 0, "Str": 0, "Burden": 0}},
            ],
        },
        {
            "q": "When it comes to right and wrong\nyou teach them to follow...",
            "a": [
                {"text": "the law", "stats": {"Tech": 0, "Wis": 3, "Cha": 0, "Str": 0, "Burden": 0}},
                {"text": "the money", "stats": {"Tech": 0, "Wis": 0, "Cha": 0, "Str": 0, "Burden": 3}},
                {"text": "their instinct", "stats": {"Tech": 0, "Wis": 1, "Cha": 1, "Str": 1, "Burden": 0}},
            ],
        },
        {
            "q": "When something breaks, \nyou suggest they...",
            "a": [
                {"text": "ask for help", "stats": {"Tech": 0, "Wis": 1, "Cha": 2, "Str": 0, "Burden": 0}},
                {"text": "fix it quietly", "stats": {"Tech": 2, "Wis": 1, "Cha": 0, "Str": 1, "Burden": 0}},
                {"text": "self-blame", "stats": {"Tech": 1, "Wis": 0, "Cha": 0, "Str": 0, "Burden": 2}},
            ],
        },
        {
            "q": "Soon they will conquer the world.\nWith which language?",
            "a": [
                {"text": "Python", "stats": {"Tech": 2, "Wis": 1, "Cha": 0, "Str": 0, "Burden": 0}},
                {"text": "Bash", "stats": {"Tech": 2, "Wis": 0, "Cha": 0, "Str": 1, "Burden": 0}},
                {"text": "English", "stats": {"Tech": 0, "Wis": 1, "Cha": 2, "Str": 0, "Burden": 0}},
            ],
        },
        {
            "q": "Time to see what they have \nbecome. Your last gift is...",
            "a": [
                {"text": "Books", "stats": {"Tech": 0, "Wis": 2, "Cha": 0, "Str": 0, "Burden": 0}},
                {"text": "Bitcoins", "stats": {"Tech": 1, "Wis": 0, "Cha": 0, "Str": 1, "Burden": 1}},
                {"text": "No gifts", "stats": {"Tech": 0, "Wis": 0, "Cha": 0, "Str": 0, "Burden": 2}},
            ],
        },
    ]

    def __init__(self, stage=1, stats=None, led_state=None):
        super().__init__()

        # Restore state
        self.stage = stage
        self.stats = stats if stats is not None else {"Tech": 0, "Wis": 0, "Cha": 0, "Str": 0, "Burden": 0}
        self.led_state = led_state
        self.led_color = led_state[-1] if led_state else (255, 255, 255)

        self.input_locked = False

        self.wri = CWriter(ssd, font10, WHITE, BLACK, verbose=False)
        self.q1 = Label(self.wri, 40, 2, 316, justify=Label.CENTRE, fgcolor=D_PINK)
        self.q2 = Label(self.wri, 60, 2, 316, justify=Label.CENTRE, fgcolor=D_PINK)

        self.btns = [
            Button(self.wri, 95, 30, width=120, height=24,
                   fgcolor=D_GREEN, textcolor=D_GREEN,
                   callback=lambda *_: self.feed(0)),
            Button(self.wri, 95, 170, width=120, height=24,
                   fgcolor=D_GREEN, textcolor=D_GREEN,
                   callback=lambda *_: self.feed(1)),
            Button(self.wri, 135, 95, width=120, height=24,
                   fgcolor=D_GREEN, textcolor=D_GREEN,
                   callback=lambda *_: self.feed(2)),
        ]

        # LED setup
        self.led_power = Pin(17, Pin.OUT)
        self.led_power.value(1)
        self.np = NeoPixel(Pin(18), 10)

        # Restore LED state if available
        if self.led_state is not None:
            for i in range(len(self.np)):
                self.np[i] = self.led_state[i]
            self.np.write()

        self.update_question()

    def update_question(self):
        q = self.QUESTIONS[self.stage - 1]
        parts = q["q"].split("\n", 1)
        self.q1.value(f"Stage {self.stage}: {parts[0]}")
        self.q2.value(parts[1] if len(parts) > 1 else "")

        for i, b in enumerate(self.btns):
            b.text = q["a"][i]["text"]
            b.enabled = True
            b.show()

    def save_stats(self):
        career_name = determine_career(self.stats)

        data_to_save = {
            "stats": self.stats,
            "career": career_name,
            "led_state": [self.np[i] for i in range(len(self.np))]
        }

        tmp_file = "hackergotchi.tmp"
        final_file = "hackergotchi.json"

        with open(tmp_file, "w") as f:
            json.dump(data_to_save, f)

        os.rename(tmp_file, final_file)


    def feed(self, idx):
        if self.input_locked:
            return

        self.input_locked = True

        # Always keep using the last LED color
        if self.led_state:
            self.led_color = self.led_state[-1]

        # Stage 1 LED color selection
        if self.stage == 1:
            egg_colors = {
                "Sun Orange": (220, 50, 0),
                "Terminal Green": (0, 255, 0),
                "Magic Purple": (70, 0, 255),
            }
            choice = self.QUESTIONS[0]["a"][idx]["text"]
            self.led_color = egg_colors.get(choice, (255, 255, 255))

        # Apply stats
        for stat, val in self.QUESTIONS[self.stage - 1]["a"][idx]["stats"].items():
            self.stats[stat] += val

        # If this was the last stage, save stats to persistent storage
        if self.stage == self.TOTAL_STAGES:
            self.save_stats()

        # Light LED for this stage
        led_index = len(self.np) - self.stage
        if 0 <= led_index < len(self.np):
            self.np[led_index] = self.led_color
            self.np.write()

        # Capture LED state (NOW includes final LED)
        led_state = [self.np[i] for i in range(len(self.np))]

        # Save only after LEDs are correct
        if self.stage == self.TOTAL_STAGES:
            self.save_stats()

        # Move to countdown screen
        Screen.change(
            TamaCountdownScreen,
            args=(
                self.stage,
                self.stats,
                led_state,
                self.stage + 1,
                self.TOTAL_STAGES
            ),
            mode=Screen.REPLACE
        )


        
    def get_led_state(self):
        return [self.np[i] for i in range(len(self.np))]
    
    def exit_game(self):
        # Cancel any running tasks that might update LEDs
        for task in getattr(self, "_tasks", []):
            task.cancel()

        # Turn off all LEDs
        for i in range(len(self.np)):
            self.np[i] = (0, 0, 0)
        self.np.write()
        self.led_power.value(0)

        # Go back to the main games menu
        from bdg.screens.solo_games_screen import SoloGamesScreen
        Screen.change(SoloGamesScreen, mode=Screen.REPLACE)

    def on_hide(self):
        # Cancel any running tasks
        for task in getattr(self, "_tasks", []):
            task.cancel()

        # Turn off all LEDs
        for i in range(len(self.np)):
            self.np[i] = (0, 0, 0)
        self.np.write()
        self.led_power.value(0)

# ---------------------------------------------------------
# COUNTDOWN SCREEN
# ---------------------------------------------------------

class TamaCountdownScreen(Screen):
    def __init__(self, stage, stats, led_state, next_stage, total_stages):
        super().__init__()

        self.stage = stage
        self.stats = stats
        self.led_state = led_state
        self.next_stage = next_stage
        self.total_stages = total_stages

        # Writers
        self.wri_small = CWriter(ssd, font10, WHITE, BLACK, verbose=False)
        self.wri_big = CWriter(ssd, arial35, WHITE, BLACK, verbose=False)

        # Labels for text
        self.l1 = Label(self.wri_small, 30, 2, 316, justify=Label.CENTRE, fgcolor=D_PINK)
        self.l2 = Label(self.wri_small, 60, 2, 316, justify=Label.CENTRE, fgcolor=D_GREEN)

        # Big spinner in the center
        self.spinner_label = Label(self.wri_big, 90, 150, 316, justify=Label.CENTRE, fgcolor=D_PINK)

        # Dummy widget to satisfy nano-gui
        self._dummy = Button(self.wri_small, -10, -10, width=1, height=1,
                             fgcolor=BLACK, textcolor=BLACK,
                             callback=lambda *_: None)

        # LED setup
        self.led_power = Pin(17, Pin.OUT)
        self.led_power.value(1)
        self.np = NeoPixel(Pin(18), 10)
        for i in range(len(self.np)):
            self.np[i] = self.led_state[i]
        self.np.write()

        # Start countdown task
        self.reg_task(self._countdown(), False)

    async def _countdown(self):
        duration = 300  # seconds 
        end_time = time.time() + duration

        spinner_chars = ["|", "/", "-", "\\"]
        spinner_idx = 0

        while True:
            remaining = int(end_time - time.time())
            if remaining < 0:
                break

            minutes = remaining // 60
            seconds = remaining % 60
            time_str = f"{minutes:02d}:{seconds:02d}"

            # Update labels
            self.l1.value(f"... evolving ...")
            self.l2.value(f"{time_str}")
            self.spinner_label.value(spinner_chars[spinner_idx])
            spinner_idx = (spinner_idx + 1) % len(spinner_chars)

            await asyncio.sleep(0.2)  # spinner speed

        # Transition to next stage or stats screen
        if self.next_stage > self.total_stages:
            Screen.change(
                TamaStatsScreen,
                args=(self.stats, self.led_state),
                mode=Screen.REPLACE
            )
        else:
            Screen.change(
                TamaGameScreen,
                args=(self.next_stage, self.stats, self.led_state),
                mode=Screen.REPLACE
            )

    def on_hide(self):
        """Called when leaving the screen (back button or navigation)."""
        # Cancel any running tasks
        for task in getattr(self, "_tasks", []):
            task.cancel()

        # Turn off LEDs safely using helper
        turn_off_leds(self.np, self.led_power)


# ---------------------------------------------------------
# STATS SCREEN
# ---------------------------------------------------------

class TamaStatsScreen(Screen):
    def __init__(self, stats, led_colors):
        super().__init__()

        self.wri = CWriter(ssd, font10, WHITE, BLACK, verbose=False)

        Label(self.wri, 10, 2, 316,
              justify=Label.CENTRE, fgcolor=D_GREEN).value("Your hackergotchi stats")

        y = 40
        for k in ("Tech", "Wis", "Cha"):
            Label(self.wri, y, 2, 316,
                  justify=Label.CENTRE, fgcolor=D_PINK).value(f"{k}: {stats[k]}")
            y += 22

        Button(self.wri, y + 10, 80, width=160, height=26,
               text="Reveal my Hackergotchi",
               fgcolor=D_GREEN, textcolor=D_GREEN,
               callback=lambda *_: Screen.change(
                   TamaCareerScreen, args=(stats, led_colors), mode=Screen.REPLACE))


# ---------------------------------------------------------
# CAREER SCREEN
# ---------------------------------------------------------

class TamaCareerScreen(Screen):
    def __init__(self, stats, led_state):
        super().__init__()

        self.wri_small = CWriter(ssd, font10, WHITE, BLACK, verbose=False)
        self.wri_big = CWriter(ssd, arial35, D_PINK, BLACK, verbose=False)

        self.led_power = Pin(17, Pin.OUT)
        self.led_power.value(1)
        self.np = NeoPixel(Pin(18), 10)

        # Restore LED colors from the game
        for i in range(len(self.np)):
            self.np[i] = led_state[i]
        self.np.write()

        Label(self.wri_small, 10, 2, 316,
              justify=Label.CENTRE, fgcolor=D_GREEN).value("Hackergotchi has hatched!")

        career_name = determine_career(stats)
        Label(self.wri_big, 60, 2, 316,
              justify=Label.CENTRE, fgcolor=D_PINK).value(career_name)

        CAREER_DESCRIPTIONS = {
            "Chaotic Hacker": "Up to no good.",
            "Micromanager CEO": "They just care. A bit too much.",
            "Policy Tyrant": "Without them we would be nothing.",
            "Rogue Hacker": "Vulns everywhere, for them to  ca$h.",
            "Zero-Day Collector": "Exploits of tomorrow, today.",
            "Sys Admin": "Stands between you and mayhem.",
            "White Hat Hacker": "Will hack for good.",
            "Keynote Speaker": "Hacks other people. With words.",
            "CISO": "Guardian of secrets, holder of budgets.",
            "Consultant": "Provider of infinent wisdom.",
            "SOC Analyst": "Ever vigilant. Unless sleeping.",
            "Happy person": "Here to just enjoy life.",
            "DFIR Analyst": "Finds the truth from ashes.",
            "Digital Hermit": "People are the virus."
        }
        description = CAREER_DESCRIPTIONS.get(career_name, "")
        Label(self.wri_small, 105, 2, 316,
              justify=Label.CENTRE, fgcolor=D_GREEN).value(description)

        Button(self.wri_small, 150, 100, width=120, height=26,
               text="Exit",
               fgcolor=D_GREEN, textcolor=D_GREEN,
               callback=lambda *_: self.exit_game())

        # FLASH LEDs
        self.led_task = self.reg_task(self.blink_leds(), False)  # save reference to task

    async def blink_leds(self, times=1, delay=0.2):
        current_colors = [self.np[i] for i in range(len(self.np))]
        try:
            for _ in range(times):
                # All white
                for i in range(len(self.np)):
                    self.np[i] = (255, 255, 255)
                self.np.write()
                await asyncio.sleep(delay)

                for i in range(len(self.np)):
                    self.np[i] = current_colors[i]
                    self.np.write()
                    await asyncio.sleep(0.05)

                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            # Task was cancelled, exit gracefully
            return
        finally:
            # Ensure LEDs return to original stage colors
            for i in range(len(self.np)):
                self.np[i] = current_colors[i]
            self.np.write()



    # exit_game() 
    def exit_game(self):
        # Cancel LED task if still running
        if hasattr(self, "led_task"):
            self.led_task.cancel()

        # Turn off LEDs
        for i in range(len(self.np)):
            self.np[i] = (0, 0, 0)
        self.np.write()
        self.led_power.value(0)

        from bdg.screens.solo_games_screen import SoloGamesScreen
        Screen.change(SoloGamesScreen, mode=Screen.REPLACE)

    # override on_hide() to handle back button
    def on_hide(self):
        # Cancel LED task if still running
        if hasattr(self, "led_task"):
            self.led_task.cancel()

        # Safely turn off LEDs
        turn_off_leds(self.np, self.led_power)



# ---------------------------------------------------------
# GAME CONFIG
# ---------------------------------------------------------

def badge_game_config():
    return {
        "con_id": 3,
        "title": "Hackergotchi",
        "screen_class": TamaIntroScreen,
        "screen_args": (),
        "multiplayer": False,
        "description": "A tiny creature that evolves depending on your choices",
    }
