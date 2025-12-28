# test_flashy_param.py
import types
import sys
from pathlib import Path

import pandas as pd
import pytest

# ---------- Dummy GUI ----------

class DummyCanvas:
    def __init__(self):
        self.configs = {}
        self.created = []
    def create_image(self, x, y, image=None):
        _id = len(self.created) + 1
        self.created.append(("image", x, y, image))
        return _id
    def create_text(self, x, y, text="", font=None):
        _id = len(self.created) + 1
        self.created.append(("text", x, y, text, font))
        return _id
    def itemconfig(self, item_id, **kwargs):
        self.configs.setdefault(item_id, {}).update(kwargs)
    def grid(self, **kwargs):
        pass

class DummyTk:
    def __init__(self):
        self.scheduled = []     # list of (id, ms, func)
        self.cancelled = set()  # set of ids
        self._timer_id = 100
        self.title_text = None
        self.config_kwargs = None
    def title(self, text):
        self.title_text = text
    def config(self, **kwargs):
        self.config_kwargs = kwargs
    def after(self, ms, func=None):
        self._timer_id += 1
        self.scheduled.append((self._timer_id, ms, func))
        return self._timer_id
    def after_cancel(self, timer_id):
        self.cancelled.add(timer_id)
    def mainloop(self):
        pass

class DummyPhotoImage:
    def __init__(self, file=None):
        self.file = file

class DummyButton:
    def __init__(self, image=None, highlightthickness=0, command=None):
        self.image = image
        self.command = command
    def grid(self, **kwargs):
        pass

# ---------- Dane wejściowe ----------

@pytest.fixture
def sample_data():
    # Dataset ma wszystkie kolumny potrzebne dla obu języków
    return [
        {"English": "house", "German": "Haus",  "French": "Maison"},
        {"English": "cat",   "German": "Katze", "French": "Chat"},
        {"English": "book",  "German": "Buch",  "French": "Livre"},
    ]

# ---------- Wspólny fixture importujący moduł z mockami ----------

@pytest.fixture
def flashy_for_language(monkeypatch, tmp_path, sample_data, request):
    """
    Importuje 'flashy' z mockami:
      - tkinter → dummy GUI
      - pandas.read_csv → kontrolowany, fallback na *_words.csv
      - random.choice → deterministyczny wybór rekordu
    Następnie ustawia LANGUAGE na wartość parametryczną ("german"/"french")
    i wywołuje next_card(), by odświeżyć UI pod obrany język.
    """
    language = request.param  # "german" albo "french"
    lang_title = language.title()  # "German" albo "French"

    # Przygotuj strukturę katalogów i chdir, aby ścieżki względne działały
    (tmp_path / "data").mkdir()
    (tmp_path / "images").mkdir()
    monkeypatch.chdir(tmp_path)

    # 1) Podmień 'tkinter' PRZED importem flashy (kod używa: from tkinter import *)
    tk_mod = types.ModuleType("tkinter")
    tk_mod.Tk = DummyTk
    tk_mod.Canvas = DummyCanvas
    tk_mod.PhotoImage = DummyPhotoImage
    tk_mod.Button = DummyButton
    monkeypatch.setitem(sys.modules, "tkinter", tk_mod)

    # 2) Podmień pandas.read_csv PRZED importem flashy (bo CSV wczytywany przy imporcie)
    real_read_csv = pd.read_csv  # zachowaj oryginał do własnego użytku

    def fake_read_csv(path, *args, **kwargs):
        p = Path(path)
        # jeżeli plik faktycznie istnieje (np. zapisane *_words_to_learn.csv), wczytaj normalnie
        if p.exists():
            return real_read_csv(p, *args, **kwargs)

        s = str(path)
        # Symulacja ścieżek modułu
        if s.endswith("_words_to_learn.csv"):
            # Wywołaj scenariusz fallback (jak w kodzie: except FileNotFoundError → *_words.csv)
            raise FileNotFoundError(s)
        if s.endswith("_words.csv"):
            # Zwróć wstępny dataset dla obu języków
            return pd.DataFrame(sample_data)

        # Domyślnie zachowuj się jak brak pliku
        raise FileNotFoundError(s)

    monkeypatch.setattr(pd, "read_csv", fake_read_csv, raising=True)

    # 3) Podmień 'random.choice' PRZED importem flashy (bo next_card() jest wywołane przy imporcie)
    #    Kod robi: from random import choice → więc podstawiamy cały moduł 'random' z naszą choice.
    rnd_mod = types.ModuleType("random")
    chosen = {"English": "cat", "German": "Katze", "French": "Chat"}
    def deterministic_choice(seq):
        return chosen
    rnd_mod.choice = deterministic_choice
    monkeypatch.setitem(sys.modules, "random", rnd_mod)

    # 4) Import modułu 'flashy' (tu zadziałają wszystkie nasze mocki)
    import importlib
    flashy = importlib.import_module("flashy")

    # 5) Przestaw LANGUAGE na żądany i odśwież UI, by testować oba języki
    flashy.LANGUAGE = language
    flashy.next_card()

    # dostępne pomocnicze oczekiwane wartości
    flashy._expected_lang_title = lang_title
    flashy._expected_word = {"German": "Katze", "French": "Chat"}[lang_title]

    return flashy

