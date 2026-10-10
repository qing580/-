from pathlib import Path
import sys

from PIL import Image


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: python generate_icon.py SOURCE_IMAGE OUTPUT_DIR")

    source = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    image = Image.open(source).convert("RGBA")
    edge_trim = max(6, round(min(image.size) * 0.008))
    image = image.crop((edge_trim, edge_trim, image.width - edge_trim, image.height - edge_trim))
    pixels = []
    for red, green, blue, _ in image.getdata():
        lightest = min(red, green, blue)
        if lightest >= 248:
            alpha = 0
        elif lightest >= 232:
            alpha = round(255 * (248 - lightest) / 16)
        else:
            alpha = 255
        pixels.append((red, green, blue, alpha))
    image.putdata(pixels)

    bounds = image.getbbox()
    if bounds:
        image = image.crop(bounds)

    canvas_size = 1024
    padding = 52
    image.thumbnail((canvas_size - padding * 2, canvas_size - padding * 2), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    canvas.alpha_composite(image, ((canvas_size - image.width) // 2, (canvas_size - image.height) // 2))

    png_path = output_dir / "maritime_anomaly_agent_icon.png"
    ico_path = output_dir / "maritime_anomaly_agent_icon.ico"
    canvas.save(png_path, optimize=True)
    canvas.save(ico_path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    print(png_path)
    print(ico_path)


if __name__ == "__main__":
    main()
