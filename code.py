import board
import digitalio
import time
import gc
import busio
import adafruit_mlx90640
from adafruit_magtag.magtag import MagTag
import displayio
import statistics
import terminalio
from adafruit_display_text import label

magtag = MagTag(
    default_bg=0x000000,
)

#magtag.peripherals.neopixels.fill((255, 255, 255))

# Turn off blinky LED
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
led.value = False

# Set up MLX90640
i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)
mlx = adafruit_mlx90640.MLX90640(i2c)
mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_1_HZ

# MagTag has 2.9" grayscale display with 296x128 pixels.
# IR image has 32x24:
#   - 5.3 pixel height
#   - 9.25 pixel width
# Round down to whole pixels, and restrict to uniform scaling:
#   - IR image gets 5x5 e-ink pixels per pixel.
#   - Takes up:
#               - 160/296 pixels horizontally - 136 columns remain.
#               - 120/128 pixels vertically - 8 rows remain.
greyscale_palette = displayio.Palette(4)
greyscale_palette[0] = 0x000000 # Black
greyscale_palette[1] = 0x555555 # Light grey
greyscale_palette[2] = 0xAAAAAA # Dark grey
greyscale_palette[3] = 0xFFFFFF # Black

image = displayio.Bitmap(32, 24, 4)
image_frame = displayio.TileGrid(
    bitmap=image,
    pixel_shader=greyscale_palette,
)
image_group = displayio.Group(
    scale=5,
    # Center frame horizontally and align it at the bottom vertically.
    x=136 // 2,
    y=8,
)
image_group.append(image_frame)

# Text banner along the top.
banner_text = label.Label(
    terminalio.FONT,
    color=0x000000,
)
# Top few pixels stay black for some reason.
banner_text.y = 3

# White background; scaled to save RAM.
bg_bitmap = displayio.Bitmap(magtag.graphics.display.width // 8, magtag.graphics.display.height // 8, 1)
bg_palette = displayio.Palette(1)
bg_palette[0] = 0xFFFFFF
bg_sprite = displayio.TileGrid(bg_bitmap, x=0, y=0, pixel_shader=bg_palette)
bg_group = displayio.Group(scale=8)
bg_group.append(bg_sprite)

frame_group = displayio.Group()
frame_group.append(bg_group)
frame_group.append(image_group)
frame_group.append(banner_text)

raw_frame = [0] * 768
while True:
    mlx.getFrame(raw_frame)

    # Assign colors based on even-probability bands per-frame.
    bands = statistics.quantiles(raw_frame)

    banner_text.text = "{:0.1f} C - {:0.1f} C; {}".format(
        min(raw_frame),
        max(raw_frame),
        " ".join(["{:0.1f}".format(x) for x in bands]),
    )

    # Use white for brightest band.
    image.fill(3)
    for y in range(24):
        for x in range(32):
            for i, bound in enumerate(bands):
                if raw_frame[y * 24 + x] < bound:
                    image[x, y] = i
                    break

    magtag.graphics.display.show(frame_group)

    # Perform and wait for refresh; keep LED on during it.
    led.value = True
    refresh_time = magtag.graphics.display.time_to_refresh
    if refresh_time > 0:
        magtag.enter_light_sleep(refresh_time)
    magtag.graphics.display.refresh()
    while magtag.graphics.display.busy:
        pass
    led.value = False