# ---------- TESTY PARAMETRYCZNE: german / french ----------

@pytest.mark.parametrize("flashy_for_language", ["german", "french"], indirect=True)
def test_next_card_updates_ui_and_schedules_flip(flashy_for_language):
    f = flashy_for_language

    # 1) random_word wybrany deterministycznie
    assert f.random_word["English"] == "cat"

    # 2) obraz karty ustawiony na front
    conf_card = f.main_view.configs.get(f.card_view, {})
    assert conf_card.get("image") is f.image_front

    # 3) Tekst języka i słowa zależny od parametru
    lang_conf = f.main_view.configs.get(f.language_text, {})
    assert lang_conf.get("text") == f._expected_lang_title
    assert lang_conf.get("fill") == "black"

    word_conf = f.main_view.configs.get(f.word_text, {})
    assert word_conf.get("text") == f._expected_word
    assert word_conf.get("fill") == "black"

    # 4) Zaplanowany flip po 3000ms
    assert any(ms == 3000 and func == f.flip_card for (_id, ms, func) in f.window.scheduled)

@pytest.mark.parametrize("flashy_for_language", ["german", "french"], indirect=True)
def test_flip_card_updates_to_back(flashy_for_language):
    f = flashy_for_language

    f.flip_card()

    conf_card = f.main_view.configs.get(f.card_view, {})
    assert conf_card.get("image") is f.image_back

    lang_conf = f.main_view.configs.get(f.language_text, {})
    assert lang_conf.get("text") == "English"
    assert lang_conf.get("fill") == "white"

    word_conf = f.main_view.configs.get(f.word_text, {})
    assert word_conf.get("text") == "cat"
    assert word_conf.get("fill") == "white"

@pytest.mark.parametrize("flashy_for_language", ["german", "french"], indirect=True)
def test_is_known_removes_word_writes_csv_and_calls_next_card(monkeypatch, flashy_for_language, tmp_path):
    f = flashy_for_language

    # Śledź wywołanie next_card
    calls = {"count": 0}
    def spy_next_card():
        calls["count"] += 1
        return None
    monkeypatch.setattr(f, "next_card", spy_next_card)

    before_len = len(f.data_dictionary)
    f.is_known()

    # 1) Usunięto bieżące słowo
    assert len(f.data_dictionary) == before_len - 1
    assert not any(row["English"] == "cat" and row.get("German") == "Katze" for row in f.data_dictionary)

    # 2) Zapisano CSV w ścieżce zależnej od języka
    out_path = Path("data") / f"{f.LANGUAGE}_words_to_learn.csv"
    assert out_path.exists()

    # 3) W pliku nie ma już "cat" ani tłumaczenia w danym języku
    df_out = pd.read_csv(out_path)  # to używa realnego read_csv, bo plik istnieje
    assert "cat" not in df_out["English"].tolist()

    # mapowanie oczekiwanego tłumaczenia wg języka
    expected_translation = {"german": "Katze", "french": "Chat"}[f.LANGUAGE]
    assert expected_translation not in df_out[f.LANGUAGE.title()].tolist()

    # 4) Wywołano next_card()
    assert calls["count"] == 1



