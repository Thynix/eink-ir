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
# Round down to whole pixels:
#   - IR image gets 9x5 e-ink pixels per pixel.
#   - Takes up:
#               - 288/296 pixels horizontally - 8 columns remain.
#               - 120/128 pixels vertically - 8 rows remain.
greyscale_palette = displayio.Palette(4)
greyscale_palette[0] = 0x000000 # Black
greyscale_palette[1] = 0x555555 # Light grey
greyscale_palette[2] = 0xAAAAAA # Dark grey
greyscale_palette[3] = 0xFFFFFF # Black

image = displayio.Bitmap(288, 120, 4)
image_frame = displayio.TileGrid(
    bitmap=image,
    pixel_shader=greyscale_palette,
    width=32,
    height=24,
    tile_width=9,
    tile_height=5,
    # Center frame horizontally and align it at the bottom vertically.
    x=4,
    y=8,
)

# Text banner along the top.
banner_text = label.Label(
    terminalio.FONT,
    color=0x000000,
)
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
frame_group.append(image_frame)
frame_group.append(banner_text)

raw_frame = [0] * 768
while True:
    mlx.getFrame(raw_frame)

    # Assign colors based on even-probability bands per-frame.
    #bands = statistics.quantiles(raw_frame)
    #print(bands)
    # Assign colors based on evenly-sized bands from min to max.
    min_temp = min(raw_frame)
    max_temp = max(raw_frame)
    band_size = (max_temp - min_temp) / 3
    bands = [
        min_temp + band_size,
        min_temp + band_size * 2,
        min_temp + band_size * 3,
    ]
    banner_text.text = "{} C - {} C".format(min_temp, max_temp)

    for y in range(24):
        for x in range(32):
            image[x, y] = 3
            for i, bound in enumerate(bands):
                if raw_frame[y * 24 + x] < bound:
                    image[x, y] = i
                    break

    for y in range(24):
        for x in range(32):
            print(image[x, y], end=" ")
            #print("{:0.1f},".format(raw_frame[y * 24 + x]), end="")
        print()
    print()

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

    print(gc.mem_free())

