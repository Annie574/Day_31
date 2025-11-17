from tkinter import *
import pandas as pd
from random import choice

FONT = "Ariel"
BACKGROUND_COLOR = "#B1DDC6"
LANGUAGE = "french"
TIME = 3



# -------------------- CHOOSE LANGUAGE --------------------  #
try:
    data = pd.read_csv(f"data/{LANGUAGE}_words_to_learn.csv")
except FileNotFoundError:
    data = pd.read_csv(f"data/{LANGUAGE}_words.csv")

data_dictionary = data.to_dict(orient="records")
# words_list = [{item['English']: item['French']} for item in data_dictionary]
# data_dictionary = {key:value for elm in words_list for (key, value) in elm.items()}

# -------------------- FLIP CARD --------------------  #
def flip_card():
    main_view.itemconfig(card_view, image = image_back)
    main_view.itemconfig(language_text, text="English", fill="white")
    main_view.itemconfig(word_text, text=random_word["English"], fill="white")

# -------------------- RANDOM WORD --------------------  #

def next_card():
    # random_word = choice(words_list)
    # random_word_eng = list(random_word)[0]
    # random_word_fr = random_word[random_word_eng]
    # main_view.itemconfig(word_text, text= random_word_fr)
    global random_word, flip_timer
    window.after_cancel(flip_timer)
    random_word = choice(data_dictionary)
    main_view.itemconfig(card_view, image=image_front)
    main_view.itemconfig(language_text, text="French", fill="black")
    main_view.itemconfig(word_text, text=random_word["French"], fill="black")
    flip_timer = window.after(3000, func=flip_card)

def is_known():
    data_dictionary.remove(random_word)
    data_to_dump = pd.DataFrame(data_dictionary)
    data_to_dump.to_csv(f"data/{LANGUAGE}_words_to_learn.csv", index=False)
    next_card()



# -------------------- UI CUSTOMISATION --------------------  #

window = Tk()
window.title("Flashy")
window.config(padx=50, pady=50, bg=BACKGROUND_COLOR)

flip_timer = window.after(3000, flip_card)

main_view = Canvas(width=800, height=526, highlightthickness=0, bg=BACKGROUND_COLOR)
image_front = PhotoImage(file="./images/card_front.png")
image_back = PhotoImage(file="./images/card_back.png")
card_view = main_view.create_image(400, 260, image = image_front)

# Texts in main_view
language_text = main_view.create_text(400, 150, text="", font=(FONT, 40, "italic"))
word_text = main_view.create_text(400, 263, text="", font=(FONT, 60, "bold"))
main_view.grid(column=0, row=0, columnspan=2)



# Images
image_right = PhotoImage(file="./images/right.png")
image_wrong = PhotoImage(file="./images/wrong.png")

# Buttons
right_button = Button(image=image_right, highlightthickness=0, command=is_known)
wrong_button = Button(image=image_wrong, highlightthickness=0, command=next_card)

right_button.grid(column=1, row = 1)
wrong_button.grid(column=0, row = 1)

next_card()

window.mainloop()