'''
Co tu jest ważne i dlaczego działa

Parametryzacja: @pytest.mark.parametrize("flashy_for_language", ["german", "french"], indirect=True) uruchamia każdy test dwa razy: raz dla niemieckiego, raz dla francuskiego.
Mocki przed importem: ponieważ Twój moduł od razu tworzy GUI, czyta CSV i wywołuje next_card(), podmieniamy:

tkinter w sys.modules → bezpieczne klasy dummy,
pandas.read_csv → sterujemy danymi (fallback jak w kodzie),
random.choice → deterministyczny wybór, by asercje były stabilne.


Po imporcie zmieniamy LANGUAGE i wywołujemy next_card(), żeby UI odzwierciedlał aktualnie testowany język.
Zapis CSV: testy używają rzeczywistego to_csv i realnego odczytu, bo nasz fake read_csv przepuszcza odczyt istniejących plików do oryginalnego pandas.read_csv.


(Opcjonalnie) Ułatw sobie testowanie w przyszłości
Jeśli kiedyś będziesz refaktoryzować:

przenieś inicjację GUI i next_card() pod:
Pythonif __name__ == "__main__":    # setup GUI i mainloopPokaż więcej wierszy

wyodrębnij logikę w czyste funkcje/klasę (np. FlashyApp) — testy będą dużo prostsze, bez globali.
'''


import pytest

@pytest.mark.parametrize("flashy_for_language", ["german", "french"], indirect=True)
def test_next_card_cancels_previous_timer_and_sets_new(flashy_for_language):
    """
    Weryfikuje, że kolejne wywołanie next_card():
      - anuluje poprzedni timer (after_cancel),
      - ustawia nowy timer (after) na 3000 ms,
      - aktualizuje globalny flip_timer na świeże ID.
    """
    f = flashy_for_language

    # Stan początkowy po fixture:
    # - flip_timer już istnieje (ID drugiego timera po imporcie + odświeżeniu UI w fixture),
    # - pierwszy timer z importu został anulowany w fixture przez wcześniejsze next_card().
    prev_id = f.flip_timer
    cancelled_before = set(f.window.cancelled)
    scheduled_before_len = len(f.window.scheduled)

    # sanity: bieżący timer nie powinien być jeszcze anulowany
    assert prev_id not in cancelled_before

    # Wywołanie: powinno anulować poprzedni timer i dodać nowy
    f.next_card()

    # 1) Poprzedni timer został anulowany
    assert prev_id in f.window.cancelled
    # liczność zbioru anulowanych wzrosła o 1
    assert len(f.window.cancelled) == len(cancelled_before) + 1

    # 2) Ustawiono nowy timer
    new_id = f.flip_timer
    assert new_id != prev_id

    # 3) Dodano nowy wpis do scheduled (timer na 3000ms z funkcją flip_card)
    assert len(f.window.scheduled) == scheduled_before_len + 1
    assert any(_id == new_id and ms == 3000 and func == f.flip_card
               for (_id, ms, func) in f.window.scheduled)

'''
Co ten test dokładnie sprawdza?

Anulowanie poprzedniego timera: poprzednie flip_timer trafia do window.cancelled.
Utworzenie nowego timera: flip_timer dostaje nowe ID, różne od poprzedniego.
Parametry nowego timera: nowy wpis w window.scheduled ma ms == 3000 i funkcję flip_card.
Stabilność: test działa dla obu języków (german i french) dzięki parametryzacji.

'''


'''
test wielokrotnych wywołań next_card(), który sprawdza, że za każdym razem poprzedni timer jest anulowany i powstaje 
nowy (z ms=3000 i funkcją flip_card). Test jest parametryzowany dla języków german i french.
'''

