"""Number verbalisation for en / de / ru / uk.

Why this exists: neural TTS models are trained mostly on text where numbers are already
written out. Given raw digits they guess — Supertonic reads "2026" in whatever language
it feels like, Piper spells digits, Kokoro is fine in English only. Feeding words instead
of digits fixes this across every model, so we do it once here.

Covers: integers up to 10^15, decimals, negatives, thousands separators (1,234 / 1.234 /
1 234), percentages, currency (€ $ £ ₽ ₴), clock times (10:30), versions (1.2.3), dates
(06.09.2026, 2026-09-06), ranges (5-10), English ordinals (1st, 22nd), years.

Languages other than en/de/ru/uk are returned unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SUPPORTED = ("en", "de", "ru", "uk")

# --------------------------------------------------------------------------- English

_EN_UNITS = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
]
_EN_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_EN_SCALES = [(10**12, "trillion"), (10**9, "billion"), (10**6, "million"), (10**3, "thousand")]
_EN_ORD_IRREGULAR = {
    "one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth",
    "nine": "ninth", "twelve": "twelfth",
}


def en_cardinal(n: int) -> str:
    if n < 0:
        return "minus " + en_cardinal(-n)
    if n < 20:
        return _EN_UNITS[n]
    if n < 100:
        t, u = divmod(n, 10)
        return _EN_TENS[t] + (f"-{_EN_UNITS[u]}" if u else "")
    if n < 1000:
        h, r = divmod(n, 100)
        return f"{_EN_UNITS[h]} hundred" + (f" {en_cardinal(r)}" if r else "")
    for value, name in _EN_SCALES:
        if n >= value:
            q, r = divmod(n, value)
            return f"{en_cardinal(q)} {name}" + (f" {en_cardinal(r)}" if r else "")
    return str(n)


def en_ordinal(n: int) -> str:
    words = en_cardinal(n)
    head, sep, last = words.rpartition("-") if "-" in words.split()[-1] else words.rpartition(" ")
    if last in _EN_ORD_IRREGULAR:
        last = _EN_ORD_IRREGULAR[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    else:
        last += "th"
    return f"{head}{sep}{last}"


def en_year(n: int) -> str:
    if 1100 <= n <= 1999 or 2010 <= n <= 2099:
        hi, lo = divmod(n, 100)
        if lo == 0:
            return f"{en_cardinal(hi)} hundred"
        if lo < 10:
            return f"{en_cardinal(hi)} oh {en_cardinal(lo)}"
        return f"{en_cardinal(hi)} {en_cardinal(lo)}"
    return en_cardinal(n)


# --------------------------------------------------------------------------- German

_DE_UNITS = [
    "null", "eins", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun", "zehn",
    "elf", "zwölf", "dreizehn", "vierzehn", "fünfzehn", "sechzehn", "siebzehn", "achtzehn", "neunzehn",
]
_DE_TENS = ["", "", "zwanzig", "dreißig", "vierzig", "fünfzig", "sechzig", "siebzig", "achtzig", "neunzig"]
_DE_SCALES = [
    (10**12, "Billion", "Billionen"),
    (10**9, "Milliarde", "Milliarden"),
    (10**6, "Million", "Millionen"),
]


def _de_below_1000(n: int, *, prefix: bool) -> str:
    """prefix=True -> 'ein' form used inside compounds (einhundert, einundzwanzig, eintausend)."""
    if n == 0:
        return ""
    if n == 1:
        return "ein" if prefix else "eins"
    if n < 20:
        return _DE_UNITS[n]
    if n < 100:
        t, u = divmod(n, 10)
        return (f"{'ein' if u == 1 else _DE_UNITS[u]}und" if u else "") + _DE_TENS[t]
    h, r = divmod(n, 100)
    return ("ein" if h == 1 else _DE_UNITS[h]) + "hundert" + _de_below_1000(r, prefix=prefix)


def de_cardinal(n: int) -> str:
    if n < 0:
        return "minus " + de_cardinal(-n)
    if n == 0:
        return "null"
    parts: list[str] = []
    for value, one, many in _DE_SCALES:
        if n >= value:
            q, n = divmod(n, value)
            parts.append(f"eine {one}" if q == 1 else f"{de_cardinal(q)} {many}")
    tail = ""
    if n >= 1000:
        q, n = divmod(n, 1000)
        tail = _de_below_1000(q, prefix=True) + "tausend"
    tail += _de_below_1000(n, prefix=bool(tail) and n != 1) if n else ""
    if tail and n == 1 and not tail.endswith("eins"):
        # e.g. 1001 -> eintausendeins
        tail += "eins"
    if tail:
        parts.append(tail)
    return " ".join(parts)


def de_ordinal(n: int, ending: str = "te") -> str:
    """3 -> dritte (ending='te'), dritten (ending='ten'), dritter (ending='ter')."""
    stem = {1: "ers", 3: "drit", 7: "sieb", 8: "ach"}.get(n)
    if stem is None:
        stem = de_cardinal(n) + ("" if n < 20 else "s")
    return stem + ending


def de_year(n: int) -> str:
    if 1100 <= n <= 1999:
        hi, lo = divmod(n, 100)
        return _de_below_1000(hi, prefix=True) + "hundert" + (_de_below_1000(lo, prefix=False) if lo else "")
    return de_cardinal(n)


# --------------------------------------------------------------------------- Russian / Ukrainian


@dataclass(frozen=True)
class _Slavic:
    units_m: tuple[str, ...]
    units_f: tuple[str, ...]
    teens: tuple[str, ...]
    tens: tuple[str, ...]
    hundreds: tuple[str, ...]
    scales: tuple[tuple[int, tuple[str, str, str], str], ...]  # value, (one, few, many), gender
    minus: str
    whole: tuple[str, str]  # (singular "целая", plural "целых")
    fractions: tuple[tuple[str, str], ...]  # ("десятая","десятых"), ("сотая","сотых"), ("тысячная","тысячных")
    point: str  # word used when reading digits after the decimal point one by one
    percent: tuple[str, str, str, str]  # one, few, many, genitive-singular (for decimals)
    currencies: dict[str, tuple[str, str, str]]
    months: tuple[str, ...]
    year_word: str
    hours_word: tuple[str, str, str]
    zero: str


_RU = _Slavic(
    units_m=("ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"),
    units_f=("ноль", "одна", "две", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"),
    teens=("десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать",
           "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"),
    tens=("", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"),
    hundreds=("", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот"),
    scales=(
        (10**12, ("триллион", "триллиона", "триллионов"), "m"),
        (10**9, ("миллиард", "миллиарда", "миллиардов"), "m"),
        (10**6, ("миллион", "миллиона", "миллионов"), "m"),
        (10**3, ("тысяча", "тысячи", "тысяч"), "f"),
    ),
    minus="минус",
    whole=("целая", "целых"),
    fractions=(("десятая", "десятых"), ("сотая", "сотых"), ("тысячная", "тысячных")),
    point="запятая",
    percent=("процент", "процента", "процентов", "процента"),
    currencies={
        "$": ("доллар", "доллара", "долларов"),
        "€": ("евро", "евро", "евро"),
        "£": ("фунт", "фунта", "фунтов"),
        "₽": ("рубль", "рубля", "рублей"),
        "₴": ("гривна", "гривны", "гривен"),
    },
    months=("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября",
            "октября", "ноября", "декабря"),
    year_word="года",
    hours_word=("час", "часа", "часов"),
    zero="ноль",
)

_UK = _Slavic(
    units_m=("нуль", "один", "два", "три", "чотири", "п'ять", "шість", "сім", "вісім", "дев'ять"),
    units_f=("нуль", "одна", "дві", "три", "чотири", "п'ять", "шість", "сім", "вісім", "дев'ять"),
    teens=("десять", "одинадцять", "дванадцять", "тринадцять", "чотирнадцять", "п'ятнадцять",
           "шістнадцять", "сімнадцять", "вісімнадцять", "дев'ятнадцять"),
    tens=("", "", "двадцять", "тридцять", "сорок", "п'ятдесят", "шістдесят", "сімдесят", "вісімдесят", "дев'яносто"),
    hundreds=("", "сто", "двісті", "триста", "чотириста", "п'ятсот", "шістсот", "сімсот", "вісімсот", "дев'ятсот"),
    scales=(
        (10**12, ("трильйон", "трильйони", "трильйонів"), "m"),
        (10**9, ("мільярд", "мільярди", "мільярдів"), "m"),
        (10**6, ("мільйон", "мільйони", "мільйонів"), "m"),
        (10**3, ("тисяча", "тисячі", "тисяч"), "f"),
    ),
    minus="мінус",
    whole=("ціла", "цілих"),
    fractions=(("десята", "десятих"), ("сота", "сотих"), ("тисячна", "тисячних")),
    point="кома",
    percent=("відсоток", "відсотки", "відсотків", "відсотка"),
    currencies={
        "$": ("долар", "долари", "доларів"),
        "€": ("євро", "євро", "євро"),
        "£": ("фунт", "фунти", "фунтів"),
        "₽": ("рубль", "рублі", "рублів"),
        "₴": ("гривня", "гривні", "гривень"),
    },
    months=("січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня", "вересня",
            "жовтня", "листопада", "грудня"),
    year_word="року",
    hours_word=("година", "години", "годин"),
    zero="нуль",
)

_SLAVIC = {"ru": _RU, "uk": _UK}


def plural_form(n: int, one: str, few: str, many: str) -> str:
    """East-Slavic plural agreement: 1 книга, 2 книги, 5 книг (21 книга, 12 книг)."""
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def _slavic_below_1000(n: int, t: _Slavic, gender: str) -> list[str]:
    words: list[str] = []
    h, r = divmod(n, 100)
    if h:
        words.append(t.hundreds[h])
    if 10 <= r <= 19:
        words.append(t.teens[r - 10])
    else:
        tens, u = divmod(r, 10)
        if tens:
            words.append(t.tens[tens])
        if u:
            words.append((t.units_f if gender == "f" else t.units_m)[u])
    return words


def slavic_cardinal(n: int, t: _Slavic, gender: str = "m") -> str:
    if n < 0:
        return f"{t.minus} {slavic_cardinal(-n, t, gender)}"
    if n == 0:
        return t.zero
    words: list[str] = []
    for value, forms, scale_gender in t.scales:
        if n >= value:
            q, n = divmod(n, value)
            if not (value == 1000 and q == 1):  # "тысяча двести", not "одна тысяча двести"
                words.extend(_slavic_below_1000(q, t, scale_gender) if q < 1000 else [slavic_cardinal(q, t, scale_gender)])
            words.append(plural_form(q, *forms))
    words.extend(_slavic_below_1000(n, t, gender))
    return " ".join(w for w in words if w)


# --------------------------------------------------------------------------- slavic ordinals


@dataclass(frozen=True)
class _SlavicOrd:
    units: tuple[str, ...]
    teens: tuple[str, ...]
    tens: tuple[str, ...]
    hundreds: tuple[str, ...]
    thousand: str
    gen_prefix: tuple[str, ...]  # "двух" + "тысячный"
    soft_ending: str  # nominative ending of the one soft-stem ordinal ("третий" / "третій")
    endings: dict[str, dict[str, str]]  # {"hard": {form: ending}, "soft": {...}}


_RU_ORD = _SlavicOrd(
    units=("", "первый", "второй", "третий", "четвёртый", "пятый", "шестой", "седьмой", "восьмой", "девятый"),
    teens=("десятый", "одиннадцатый", "двенадцатый", "тринадцатый", "четырнадцатый", "пятнадцатый",
           "шестнадцатый", "семнадцатый", "восемнадцатый", "девятнадцатый"),
    tens=("", "", "двадцатый", "тридцатый", "сороковой", "пятидесятый", "шестидесятый", "семидесятый",
          "восьмидесятый", "девяностый"),
    hundreds=("", "сотый", "двухсотый", "трёхсотый", "четырёхсотый", "пятисотый", "шестисотый", "семисотый",
              "восьмисотый", "девятисотый"),
    thousand="тысячный",
    gen_prefix=("", "", "двух", "трёх", "четырёх", "пяти", "шести", "семи", "восьми", "девяти"),
    soft_ending="ий",
    endings={
        "hard": {"m": None, "gen": "ого", "loc": "ом", "n": "ое", "f": "ая", "f_acc": "ую"},
        "soft": {"m": None, "gen": "ьего", "loc": "ьем", "n": "ье", "f": "ья", "f_acc": "ью"},
    },
)

_UK_ORD = _SlavicOrd(
    units=("", "перший", "другий", "третій", "четвертий", "п'ятий", "шостий", "сьомий", "восьмий", "дев'ятий"),
    teens=("десятий", "одинадцятий", "дванадцятий", "тринадцятий", "чотирнадцятий", "п'ятнадцятий",
           "шістнадцятий", "сімнадцятий", "вісімнадцятий", "дев'ятнадцятий"),
    tens=("", "", "двадцятий", "тридцятий", "сороковий", "п'ятдесятий", "шістдесятий", "сімдесятий",
          "вісімдесятий", "дев'яностий"),
    hundreds=("", "сотий", "двохсотий", "трьохсотий", "чотирьохсотий", "п'ятисотий", "шестисотий", "семисотий",
              "восьмисотий", "дев'ятисотий"),
    thousand="тисячний",
    gen_prefix=("", "", "двох", "трьох", "чотирьох", "п'яти", "шести", "семи", "восьми", "дев'яти"),
    soft_ending="ій",
    endings={
        "hard": {"m": None, "gen": "ого", "loc": "ому", "n": "е", "f": "а", "f_acc": "у"},
        "soft": {"m": None, "gen": "ього", "loc": "ьому", "n": "є", "f": "я", "f_acc": "ю"},
    },
)

_ORD = {"ru": _RU_ORD, "uk": _UK_ORD}


def _inflect_ordinal(word: str, lang: str, form: str) -> str:
    """Nominative masculine ordinal -> requested form (m, n, f, f_acc, gen, loc)."""
    o = _ORD[lang]
    kind = "soft" if word.endswith(o.soft_ending) else "hard"
    ending = o.endings[kind][form]
    if ending is None:
        return word
    return word[:-2] + ending


def slavic_ordinal(n: int, lang: str, form: str = "m") -> str:
    """2024 -> "две тысячи двадцать четвёртый" (form=m) / "...четвёртом" (loc) / "...четвёртого" (gen).

    Only the last word is an ordinal; everything before it stays cardinal, as in speech.
    """
    if n <= 0 or n >= 10**6:
        return cardinal(n, lang)
    o, t = _ORD[lang], _SLAVIC[lang]
    words: list[str] = []
    q, r = divmod(n, 1000)
    if r == 0:
        if q == 1:
            last = o.thousand
        elif q < 10:
            last = o.gen_prefix[q] + o.thousand
        else:
            words.append(slavic_cardinal(q, t, "f"))
            last = o.thousand
    else:
        if q:
            words.append(slavic_cardinal(q * 1000, t))
        h, rr = divmod(r, 100)
        if rr == 0:
            last = o.hundreds[h]
        else:
            if h:
                words.append(t.hundreds[h])
            if 10 <= rr <= 19:
                last = o.teens[rr - 10]
            else:
                tens, u = divmod(rr, 10)
                if u == 0:
                    last = o.tens[tens]
                else:
                    if tens:
                        words.append(t.tens[tens])
                    last = o.units[u]
    words.append(_inflect_ordinal(last, lang, form))
    return " ".join(words)


# Ukrainian plural nouns whose gender the ending alone does not reveal ("два роки" vs "дві книги").
_UK_MASC_PL = frozenset(
    "роки дні тижні місяці рази кроки столи метри кілометри сантиметри міліметри кілограми грами літри "
    "бали пункти файли рядки символи байти кілобайти мегабайти гігабайти пікселі кадри голоси класи приклади "
    "варіанти способи елементи об'єкти проєкти проекти сезони епізоди рівні поверхи ряди етапи параметри "
    "користувачі гравці учні студенти хлопці чоловіки коти пси автомобілі потяги літаки квитки долари "
    "рублі фунти центи відсотки процеси потоки сервери клієнти запити пакети токени пункти".split()
)
_UK_FEM_PL = frozenset(
    "години хвилини секунди гривні копійки книги штуки сторінки тисячі сотні картинки спроби версії лінії "
    "кнопки моделі мови речі папки частини хвилі ночі зміни вправи помилки задачі функції команди форми фрази "
    "статті пісні жінки дівчини дівчата дитини людини особи країни машини квартири кімнати школи компанії "
    "таблиці колонки категорії теми ідеї цілі причини умови дії операції ціни знижки покупки".split()
)
_NEXT_WORD_RE = re.compile(r"^\s+([^\W\d_][\w'’-]*)")


def slavic_count(n: int, lang: str, following: str) -> str:
    """Cardinal that agrees with the noun that follows: "1 штуку" -> "одну штуку", "2 книги" -> "дві книги"."""
    tab = _SLAVIC[lang]
    mw = _NEXT_WORD_RE.match(following)
    noun = mw.group(1).lower() if mw else ""
    form = "m"
    if noun:
        last = noun[-1]
        if n % 10 == 1 and n % 100 != 11:
            if last in "ая":
                form = "f"
            elif last in "ую":
                form = "f_acc"
            elif last in "оеє":
                form = "n"
        elif n % 10 == 2 and n % 100 != 12:
            if lang == "ru":
                form = "f" if last in "иы" else "m"
            elif noun in _UK_FEM_PL:
                form = "f"
            elif noun in _UK_MASC_PL:
                form = "m"
            elif noun.endswith(("ки", "ги", "хи", "ції", "сії", "зії", "ні", "лі")) and not noun.endswith(("дні", "тижні")):
                form = "f"  # книги, помилки, функції, гривні ... (best effort)
    words = slavic_cardinal(n, tab, "f" if form in ("f", "f_acc") else "m")
    if form == "f_acc" and words.endswith("одна"):
        words = words[:-4] + "одну"
    elif form == "n" and words.endswith("один"):
        words = words[:-4] + ("одно" if lang == "ru" else "одне")
    return words


# --------------------------------------------------------------------------- shared helpers


def cardinal(n: int, lang: str, gender: str = "m") -> str:
    if lang == "en":
        return en_cardinal(n)
    if lang == "de":
        return de_cardinal(n)
    if lang in _SLAVIC:
        return slavic_cardinal(n, _SLAVIC[lang], gender)
    return str(n)


def year(n: int, lang: str) -> str:
    if lang == "en":
        return en_year(n)
    if lang == "de":
        return de_year(n)
    return cardinal(n, lang)


def digits(s: str, lang: str) -> str:
    return " ".join(cardinal(int(ch), lang) for ch in s)


def decimal(n: int, frac: str, lang: str) -> str:
    """3.14 -> three point one four / drei Komma eins vier / три целых четырнадцать сотых."""
    if lang == "en":
        return f"{en_cardinal(n)} point {digits(frac, lang)}"
    if lang == "de":
        return f"{de_cardinal(n)} Komma {digits(frac, lang)}"
    t = _SLAVIC[lang]
    if len(frac) > 3:
        return f"{slavic_cardinal(n, t)} {t.point} {digits(frac, lang)}"
    whole = slavic_cardinal(n, t, "f") + " " + (t.whole[0] if plural_form(n, "1", "x", "x") == "1" else t.whole[1])
    fv = int(frac)
    unit_one, unit_many = t.fractions[len(frac) - 1]
    unit = unit_one if plural_form(fv, "1", "x", "x") == "1" else unit_many
    return f"{whole} {slavic_cardinal(fv, t, 'f')} {unit}"


def percent(words: str, n: int, lang: str, *, is_decimal: bool = False) -> str:
    if lang == "en":
        return f"{words} percent"
    if lang == "de":
        return f"{words} Prozent"
    t = _SLAVIC[lang]
    one, few, many, gen = t.percent
    return f"{words} {gen if is_decimal else plural_form(n, one, few, many)}"


_EN_CUR = {"$": ("dollar", "dollars"), "€": ("euro", "euros"), "£": ("pound", "pounds"), "₽": ("ruble", "rubles"), "₴": ("hryvnia", "hryvnias")}
_DE_CUR = {"$": "Dollar", "€": "Euro", "£": "Pfund", "₽": "Rubel", "₴": "Hrywnja"}


def currency(sym: str, n: int, frac: str | None, lang: str) -> str:
    cents = int(frac[:2].ljust(2, "0")) if frac else 0
    if lang == "en":
        one, many = _EN_CUR[sym]
        out = f"{en_cardinal(n)} {one if n == 1 else many}"
        return f"{out} {en_cardinal(cents)}" if cents else out
    if lang == "de":
        out = f"{de_cardinal(n) if n != 1 else 'ein'} {_DE_CUR[sym]}"
        return f"{out} {de_cardinal(cents)}" if cents else out
    t = _SLAVIC[lang]
    forms = t.currencies[sym]
    gender = "f" if sym == "₴" else "m"
    out = f"{slavic_cardinal(n, t, gender)} {plural_form(n, *forms)}"
    return f"{out} {slavic_cardinal(cents, t)}" if cents else out


def clock(h: int, m: int, lang: str) -> str:
    if lang == "en":
        if m == 0:
            return f"{en_cardinal(h)} o'clock"
        return f"{en_cardinal(h)} {'oh ' if m < 10 else ''}{en_cardinal(m)}"
    if lang == "de":
        return f"{de_cardinal(h)} Uhr" + (f" {de_cardinal(m)}" if m else "")
    t = _SLAVIC[lang]
    if m == 0:
        return f"{slavic_cardinal(h, t)} {plural_form(h, *t.hours_word)}"
    return f"{slavic_cardinal(h, t)} {t.zero + ' ' if m < 10 else ''}{slavic_cardinal(m, t)}"


_EN_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
_DE_MONTHS = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember")


def date_words(d: int, mo: int, y: int, lang: str) -> str:
    if lang == "en":
        return f"{_EN_MONTHS[mo - 1]} {en_ordinal(d)}, {en_year(y)}"
    if lang == "de":
        return f"{de_ordinal(d, 'ten')} {_DE_MONTHS[mo - 1]} {de_year(y)}"
    t = _SLAVIC[lang]
    return f"{slavic_ordinal(d, lang, 'n')} {t.months[mo - 1]} {slavic_ordinal(y, lang, 'gen')} {t.year_word}"


# --------------------------------------------------------------------------- the normaliser

_GROUPED = r"(?:\d{1,3}(?:[,.\u00a0\u202f ]\d{3})+|\d+)(?:[.,]\d+)?"
_YEAR_SUFFIX = r"(?:\s*(?:г\.|р\.|года|року|году|році)(?![\w]))?"  # "12.05.2026 р." -> year word already spoken
_DATE_DMY_RE = re.compile(r"(?<![\d.])(\d{1,2})[./](\d{1,2})[./](\d{4})(?![\d.]\d)" + _YEAR_SUFFIX)
_DATE_ISO_RE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)" + _YEAR_SUFFIX)
_TIME_RE = re.compile(r"(?<![\d:])(\d{1,2}):(\d{2})(?![\d:])(\s?Uhr\b)?")
_VERSION_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+){2,})(?!\.?\d)")
_CUR_BEFORE_RE = re.compile(rf"([$€£₽₴])\s?({_GROUPED})(?![\w])")
_CUR_AFTER_RE = re.compile(rf"(?<![\w.,])({_GROUPED})\s?([$€£₽₴])")
_PERCENT_RE = re.compile(rf"(?<![\w.,])(-?{_GROUPED})\s?%")
_RANGE_RE = re.compile(r"(?<![\d.,])(\d+)\s?[-–—]\s?(\d+)(?![\d.,])")
_EN_ORDINAL_RE = re.compile(r"\b(\d+)(st|nd|rd|th)\b")
_DE_ORDINAL_RE = re.compile(r"(?<![\d.,])(\d{1,2})\.(?=\s+[A-ZÄÖÜ][a-zäöüß]+)")  # "6. September", "3. Platz"
_NUMBER_RE = re.compile(rf"(?<![\w.,])(-?)({_GROUPED})(?![\w])")
_ATTACHED_RE = re.compile(r"(?<=[A-Za-z\u00c0-\u024f\u0400-\u04ff])(?=\d)|(?<=\d)(?=[A-Za-z\u00c0-\u024f\u0400-\u04ff])")
_SLAVIC_YEAR_RE = re.compile(r"(?<![\d.,])(\d{4})\s*(году|года|год|г\.|році|року|рік|р\.)(?![\w])")
_YEAR_FORMS = {"году": "loc", "році": "loc", "года": "gen", "року": "gen", "г.": "gen", "р.": "gen", "год": "m", "рік": "m"}
_MAX = 10**15
_SENTENCE_START_RE = re.compile(r"\s*(?:$|[A-Z\u00c0-\u00de\u0400-\u042f\u0490])")


def _keep_period(m: re.Match, text: str) -> str:
    """'... 1999 г. Next' - the abbreviation dot also ended the sentence; give it back."""
    if m.group(0).endswith(".") and _SENTENCE_START_RE.match(text, m.end()):
        return "."
    return ""

_TO = {"en": "to", "de": "bis", "ru": "до", "uk": "до"}
_MINUS = {"en": "minus", "de": "minus", "ru": "минус", "uk": "мінус"}
_POINT = {"en": " point ", "de": " Punkt ", "ru": " точка ", "uk": " крапка "}


def _parse_number(raw: str, lang: str) -> tuple[int, str | None] | None:
    """'1,234.5' (en) / '1.234,5' or '1 234,5' (de/ru/uk) -> (1234, '5')."""
    s = raw.replace("\u00a0", "").replace("\u202f", "").replace(" ", "").strip()
    group, dec = (",", ".") if lang == "en" else (".", ",")
    if s.count(dec) >= 2:
        # "1.000.000" in English text / "1,000,000" in German text -> grouping with the other separator
        joined = s.replace(dec, "").replace(group, "")
        return (int(joined), None) if joined.isdigit() else None
    if dec in s:
        head, _, frac = s.partition(dec)
        head = head.replace(group, "")
        if head.isdigit() and frac.isdigit():
            return int(head), frac
        return None
    s = s.replace(group, "")
    if not s.isdigit():
        return None
    return int(s), None


def normalize_numbers(text: str, lang: str) -> str:
    """Replace digits with words in `lang`. No-op for unsupported languages or digit-free text."""
    if lang not in SUPPORTED or not any(ch.isdigit() for ch in text):
        return text
    t = text

    def _date_dmy(m: re.Match) -> str:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if lang == "en" and d > 12 and mo <= 12:
            pass  # dd.mm.yyyy written by a European; fine
        elif lang == "en" and mo > 12 and d <= 12:
            d, mo = mo, d  # mm/dd/yyyy
        if not (1 <= d <= 31 and 1 <= mo <= 12):
            return m.group(0)
        return date_words(d, mo, y, lang) + _keep_period(m, t)

    def _date_iso(m: re.Match) -> str:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (1 <= d <= 31 and 1 <= mo <= 12):
            return m.group(0)
        return date_words(d, mo, y, lang) + _keep_period(m, t)

    t = _DATE_ISO_RE.sub(_date_iso, t)
    t = _DATE_DMY_RE.sub(_date_dmy, t)

    def _time(m: re.Match) -> str:
        h, mi = int(m.group(1)), int(m.group(2))
        if h >= 24 or mi >= 60:
            return m.group(0)
        words = clock(h, mi, lang)
        if m.group(3) and lang != "de":  # "10:30 Uhr" inside non-German text: keep the word
            words += m.group(3)
        return words

    t = _TIME_RE.sub(_time, t)
    t = _VERSION_RE.sub(lambda m: _POINT[lang].join(cardinal(int(p), lang) for p in m.group(1).split(".")), t)

    def _cur(sym: str, raw: str) -> str | None:
        parsed = _parse_number(raw, lang)
        if parsed is None or parsed[0] >= _MAX:
            return None
        return currency(sym, parsed[0], parsed[1], lang)

    t = _CUR_BEFORE_RE.sub(lambda m: _cur(m.group(1), m.group(2)) or m.group(0), t)
    t = _CUR_AFTER_RE.sub(lambda m: _cur(m.group(2), m.group(1)) or m.group(0), t)

    def _pct(m: re.Match) -> str:
        raw = m.group(1)
        neg = raw.startswith("-")
        parsed = _parse_number(raw.lstrip("-"), lang)
        if parsed is None or parsed[0] >= _MAX:
            return m.group(0)
        n, frac = parsed
        words = decimal(n, frac, lang) if frac else cardinal(n, lang)
        if neg:
            words = f"{_MINUS[lang]} {words}"
        return percent(words, n, lang, is_decimal=bool(frac))

    t = _PERCENT_RE.sub(_pct, t)
    t = _RANGE_RE.sub(lambda m: f"{m.group(1)} {_TO[lang]} {m.group(2)}", t)
    if lang == "en":
        t = _EN_ORDINAL_RE.sub(lambda m: en_ordinal(int(m.group(1))) if int(m.group(1)) < _MAX else m.group(0), t)
    elif lang == "de":
        t = _DE_ORDINAL_RE.sub(lambda m: de_ordinal(int(m.group(1))), t)
    t = _ATTACHED_RE.sub(" ", t)  # RTX4060 -> RTX 4060, 16GB -> 16 GB

    if lang in _SLAVIC:

        def _year_noun(m: re.Match) -> str:
            y, word = int(m.group(1)), m.group(2)
            if not 1000 <= y <= 2999:
                return m.group(0)
            form = _YEAR_FORMS[word]
            spoken = word
            if word in ("г.", "р."):
                # "в 1999 г." -> "в ... году"; "с 1999 г." -> "с ... года"
                in_prep = re.search(r"(?:^|[^\w])[вВуУ]\s+$", t[: m.start()]) is not None
                form = "loc" if in_prep else "gen"
                spoken = ("году" if lang == "ru" else "році") if in_prep else ("года" if lang == "ru" else "року")
            return f"{slavic_ordinal(y, lang, form)} {spoken}" + _keep_period(m, t)

        t = _SLAVIC_YEAR_RE.sub(_year_noun, t)

    def _num(m: re.Match) -> str:
        neg = m.group(1) == "-"
        raw = m.group(2)
        parsed = _parse_number(raw, lang)
        if parsed is None or parsed[0] >= _MAX:
            return m.group(0)
        n, frac = parsed
        after = t[m.end() : m.end() + 2]
        if frac is not None:
            words = decimal(n, frac, lang)
        elif lang == "de" and n == 1 and not neg and re.match(r"\s[A-Za-z\u00c0-\u024f]", after or ""):
            words = "ein"  # "1 Apfel" -> "ein Apfel"; standalone stays "eins"
        elif lang in _SLAVIC and not neg and n % 10 in (1, 2) and n % 100 not in (11, 12):
            words = slavic_count(n, lang, t[m.end() : m.end() + 40])
        else:
            plain = re.sub(r"[\s\u00a0\u202f]", "", raw)
            words = year(n, lang) if plain.isdigit() and len(plain) == 4 else cardinal(n, lang)
        return f"{_MINUS[lang]} {words}" if neg else words

    t = _NUMBER_RE.sub(_num, t)
    return re.sub(r"[ \t]{2,}", " ", t)


verbalize_numbers = normalize_numbers
