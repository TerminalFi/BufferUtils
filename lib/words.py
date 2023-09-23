import random
import sublime
import os

def load_words_from_file(filename=os.path.join(sublime.packages_path(), "BufferUtils", "lib", "words.list")):
    """Load words from the specified file."""
    with open(filename, 'r') as file:
        return [word.strip() for word in file.readlines()]

def generate_random_words(num_words=1, word_list=[]):
    """Generate a random sequence of words joined by `-`."""
    if not word_list or num_words <= 0:
        return ""

    chosen_words = random.sample(word_list, min(num_words, len(word_list)))
    return '-'.join(chosen_words)

def get_buffer_name():
    words = load_words_from_file()
    num_of_words = random.randint(1, 3)  # Randomly choose between 1 and 3 words
    return generate_random_words(num_of_words, words)