@pytest.mark.parametrize("flashy_for_language", ["german", "french"], indirect=True)
def test_next_card_multiple_calls_cancel_each_previous_and_create_new(flashy_for_language):
    """
    Wielokrotne wywołania next_card() (3x):
      - każdorazowo anulują poprzedni timer,
      - ustawiają nowy timer na 3000 ms z flip_card,
      - flip_timer zmienia się na nowe ID po każdym wywołaniu.
    """
    f = flashy_for_language

    # Stan początkowy
    prev_id = f.flip_timer
    cancelled_before_len = len(f.window.cancelled)
    scheduled_before_len = len(f.window.scheduled)

    # sanity: bieżący timer nie powinien być jeszcze anulowany
    assert prev_id not in f.window.cancelled

    new_ids = []
    repeats = 3
    expected_scheduled_len = scheduled_before_len

    for i in range(repeats):
        # Wywołanie next_card – powinno anulować poprzedni timer i utworzyć nowy
        f.next_card()

        # Poprzedni timer MUSI być anulowany
        assert prev_id in f.window.cancelled, f"Iteracja {i}: poprzedni timer nie został anulowany."

        # Nowy timer MUSI mieć nowe ID
        new_id = f.flip_timer
        assert new_id != prev_id, f"Iteracja {i}: flip_timer nie zmienił ID."

        # Lista scheduled powinna wzrosnąć o 1, a nowy wpis mieć ms=3000 i func=flip_card
        expected_scheduled_len += 1
        assert len(f.window.scheduled) == expected_scheduled_len, f"Iteracja {i}: liczba scheduled nie wzrosła."
        assert any(_id == new_id and ms == 3000 and func == f.flip_card
                   for (_id, ms, func) in f.window.scheduled), f"Iteracja {i}: brak nowego timera (3000ms, flip_card)."

        new_ids.append(new_id)
        prev_id = new_id  # przygotuj na kolejną iterację

    # Po 3 wywołaniach: dodano 3 nowe timery i anulowano 3 poprzednie
    assert len(f.window.cancelled) == cancelled_before_len + repeats
    assert len(f.window.scheduled) == scheduled_before_len + repeats

    # Wszystkie nowe ID są unikalne (każde wywołanie tworzy świeży timer)
    assert len(set(new_ids)) == repeats


'''
Świetnie — dokładam test „init state”, który sprawdza, że pierwotny timer ustawiony przy imporcie modułu 
(tj. flip_timer = window.after(3000, flip_card)) zostaje anulowany przy pierwszym wywołaniu next_card() w trakcie importu, 
oraz że aktualny timer (ustawiony później) nie jest anulowany. Test jest parametryzowany dla german i french.
'''

@pytest.mark.parametrize("flashy_for_language", ["german", "french"], indirect=True)
def test_initial_import_timer_is_cancelled_on_first_next_card(flashy_for_language):
    """
    Sprawdza stan po imporcie modułu:
      - pierwszy timer utworzony przy imporcie (window.after(...)) jest anulowany
        przez pierwsze next_card() wywołane w module,
      - aktualny flip_timer wskazuje na najnowszy, nieanulowany timer,
      - w scheduled istnieje wpis dla aktualnego timera z ms=3000 i func=flip_card.
    """
    f = flashy_for_language

    # lista wszystkich zaplanowanych timerów w kolejności ich tworzenia
    scheduled = f.window.scheduled
    assert len(scheduled) >= 2, "Oczekujemy co najmniej dwóch timerów: init oraz po first next_card()."

    # Pierwotny timer powstały przy imporcie modułu (pierwszy wpis w scheduled)
    initial_id, initial_ms, initial_func = scheduled[0]
    assert initial_ms == 3000
    assert initial_func == f.flip_card

    # Ten pierwotny timer MUSI być anulowany przez first next_card() wywołane w module
    assert initial_id in f.window.cancelled, "Init timer z importu nie został anulowany."

    # Aktualny flip_timer to najnowszy (ostatni) timer; nie powinien być anulowany
    latest_id = scheduled[-1][0]
    assert f.flip_timer == latest_id, "flip_timer nie wskazuje na najnowszy timer."
    assert f.flip_timer not in f.window.cancelled, "Aktualny timer nie powinien być anulowany."

    # W scheduled musi istnieć wpis dla current flip_timer z parametrami 3000ms i flip_card
    assert any((_id == f.flip_timer and ms == 3000 and func == f.flip_card)
               for (_id, ms, func) in scheduled), "Brak wpisu dla aktualnego timera (3000ms, flip_card)."

    # (Opcjonalnie) sanity check: po imporcie i odświeżeniu we fixture zwykle mamy >=3 scheduled i >=2 cancelled
    assert len(scheduled) >= 3, "Sanity: spodziewamy się co najmniej trzech zaplanowanych timerów."
    assert len(f.window.cancelled) >= 2, "Sanity: spodziewamy się co najmniej dwóch anulowanych timerów."
