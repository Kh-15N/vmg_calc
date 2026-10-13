import pyautogui
import time
import random
import string

# ============================================================
# TEXT
# ============================================================

TEXT = """The missile knows where it is at all times.
It knows this because it knows where it isn't.
By subtracting where it is from where it isn't,
Or where it isn't from where it is (whichever is
Greater), it obtains a difference, or deviation.
The guidance subsystem uses deviations to generate corrective
Commands to drive the missile from a position where it is to a
Position where it isn't,
And arriving at a position where it wasn't, it now is.
Consequently, the position where it is,
Is now the position that it wasn't,
And it follows that the position that
It was, is now the position that it isn't.
In the event that the position that it is in is not the position that
It wasn't, the system has acquired a variation,
The variation being the difference between
Where the missile is, and where it wasn't.
If variation is considered to be a
Significant factor, it too may be corrected by the GEA.
However, the missile must also know where it was.
The missile guidance computer scenario works as follows.
Because a variation has modified some of the information
The missile has obtained, it is not sure just where it is.
However, it is sure where it isn't,
Within reason, and it knows where it was.
It now subtracts where it should be from where it wasn't,
Or vice-versa, and by differentiating this from the algebraic sum of
Where it shouldn't be, and where it was,
It is able to obtain the deviation
And its variation, which is called error."""


# ============================================================
# GLOBAL SETTINGS
# ============================================================

START_DELAY = 5.0

# Базовая скорость символов
MIN_DELAY = 0.001
MAX_DELAY = 0.015

# Индивидуальный разброс
JITTER = 0.30

# Вероятность небольшой "задумчивой" паузы
HESITATION_CHANCE = 0.01

# Как часто немного меняется общий темп
TEMPO_CHANGE_CHANCE = 0.025

# Насколько может изменяться темп
MIN_TEMPO = 0.92
MAX_TEMPO = 1.65


# ============================================================
# STATE
# ============================================================

tempo = random.uniform(MIN_TEMPO, MAX_TEMPO)


# ============================================================
# KEYBOARD
# ============================================================

# Английская раскладка QWERTY.
# Поскольку текст английский, дополнительных переключений
# раскладки не требуется.

DIRECT_KEYS = {
    ' ': 'space',
    '\n': 'enter',
    '\t': 'tab',

    '`': '`',
    '-': '-',
    '=': '=',
    '[': '[',
    ']': ']',
    '\\': '\\',
    ';': ';',
    "'": "'",
    ',': ',',
    '.': '.',
    '/': '/',
}


# Символы, которые печатаются через SHIFT + key
SHIFT_KEYS = {
    '~': '`',
    '!': '1',
    '@': '2',
    '#': '3',
    '$': '4',
    '%': '5',
    '^': '6',
    '&': '7',
    '*': '8',
    '(': '9',
    ')': '0',
    '_': '-',
    '+': '=',
    '{': '[',
    '}': ']',
    '|': '\\',
    ':': ';',
    '"': "'",
    '<': ',',
    '>': '.',
    '?': '/',
}


# ============================================================
# LOW LEVEL KEY PRESS
# ============================================================

def press_key(key, shift=False):
    """
    Настоящее OS-level нажатие:
        keyDown()
        небольшое удержание
        keyUp()
    """

    if shift:
        pyautogui.keyDown("shift")

    # Человек не отпускает каждую клавишу
    # абсолютно за одинаковое время.
    hold_time = random.uniform(0.008, 0.035)

    pyautogui.keyDown(key)

    time.sleep(hold_time)

    pyautogui.keyUp(key)

    if shift:
        pyautogui.keyUp("shift")


# ============================================================
# TYPE ONE CHARACTER
# ============================================================

def type_char(char):

    # --------------------------------------------------------
    # Lowercase letters
    # --------------------------------------------------------

    if char in string.ascii_lowercase:
        press_key(char)
        return

    # --------------------------------------------------------
    # Uppercase letters
    # --------------------------------------------------------

    if char in string.ascii_uppercase:
        press_key(char.lower(), shift=True)
        return

    # --------------------------------------------------------
    # Numbers
    # --------------------------------------------------------

    if char in string.digits:
        press_key(char)
        return

    # --------------------------------------------------------
    # Shift punctuation
    # --------------------------------------------------------

    if char in SHIFT_KEYS:
        press_key(SHIFT_KEYS[char], shift=True)
        return

    # --------------------------------------------------------
    # Direct keys
    # --------------------------------------------------------

    if char in DIRECT_KEYS:
        press_key(DIRECT_KEYS[char])
        return

    # --------------------------------------------------------
    # Unknown character
    # --------------------------------------------------------

    print(f"[WARN] Unsupported character: {repr(char)}")


# ============================================================
# HUMAN-LIKE DELAY
# ============================================================

def base_delay():

    delay = random.uniform(
        MIN_DELAY,
        MAX_DELAY
    )

    # Общая скорость пользователя
    delay *= tempo

    # Небольшое индивидуальное отклонение
    delay *= random.uniform(
        1.0 - JITTER,
        1.0 + JITTER
    )

    return delay


