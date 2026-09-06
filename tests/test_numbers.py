from utter.tts.numbers import (
    SUPPORTED,
    cardinal,
    de_ordinal,
    en_ordinal,
    normalize_numbers,
    slavic_ordinal,
)


def test_supported_languages():
    assert set(SUPPORTED) == {"en", "de", "ru", "uk"}
    assert normalize_numbers("5 chats", "fr") == "5 chats"  # unsupported -> untouched


def test_english_basics():
    n = lambda t: normalize_numbers(t, "en")  # noqa: E731
    assert n("In 2024 we sold 1,250 units.") == "In twenty twenty-four we sold one thousand two hundred fifty units."
    assert n("$5.99 each, up 3.5%.") == "five dollars ninety-nine each, up three point five percent."
    assert n("Meet at 10:30.") == "Meet at ten thirty."
    assert n("The 3rd try and the 21st.") == "The third try and the twenty-first."
    assert n("Version 0.2.0.") == "Version zero point two point zero."
    assert n("On 2026-09-06.") == "On September sixth, twenty twenty-six."
    assert n("range 5-10 items") == "range five to ten items"
    assert n("RTX4060 has 16GB") == "RTX four thousand sixty has sixteen GB"
    assert en_ordinal(12) == "twelfth" and en_ordinal(100) == "one hundredth"


def test_german_basics():
    n = lambda t: normalize_numbers(t, "de")  # noqa: E731
    assert n("Im Jahr 1999 kostete es 1 000 €.") == "Im Jahr neunzehnhundertneunundneunzig kostete es eintausend Euro."
    assert n("Um 10:30 Uhr am 12.05.2026.") == "Um zehn Uhr dreißig am zwölften Mai zweitausendsechsundzwanzig."
    assert n("1 Apfel, 2 Äpfel.") == "ein Apfel, zwei Äpfel."
    assert n("3,5 %") == "drei Komma fünf Prozent"
    assert de_ordinal(1) == "erste" and de_ordinal(3) == "dritte" and de_ordinal(20) == "zwanzigste"
    assert cardinal(1001, "de") == "eintausendeins"


def test_russian_agreement_and_years():
    n = lambda t: normalize_numbers(t, "ru")  # noqa: E731
    assert n("В 2024 году") == "В две тысячи двадцать четвёртом году"
    assert n("С 2020 года по 2023 год.") == "С две тысячи двадцатого года по две тысячи двадцать третий год."
    assert n("В 1999 г. Потом.") == "В тысяча девятьсот девяносто девятом году. Потом."
    assert n("1 штуку, 2 книги, 22 минуты, 1 окно, 21 день") == (
        "одну штуку, две книги, двадцать две минуты, одно окно, двадцать один день"
    )
    assert n("6.09.2026") == "шестое сентября две тысячи двадцать шестого года"
    assert n("1250 штук") == "тысяча двести пятьдесят штук"
    assert n("Рост 3,5 %.") == "Рост три целых пять десятых процента."
    assert n("5 $") == "пять долларов"
    assert slavic_ordinal(2000, "ru", "loc") == "двухтысячном"
    assert slavic_ordinal(3, "ru", "n") == "третье"


def test_ukrainian_agreement_and_years():
    n = lambda t: normalize_numbers(t, "uk")  # noqa: E731
    assert n("У 2024 році") == "У дві тисячі двадцять четвертому році"
    assert n("21 штуку і 2 книги, 2 роки, 2 гривні, 1 вікно, 1 година") == (
        "двадцять одну штуку і дві книги, два роки, дві гривні, одне вікно, одна година"
    )
    assert n("03.03.2003 р. Далі.") == "третє березня дві тисячі третього року. Далі."
    assert n("100 грн") == "сто грн"
    assert slavic_ordinal(3, "uk", "gen") == "третього"
    assert slavic_ordinal(1999, "uk", "m") == "тисяча дев'ятсот дев'яносто дев'ятий"


def test_idempotent_and_no_digits_left():
    for lang in SUPPORTED:
        out = normalize_numbers("Test 12 and 3.5 and 2024-01-02 and 99 %.", lang)
        assert not any(ch.isdigit() for ch in out), (lang, out)
        assert normalize_numbers(out, lang) == out
