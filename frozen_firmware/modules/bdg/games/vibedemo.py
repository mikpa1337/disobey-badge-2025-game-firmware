import hardware_setup as hardware_setup
import asyncio
import time
import math
from machine import Pin
from neopixel import NeoPixel


from gui.core.ugui import Screen, ssd, display
from bdg.asyncbutton import ButtonEvents, ButAct
from gui.core.writer import CWriter
from gui.widgets import Button
from gui.fonts import font10
from gui.core.colors import BLACK, WHITE


class VibeDemo(Screen):
   """Graphics demo screen showcasing display and animation capabilities."""
  
   # Display dimensions
   DISPLAY_WIDTH = 320
   DISPLAY_HEIGHT = 170
  
   # Phase configuration with durations in seconds
   PHASE_DURATIONS = {
       "intro": 10,  # LED intro with gradual fill and fade
       "morphing": 30,  # Morphing 3D shapes
       "plasma": 20,  # Plasma effect
       "bars_leds": 30,  # Copper bars and LED scanner
   }
  
   # Phase cycle order
   PHASE_ORDER = ["intro", "plasma", "morphing", "bars_leds"]
  
   def __init__(self, *args, **kwargs):
       super().__init__()
      
       # State machine
       self.current_phase = "intro"
       self.phase_start_time = None
       self.phase_frame = 0
       self.phase_tasks = []
      
       # Allow phase duration override
       self.phase_durations = self.PHASE_DURATIONS.copy()
       if "phase_durations" in kwargs:
           self.phase_durations.update(kwargs["phase_durations"])
      
       # LED hardware setup
       self.led_power = Pin(17, Pin.OUT)
       self.led_power.value(1)  # Enable LED power
       self.np = NeoPixel(Pin(18), 10)  # 10 LEDs
      
       # Copper bar state
       self.num_bars = 4
       self.bar_height = 35  # Height of each copper bar (increased for smoother gradients)
       
       # Custom smooth color palettes for copper bars
       # Each gradient has 5 steps for smooth transitions that fit well in 35 pixels
       self.copper_bar_colors = [
           # Red/Orange bar - warm gradient
           (
               ssd.rgb(80, 0, 0),       # Dark red
               ssd.rgb(192, 32, 0),     # Red-orange
               ssd.rgb(255, 128, 16),   # Bright orange
               ssd.rgb(192, 32, 0),     # Red-orange
               ssd.rgb(80, 0, 0),       # Dark red
           ),
           # Blue/Cyan bar - cool gradient
           (
               ssd.rgb(0, 0, 80),       # Dark blue
               ssd.rgb(0, 64, 192),     # Blue
               ssd.rgb(64, 160, 255),   # Bright cyan
               ssd.rgb(0, 64, 192),     # Blue
               ssd.rgb(0, 0, 80),       # Dark blue
           ),
           # Purple/Magenta bar - vibrant gradient
           (
               ssd.rgb(80, 0, 80),      # Dark purple
               ssd.rgb(192, 0, 128),    # Magenta
               ssd.rgb(255, 64, 224),   # Bright magenta
               ssd.rgb(192, 0, 128),    # Magenta
               ssd.rgb(80, 0, 80),      # Dark purple
           ),
           # Green/Yellow bar - fresh gradient
           (
               ssd.rgb(0, 80, 0),       # Dark green
               ssd.rgb(64, 192, 0),     # Lime green
               ssd.rgb(160, 255, 64),   # Bright lime
               ssd.rgb(64, 192, 0),     # Lime green
               ssd.rgb(0, 80, 0),       # Dark green
           ),
       ]
       
       # Scrolling text state
       self.scroll_x = self.DISPLAY_WIDTH  # Start from right edge
       self.font_scale = 2  # Scale factor for bitmap font (2x = 10x14 pixels)
       self.scroll_completed = False  # Track when one full scroll pass completes
       
       # Demo scene scrolltext with greetings
       self.scroll_text = (
           "HELLO DISOBEY 2026! WE BRING YOU A NICE LITTLE VIBECODED OLDSCHOOLISH DEMO ... "
           "VISIT SKROLLI AT COMMUNITY VILLAGE AND SUBSCRIBE FOR THE NEXT FOUR MAGAZINES ... OR JUST BUY ONE OF THE OLDER ONES - THEY ARE ALL GREAT!   "
           "VIBES - CLAUDE ... DIRECTION - EIMINK ... "
           "GREETINGS TO MSP, JUMALAUTA, SCENESAT, WHOLE DISOBEY ORG AND YOU!!! "
       )
       
       # Calculate scroll duration - how long it takes for text to complete one loop
       # Text width = number of characters * (char_width) where char_width = 6 * scale
       text_width = len(self.scroll_text) * (6 * self.font_scale)
       # Total distance to scroll = screen width + text width
       total_scroll_distance = self.DISPLAY_WIDTH + text_width
       # Scroll speed = 3 pixels per frame, frame rate = 20 FPS (0.05s per frame)
       scroll_frames = total_scroll_distance / 3
       scroll_duration = scroll_frames * 0.05
       # Update phase duration for bars_leds to match scroll duration
       self.phase_durations["bars_leds"] = scroll_duration
       
       # Plasma effect state - pre-calculated sine tables for speed
       # Plasma timers (initialized when plasma phase starts)
       self.plasma_time1 = 0
       self.plasma_time2 = 0
       self.plasma_time3 = 0
       self.plasma_time4 = 0
       
       # 3D shape morphing state
       # Define base shapes for morphing
       
       # Pyramid (4 vertices: base triangle + apex)
       self.pyramid_vertices = [
           [0, -1, 0],      # Apex
           [-1, 1, -1],     # Base corner 1
           [1, 1, -1],      # Base corner 2
           [0, 1, 1],       # Base corner 3
       ]
       self.pyramid_edges = [(0, 1), (0, 2), (0, 3), (1, 2), (2, 3), (3, 1)]
       
       # Cube (8 vertices)
       self.cube_vertices = [
           [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],  # Front face
           [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],      # Back face
       ]
       self.cube_edges = [
           (0, 1), (1, 2), (2, 3), (3, 0),  # Front face
           (4, 5), (5, 6), (6, 7), (7, 4),  # Back face
           (0, 4), (1, 5), (2, 6), (3, 7),  # Connecting edges
       ]
       
       # Pre-create sine and cosine lookup tables (needed for cylinder init and all phases)
       self.sine_table = [int(math.sin(i * 0.0245) * 127) for i in range(256)]
       self.cos_table = [int(math.cos(i * 0.0245) * 127) for i in range(256)]
       
       # Cylinder (approximate with icosphere-like structure)
       self.cylinder_vertices = []
       self.cylinder_edges = []
       self._init_cylinder()
       
       # Current morph state
       self.morph_phase = 0  # 0=pyramid, 1=cube, 2=sphere
       self.morph_progress = 0.0  # 0.0 to 1.0 within each phase
       
       # Rotation angles
       self.angle_x = 0
       self.angle_y = 0
       self.angle_z = 0
       
       # Cache bitmap font to avoid recreating every frame
       self._init_font_cache()
      
       # Create writer for title/info
       self.wri = CWriter(ssd, font10, WHITE, BLACK, verbose=False)
      
       # Create Exit button (required - Screen needs at least one widget)
       Button(
           self.wri,
           row=150,
           col=250,
           width=60,
           height=16,
           text="Exit",
           callback=self.exit_demo,
       )
      
   def _init_font_cache(self):
       """Initialize cached bitmap font."""
       self.FONT = {
           'A': [0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001],
           'B': [0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110],
           'C': [0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110],
           'D': [0b11110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11110],
           'E': [0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111],
           'F': [0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000],
           'G': [0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01110],
           'H': [0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001],
           'I': [0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b11111],
           'J': [0b00111, 0b00010, 0b00010, 0b00010, 0b00010, 0b10010, 0b01100],
           'K': [0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001],
           'L': [0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111],
           'M': [0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001],
           'N': [0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001],
           'O': [0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110],
           'P': [0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000],
           'Q': [0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101],
           'R': [0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001],
           'S': [0b01111, 0b10000, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110],
           'T': [0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100],
           'U': [0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110],
           'V': [0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100],
           'W': [0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b11011, 0b10001],
           'X': [0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001],
           'Y': [0b10001, 0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100],
           'Z': [0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111],
           '0': [0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110],
           '1': [0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110],
           '2': [0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b01000, 0b11111],
           '3': [0b11111, 0b00010, 0b00100, 0b00010, 0b00001, 0b10001, 0b01110],
           '4': [0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010],
           '5': [0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110],
           '6': [0b00110, 0b01000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110],
           '7': [0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000],
           '8': [0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110],
           '9': [0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00010, 0b01100],
           ' ': [0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000],
           '!': [0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00000, 0b00100],
           '.': [0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b01100],
           '/': [0b00001, 0b00010, 0b00100, 0b00100, 0b01000, 0b10000, 0b10000],
       }
   
   def after_open(self):
       """Start the demo animations after screen opens."""
       self.phase_start_time = time.time()
      
       # Launch main phase controller task
       task = asyncio.create_task(self._phase_controller())
       self.phase_tasks.append(task)
       
       # Launch button event handler
       task = asyncio.create_task(self._handle_buttons())
       self.phase_tasks.append(task)
  
   async def _handle_buttons(self):
       """Handle button presses for exiting the demo."""
       button_events = ButtonEvents()
       async for button, event in button_events.get_btn_events():
           # Yellow button (btn_start) exits the demo
           if button == "btn_start" and event == ButAct.ACT_PRESS:
               self.exit_demo()
               break
   
   async def _phase_controller(self):
       """Main controller task monitoring phase timing and transitions."""
       flash_frames = 0  # Track flash animation
       
       while True:
           # Check if phase should transition
           should_transition = False
           
           if self.current_phase == "intro":
               # Transition after 200 frames (10 seconds at 20 FPS)
               should_transition = self.phase_frame >= 200
           elif self.current_phase == "plasma":
               # Transition after 20 seconds
               elapsed = time.time() - self.phase_start_time
               should_transition = elapsed >= 20
           elif self.current_phase == "bars_leds":
               # Transition when scroll completes
               should_transition = self.scroll_completed
           elif self.current_phase == "morphing":
               # Transition after 30 seconds
               elapsed = time.time() - self.phase_start_time
               should_transition = elapsed >= 30
          
           if should_transition:
               # Skip flash transition for intro→morphing, use flash for others
               if self.current_phase == "intro":
                   # Direct transition without flash
                   ssd.fill(BLACK)
                   current_index = self.PHASE_ORDER.index(self.current_phase)
                   next_index = (current_index + 1) % len(self.PHASE_ORDER)
                   self.current_phase = self.PHASE_ORDER[next_index]
                   self.phase_start_time = time.time()
                   self.phase_frame = 0
               else:
                   # Flash transition for 3 frames (0.15 seconds)
                   if flash_frames < 3:
                       # Create white flash that fades out
                       brightness = int((1.0 - flash_frames / 3) * 255)
                       flash_color = ssd.rgb(brightness, brightness, brightness)
                       ssd.fill(flash_color)
                       
                       # Set all LEDs to white during flash
                       for i in range(10):
                           self.np[i] = (brightness, brightness, brightness)
                       self.np.write()
                       
                       flash_frames += 1
                       await asyncio.sleep(0.05)
                       continue
                   
                   # Flash complete, transition to next phase
                   flash_frames = 0
                   ssd.fill(BLACK)
                   
                   # Transition to next phase
                   current_index = self.PHASE_ORDER.index(self.current_phase)
                   next_index = (current_index + 1) % len(self.PHASE_ORDER)
                   self.current_phase = self.PHASE_ORDER[next_index]
                   self.phase_start_time = time.time()
                   self.phase_frame = 0
          
           # Call appropriate draw method
           if self.current_phase == "intro":
               self._draw_intro()
           elif self.current_phase == "plasma":
               self._draw_plasma()
           elif self.current_phase == "bars_leds":
               # Reset scrolltext at start of bars_leds phase
               if self.phase_frame == 0:
                   self.scroll_x = self.DISPLAY_WIDTH
                   self.scroll_completed = False
               self._draw_bars_leds()
           elif self.current_phase == "morphing":
               # Reset to pyramid at start of morphing phase
               if self.phase_frame == 0:
                   self.morph_phase = 0
                   self.morph_progress = 0.0
               self._draw_morphing_shapes()
          
           # Update frame counter
           self.phase_frame += 1
          
           # Sleep to control animation speed
           await asyncio.sleep(0.05)  # ~20 FPS
  
   def _draw_intro(self):
       """LED intro with gradual screen fill and fade - no flash transition."""
       # Calculate progress through the intro (0.0 to 1.0)
       # 10 seconds = 200 frames, complete fade 5 frames before end
       progress = self.phase_frame / 195.0  # Complete by frame 195
           
       if progress < 0.35:
           # Phase 1 (1.5-3.5s): Black screen with full LED animation
           ssd.fill(BLACK)
           
           # LEDs do a color cycling wave pattern
           wave_pos = self.phase_frame * 0.1
           fade_in = progress / 0.35  # 0 to 1
           # LEDs do a color cycling wave pattern with fade in
           wave_pos = self.phase_frame * 0.1
           for i in range(10):
               phase = (i * 0.6 + wave_pos) % 6.28
               r = int((math.sin(phase) + 1) * 64 * fade_in)
               g = int((math.sin(phase + 2.09) + 1) * 64 * fade_in)
               b = int((math.sin(phase + 4.18) + 1) * 64 * fade_in)
               self.np[i] = (r, g, b)
           self.np.write()
           
       elif progress < 0.65:
           # Phase 2 (3.5-6.5s): Gradual screen fill with LED color
           fill_progress = (progress - 0.35) / 0.3  # 0 to 1
           
           # Calculate current LED color (use middle LED as reference)
           phase = (5 * 0.6 + self.phase_frame * 0.1) % 6.28
           r = int((math.sin(phase) + 1) * 64 * fill_progress)
           g = int((math.sin(phase + 2.09) + 1) * 64 * fill_progress)
           b = int((math.sin(phase + 4.18) + 1) * 64 * fill_progress)
           
           fill_color = ssd.rgb(r, g, b)
           ssd.fill(fill_color)
           
           # LEDs continue cycling
           wave_pos = self.phase_frame * 0.1
           for i in range(10):
               led_phase = (i * 0.6 + wave_pos) % 6.28
               lr = int((math.sin(led_phase) + 1) * 64)
               lg = int((math.sin(led_phase + 2.09) + 1) * 64)
               lb = int((math.sin(led_phase + 4.18) + 1) * 64)
               self.np[i] = (lr, lg, lb)
           self.np.write()
           
       elif progress <= 1.0:
           # Phase 3 (6.5-9.75s): Fade to black (completes 5 frames before transition)
           fade_progress = (progress - 0.65) / 0.35  # 0 to 1
           brightness = 1.0 - fade_progress
           
           # Fade screen
           phase = (5 * 0.6 + self.phase_frame * 0.1) % 6.28
           r = int((math.sin(phase) + 1) * 64 * brightness)
           g = int((math.sin(phase + 2.09) + 1) * 64 * brightness)
           b = int((math.sin(phase + 4.18) + 1) * 64 * brightness)
           
           fill_color = ssd.rgb(r, g, b)
           ssd.fill(fill_color)
           
           # Fade LEDs
           wave_pos = self.phase_frame * 0.1
           for i in range(10):
               led_phase = (i * 0.6 + wave_pos) % 6.28
               lr = int((math.sin(led_phase) + 1) * 64 * brightness)
               lg = int((math.sin(led_phase + 2.09) + 1) * 64 * brightness)
               lb = int((math.sin(led_phase + 4.18) + 1) * 64 * brightness)
               self.np[i] = (lr, lg, lb)
           self.np.write()
       else:
           # Final 5 frames (9.75-10s): Hold black
           ssd.fill(BLACK)
           for i in range(10):
               self.np[i] = (0, 0, 0)
           self.np.write()
  
   def _draw_bars_leds(self):
       """Draw Amiga-style copper bars with LED animation."""
       # Clear screen
       ssd.fill(BLACK)
       
       for bar_idx in range(self.num_bars):
           # Calculate sine wave position using sine_table for smooth animation
           sine_idx = (self.phase_frame * 2 + bar_idx * 64) & 255
           sine_value = self.sine_table[sine_idx] / 127.0
           y_center = self.DISPLAY_HEIGHT // 2 + int(sine_value * (self.DISPLAY_HEIGHT / 3))
           
           # Draw the bar with full 5-step gradient
           gradient_colors = self.copper_bar_colors[bar_idx % 4]
           bar_start = y_center - (self.bar_height // 2)
           pixels_per_step = self.bar_height / 5
           
           for step in range(5):
               y_pos = int(bar_start + step * pixels_per_step)
               
               if 0 <= y_pos < self.DISPLAY_HEIGHT:
                   h = int(min(pixels_per_step + 1, self.DISPLAY_HEIGHT - y_pos))
                   if h > 0:
                       ssd.fill_rect(0, y_pos, self.DISPLAY_WIDTH, h, gradient_colors[step])
       
       # LED animation with sine_table
       led_time_base = self.phase_frame * 4
       color_cycle = (self.phase_frame // 100) % 2
       
       for i in range(10):
           sine_idx = (led_time_base + i * 16) & 255
           brightness = (self.sine_table[sine_idx] + 128) // 8  # 0-31 range (half)
           
           if color_cycle == 0:
               self.np[i] = (brightness * 2, brightness, 0)  # Orange
           else:
               self.np[i] = (brightness * 2, 0, brightness * 2)  # Magenta
       
       self.np.write()
       
       # Draw scrolling text with sinusoidal path
       self._draw_scrolling_text()
   
   def _draw_scrolling_text(self):
       """Draw scrolling text following a sinusoidal path using direct pixel rendering."""
       # Calculate text position - scroll from right to left
       text_x = int(self.scroll_x)
       
       # Base Y position (center of screen)
       base_y = self.DISPLAY_HEIGHT // 2
       
       # Draw text using simple bitmap font with per-character sine wave
       self._draw_bitmap_text(self.scroll_text, text_x, base_y, WHITE, self.font_scale)
       
       # Update scroll position - move left
       self.scroll_x -= 3  # Scroll speed (pixels per frame)
       
       # Calculate approximate text width (scaled)
       text_width = len(self.scroll_text) * (6 * self.font_scale)
       
       # Reset when text goes completely off screen
       if self.scroll_x < -text_width:
           self.scroll_x = self.DISPLAY_WIDTH
   
   def _draw_bitmap_text(self, text, x, base_y, color, scale=1):
       """Draw text using cached bitmap font with optimized rendering.
       
       Args:
           scale: Font scaling factor (1 = 5x7, 2 = 10x14, etc.)
       """
       char_width = 6 * scale
       
       # Calculate visible character range
       start_char = max(0, int(-x / char_width) - 1)
       end_char = min(len(text), int((self.DISPLAY_WIDTH - x) / char_width) + 2)
       
       if start_char >= len(text) or end_char <= 0:
           return
       
       cursor_x = x + (start_char * char_width)
       scale_5 = 5 * scale
       
       # Pre-calculate sine offset multiplier
       sine_mult = 2.44  # Approximation of 0.06 * 256 / (2*pi)
       
       for i in range(start_char, end_char):
           char = text[i]
           
           if cursor_x > self.DISPLAY_WIDTH:
               break
           
           # Convert to uppercase inline
           if 'a' <= char <= 'z':
               char = chr(ord(char) - 32)
           
           bitmap = self.FONT.get(char)
           if bitmap and cursor_x + scale_5 >= 0:
               # Calculate sine wave Y offset using sine_table
               sine_idx = int(cursor_x * sine_mult) & 255
               sine_offset = (self.sine_table[sine_idx] * 15) >> 7
               char_base_y = base_y + sine_offset
               
               # Draw character rows
               for row_idx in range(7):
                   char_y = char_base_y + (row_idx * scale)
                   
                   if 0 <= char_y < self.DISPLAY_HEIGHT:
                       row_bits = bitmap[row_idx]
                       
                       # Skip empty rows
                       if row_bits == 0:
                           continue
                       
                       # Process pixel runs
                       run_start = -1
                       for col_idx in range(6):
                           if col_idx < 5 and (row_bits & (16 >> col_idx)):  # 16 = 1 << 4
                               if run_start == -1:
                                   run_start = col_idx
                           else:
                               if run_start != -1:
                                   run_x = cursor_x + (run_start * scale)
                                   run_width = (col_idx - run_start) * scale
                                   
                                   if 0 <= run_x < self.DISPLAY_WIDTH:
                                       draw_h = min(scale, self.DISPLAY_HEIGHT - char_y)
                                       ssd.fill_rect(run_x, char_y, run_width, draw_h, color)
                                   
                                   run_start = -1
           
           cursor_x += char_width
   
   def _draw_plasma(self):
       """Draw fast animated plasma effect using pre-calculated sine tables."""
       # Clear screen
       ssd.fill(BLACK)
       
       # Update plasma animation timers
       self.plasma_time1 = (self.plasma_time1 + 1) & 255
       self.plasma_time2 = (self.plasma_time2 + 2) & 255
       self.plasma_time3 = (self.plasma_time3 + 3) & 255
       self.plasma_time4 = (self.plasma_time4 + 4) & 255
       
       # Draw plasma in 8x8 blocks for speed (320x170 = 40x22 blocks)
       block_size = 8
       for block_y in range(0, 170, block_size):
           for block_x in range(0, 320, block_size):
               # Calculate plasma value for this block using sine table lookups
               x = block_x >> 1  # Divide by 2 for tighter patterns (was >>2)
               y = block_y >> 1
               
               # Combine multiple sine waves for plasma effect
               v1 = self.sine_table[(x + self.plasma_time1) & 255]
               v2 = self.sine_table[(y + self.plasma_time2) & 255]
               v3 = self.sine_table[((x + y) + self.plasma_time3) & 255]
               v4 = self.sine_table[((x - y + 256) + self.plasma_time4) & 255]
               
               # Combine values
               plasma_val = ((v1 + v2 + v3 + v4) >> 2) + 128  # Average and shift to 0-255
               
               # Map plasma value to color (vibrant trans pride flag palette)
               # Brighter and more saturated colors
               color_idx = (plasma_val + self.phase_frame) & 255
               
               # Divide into 5 segments for smooth transitions (sun palette)
               # Deep red -> Orange -> Yellow/White -> Orange -> Deep red
               if color_idx < 51:  # Deep red to orange
                   t = color_idx / 51.0
                   r = int(180 + (255 - 180) * t)  # Dark red to bright orange red
                   g = int(0 + (140 - 0) * t)  # Add orange
                   b = 0
               elif color_idx < 102:  # Orange to yellow/white
                   t = (color_idx - 51) / 51.0
                   r = 255
                   g = int(140 + (240 - 140) * t)  # Brighten to yellow
                   b = int(0 + (100 - 0) * t)  # Slight warmth
               elif color_idx < 153:  # Yellow/white to orange
                   t = (color_idx - 102) / 51.0
                   r = 255
                   g = int(240 + (140 - 240) * t)  # Back to orange
                   b = int(100 + (0 - 100) * t)  # Remove warmth
               elif color_idx < 204:  # Orange to deep red
                   t = (color_idx - 153) / 51.0
                   r = int(255 + (180 - 255) * t)  # Darken to deep red
                   g = int(140 + (0 - 140) * t)  # Remove orange
                   b = 0
               else:  # Deep red (completing cycle)
                   r, g, b = 180, 0, 0
               
               color = ssd.rgb(int(r * 0.75), int(g * 0.75), int(b * 0.75))  # 75% brightness
               
               # Draw block with fill_rect (super fast)
               ssd.fill_rect(block_x, block_y, block_size, block_size, color)
       
       # LED effect - sample actual plasma values at LED positions
       # Left side LEDs (0-4) sample from left side of screen
       # Right side LEDs (5-9) sample from right side of screen
       led_y = 85  # Middle of screen height
       
       for i in range(5):
           # Left LEDs: sample from left side positions
           led_x = i * 64  # 0, 64, 128, 192, 256
           x = led_x >> 1
           y = led_y >> 1
           
           # Calculate plasma value at this position (same logic as screen rendering)
           v1 = self.sine_table[(x + self.plasma_time1) & 255]
           v2 = self.sine_table[(y + self.plasma_time2) & 255]
           v3 = self.sine_table[((x + y) + self.plasma_time3) & 255]
           v4 = self.sine_table[((x - y + 256) + self.plasma_time4) & 255]
           plasma_val = ((v1 + v2 + v3 + v4) >> 2) + 128
           color_idx = (plasma_val + self.phase_frame) & 255
           
           # Map to sun palette color (same as screen)
           if color_idx < 51:
               t = color_idx / 51.0
               r = int(180 + (255 - 180) * t)
               g = int(0 + (140 - 0) * t)
               b = 0
           elif color_idx < 102:
               t = (color_idx - 51) / 51.0
               r = 255
               g = int(140 + (240 - 140) * t)
               b = int(0 + (100 - 0) * t)
           elif color_idx < 153:
               t = (color_idx - 102) / 51.0
               r = 255
               g = int(240 + (140 - 240) * t)
               b = int(100 + (0 - 100) * t)
           elif color_idx < 204:
               t = (color_idx - 153) / 51.0
               r = int(255 + (180 - 255) * t)
               g = int(140 + (0 - 140) * t)
               b = 0
           else:
               r, g, b = 180, 0, 0
           
           # Apply with dimmed brightness
           self.np[i] = (r >> 3, g >> 3, b >> 3)
       
       for i in range(5, 10):
           # Right LEDs: sample from right side positions (mirrored spacing)
           led_x = 320 - ((i - 5) * 64)  # 320, 256, 192, 128, 64
           x = led_x >> 1
           y = led_y >> 1
           
           # Calculate plasma value at this position
           v1 = self.sine_table[(x + self.plasma_time1) & 255]
           v2 = self.sine_table[(y + self.plasma_time2) & 255]
           v3 = self.sine_table[((x + y) + self.plasma_time3) & 255]
           v4 = self.sine_table[((x - y + 256) + self.plasma_time4) & 255]
           plasma_val = ((v1 + v2 + v3 + v4) >> 2) + 128
           color_idx = (plasma_val + self.phase_frame) & 255
           
           # Map to sun palette color
           if color_idx < 51:
               t = color_idx / 51.0
               r = int(180 + (255 - 180) * t)
               g = int(0 + (140 - 0) * t)
               b = 0
           elif color_idx < 102:
               t = (color_idx - 51) / 51.0
               r = 255
               g = int(140 + (240 - 140) * t)
               b = int(0 + (100 - 0) * t)
           elif color_idx < 153:
               t = (color_idx - 102) / 51.0
               r = 255
               g = int(240 + (140 - 240) * t)
               b = int(100 + (0 - 100) * t)
           elif color_idx < 204:
               t = (color_idx - 153) / 51.0
               r = int(255 + (180 - 255) * t)
               g = int(140 + (0 - 140) * t)
               b = 0
           else:
               r, g, b = 180, 0, 0
           
           # Apply with dimmed brightness
           self.np[i] = (r >> 3, g >> 3, b >> 3)
       
       self.np.write()
   
   def _init_cylinder(self):
       """Create cylinder vertices."""
       import math
       self.cylinder_vertices = []
       self.cylinder_edges = []
       
       # Cylinder with top and bottom circles
       lon_bands = 8  # Number of sides
       height_levels = 2  # Top and bottom only
       
       # Create vertices at different heights
       for level in range(height_levels):
           y = 1 - (level * 2.0)  # Top: 1, Bottom: -1
           
           for lon in range(lon_bands):
               # Map lon to 0-255 range (8 bands = 32 per band)
               idx = (lon * 32) & 255
               x = self.cos_table[idx] / 127.0  # Normalize to -1.0 to 1.0
               z = self.sine_table[idx] / 127.0
               self.cylinder_vertices.append([x, y, z])
       
       # Create edges
       for level in range(height_levels - 1):
           for lon in range(lon_bands):
               first = level * lon_bands + lon
               second = first + lon_bands
               
               # Horizontal edge (around the circle)
               self.cylinder_edges.append((first, level * lon_bands + ((lon + 1) % lon_bands)))
               # Vertical edge (connecting levels)
               self.cylinder_edges.append((first, second))
       
       # Add edges for the bottom circle
       bottom_level = height_levels - 1
       for lon in range(lon_bands):
           first = bottom_level * lon_bands + lon
           self.cylinder_edges.append((first, bottom_level * lon_bands + ((lon + 1) % lon_bands)))
   
   def _rotate_3d_fast(self, x, y, z, cos_x, sin_x, cos_y, sin_y, cos_z, sin_z):
       """Fast 3D rotation using pre-calculated sin/cos values."""
       # Rotation around X axis
       y_new = y * cos_x - z * sin_x
       z = y * sin_x + z * cos_x
       y = y_new
       
       # Rotation around Y axis
       x_new = x * cos_y + z * sin_y
       z = -x * sin_y + z * cos_y
       x = x_new
       
       # Rotation around Z axis
       x_new = x * cos_z - y * sin_z
       y = x * sin_z + y * cos_z
       
       return x_new, y, z
   
   def _project_fast(self, x, y, z):
       """Fast integer-based projection."""
       # Simplified perspective (z + 3.5)
       # Increased scale to 80 for larger shapes
       factor = 80 / (3.5 + z)
       screen_x = 160 + int(x * factor)  # 160 = DISPLAY_WIDTH / 2
       screen_y = 85 + int(y * factor)   # 85 = DISPLAY_HEIGHT / 2
       return screen_x, screen_y
   
   def _draw_morphing_shapes(self):
       """Draw morphing 3D shapes (optimized for speed)."""
       # Clear screen
       ssd.fill(BLACK)
       
       # State machine for morphing with pauses
       # morph_progress: 0.0 = start shape, 1.0 = end shape, >1.0 = pause
       
       if self.morph_progress < 1.0:
           # Actively morphing
           self.morph_progress += 0.01
       elif self.morph_progress < 1.4:
           # Pause for 2 seconds (40 frames) after reaching target shape
           self.morph_progress += 0.01
       else:
           # Check if we should transition to next demo phase
           if self.morph_phase == 1:  # Just finished cylinder
               # Force transition to bars_leds phase by setting time to past duration
               self.phase_start_time = time.time() - self.phase_durations["morphing"] - 1
               return  # Let phase controller handle the flash transition
           # Otherwise advance to next morph
           self.morph_progress = 0.0
           self.morph_phase = (self.morph_phase + 1) % 3
       
       # Calculate actual morph factor (clamped to 0-1 for shape interpolation)
       t = min(1.0, self.morph_progress)
       # Fast ease-in-out calculation
       t = t * t * (3 - 2 * t)
       
       # Select shape and color - handle vertex count mismatches with better interpolation
       if self.morph_phase == 0:  # Pyramid to Cube
           v1 = self.pyramid_vertices
           v2 = self.cube_vertices
           # Map pyramid to cube: apex splits to 4 top vertices, base splits to 4 bottom vertices
           # Pyramid: [apex, base1, base2, base3]
           # Cube: [front-bottom-left, front-bottom-right, front-top-right, front-top-left,
           #        back-bottom-left, back-bottom-right, back-top-right, back-top-left]
           v1_padded = [
               v1[0], v1[0], v1[0], v1[0],  # Apex -> top 4 vertices
               v1[1], v1[2], v1[2], v1[3],  # Base corners -> bottom 4 vertices
           ]
           v1 = v1_padded
           edges = self.cube_edges
           # Blend color from magenta to cyan
           r = int(255 * (1 - t))
           g = int(255 * t)
           b = 255
           shape_color = ssd.rgb(r, g, b)
       elif self.morph_phase == 1:  # Cube to Cylinder
           v1 = self.cube_vertices
           v2 = self.cylinder_vertices
           # Map cube to cylinder: each cube vertex becomes 2 adjacent cylinder vertices
           # Cylinder has 8 vertices on top ring, 8 on bottom ring
           # Cube has 4 on top, 4 on bottom
           v1_padded = [
               v1[0], v1[1], v1[1], v1[2], v1[2], v1[3], v1[3], v1[0],  # Bottom ring
               v1[4], v1[5], v1[5], v1[6], v1[6], v1[7], v1[7], v1[4],  # Top ring
           ]
           v1 = v1_padded
           edges = self.cylinder_edges
           # Stay cyan
           shape_color = ssd.rgb(0, 255, 255)
       else:  # Cylinder to Pyramid (won't reach here due to early transition)
           v1 = self.cylinder_vertices
           v2 = self.pyramid_vertices
           edges = self.pyramid_edges
           shape_color = ssd.rgb(255, 128, 0)
       
       # Update rotation angles (store as indices 0-255 for faster lookup)
       self.angle_x = (self.angle_x + 2) & 255  # ~0.03 radians per frame
       self.angle_y = (self.angle_y + 3) & 255  # ~0.04 radians per frame  
       self.angle_z = (self.angle_z + 1) & 255  # ~0.02 radians per frame
       
       # Get sin/cos from lookup tables
       cos_x = self.cos_table[self.angle_x] / 127.0
       sin_x = self.sine_table[self.angle_x] / 127.0
       cos_y = self.cos_table[self.angle_y] / 127.0
       sin_y = self.sine_table[self.angle_y] / 127.0
       cos_z = self.cos_table[self.angle_z] / 127.0
       sin_z = self.sine_table[self.angle_z] / 127.0
       
       # Fast vertex processing with inline lerp
       projected = []
       len1 = len(v1)
       len2 = len(v2)
       t_inv = 1 - t
       
       for i in range(max(len1, len2)):
           # Inline lerp with bounds checking
           if i < len1 and i < len2:
               x = v1[i][0] * t_inv + v2[i][0] * t
               y = v1[i][1] * t_inv + v2[i][1] * t
               z = v1[i][2] * t_inv + v2[i][2] * t
           elif i < len1:
               x, y, z = v1[i]
           else:
               x, y, z = v2[i]
           
           # Fast rotation
           x, y, z = self._rotate_3d_fast(x, y, z, cos_x, sin_x, cos_y, sin_y, cos_z, sin_z)
           
           # Fast projection
           sx, sy = self._project_fast(x, y, z)
           projected.append((sx, sy))
       
       # Draw edges (minimal bounds checking for speed)
       # Special handling for cube-to-cylinder: show all edges but morph positions smoothly
       if self.morph_phase == 1:  # Cube to Cylinder
           # Show all cylinder edges from the start for smoother appearance
           # The vertices will gradually move from cube to cylinder positions
           draw_edges = edges
       else:
           draw_edges = edges
       
       for i, j in draw_edges:
           if i < len(projected) and j < len(projected):
               x1, y1 = projected[i]
               x2, y2 = projected[j]
               # Relaxed bounds check
               if (-100 < x1 < 420 and -100 < y1 < 270 and
                   -100 < x2 < 420 and -100 < y2 < 270):
                   display.line(x1, y1, x2, y2, shape_color)
       
       # Fast LED update
       led_base = self.phase_frame * 4
       for i in range(10):
           offset = led_base + i * 16
           brightness = int((math.sin(offset * 0.1) + 1) * 31)  # 0-62 range
           
           if self.morph_phase == 0:
               self.np[i] = (brightness * 2, 0, brightness * 2)  # Magenta for pyramid
           elif self.morph_phase == 1:
               self.np[i] = (0, brightness * 2, brightness * 2)  # Cyan for cube->cylinder
           else:
               self.np[i] = (brightness * 2, brightness, 0)  # Orange for cylinder->pyramid
       
       self.np.write()
  
   def exit_demo(self, *args):
       """Exit the demo and return to solo games screen."""
       self.on_close()
       from bdg.screens.solo_games_screen import SoloGamesScreen
       Screen.change(SoloGamesScreen, mode=Screen.REPLACE)
  
   def on_close(self):
       """Cleanup when screen closes."""
       # Cancel all tasks
       for task in self.phase_tasks:
           task.cancel()
       
       # Free sine and cosine tables if they exist
       if hasattr(self, 'sine_table'):
           del self.sine_table
       if hasattr(self, 'cos_table'):
           del self.cos_table
      
       # Turn off LEDs
       try:
           for i in range(10):
               self.np[i] = (0, 0, 0)
           self.np.write()
           self.led_power.value(0)
       except:
           pass




def badge_game_config():
   """Configuration for Graphics Demo app.
  
   Returns:
       dict: Game configuration with con_id, title, screen_class, etc.
   """
   return {
       "con_id": 10,
       "title": "VibeDemo",
       "screen_class": VibeDemo,
       "screen_args": (),
       "multiplayer": False,
       "description": "Display graphics, palette effects, and animations",
   }