import time
import os
import sys

def key_pressed():
    try:
        import msvcrt
        return msvcrt.kbhit()
    except ImportError:
        import select
        dr, _, _ = select.select([sys.stdin], [], [], 0)
        return dr != []

def clear():
    os.system("cls" if os.name == "nt" else "clear")

C = {
    "cyan": "\033[96m",
    "blue": "\033[94m",
    "green": "\033[92m",
    "reset": "\033[0m"
}

AI_FRAMES = [
r"""   Red: ●──●──●""",
r"""   Red: ●──●──○""",
r"""   Red: ○──●──●""",
r"""   Red: ●──○──●""",
]

GIT_FRAMES = [
r"""   Git: ●─○─○""",
r"""   Git: ○─●─○""",
r"""   Git: ○─○─●""",
]

def final_frame():
    clear()
    print(C["green"] + ">>> Starting AI-Powered Git Tool..." + C["reset"])
    time.sleep(0.15)

def splash(total_duration=1.0):
    # 1 saniye hedef → frame başına süre = total_duration / frame_count
    frames = []

    # AI (4 frame x2)
    frames += AI_FRAMES * 2

    # Git (3 frame x2)
    frames += GIT_FRAMES * 2

    frame_duration = total_duration / len(frames)

    for f in frames:
        if key_pressed():
            return final_frame()
        clear()
        print(C["cyan"] + f + C["reset"])
        time.sleep(frame_duration)

    final_frame()


if __name__ == "__main__":
    if os.name != "nt":
        import termios, tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        tty.setcbreak(fd)

    try:
        splash(1.0)  # Hedef: tam 1 saniye
    finally:
        if os.name != "nt":
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    print("Yükleniyor...")