# ============================================================
# WORD / PUNCTUATION ANALYSIS
# ============================================================

def get_word_before(text, index):

    start = index - 1

    while start >= 0 and (
        text[start].isalpha() or
        text[start] == "'"
    ):
        start -= 1

    return text[start + 1:index]


def get_word_after(text, index):

    end = index

    while end < len(text) and (
        text[end].isalpha() or
        text[end] == "'"
    ):
        end += 1

    return text[index:end]


# ============================================================
# PUNCTUATION PAUSES
# ============================================================

def punctuation_pause(char):

    if char == ',':
        return random.uniform(0.10, 0.30)

    if char == ';':
        return random.uniform(0.15, 0.35)

    if char == ':':
        return random.uniform(0.15, 0.38)

    if char == '.':
        return random.uniform(0.30, 0.80)

    if char == '!':
        return random.uniform(0.35, 0.90)

    if char == '?':
        return random.uniform(0.35, 0.95)

    # После закрывающей кавычки/скобки
    if char in ['"', "'", ')', ']', '}']:
        return random.uniform(0.08, 0.25)

    # Дефис обычно почти не вызывает паузу
    if char == '-':
        return random.uniform(0.03, 0.12)

    return 0.0


# ============================================================
# WORD-SPECIFIC RHYTHM
# ============================================================

def word_boundary_delay(char):

    if char != ' ':
        return 0.0

    # Небольшая естественная пауза между словами.
    return random.uniform(0.06, 0.75)


# ============================================================
# SPECIAL ENGLISH PATTERNS
# ============================================================

def english_pattern_delay(text, index):

    char = text[index]

    # --------------------------------------------------------
    # Apostrophe inside contractions:
    #
    # don't
    # can't
    # I'm
    # we're
    # they've
    # John's
    # --------------------------------------------------------

    if char == "'":
        return random.uniform(0.015, 0.07)

    # --------------------------------------------------------
    # Double punctuation
    # --------------------------------------------------------

    if index + 1 < len(text):

        pair = text[index:index + 2]

        if pair == "..":
            return random.uniform(0.05, 0.15)

        if pair == "?!":
            return random.uniform(0.15, 0.4)

        if pair == "!?":
            return random.uniform(0.15, 0.4)

    # --------------------------------------------------------
    # Opening punctuation
    # --------------------------------------------------------

    if char in ['(', '[', '{']:
        return random.uniform(0.03, 0.10)

    # --------------------------------------------------------
    # Closing punctuation
    # --------------------------------------------------------

    if char in [')', ']', '}']:
        return random.uniform(0.05, 0.18)

    return 0.0


# ============================================================
# THINKING PAUSE
# ============================================================

def maybe_hesitate():

    if random.random() < HESITATION_CHANCE:
        time.sleep(
            random.uniform(0.65, 6.30)
        )


# ============================================================
# TEMPO CHANGE
# ============================================================

def maybe_change_tempo():

    global tempo

    if random.random() < TEMPO_CHANGE_CHANCE:

        tempo = random.uniform(
            MIN_TEMPO,
            MAX_TEMPO
        )


# ============================================================
# MAIN TYPING LOOP
# ============================================================

print("Starting in 5 seconds...")
time.sleep(START_DELAY)

for index, char in enumerate(TEXT):

    # --------------------------------------------------------
    # Type actual key
    # --------------------------------------------------------

    type_char(char)

    # --------------------------------------------------------
    # Base timing
    # --------------------------------------------------------

    delay = base_delay()

    # --------------------------------------------------------
    # Space between words
    # --------------------------------------------------------

    delay += word_boundary_delay(char)

    # --------------------------------------------------------
    # Punctuation
    # --------------------------------------------------------

    delay += punctuation_pause(char)

    # --------------------------------------------------------
    # English-specific patterns
    # --------------------------------------------------------

    delay += english_pattern_delay(
        TEXT,
        index
    )

    # --------------------------------------------------------
    # New paragraph
    # --------------------------------------------------------

    if char == '\n':

        delay += random.uniform(
            2,
            9
        )

        # Дополнительная пауза между абзацами
        if (
            index + 1 < len(TEXT)
            and TEXT[index + 1] == '\n'
        ):
            delay += random.uniform(
                9,
                19
            )

    # --------------------------------------------------------
    # Longer hesitation after punctuation
    # --------------------------------------------------------

    if char in '.!?':
        if random.random() < 0.35:
            delay += random.uniform(
                1.1,
                3.8
            )

    # --------------------------------------------------------
    # Random hesitation
    # --------------------------------------------------------

    maybe_hesitate()

    # --------------------------------------------------------
    # Occasionally change typing rhythm
    # --------------------------------------------------------

    maybe_change_tempo()

    # --------------------------------------------------------
    # Final delay
    # --------------------------------------------------------

    time.sleep(delay)
